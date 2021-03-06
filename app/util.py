from babel.numbers import format_percent
from flask import flash, redirect, url_for
from os import urandom
from os.path import abspath, dirname, exists, join
from datetime import datetime
from time import sleep
from werkzeug.utils import secure_filename
import json
import locale
import os
import socket
import sys

from app import app, db
from app.email import send_invite
from app.forms import PaymentForm, TransactionAttachmentForm, RemoveAttachmentForm
from app.models import Payment, Project, Subproject, IBAN, User, File

from sqlalchemy.exc import IntegrityError
from bunq.sdk.context.bunq_context import ApiContext
from bunq.sdk.context.api_environment_type import ApiEnvironmentType
from bunq.sdk.model.generated import endpoint

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))
from libs.bunq_lib import BunqLib


def create_bunq_api_config(bunq_access_token, project_id):
    environment = app.config['BUNQ_ENVIRONMENT_TYPE']

    filename = 'bunq-production'
    if environment == ApiEnvironmentType.SANDBOX:
        filename = 'bunq-sandbox'

    api_context = ApiContext.create(
        environment, bunq_access_token, socket.gethostname()
    ).save('%s-project-%s.conf' % (filename, project_id))


def get_bunq_api_config_filename(environment_type, project_id):
    filename_base = 'bunq-production'
    if environment_type == ApiEnvironmentType.SANDBOX:
        filename_base = 'bunq-sandbox'

    return '%s-project-%s.conf' % (filename_base, project_id)


def get_all_monetary_account_active(project_id):
    environment_type = app.config['BUNQ_ENVIRONMENT_TYPE']
    filename = get_bunq_api_config_filename(environment_type, project_id)
    if not exists(filename):
        return []
    bunq_api = BunqLib(environment_type, conf=filename)
    return bunq_api.get_all_monetary_account_active()


def get_all_monetary_account_active_ibans(project_id):
    # Remove any already existing IBANs for this project
    IBAN.query.filter_by(project_id=project_id).delete()
    db.session.commit()

    new_ibans_count = 0
    for monetary_account in get_all_monetary_account_active(project_id):
        for alias in monetary_account._alias:
            if alias._type_ == 'IBAN':
                new_iban = IBAN(
                    project_id=project_id,
                    iban=alias._value,
                    iban_name=monetary_account._description
                )
                db.session.add(new_iban)
                new_ibans_count += 1
    db.session.commit()
    return new_ibans_count


def _transform_payment(payment):
    payment_as_dict = json.loads(payment.to_json())
    result = {}
    for k, v in payment_as_dict.items():
        # Skip these fields as we don't use them
        if k in ['allow_chat', 'attachment',
                 'request_reference_split_the_bill', 'geolocation']:
            continue

        # Rename the 'id' field
        if k == 'id':
            k = 'bank_payment_id'

        # flatten dicts
        if type(v) == dict:
            for k2, v2 in v.items():
                f = "%s_%s" % (k, k2)
                result[f] = v2
        else:
            result[k] = v
    return result


def get_new_payments(project_id):
    # Loop over all monetary accounts (i.e., all IBANs belonging to one
    # Bunq account)
    for monetary_account in get_all_monetary_account_active(project_id):
        new_payments_count = 0
        new_payments = True
        payments = None
        # Use a while loop because of pagination; stop when we find a
        # payment that already exists in our database or if no new
        # payments are found or in case of an error
        while new_payments:
            # Retrieve payments from Bunq
            try:
                if payments:
                    params = payments.pagination.url_params_previous_page
                else:
                    params = {'count': 10}

                # Bunq allows max 3 requests per 3 seconds
                sleep(1)
                payments = endpoint.Payment.list(
                    monetary_account_id=monetary_account._id_,
                    params=params
                )
            except Exception as e:
                app.logger.error(
                    "Getting Bunq payments resulted in an exception:\n" + repr(e)
                )
                new_payments = False
                continue

            if not payments.value:
                new_payments = False
                continue

            # Save payments to database
            for full_payment in payments.value:
                try:
                    payment = _transform_payment(full_payment)
                except Exception as e:
                    app.logger.error(
                        "Transforming a Bunq payment resulted in an exception:\n" + repr(e)
                    )
                    new_payments = False
                    continue
                try:
                    existing_payment = Payment.query.filter_by(
                        bank_payment_id=payment['bank_payment_id']
                    ).first()

                    if existing_payment:
                        new_payments = False
                    else:
                        project = Project.query.filter_by(
                            iban=payment['alias_value']
                        ).first()
                        if project:
                            payment['project_id'] = project.id

                        subproject = Subproject.query.filter_by(
                            iban=payment['alias_value']
                        ).first()
                        if subproject:
                            payment['subproject_id'] = subproject.id

                        if 'scheduled_id' in payment:
                            del payment['scheduled_id']

                        p = Payment(**payment)
                        db.session.add(p)
                        db.session.commit()
                        new_payments_count += 1
                except Exception as e:
                    app.logger.error(
                        "Saving a Bunq payment resulted in an exception:\n" + repr(e)
                    )
                    new_payments = False
                    continue

            if not payments.pagination.has_previous_page():
                new_payments = False

        # Log the number of retrieved payments
        iban = ''
        iban_name = ''
        for alias in monetary_account._alias:
            if alias._type_ == 'IBAN':
                iban = alias._value
                iban_name = alias._name
        app.logger.info(
            'Project %s: retrieved %s payments for %s (%s)' % (
                project_id, new_payments_count, iban, iban_name
            )
        )


def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0

    if magnitude > 0:
        return '%s%s' % (locale.format("%.1f", num), ['', 'K', 'M'][magnitude])
    else:
        return locale.format("%.1f", round(num))


def format_currency(num, currency_symbol='€ '):
    return '%s%s' % (
        currency_symbol,
        locale.format(
            "%d", round(num), grouping=True, monetary=True
        )
    )


def calculate_project_amounts(project_id):
    project = Project.query.get(project_id)

    # Calculate amounts awarded
    subproject_ibans = [s.iban for s in project.subprojects]
    project_awarded = 0
    if len(list(project.payments)) > 0:
        project_awarded = project.payments.order_by(
            Payment.created.desc()
        ).first().balance_after_mutation_value
        for payment in project.payments:
            # Don't add incoming payments (as they are already
            # reflected in the current balance), but do actively
            # subtract incoming payments from our own subproject
            # IBANs
            if payment.amount_value > 0:
                if payment.counterparty_alias_value in subproject_ibans:
                    project_awarded -= payment.amount_value
            else:
                project_awarded += abs(payment.amount_value)
    else:
        # If we have not project payments (e.g. because we don't
        # have a main IBAN), use the incomming ammounts of the sub
        # accounts
        subprojects = Subproject.query.filter_by(project_id=project_id).all()
        project_awarded = 0
        for subproject in subprojects:
            if len(list(subproject.payments)) > 0:
                project_awarded += (
                    subproject.payments.order_by(
                        Payment.created.desc()
                    ).first().balance_after_mutation_value
                )
                for payment in subproject.payments:
                    # Don't add incoming payments (as they are already
                    # reflected in the current balance)
                    if payment.amount_value > 0:
                        continue
                    else:
                        project_awarded += abs(payment.amount_value)
    amounts = {
        'id': project.id,
        'awarded': project_awarded,
        'awarded_str': format_currency(project_awarded),
        'spent': 0
    }

    # Calculate amounts spent
    if project.contains_subprojects:
        subprojects = Subproject.query.filter_by(project_id=project_id).all()
        for subproject in subprojects:
            subproject_spent = 0
            for payment in subproject.payments:
                if payment.amount_value < 0:
                    # If the project contains an IBAN and the payment is to
                    # that IBAN then don't count the payment
                    if (subproject.project.iban == None or
                            (not payment.counterparty_alias_value ==
                            subproject.project.iban)):
                        subproject_spent += abs(payment.amount_value)
            amounts['spent'] += subproject_spent
    else:
        for payment in project.payments:
            if payment.amount_value < 0:
                amounts['spent'] += abs(payment.amount_value)

    # Calculate percentage spent
    if amounts['awarded'] == 0:
        amounts['percentage_spent_str'] = (
            format_percent(0)
        )
    else:
        amounts['percentage_spent_str'] = (
            format_percent(
                amounts['spent'] / amounts['awarded']
            )
        )

    amounts['spent_str'] = format_currency(amounts['spent'])
    amounts['left_str'] = format_currency(
        round(amounts['awarded']) - round(amounts['spent'])
    )

    return amounts


def calculate_subproject_amounts(subproject_id):
    subproject = Subproject.query.get(subproject_id)

    # Calculate amounts awarded
    subproject_awarded = 0
    if len(list(subproject.payments)) > 0:
        subproject_awarded = (
            subproject.payments.order_by(
                Payment.created.desc()
            ).first().balance_after_mutation_value
        )
        for payment in subproject.payments:
            # Don't add incoming payments (as they are already
            # reflected in the current balance)
            if payment.amount_value > 0:
                continue
            else:
                subproject_awarded += abs(payment.amount_value)
    amounts = {
        'id': subproject.id,
        'awarded': subproject_awarded,
        'awarded_str': format_currency(subproject_awarded),
        'spent': 0
    }

    # Calculate amounts spent
    subproject_spent = 0
    for payment in subproject.payments:
        if payment.amount_value < 0:
            # If the project contains an IBAN and the payment is to
            # that IBAN then don't count the payment
            if (subproject.project.iban == None or
                    (not payment.counterparty_alias_value ==
                    subproject.project.iban)):
                subproject_spent += abs(payment.amount_value)
    amounts['spent'] += subproject_spent

    # Calculate percentage spent
    if amounts['awarded'] == 0:
        amounts['percentage_spent_str'] = (
            format_percent(0)
        )
    else:
        amounts['percentage_spent_str'] = (
            format_percent(
                amounts['spent'] / amounts['awarded']
            )
        )

    amounts['spent_str'] = format_currency(amounts['spent'])
    amounts['left_str'] = format_currency(
        round(amounts['awarded']) - round(amounts['spent'])
    )

    return amounts


def calculate_total_amounts():
    # Calculate amounts awarded and spent
    # total_awarded = all current project balances
    #               + abs(all spent project amounts)
    #               - all amounts received from own subprojects (in the
    #                 case the didn't spend all their money and gave it
    #                 back)
    # total_spent = abs(all spend subproject amounts)
    #             - all amounts paid back by suprojects to their project
    total_awarded = 0
    total_spent = 0
    for project in Project.query.all():
        amounts = calculate_project_amounts(project.id)
        total_awarded += amounts['awarded']
        total_spent += amounts['spent']

    return total_awarded, total_spent


# Check if the given form is in the request
def form_in_request(form, request):
    if not request.form:
        return False

    if next(iter(request.form)).startswith(form._prefix):
        return True
    else:
        return False


# Output form errors to flashed messages
def flash_form_errors(form, request):
    # Don't print the errors if the request doesn't contain values for
    # this form
    if not request.form:
        return
    if not form_in_request(form, request):
        return

    for f in form:
        for error in f.errors:
            flash(
                '<span class="text-red">%s: %s</span>' % (f.label, error)
            )


def _set_user_role(user, admin=False, project_id=0, subproject_id=0):
    if admin:
        user.admin = True
        db.session.commit()
    if project_id:
        project = Project.query.get(project_id)
        if user in project.users:
            raise ValueError('Gebruiker niet toegevoegd: deze gebruiker was al project owner van dit project')
        project.users.append(user)
        db.session.commit()
    if subproject_id:
        subproject = Subproject.query.get(subproject_id)
        if user in subproject.users:
            raise ValueError('Gebruiker niet toegevoegd: deze gebruiker was al project owner van dit project')
        subproject.users.append(user)
        db.session.commit()


def add_user(email, admin=False, project_id=0, subproject_id=0):
    # Check if a user already exists with this email address
    user = User.query.filter_by(email=email).first()

    if user:
        _set_user_role(user, admin, project_id, subproject_id)
    if not user:
        user = User(email=email)
        user.set_password(urandom(24))
        db.session.add(user)
        db.session.commit()

        _set_user_role(user, admin, project_id, subproject_id)

        # Send the new user an invitation email
        send_invite(user)

# Process filled in payment form
def process_payment_form(request, project_or_subproject, is_subproject):
    payment_form = PaymentForm(prefix="payment_form")
    payment_form.category_id.choices = project_or_subproject.make_category_select_options()

    if payment_form.validate_on_submit():
        # Get data from the form
        new_payment_data = {}
        for f in payment_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                # If the category is edited to be empty again, make
                # sure to set it to None instead of ''
                if f.short_name == 'category_id':
                    if f.data == '':
                        new_payment_data[f.short_name] = None
                    else:
                        new_payment_data[f.short_name] = f.data
                else:
                    new_payment_data[f.short_name] = f.data

        try:
            # Update if the payment already exists
            payments = Payment.query.filter_by(
                id=payment_form.id.data
            )
            if len(payments.all()):
                payments.update(new_payment_data)
                db.session.commit()
                flash(
                    '<span class="text-green">Transactie is bijgewerkt</span>'
                )
        except IntegrityError as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-red">Transactie bijwerken mislukt<span>'
            )

        if is_subproject:
            # redirect back to clear form data
            return redirect(
                url_for(
                    'subproject',
                    project_id=project_or_subproject.project_id,
                    subproject_id=project_or_subproject.id
                )
            )

        return redirect(
            url_for(
                'project',
                project_id=project_or_subproject.id,
            )
        )
    else:
        flash_form_errors(payment_form, request)

# Populate the payment forms which allows the user to edit it
def create_payment_forms(payments, project_owner, select_options):
    payment_forms = {}
    for payment in payments:
        # If a payment already contains a category, retrieve it to set
        # this category as the selected category in the drop-down menu
        selected_category = ''
        if payment.category:
            selected_category = payment.category.id
        payment_form = PaymentForm(prefix='payment_form', **{
            'short_user_description': payment.short_user_description,
            'long_user_description': payment.long_user_description,
            'id': payment.id,
            'category_id': selected_category
        })

        payment_form.category_id.choices = select_options

        # Only allow project owners to hide a transaction
        if project_owner:
            payment_form.hidden = payment.hidden

        payment_forms[payment.id] = payment_form

    return payment_forms

# Process filled in transaction attachment form
def process_transaction_attachment_form(request, transaction_attachment_form, project_id=0, subproject_id=0):
    if transaction_attachment_form.validate_on_submit():
        # Save attachment to disk
        f = transaction_attachment_form.data_file.data
        filename = secure_filename(f.filename)
        filename = '%s_%s' % (
            datetime.now(app.config['TZ']).isoformat()[:19], filename
        )
        filepath = os.path.join(
            os.path.abspath(
                os.path.join(
                    app.instance_path, '../%s/transaction-attachment' % (
                        app.config['UPLOAD_FOLDER']
                    )
                )
            ),
            filename
        )
        f.save(filepath)
        new_file = File(filename=filename, mimetype=f.headers[1][1])
        db.session.add(new_file)
        db.session.commit()

        # Link attachment to payment in the database
        payment = Payment.query.get(
            transaction_attachment_form.payment_id.data
        )
        payment.attachments.append(new_file)
        db.session.commit()

        # redirect back to clear form data
        if subproject_id:
            # redirect back to clear form data
            return redirect(
                url_for(
                    'subproject',
                    project_id=project_id,
                    subproject_id=subproject_id
                )
            )

        return redirect(
            url_for(
                'project',
                project_id=project_id,
            )
        )
    else:
        flash_form_errors(transaction_attachment_form, request)

def process_remove_attachment_form(remove_attachment_form, project_id=0, subproject_id=0):
    # Remove attachment
    if remove_attachment_form.remove.data:
        File.query.filter_by(id=remove_attachment_form.id.data).delete()
        db.session.commit()
        flash('<span class="text-green">Media is verwijderd</span>')

        # redirect back to clear form data
        if subproject_id:
            # redirect back to clear form data
            return redirect(
                url_for(
                    'subproject',
                    project_id=project_id,
                    subproject_id=subproject_id
                )
            )

        return redirect(
            url_for(
                'project',
                project_id=project_id,
            )
        )

def get_export_timestamp():
    return datetime.now(
        app.config['TZ']
    ).isoformat()[:19].replace('-', '_').replace('T', '-').replace(':', '_')

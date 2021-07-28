from babel.numbers import format_percent
from flask import flash, redirect, url_for
from os import urandom
from os.path import abspath, dirname, exists, join
from datetime import datetime
from time import sleep
import json
import jwt
import locale
import os
import requests
import socket
import sys

from app import app, db
from app.email import send_invite
from app.models import Payment, Project, Subproject, IBAN, User

from sqlalchemy.exc import IntegrityError
from bunq.sdk.context.bunq_context import ApiContext
from bunq.sdk.context.api_environment_type import ApiEnvironmentType
from bunq.sdk.model.generated import endpoint

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))
from libs.bunq_lib import BunqLib


# Process Bunq OAuth callback (this will redirect to the project page)
def process_bunq_oauth_callback(request, current_user):
    base_url_token = 'https://api.oauth.bunq.com'
    if app.config['BUNQ_ENVIRONMENT_TYPE'] == ApiEnvironmentType.SANDBOX:
        base_url_token = 'https://api-oauth.sandbox.bunq.com'
    authorization_code = ''
    token = request.args.get('state')

    # Check if JWT token is valid and retrieve info
    token_info = ''
    try:
        token_info = jwt.decode(
            token,
            app.config['SECRET_KEY'],
            algorithms='HS256'
        )
    except Exception as e:
        flash(
            '<span class="text-default-red">Bunq account koppelen aan het project '
            ' is mislukt. Probeer het later nog een keer of neem contact '
            'op met <a href="mailto:info@openpoen.nl>info@openpoen.nl</a>.'
        )
        app.logger.warn(
            'Retrieved wrong token (used for retrieving Bunq '
            'authorization code): %s' % e
        )

    if token_info:
        print('2')
        user_id = token_info['user_id']
        project_id = token_info['project_id']
        bank_name = token_info['bank_name']

        # A project owner is either an admin or a user that is part
        # of the project where this subproject belongs to
        project_owner = False
        project = Project.query.filter_by(id=project_id).first()
        if current_user.is_authenticated and (
            current_user.admin or project.has_user(current_user.id)
        ):
            project_owner = True

        if project_owner:
            # If authorization code, retrieve access token from Bunq
            authorization_code = request.args.get('code')
            print('3')
            if authorization_code:
                response = requests.post(
                    '%s/v1/token?grant_type=authorization_code&code=%s'
                    '&redirect_uri=https://%s/&client_id=%s'
                    '&client_secret=%s' % (
                        base_url_token,
                        authorization_code,
                        app.config['SERVER_NAME'],
                        app.config['BUNQ_CLIENT_ID'],
                        app.config['BUNQ_CLIENT_SECRET'],
                    )
                ).json()

                # Add access token to the project in the database
                if 'access_token' in response:
                    bunq_access_token = response['access_token']
                    project.set_bank_name(bank_name)
                    project.set_bunq_access_token(bunq_access_token)
                    db.session.commit()

                    # Create Bunq API .conf file
                    create_bunq_api_config(
                        bunq_access_token, project.id
                    )

                    get_all_monetary_account_active_ibans(project.id)

                    flash(
                        '<span class="text-default-green">Bunq account succesvol '
                        'gekoppeld aan project "%s". De transacties '
                        'worden nu op de achtergrond binnengehaald. '
                        'Bewerk het nieuwe project om aan te geven welk '
                        'IBAN bij het project hoort. Maak nieuwe '
                        'subprojecten aan en koppel ook daar de IBANs die '
                        'daarbij horen.</span>' % (
                            project.name
                        )
                    )
                else:
                    flash(
                        '<span class="text-default-red">Bunq account koppelen aan '
                        'het project is mislukt. Probeer het later nog '
                        'een keer of neem contact op met '
                        '<a href="mailto:info@openpoen.nl>info@openpoen.nl'
                        '</a>.'
                    )
                    app.logger.error(
                        'Retrieval of Bunq access token failed. Bunq '
                        'Error: "%s". Bunq error description: "%s"' % (
                            response['error'],
                            response['error_description']
                        )
                    )

        # redirect back to clear form data
        return redirect(url_for('project', project_id=project.id))


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
                        p.route = 'subsidie'
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
    # If the project has payments then add the incoming/positive
    # payments, but skip the incoming/positive payments from
    # subprojects as we don't want to count them double
    if len(list(project.payments)) > 0:
        for payment in project.payments:
            if payment.amount_value > 0:
                if payment.counterparty_alias_value in subproject_ibans:
                    continue
                else:
                    project_awarded += payment.amount_value

    # Also add any incoming/positive payments for all subprojects, which
    # can come from external IBANs or by manually adding transactions
    if project.contains_subprojects:
        subprojects = Subproject.query.filter_by(project_id=project_id).all()
        for subproject in subprojects:
            if len(list(subproject.payments)) > 0:
                for payment in subproject.payments:
                    # We don't add payments coming from the project
                    # IBAN to make sure that they aren't counted double
                    if payment.amount_value > 0 and (project.iban and payment.counterparty_alias_value != project.iban):
                        project_awarded += payment.amount_value

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
                if payment.amount_value < 0 and not payment.counterparty_alias_value == subproject.project.iban:
                    amounts['spent']+= abs(payment.amount_value)
    else:
        for payment in project.payments:
            if payment.amount_value < 0:
                amounts['spent'] += abs(payment.amount_value)

    # Calculate percentage spent
    denominator = amounts['awarded']
    if project.budget:
        denominator = project.budget

    if denominator == 0:
        amounts['percentage_spent_str'] = (
            format_percent(0)
        )
    else:
        amounts['percentage_spent_str'] = (
            format_percent(
                amounts['spent'] / denominator
            )
        )

    amounts['spent_str'] = format_currency(amounts['spent'])

    amounts['left_str'] = format_currency(
        round(amounts['awarded']) - round(amounts['spent'])
    )
    if project.budget:
        amounts['left_str'] = format_currency(
            round(project.budget) - round(amounts['spent'])
        )

    return amounts


def calculate_subproject_amounts(subproject_id):
    subproject = Subproject.query.get(subproject_id)

    # Calculate amounts awarded
    subproject_awarded = 0
    if len(list(subproject.payments)) > 0:
        for payment in subproject.payments:
            if payment.amount_value > 0:
                subproject_awarded += payment.amount_value

    amounts = {
        'id': subproject.id,
        'awarded': subproject_awarded,
        'awarded_str': format_currency(subproject_awarded),
        'spent': 0
    }

    # Calculate amounts spent
    subproject_spent = 0
    for payment in subproject.payments:
        if payment.amount_value < 0 and not payment.counterparty_alias_value == subproject.project.iban:
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
        if subproject.budget:
            amounts['percentage_spent_str'] = (
                format_percent(
                    amounts['spent'] / subproject.budget
                )
            )

    amounts['spent_str'] = format_currency(amounts['spent'])

    amounts['left_str'] = format_currency(
        round(amounts['awarded']) - round(amounts['spent'])
    )
    if subproject.budget:
        amounts['left_str'] = format_currency(
            round(subproject.budget) - round(amounts['spent'])
        )

    return amounts


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
                '<span class="text-default-red">%s: %s</span>' % (f.label, error)
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

def get_export_timestamp():
    return datetime.now(
        app.config['TZ']
    ).isoformat()[:19].replace('-', '_').replace('T', '-').replace(':', '_')

from datetime import datetime
from flask import flash, redirect, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os

from app import app, db
from app.forms import CategoryForm, PaymentForm
from app.models import Category, Payment, File
from app.util import flash_form_errors


def return_redirect(project_id, subproject_id):
    # redirect back to clear form data
    if subproject_id:
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
            project_id=project_id
        )
    )


# Process filled in category form
def process_category_form(request):
    category_form = CategoryForm(prefix="category_form")

    # Check whether the category form is for a project or subproject
    project_id = category_form.project_id.data
    subproject_id = 0
    if category_form.subproject_id.data:
        subproject_id = category_form.subproject_id.data

    # Remove category
    if category_form.remove.data:
        Category.query.filter_by(id=category_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-default-green">Categorie "%s" is verwijderd</span>' % (
                category_form.name.data
            )
        )
        return return_redirect(project_id, subproject_id)

    # Update or save category
    if category_form.validate_on_submit():
        category = Category.query.filter_by(id=category_form.id.data)
        if len(category.all()):
            category.update({'name': category_form.name.data})
            db.session.commit()
            flash(
                '<span class="text-default-green">Categorie is bijgewerkt</span>'
            )
        else:
            try:
                if subproject_id:
                    category = Category(
                        name=category_form.name.data,
                        subproject_id=subproject_id
                    )
                else:
                    category = Category(
                        name=category_form.name.data,
                        project_id=project_id
                    )
                db.session.add(category)
                db.session.commit()
                flash(
                    '<span class="text-default-green">Categorie '
                    f'{category_form.name.data} is toegevoegd</span>'
                )
            except IntegrityError as e:
                db.session().rollback()
                app.logger.error(repr(e))
                flash(
                    '<span class="text-default-red">Categorie toevoegen mislukt: naam '
                    f'"{category_form.name.data}" bestaat al, kies een '
                    'andere naam<span>'
                )

        # redirect back to clear form data
        return return_redirect(project_id, subproject_id)
    else:
        flash_form_errors(category_form, request)


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
                    '<span class="text-default-green">Transactie is bijgewerkt</span>'
                )
        except IntegrityError as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-default-red">Transactie bijwerken mislukt<span>'
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
        flash('<span class="text-default-green">Media is verwijderd</span>')

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

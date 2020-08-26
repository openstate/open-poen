from flask import (
    render_template, redirect, url_for, flash, session, request,
    send_from_directory
)
from flask_login import login_required, login_user, logout_user, current_user

from app import app, db
from app.forms import (
    ResetPasswordRequestForm, ResetPasswordForm, LoginForm, ProjectForm,
    SubprojectForm, TransactionAttachmentForm,
    RemoveAttachmentForm, FunderForm, AddUserForm, EditAdminForm,
    EditProjectOwnerForm, EditUserForm, EditProfileForm, CategoryForm
)
from app.email import send_password_reset_email
from app.models import (
    User, Project, Subproject, Payment, UserStory, IBAN, File, Funder, Category
)
from app import util
from app.categories import process_category_form
from sqlalchemy.exc import IntegrityError

from bunq.sdk.context.api_environment_type import ApiEnvironmentType

from datetime import datetime
from time import time
from werkzeug.utils import secure_filename
import os
import jwt
import re
import requests


# Add 'Cache-Control': 'private' header if users are logged in
@app.after_request
def after_request_callback(response):
    if current_user.is_authenticated:
        response.headers['Cache-Control'] = 'private'

    return response


# Things to do before every request is processed
@app.before_request
def before_request():
    # Check if the current user is still active before every request. If
    # an admin/project owner sets a user to inactive then the user will
    # be logged out when it tries to make a new request.
    if current_user.is_authenticated and not current_user.is_active():
        flash(
            '<span class="text-red">Deze gebruiker is niet meer '
            'actief</span>'
        )
        logout_user()
        return redirect(url_for('index'))

    # If the current user has no first name, last name or biography then
    # send them to their profile page where they can add them
    if current_user.is_authenticated and request.path != '/profiel':
        if (not current_user.first_name
                or not current_user.last_name or not current_user.biography):
            flash(
                '<span class="text-red">Sommige velden in uw profiel zijn nog '
                'niet ingevuld. Vul deze in om verder te kunnen gaan.</span>'
            )
            return redirect(url_for('profile'))


@app.route("/", methods=['GET', 'POST'])
def index():
    base_url_auth = ''
    project_form = ''
    # Process Bunq OAuth callback
    base_url_auth = 'https://oauth.bunq.com'
    base_url_token = 'https://api.oauth.bunq.com'
    if app.config['BUNQ_ENVIRONMENT_TYPE'] == ApiEnvironmentType.SANDBOX:
        base_url_auth = 'https://oauth.sandbox.bunq.com'
        base_url_token = 'https://api-oauth.sandbox.bunq.com'
    authorization_code = ''
    if request.args.get('state'):
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
                '<span class="text-red">Bunq account koppelen aan het project '
                ' is mislukt. Probeer het later nog een keer of neem contact '
                'op met <a href="mailto:info@openpoen.nl>info@openpoen.nl</a>.'
            )
            app.logger.warn(
                'Retrieved wrong token (used for retrieving Bunq '
                'authorization code): %s' % e
            )

        if token_info:
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
                        util.create_bunq_api_config(
                            bunq_access_token, project.id
                        )

                        util.get_all_monetary_account_active_ibans(project.id)

                        flash(
                            '<span class="text-green">Bunq account succesvol '
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
                            '<span class="text-red">Bunq account koppelen aan '
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
            return redirect(url_for('index'))

    # Process filled in edit admin form
    edit_admin_form = EditAdminForm(prefix="edit_admin_form")

    # Update admin
    if edit_admin_form.validate_on_submit():
        admins = User.query.filter_by(id=edit_admin_form.id.data)
        new_admin_data = {}
        for f in edit_admin_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_admin_data[f.short_name] = f.data

        # Update if the admin exists
        if len(admins.all()):
            admins.update(new_admin_data)
            db.session.commit()
            flash('<span class="text-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        util.flash_form_errors(edit_admin_form, request)

    # Populate the edit admin forms which allows the user to edit it
    edit_admin_forms = {}
    for admin in User.query.filter_by(admin=True).order_by('email'):
        edit_admin_forms[admin.email] = EditAdminForm(
            prefix="edit_admin_form", **{
                'admin': admin.admin,
                'active': admin.active,
                'id': admin.id
            }
        )

    # Process filled in edit project owner form
    edit_project_owner_form = EditProjectOwnerForm(
        prefix="edit_project_owner_form"
    )

    # Update project owner
    if edit_project_owner_form.validate_on_submit():
        edited_project_owner = User.query.filter_by(
            id=edit_project_owner_form.id.data
        )
        new_project_owner_data = {}
        remove_from_project = False
        remove_from_project_id = 0
        for f in edit_project_owner_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'remove_from_project' and f.data:
                    remove_from_project = True
                elif f.short_name == 'project_id' and f.data:
                    remove_from_project_id = f.data
                else:
                    new_project_owner_data[f.short_name] = f.data

        # Update if the project owner exists
        if len(edited_project_owner.all()):
            edited_project_owner.update(new_project_owner_data)
            if remove_from_project:
                # We need to get the user using '.first()' otherwise we
                # can't remove the project because of garbage collection
                edited_project_owner = edited_project_owner.first()
                edited_project_owner.projects.remove(
                    Project.query.get(remove_from_project_id)
                )

            db.session.commit()
            flash('<span class="text-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        util.flash_form_errors(edit_project_owner_form, request)

    # Populate the edit project owner forms which allows the user to
    # edit it
    edit_project_owner_forms = {}
    for project in Project.query.all():
        temp_edit_project_owner_forms = {}
        for project_owner in project.users:
            temp_edit_project_owner_forms[project_owner.email] = (
                EditProjectOwnerForm(
                    prefix="edit_project_owner_form", **{
                        'active': project_owner.active,
                        'id': project_owner.id,
                        'project_id': project.id
                    }
                )
            )
        edit_project_owner_forms[project.id] = temp_edit_project_owner_forms

    # Process filled in add user form
    add_user_form = AddUserForm(prefix="add_user_form")

    # Add user (either admin or project owner)
    if add_user_form.validate_on_submit():
        new_user_data = {}
        for f in add_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_user_data[f.short_name] = f.data

        try:
            util.add_user(**new_user_data)
            flash(
                '<span class="text-green">"%s" is uitgenodigd als admin of '
                'project owner (of toegevoegd als admin of project owner als de '
                'gebruiker al bestond)' % (
                    new_user_data['email']
                )
            )
        except ValueError as e:
            flash(str(e))

        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        util.flash_form_errors(add_user_form, request)

    # Process filled in project form
    project_form = ProjectForm(prefix="project_form")

    # Remove project
    if project_form.remove.data:
        Project.query.filter_by(id=project_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-green">Project "%s" is verwijderd</span>' % (
                project_form.name.data
            )
        )
        # redirect back to clear form data
        return redirect(url_for('index'))

    # Save or update project
    # Somehow we need to repopulate the iban.choices with the same
    # values as used when the form was generated for this project.
    # Probably to validate if the selected value is valid.
    if util.form_in_request(project_form, request):
        if request.method == 'POST' and project_form.name.data:
            projects = Project.query.filter_by(id=project_form.id.data)
            if len(projects.all()):
                project_form.iban.choices = (
                    projects.first().make_select_options()
                )

    if project_form.validate_on_submit():
        new_project_data = {}
        for f in project_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'iban':
                    new_iban = None
                    new_iban_name = None
                    # New projects f.data is 'None', editing an existing
                    # project with an IBAN to have no IBAN will make
                    # f.data be ''
                    if not f.data == '' and f.data != 'None':
                        new_iban, new_iban_name = f.data.split(
                            ' - ', maxsplit=1
                        )
                    new_project_data['iban'] = new_iban
                    new_project_data['iban_name'] = new_iban_name
                else:
                    new_project_data[f.short_name] = f.data

        try:
            # Update if the project already exists
            if len(projects.all()):
                # If the IBAN changes, then link the correct payments
                # to this project
                project = projects.first()

                # We don't allow editing of the 'contains_subprojects' value after a project is created
                del new_project_data['contains_subprojects']

                if project.iban != new_project_data['iban']:
                    for payment in project.payments:
                        payment.project_id = None
                    Payment.query.filter_by(
                        alias_value=new_project_data['iban']
                    ).update({'project_id': project.id})

                projects.update(new_project_data)
                db.session.commit()

                flash(
                    '<span class="text-green">Project "%s" is '
                    'bijgewerkt</span>' % (
                        new_project_data['name']
                    )
                )
            # Otherwise, save a new project
            else:
                # IBAN can't be set during initial creation of a new
                # project so remove it
                new_project_data.pop('iban')
                project = Project(**new_project_data)
                db.session.add(project)
                db.session.commit()
                flash(
                    '<span class="text-green">Project "%s" is '
                    'toegevoegd</span>' % (
                        new_project_data['name']
                    )
                )
        except IntegrityError as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-red">Project toevoegen/bijwerken mislukt: '
                'naam "%s" en/of IBAN "%s" bestaan al, kies een andere naam '
                'en/of IBAN<span>' % (
                    new_project_data['name'],
                    new_project_data['iban']
                )
            )
        # redirect back to clear form data
        return redirect(url_for('index'))
    else:
        util.flash_form_errors(project_form, request)

    # Process filled in category form
    category_form = ''
    category_form_return = process_category_form(request)
    if category_form_return:
        return category_form_return

    # Retrieve data for each project
    project_data = []
    for project in Project.query.all():
        project_owner = False
        if current_user.is_authenticated and (
            current_user.admin or project.has_user(current_user.id)
        ):
            project_owner = True

        if project.hidden and not project_owner:
            continue

        already_authorized = False
        bunq_token = ''
        form = ''

        if project_owner:
            if project.bunq_access_token and len(project.bunq_access_token):
                already_authorized = True

            # Always generate a token as the user can connect to Bunq
            # again in order to allow access to new IBANs
            bunq_token = jwt.encode(
                {
                    'user_id': current_user.id,
                    'project_id': project.id,
                    'bank_name': 'Bunq',
                    'exp': time() + 1800
                },
                app.config['SECRET_KEY'],
                algorithm='HS256'
            ).decode('utf-8')

            # Populate the project's form which allows the user to edit
            # it
            form = ProjectForm(prefix="project_form", **{
                'name': project.name,
                'description': project.description,
                'hidden': project.hidden,
                'id': project.id,
                'contains_subprojects': project.contains_subprojects
            })
            # We don't allow editing of the 'contains_subprojects'
            # value after a project is created, but we do need to pass the
            # value in the form, so simply disable it
            form.contains_subprojects.render_kw = {'disabled': ''}

            # If a bunq account is available, allow the user to select
            # an IBAN
            if project.bunq_access_token:
                form.iban.choices = project.make_select_options()
                # Set default selected value
                form.iban.data = '%s - %s' % (
                    project.iban, project.iban_name
                )

        # Populate the category forms which allows the user to
        # edit it
        category_forms = []
        if not project.contains_subprojects:
            for category in Category.query.filter_by(
                    project_id=project.id).order_by('name'):
                category_forms.append(
                    CategoryForm(
                        prefix="category_form", **{
                            'id': category.id,
                            'name': category.name,
                            'project_id': project.id
                        }
                    )
                )

        # Retrieve the amounts for this project
        amounts = util.calculate_project_amounts(project.id)

        project_data.append(
            {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'hidden': project.hidden,
                'project_owner': project_owner,
                'already_authorized': already_authorized,
                'bunq_token': bunq_token,
                'iban': project.iban,
                'iban_name': project.iban_name,
                'bank_name': project.bank_name,
                'amounts': amounts,
                'form': form,
                'contains_subprojects': project.contains_subprojects,
                'category_forms': category_forms,
                'category_form': CategoryForm(prefix="category_form", **{'project_id': project.id})
            }
        )

    total_awarded, total_spent = util.calculate_total_amounts()

    return render_template(
        'index.html',
        project_data=project_data,
        total_awarded_str=util.human_format(total_awarded),
        total_spent_str=util.human_format(total_spent),
        project_form=project_form,
        add_user_form=AddUserForm(prefix='add_user_form'),
        edit_admin_forms=edit_admin_forms,
        edit_project_owner_forms=edit_project_owner_forms,
        user_stories=UserStory.query.all(),
        server_name=app.config['SERVER_NAME'],
        bunq_client_id=app.config['BUNQ_CLIENT_ID'],
        base_url_auth=base_url_auth
    )


@app.route("/project/<project_id>", methods=['GET', 'POST'])
def project(project_id):
    project = Project.query.get(project_id)

    if not project:
        return render_template(
            '404.html'
        )

    # A project owner is either an admin or a user that is part of the
    # project where this subproject belongs to
    project_owner = False
    if current_user.is_authenticated and (
        current_user.admin or project.has_user(current_user.id)
    ):
        project_owner = True

    if project.hidden and not project_owner:
        return render_template(
            '404.html'
        )

    # Process filled in funder form
    funder_form = FunderForm(prefix="funder_form")

    # Remove funder
    if funder_form.remove.data:
        Funder.query.filter_by(id=funder_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-green">Sponsor "%s" is verwijderd</span>' % (
                funder_form.name.data
            )
        )
        # redirect back to clear form data
        return redirect(url_for('project', project_id=project_id))

    # Save or update funder
    if funder_form.validate_on_submit():
        funders = Funder.query.filter_by(id=funder_form.id.data)
        new_funder_data = {}
        for f in funder_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_funder_data[f.short_name] = f.data

        # Update if the funder already exists
        if len(funders.all()):
            funders.update(new_funder_data)
            db.session.commit()
            flash(
                '<span class="text-green">Sponsor "%s" is '
                'bijgewerkt</span>' % (
                    new_funder_data['name']
                )
            )
        # Otherwise, save a new funder
        else:
            funder = Funder(**new_funder_data)
            funder.project_id = project_id
            db.session.add(funder)
            db.session.commit()
            flash(
                '<span class="text-green">Sponsor "%s" is '
                'toegevoegd</span>' % (
                    new_funder_data['name']
                )
            )

        # redirect back to clear form data
        return redirect(url_for('project', project_id=project_id))
    else:
        util.flash_form_errors(funder_form, request)

    # Populate the funder forms which allows the user to edit
    # it
    funder_forms = []
    for funder in project.funders:
        funder_forms.append(
            FunderForm(prefix="funder_form", **{
                'name': funder.name,
                'url': funder.url,
                'id': funder.id
            })
        )

    # Process filled in subproject form
    subproject_form = SubprojectForm(prefix="subproject_form")

    # Save subproject
    # Somehow we need to repopulate the iban.choices with the same
    # values as used when the form was generated for this
    # subproject. Probably to validate if the selected value is valid.
    if util.form_in_request(subproject_form, request):
        if request.method == 'POST' and subproject_form.name.data:
            subproject_form.iban.choices = project.make_select_options()

    if subproject_form.validate_on_submit():
        # Get data from the form
        new_subproject_data = {}
        for f in subproject_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'iban':
                    new_iban = None
                    new_iban_name = None
                    if not f.data == '' and f.data != 'None':
                        new_iban, new_iban_name = f.data.split(
                            ' - ', maxsplit=1
                        )
                    new_subproject_data['iban'] = new_iban
                    new_subproject_data['iban_name'] = new_iban_name
                else:
                    new_subproject_data[f.short_name] = f.data

        try:
            # Save a new subproject
            subproject = Subproject(**new_subproject_data)
            db.session.add(subproject)
            db.session.commit()

            # If IBAN, link the correct payments to this subproject
            if new_subproject_data['iban'] is not None:
                Payment.query.filter_by(
                    alias_value=new_subproject_data['iban']
                ).update({'subproject_id': subproject.id})
                db.session.commit()
            flash(
                '<span class="text-green">Subproject "%s" is '
                'toegevoegd</span>' % (
                    new_subproject_data['name']
                )
            )
        except IntegrityError as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-red">Subproject toevoegen mislukt: naam '
                '"%s" en/of IBAN "%s" bestaan al, kies een andere naam en/of '
                'IBAN<span>' % (
                    new_subproject_data['name'],
                    new_subproject_data['iban']
                )
            )
        # redirect back to clear form data
        return redirect(url_for('project', project_id=project_id))
    else:
        util.flash_form_errors(subproject_form, request)

    # Populate the the new subproject form with its project's ID
    subproject_form = SubprojectForm(prefix="subproject_form", **{
        'project_id': project.id
    })

    # If a bunq account is available, allow the user to select
    # an IBAN
    if project.bunq_access_token:
        subproject_form.iban.choices = project.make_select_options()

    # Process/create (filled in) payment form (only available when a project doesn't work with subprojects)
    payment_forms = {}
    transaction_attachment_form = ''
    remove_attachment_form = ''
    if project_owner and not project.contains_subprojects:
        payment_form_return = util.process_payment_form(request, project, is_subproject=False)
        if payment_form_return:
            return payment_form_return

        # Populate the payment forms which allows the user to edit it
        payment_forms = util.create_payment_forms(
            project.payments,
            project_owner,
            project.make_category_select_options()
        )

        # Process transaction attachment form
        transaction_attachment_form = TransactionAttachmentForm(
            prefix="transaction_attachment_form"
        )
        transaction_attachment_form_return = util.process_transaction_attachment_form(
            request,
            transaction_attachment_form,
            project.id
        )
        if transaction_attachment_form_return:
            return transaction_attachment_form_return

        # Process transaction attachment removal form
        remove_attachment_form = RemoveAttachmentForm(
            prefix="remove_attachment_form"
        )
        remove_attachment_form_return = util.process_remove_attachment_form(
            remove_attachment_form,
            project.id,
        )
        if remove_attachment_form_return:
            return remove_attachment_form_return

    amounts = util.calculate_project_amounts(project_id)

    payments = []
    if project.contains_subprojects:
        for subproject in project.subprojects:
            payments += subproject.payments
    else:
        payments += project.payments

    return render_template(
        'project.html',
        project=project,
        amounts=amounts,
        payments=payments,
        subproject_form=subproject_form,
        payment_forms=payment_forms,
        transaction_attachment_form=transaction_attachment_form,
        remove_attachment_form=remove_attachment_form,
        funder_forms=funder_forms,
        new_funder_form=FunderForm(prefix="funder_form"),
        project_owner=project_owner,
        timestamp=util.get_export_timestamp()
    )


@app.route(
    "/project/<project_id>/subproject/<subproject_id>", methods=['GET', 'POST']
)
def subproject(project_id, subproject_id):
    subproject = Subproject.query.get(subproject_id)

    if not subproject:
        return render_template(
            '404.html'
        )

    # Check if the user is logged in and is part of this subproject
    user_in_subproject = False
    if current_user.is_authenticated and subproject.has_user(current_user.id):
        user_in_subproject = True

    # A project owner is either an admin or a user that is part of the
    # project where this subproject belongs to
    project_owner = False
    if current_user.is_authenticated and (
        current_user.admin or subproject.project.has_user(current_user.id)
    ):
        project_owner = True

    if subproject.hidden and not project_owner:
        return render_template(
            '404.html'
        )

    # Process filled in subproject form
    subproject_form = SubprojectForm(prefix="subproject_form")

    # Remove subproject
    if subproject_form.remove.data:
        Subproject.query.filter_by(id=subproject_form.id.data).delete()
        db.session.commit()
        flash(
            '<span class="text-green">Subproject "%s" is verwijderd</span>' % (
                subproject_form.name.data
            )
        )
        # redirect back to clear form data
        return redirect(
            url_for(
                'project',
                project_id=project_id,
            )
        )

    # Update subproject
    # Somehow we need to repopulate the iban.choices with the same
    # values as used when the form was generated for this subproject.
    # Probably to validate if the selected value is valid.
    if util.form_in_request(subproject_form, request):
        if request.method == 'POST' and subproject_form.name.data:
            subproject_form.iban.choices = (
                subproject.project.make_select_options()
            )

    if subproject_form.validate_on_submit():
        # Get data from the form
        new_subproject_data = {}
        for f in subproject_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'iban':
                    new_iban = None
                    new_iban_name = None
                    if not f.data == '':
                        new_iban, new_iban_name = f.data.split(
                            ' - ', maxsplit=1
                        )
                    new_subproject_data['iban'] = new_iban
                    new_subproject_data['iban_name'] = new_iban_name
                else:
                    new_subproject_data[f.short_name] = f.data

        try:
            # Update if the subproject already exists
            subprojects = Subproject.query.filter_by(
                id=subproject_form.id.data
            )
            if len(subprojects.all()):
                # If the IBAN changes, then link the correct payments
                # to this subproject
                subproject = subprojects.first()
                if subproject.iban != new_subproject_data['iban']:
                    for payment in subproject.payments:
                        payment.subproject_id = None
                    Payment.query.filter_by(
                        alias_value=new_subproject_data['iban']
                    ).update({'subproject_id': subproject.id})
                subprojects.update(new_subproject_data)
                db.session.commit()
                flash(
                    '<span class="text-green">Subproject "%s" is '
                    'bijgewerkt</span>' % (
                        new_subproject_data['name']
                    )
                )
        except IntegrityError as e:
            db.session().rollback()
            app.logger.error(repr(e))
            flash(
                '<span class="text-red">Subproject bijwerken mislukt: naam '
                '"%s" en/of IBAN "%s" bestaan al, kies een andere naam en/of '
                'IBAN<span>' % (
                    new_subproject_data['name'],
                    new_subproject_data['iban']
                )
            )
        # redirect back to clear form data
        return redirect(
            url_for(
                'subproject',
                project_id=subproject.project.id,
                subproject_id=subproject.id
            )
        )
    else:
        util.flash_form_errors(subproject_form, request)

    # Populate the subproject's form which allows the user to edit it
    subproject_form = SubprojectForm(prefix='subproject_form', **{
        'name': subproject.name,
        'description': subproject.description,
        'hidden': subproject.hidden,
        'project_id': subproject.project.id,
        'id': subproject.id
    })

    # If a bunq account is available, allow the user to select
    # an IBAN
    if subproject.project.bunq_access_token:
        subproject_form.iban.choices = subproject.project.make_select_options()
        # Set default selected value
        subproject_form.iban.data = '%s - %s' % (
            subproject.iban, subproject.iban_name
        )

    # Process filled in payment form
    payment_form_return = util.process_payment_form(request, subproject, is_subproject=True)
    if payment_form_return:
        return payment_form_return

    # Populate the payment forms which allows the user to edit it
    payment_forms = {}
    if project_owner or user_in_subproject:
        payment_forms = util.create_payment_forms(
            subproject.payments,
            project_owner,
            subproject.make_category_select_options()
        )

    # Process filled in category form
    category_form_return = process_category_form(request)
    if category_form_return:
        return category_form_return

    # Populate the category forms which allows the user to
    # edit it
    category_forms = []
    for category in Category.query.filter_by(
            subproject_id=subproject.id).order_by('name'):
        category_forms.append(
            CategoryForm(
                prefix="category_form", **{
                    'id': category.id,
                    'name': category.name,
                    'subproject_id': subproject.id,
                    'project_id': subproject.project.id
                }
            )
        )

    amounts = util.calculate_subproject_amounts(subproject_id)

    # Process filled in edit user form
    edit_user_form = EditUserForm(
        prefix="edit_user_form"
    )

    # Update user
    if edit_user_form.validate_on_submit():
        users = User.query.filter_by(
            id=edit_user_form.id.data
        )
        new_user_data = {}
        remove_from_subproject = False
        remove_from_subproject_id = 0
        for f in edit_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                if f.short_name == 'remove_from_subproject' and f.data:
                    remove_from_subproject = True
                elif f.short_name == 'subproject_id' and f.data:
                    remove_from_subproject_id = f.data
                else:
                    new_user_data[f.short_name] = f.data

        # Update if the user exists
        if len(users.all()):
            users.update(new_user_data)
            if remove_from_subproject:
                # We need to get the user using '.first()' otherwise we
                # can't remove the project because of garbage collection
                initiatiefnemer = users.first()
                initiatiefnemer.subprojects.remove(
                    Subproject.query.get(remove_from_subproject_id)
                )

            db.session.commit()
            flash('<span class="text-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(
            url_for(
                'subproject',
                project_id=subproject.project.id,
                subproject_id=subproject.id
            )
        )
    else:
        util.flash_form_errors(edit_user_form, request)

    # Populate the edit user forms which allows the user to edit it
    edit_user_forms = {}
    for user in subproject.users:
        edit_user_forms[user.email] = (
            EditUserForm(
                prefix="edit_user_form", **{
                    'active': user.active,
                    'id': user.id,
                    'subproject_id': subproject.id
                }
            )
        )

    # Process filled in add user form
    add_user_form = AddUserForm(prefix="add_user_form")

    # Add user
    if add_user_form.validate_on_submit():
        new_user_data = {}
        for f in add_user_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_user_data[f.short_name] = f.data

        try:
            util.add_user(**new_user_data)
            flash(
                '<span class="text-green">"%s" is uitgenodigd als initiatiefnemer '
                '(of toegevoegd als initiatiefnemer als de gebruiker al '
                'bestond)' % (
                    new_user_data['email']
                )
            )
        except ValueError as e:
            flash(str(e))

        # redirect back to clear form data
        return redirect(
            url_for(
                'subproject',
                project_id=subproject.project.id,
                subproject_id=subproject.id
            )
        )
    else:
        util.flash_form_errors(add_user_form, request)

    transaction_attachment_form = ''
    remove_attachment_form = ''
    if project_owner or user_in_subproject:
        # Process transaction attachment form
        transaction_attachment_form = TransactionAttachmentForm(
            prefix="transaction_attachment_form"
        )
        transaction_attachment_form_return = util.process_transaction_attachment_form(
            request,
            transaction_attachment_form,
            subproject.project.id,
            subproject.id
        )
        if transaction_attachment_form_return:
            return transaction_attachment_form_return

        # Process transaction attachment removal form
        remove_attachment_form = RemoveAttachmentForm(
            prefix="remove_attachment_form"
        )
        remove_attachment_form_return = util.process_remove_attachment_form(
            remove_attachment_form,
            subproject.project.id,
            subproject.id
        )
        if remove_attachment_form_return:
            return remove_attachment_form_return

    return render_template(
        'subproject.html',
        subproject=subproject,
        amounts=amounts,
        subproject_form=subproject_form,
        payment_forms=payment_forms,
        transaction_attachment_form=transaction_attachment_form,
        remove_attachment_form=remove_attachment_form,
        edit_user_forms=edit_user_forms,
        add_user_form=AddUserForm(prefix='add_user_form'),
        project_owner=project_owner,
        user_in_subproject=user_in_subproject,
        timestamp=util.get_export_timestamp(),
        category_forms=category_forms,
        category_form=CategoryForm(
            prefix="category_form",
            **{
                'subproject_id': subproject.id,
                'project_id': subproject.project.id
            }
        )
    )

@app.route("/over", methods=['GET', 'POST'])
def over():
    return render_template(
        'over.html',
    )

@app.route('/upload/<filename>')
def upload(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'], filename
    )


@app.route("/reset-wachtwoord-verzoek", methods=['GET', 'POST'])
def reset_wachtwoord_verzoek():
    form = ResetPasswordRequestForm(prefix="reset_password_request_form")
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(
            '<span class="text-green">Er is een e-mail verzonden met '
            'instructies om het wachtwoord te veranderen</span>'
        )
        return redirect(url_for('login'))
    return render_template('reset-wachtwoord-verzoek.html', form=form)


@app.route("/reset-wachtwoord/<token>", methods=['GET', 'POST'])
def reset_wachtwoord(token):
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm(prefix="reset_password_request_form")
    if form.validate_on_submit():
        user.set_password(form.Wachtwoord.data)
        db.session.commit()
        flash('<span class="text-green">Uw wachtwoord is aangepast</span>')
        return redirect(url_for('login'))
    return render_template('reset-wachtwoord.html', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm(prefix="login_form")
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.Wachtwoord.data):
            flash(
                '<span class="text-red">Fout e-mailadres of wachtwoord</span>'
            )
            return(redirect(url_for('login')))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html', form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route("/profiel", methods=['GET', 'POST'])
@login_required
def profile():
    # Process filled in edit profile form
    edit_profile_form = EditProfileForm(
        prefix="edit_profile_form"
    )

    # Update profile
    if edit_profile_form.validate_on_submit():
        users = User.query.filter_by(
            id=current_user.id
        )
        new_profile_data = {}
        for f in edit_profile_form:
            if f.type != 'SubmitField' and f.type != 'CSRFTokenField':
                new_profile_data[f.short_name] = f.data

        # Update if the user exists
        if len(users.all()):
            users.update(new_profile_data)
            db.session.commit()
            flash('<span class="text-green">gebruiker is bijgewerkt</span>')

        # redirect back to clear form data
        return redirect(
            url_for(
                'profile',
                id=current_user.id
            )
        )
    else:
        util.flash_form_errors(edit_profile_form, request)

    # Populate the edit profile form which allows the user to edit it
    edit_profile_form = EditProfileForm(
        prefix="edit_profile_form", **{
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'biography': current_user.biography
        }
    )
    return render_template('profiel.html', edit_profile_form=edit_profile_form)


@app.errorhandler(413)
def request_entity_too_large(error):
    flash(
        '<span class="text-red">Het verstuurde bestand is te groot. Deze mag '
        'maximaal %sMB zijn.</span>' % (
            app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024
        )
    )
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(threaded=True)

from flask import render_template, redirect, url_for, flash, session, request
from flask_login import login_required, login_user, logout_user, current_user

from app import app, db
from app.forms import ResetPasswordRequestForm, ResetPasswordForm, LoginForm
from app.email import send_password_reset_email
from app.models import User, Project
from app.util import create_bunq_api_config

from bunq.sdk.context import ApiEnvironmentType

from time import time
import jwt
import requests


# Add 'Cache-Control': 'private' header if users are logged in
@app.after_request
def after_request_callback(response):
    if current_user.is_authenticated:
        response.headers['Cache-Control'] = 'private'

    return response


@app.route("/")
def index():
    return render_template(
        'index.html'
    )


@app.route("/reset-wachtwoord-verzoek", methods=['GET', 'POST'])
def reset_wachtwoord_verzoek():
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(
            'Er is een e-mail verzonden met instructies om het wachtwoord te '
            'veranderen'
        )
        return redirect(url_for('login'))
    return render_template('reset-wachtwoord-verzoek.html', form=form)


@app.route("/reset-wachtwoord/<token>", methods=['GET', 'POST'])
def reset_wachtwoord(token):
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.Wachtwoord.data)
        db.session.commit()
        flash('Uw wachtwoord is aangepast')
        return redirect(url_for('login'))
    return render_template('reset-wachtwoord.html', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.Wachtwoord.data):
            flash('Fout e-mailadres of wachtwoord')
            return(redirect(url_for('login')))
        if not user.is_active:
            flash('Deze gebruiker is niet meer actief')
            return(redirect(url_for('login')))
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('login.html', form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route(
    "/dashboard",
    methods=['GET', 'POST']
)
@login_required
def dashboard():
    # Process Bunq OAuth callback
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
        except:
            app.logger.warn(
                'Retrieved wrong token (used for retrieving Bunq '
                'authorization code)'
            )

        if token_info:
            user_id = token_info['user_id']
            project_id = token_info['project_id']
            bank_name = token_info['bank_name']

            # If authorization code, retrieve access token from Bunq
            authorization_code = request.args.get('code')
            if authorization_code:
                base_url = 'https://api.oauth.bunq.com'
                if (app.config['BUNQ_ENVIRONMENT_TYPE'] ==
                        ApiEnvironmentType.SANDBOX):
                    base_url = 'https://api-oauth.sandbox.bunq.com'
                response = requests.post(
                    '%s/v1/token?grant_type=authorization_code&code=%s'
                    '&redirect_uri=https://openpoen.nl/dashboard&client_id=%s'
                    '&client_secret=%s' % (
                        base_url,
                        authorization_code,
                        app.config['BUNQ_CLIENT_ID'],
                        app.config['BUNQ_CLIENT_SECRET'],
                    )
                ).json()

                # Add access token to the project in the database
                if 'access_token' in response:
                    bunq_access_token = response['access_token']
                    project = Project.query.filter_by(id=project_id).first()
                    project.set_bank_name(bank_name)
                    project.set_bunq_access_token(bunq_access_token)
                    db.session.commit()

                    # Create Bunq API .conf file
                    create_bunq_api_config(bunq_access_token, project.id)
                else:
                    app.logger.error(
                        'Retrieval of Bunq access token failed. Bunq Error: '
                        '"%s". Bunq error description: "%s"' % (
                            response['error'], response['error_description']
                        )
                    )

    # Retrieve all the user's owned projects (if any); used to connect
    # to a Bunq account
    owned_projects = []
    for owned_project in current_user.owned_projects:
        bunq_token = jwt.encode(
            {
                'user_id': current_user.id,
                'project_id': owned_project.id,
                'bank_name': 'Bunq',
                'exp': time() + 1800
            },
            app.config['SECRET_KEY'],
            algorithm='HS256'
        ).decode('utf-8')

        already_authorized = False
        if owned_project.bunq_access_token and len(owned_project.bunq_access_token):
            already_authorized = True

        owned_projects.append(
            {
                'name': owned_project.name,
                'already_authorized': already_authorized,
                'bunq_token': bunq_token
            }
        )

    return render_template(
        'dashboard.html',
        user=current_user,
        owned_projects=owned_projects,
        bunq_client_id=app.config['BUNQ_CLIENT_ID']
    )


if __name__ == "__main__":
    app.run(threaded=True)

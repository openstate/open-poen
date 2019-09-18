from app import app, db
from app.email import send_invite
from app.models import User, Payment, Project, Subproject
from flask import url_for
from os import urandom
from os.path import abspath, join, dirname
from pprint import pprint
import click
import json
import sys

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))

from bunq.sdk.client import Pagination
from bunq.sdk.context import ApiEnvironmentType
from bunq.sdk.model.generated import endpoint
from libs.bunq_lib import BunqLib
from libs.share_lib import ShareLib

from app import util


# Bunq commands
environment_type = app.config['BUNQ_ENVIRONMENT_TYPE']


@app.cli.group()
def bunq():
    """Bunq related commands"""
    pass


@bunq.command()
@click.argument('project_id')
def get_new_payments(project_id):
    """Get new payments from all IBANs belonging to one Bunq account"""
    util.get_new_payments(project_id)


@bunq.command()
@click.argument('project_id')
def create_bunq_api_conf(project_id):
    """ Get/renew Bunq API .conf file for a specific project"""
    p = Project.query.filter_by(id=project_id).first()
    if not p:
        app.logger.error('Project %s does not exist' % project_id)
        return

    if p.bunq_access_token:
        util.create_bunq_api_config(p.bunq_access_token, p.id)
        app.logger.info('Created Bunq API .conf file for project %s' % p.id)
    else:
        app.logger.error(
            'No Bunq access token available for project %s' % p.id
        )


@bunq.command()
def create_all_bunq_api_conf():
    """ Get/renew Bunq API .conf files for a all projects"""
    for p in Project.query.all():
        if p.bunq_access_token:
            util.create_bunq_api_config(p.bunq_access_token, p.id)
            app.logger.info(
                'Created Bunq API .conf file for project %s' % p.id
            )
        else:
            app.logger.error(
                'No Bunq access token available for project %s' % p.id
            )


@bunq.command()
def show_sandbox_users():
    """Show Bunq sandbox users; useful during development to log in to the Bunq
    app
    """
    if environment_type is ApiEnvironmentType.SANDBOX:
        bunq_api = BunqLib(environment_type)
        all_alias = bunq_api.get_all_user_alias()
        ShareLib.print_all_user_alias(all_alias)


# Database commands
@app.cli.group()
def database():
    """Open Poen database related commands"""
    pass


@database.command()
def show_all_users():
    """
    Show all Open Poen users
    """
    for user in User.query.all():
        pprint(vars(user))


@database.command()
def show_all_payments():
    """
    Show all payments
    """
    for payment in Payment.query.all():
        pprint(vars(payment))


@database.command()
@click.argument('email')
def add_admin_user(email):
    """
    Adds an admin user. This command will prompt for an email address.
    If it does not exist yet a user will be created and given admin
    rights.
    """

    # Check if a user already exists with this email address
    user = User.query.filter_by(email=email).first()

    if user:
        user.admin = True
    if not user:
        user = User(
            email=email,
            admin=True
        )
        user.set_password(urandom(24))
        db.session.add(user)
        db.session.commit()

        # Send the new user an invitation email
        send_invite(user)

    db.session.commit()

    print("Added user as admin")


@database.command()
@click.argument('email')
def add_user(email):
    """
    Adds a user. This command will prompt for an email address.
    """

    # Check if a user already exists with this email address
    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            email=email
        )
        user.set_password(urandom(24))
        db.session.add(user)
        db.session.commit()

        # Send the new user an invitation email
        send_invite(user)

    db.session.commit()

    print("Added user")


@database.command()
@click.argument('email')
def create_user_invite_link(email):
    """
    Create a 'reset password' URL for a user. Useful to avoid emails
    in the process of resetting a users password. Provide the users
    email address as parameter.
    """
    user = User.query.filter_by(email=email).first()
    if not user:
        print('No user with email address %s' % (email))
        return
    token = user.get_reset_password_token()
    print(
        'Password reset URL for %s: %s' % (
            email,
            url_for('reset_wachtwoord', token=token, _external=True)
        )
    )

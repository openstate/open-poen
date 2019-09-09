from app import app, db
from app.models import User
from app.email import send_invite
from flask import url_for
import click
import os
import sys
from os.path import abspath, join, dirname
from pprint import pprint
import json

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))

from libs.bunq_lib import BunqLib
from libs.share_lib import ShareLib
from bunq.sdk.context import ApiEnvironmentType

# bunq commands
@app.cli.group()
def bunq():
    """Bunq related commands."""
    pass

@bunq.command()
def payments():
    """Get recent payments from all cards."""

    # TODO: make configurable?

    #cls.environment_type = ApiEnvironmentType.PRODUCTION
    environment_type = ApiEnvironmentType.SANDBOX

    bunq_api = BunqLib(environment_type)

    try:
        all_payments = bunq_api.get_all_payment(10)
    except Exception as e:
        print("Getting bunq payments resulted in an exception:")
        print(e)
        all_payments = []

    for p in all_payments:
        try:
            payload = transform(p)
        except Exception as e:
            print("Transforming a bunq payment resulted in an exception:")
            print(e)
            payload = {}
        try:
            store(payload)
        except Exception as e:
            print("Saving a bunq payment resulted in an exception:")
            print(e)

    if environment_type is ApiEnvironmentType.SANDBOX:
        all_alias = bunq_api.get_all_user_alias()
        ShareLib.print_all_user_alias(all_alias)

    bunq_api.update_context()

# Database commands
@app.cli.group()
def database():
    """Open Poen database related commands."""
    pass


@database.command()
def show_all_users():
    """
    Show all users and their corresponding gemeenten
    """
    for user in User.query.all():
        print(
            '"%s","%s"' % (
                user.email
            )
        )


@database.command()
@click.argument('email')
def add_admin_user(email):
    """
    Adds an admin user. This command will prompt for an email address.
    If it does not exist yet a user will be created and given admin
    rights
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
        user.set_password(os.urandom(24))
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
        user.set_password(os.urandom(24))
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

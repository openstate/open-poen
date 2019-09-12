from app import app, db
from app.email import send_invite
from app.models import User, Payment
from flask import url_for
from os import urandom
from os.path import abspath, join, dirname
from pprint import pprint
import click
import json
import sys

sys.path.insert(0, abspath(join(dirname(__file__), '../tinker/tinker')))

from libs.bunq_lib import BunqLib
from libs.share_lib import ShareLib


# Bunq commands
environment_type = app.config['BUNQ_ENVIRONMENT_TYPE']


@app.cli.group()
def bunq():
    """Bunq related commands"""
    pass


def transform_payment(payment):
    payment_as_dict = json.loads(payment.to_json())
    result = {}
    for k, v in payment_as_dict.items():
        # Skip these fields as we don't use them
        if k in ['allow_chat', 'attachment',
                 'request_reference_split_the_bill']:
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


@bunq.command()
def get_recent_payments():
    """Get recent payments from all cards"""
    bunq_api = BunqLib(environment_type)

    try:
        all_payments = bunq_api.get_all_payment(10)
    except Exception as e:
        app.logger.error("Getting bunq payments resulted in an exception:")
        app.logger.error(e)
        all_payments = []

    new_payments = 0
    for payment in all_payments:
        try:
            payload = transform_payment(payment)
        except Exception as e:
            app.logger.error(
                "Transforming a bunq payment resulted in an exception:"
            )
            app.logger.error(e)
            payload = {}
        try:
            payment = Payment.query.filter_by(
                bank_payment_id=payload['bank_payment_id']
            ).first()
            if not payment:
                payment = Payment(**payload)
                db.session.add(payment)
                db.session.commit()
                new_payments += 1
        except Exception as e:
            app.logger.error("Saving a bunq payment resulted in an exception:")
            app.logger.error(e)

    bunq_api.update_context()
    app.logger.info('Newly retrieved payments: %s' % (new_payments))


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

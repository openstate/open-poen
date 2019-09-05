from app import app, db
from app.models import User
from app.email import send_invite
from flask import url_for
import click
import os


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

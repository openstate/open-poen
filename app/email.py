from flask import render_template
from flask_mail import Message
from app import app, mail


def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    mail.send(msg)


def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email(
        '[%s] Wachtwoord aanpassen' % app.config['SERVER_NAME'],
        sender=app.config['FROM'],
        recipients=[user.email],
        text_body=render_template(
            'email/reset_password.txt',
            user=user,
            token=token,
            server_name=app.config['SERVER_NAME']
        ),
        html_body=render_template(
            'email/reset_password.html',
            user=user,
            token=token,
            server_name=app.config['SERVER_NAME']
        )
    )


# Sends an invite to a user
def send_invite(user):
    token = user.get_reset_password_token()
    send_email(
        'Uitnodiging deelname [%s]' % app.config['SERVER_NAME'],
        sender=app.config['FROM'],
        recipients=[user.email],
        text_body=render_template(
            'email/uitnodiging.txt',
            user=user,
            token=token,
            server_name=app.config['SERVER_NAME'],
            website_name=app.config['WEBSITE_NAME']
        ),
        html_body=render_template(
            'email/uitnodiging.html',
            user=user,
            token=token,
            server_name=app.config['SERVER_NAME'],
            website_name=app.config['WEBSITE_NAME']
        )
    )

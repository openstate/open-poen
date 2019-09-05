#/usr/bin/env python
# -*- coding: utf-8 -*-
import locale
import os
import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
from config import Config
from flask import Flask
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

mail = Mail(app)

# Used for translating error messages for Flask-WTF forms
babel = Babel(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_message = u"Log in om verder te gaan"
login_manager.login_view = "login"

locale.setlocale(locale.LC_NUMERIC, 'nl_NL.UTF-8')

from app import routes, models, errors

if not app.debug:
    # Send email on errors
    if app.config['MAIL_SERVER']:
        auth = None
        if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
            auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        secure = None
        if app.config['MAIL_USE_TLS']:
            secure = ()
        mail_handler = SMTPHandler(
            mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
            fromaddr=app.config['FROM'],
            toaddrs=app.config['ADMINS'],
            subject='[Open Poen] website error',
            credentials=auth,
            secure=secure
        )
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

# Log info messages and up to file
if not os.path.exists('log'):
    os.mkdir('log')
file_handler = RotatingFileHandler(
    'log/open_poen.log',
    maxBytes=1000000,
    backupCount=10
)
file_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    )
)
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Open Poen startup')

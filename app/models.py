from app import app, db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from time import time
import jwt


class Payment(db.Model):
    # {*'alias_name': 'Highchurch',
    #  *'alias_type': 'IBAN',
    #  *'alias_value': 'NL13BUNQ9900299981',
    #  'allow_chat': False,
    #  *'amount_currency': 'EUR',
    #  *'amount_value': '500.00',
    #  'attachment': [],
    #  *'balance_after_mutation_currency': 'EUR',
    #  *'balance_after_mutation_value': '500.00',
    #  *'counterparty_alias_name': 'S. Daddy',
    #  *'counterparty_alias_type': 'IBAN',
    #  *'counterparty_alias_value': 'NL65BUNQ9900000188',
    #  *'created': '2019-09-09 14:07:38.942900',
    #  *'description': 'Requesting some spending money.',
    #  *'id': 369127,
    #  *'monetary_account_id': 27307,
    #  'request_reference_split_the_bill': [],
    #  *'sub_type': 'REQUEST',
    #  *'type': 'BUNQ',
    #  *'updated': '2019-09-09 14:07:38.942900'}
    id = db.Column(db.Integer, primary_key=True)
    alias_name = db.Column(db.String(120))
    alias_type = db.Column(db.String(12))
    alias_value = db.Column(db.String(120), index=True)
    amount_currency = db.Column(db.String(12))
    amount_value = db.Column(db.Float())
    balance_after_mutation_currency = db.Column(db.String(12))
    balance_after_mutation_value = db.Column(db.Float())
    counterparty_alias_name = db.Column(db.String(120))
    counterparty_alias_type = db.Column(db.String(12))
    counterparty_alias_value = db.Column(db.String(120), index=True)
    description = db.Column(db.Text())
    created = db.Column(db.DateTime(timezone=True))
    updated = db.Column(db.DateTime(timezone=True))
    monetary_account_id = db.Column(db.Integer(), index=True)
    sub_type = db.Column(db.String(12))
    type = db.Column(db.String(12))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        if len(password) < 12:
            raise RuntimeError(
                'Attempted to set password with length less than 12 characters'
            )
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=86400):
        return jwt.encode(
            {
                'reset_password': self.id,
                'exp': time() + expires_in
            },
            app.config['SECRET_KEY'],
            algorithm='HS256'
        ).decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            user_id = jwt.decode(
                token,
                app.config['SECRET_KEY'],
                algorithms='HS256'
            )['reset_password']
        except:
            return
        return User.query.get(user_id)

    def __repr__(self):
        return '<User {}>'.format(self.email)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create the tables if they don't exist
db.create_all()

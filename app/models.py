from app import app, db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from time import time
import jwt


# Association table between Project and User
project_user = db.Table('project_user',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.PrimaryKeyConstraint('project_id', 'user_id')
)


# Association table between Subproject and User
subproject_user = db.Table('subproject_user',
    db.Column('subproject_id', db.Integer, db.ForeignKey('subproject.id')),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.PrimaryKeyConstraint('subproject_id', 'user_id')
)


class Funder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subproject_id = db.Column(db.Integer, db.ForeignKey('subproject.id'))
    name = db.Column(db.String(120), index=True)
    url = db.Column(db.String(2000))


class DebitCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iban = db.Column(db.Integer, db.ForeignKey('subproject.iban'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    card_id = db.Column(db.Integer)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(120), index=True)
    last_name = db.Column(db.String(120), index=True)
    is_active = db.Column(db.Boolean, default=True)
    biography = db.Column(db.String(1000), default=True)

    debit_cards = db.relationship(DebitCard, backref='user', lazy='dynamic')

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


class Subproject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    iban = db.Column(db.String(34), index=True, unique=True)
    name = db.Column(db.String(120), index=True, unique=True)
    description = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)

    users = db.relationship(User, secondary=subproject_user, backref='subprojects', lazy='dynamic')
    debit_cards = db.relationship(DebitCard, backref='subproject', lazy='dynamic')
    funders = db.relationship(Funder, backref='subproject', lazy='dynamic')


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iban = db.Column(db.String(34), index=True, unique=True)
    name = db.Column(db.String(120), index=True, unique=True)
    description = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)

    subprojects = db.relationship(Subproject, backref='project', lazy='dynamic')
    users = db.relationship(User, secondary=project_user, backref='projects', lazy='dynamic')


class Payment(db.Model):
    # Example payment values. The '*' denotes fields we save.
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


class UserStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    text = db.Column(db.String(200))
    hidden = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create the tables if they don't exist
db.create_all()

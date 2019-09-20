from app import app, db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from time import time
import jwt


# Association table between Project and User
project_user = db.Table(
    'project_user',
    db.Column(
        'project_id', db.Integer, db.ForeignKey(
            'project.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('project_id', 'user_id')
)


# Association table between Subproject and User
subproject_user = db.Table(
    'subproject_user',
    db.Column(
        'subproject_id', db.Integer, db.ForeignKey(
            'subproject.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('subproject_id', 'user_id')
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(120), index=True)
    last_name = db.Column(db.String(120), index=True)
    biography = db.Column(db.String(1000), default=True)
    is_active = db.Column(db.Boolean, default=True)

    debit_cards = db.relationship('DebitCard', backref='user', lazy='dynamic')
    payments = db.relationship('Payment', backref='user', lazy='dynamic')

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


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(64), index=True)
    bunq_access_token = db.Column(db.String(64))
    iban = db.Column(db.String(34), index=True, unique=True)
    iban_name = db.Column(db.String(120), index=True)
    name = db.Column(db.String(120), index=True, unique=True)
    description = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)

    subprojects = db.relationship(
        'Subproject',
        backref='project',
        lazy='dynamic'
    )
    users = db.relationship(
        'User',
        secondary=project_user,
        backref='projects',
        lazy='dynamic'
    )
    funders = db.relationship('Funder', backref='project', lazy='dynamic')
    payments = db.relationship(
        'Payment',
        backref='project',
        lazy='dynamic',
        order_by='Payment.bank_payment_id.desc()'
    )

    def set_bank_name(self, bank_name):
        self.bank_name = bank_name

    def set_bunq_access_token(self, access_token):
        if len(access_token) == 64:
            self.bunq_access_token = access_token
        else:
            app.logger.error(
                'Did not save Bunq access token, its length is not 64'
            )

    # Returns true if the project is linked to the given user_id
    def has_user(self, user_id):
        return self.users.filter(
            project_user.c.user_id == user_id
        ).count() > 0


class Subproject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE')
    )
    iban = db.Column(db.String(34), index=True, unique=True)
    iban_name = db.Column(db.String(120), index=True)
    name = db.Column(db.String(120), index=True, unique=True)
    description = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)

    users = db.relationship(
        'User',
        secondary=subproject_user,
        backref='subprojects',
        lazy='dynamic'
    )
    debit_cards = db.relationship(
        'DebitCard',
        backref='subproject',
        lazy='dynamic'
    )
    payments = db.relationship('Payment', backref='subproject', lazy='dynamic')


class DebitCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iban = db.Column(db.String(34), db.ForeignKey('subproject.iban'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    card_id = db.Column(db.Integer)


class Payment(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    subproject_id = db.Column(
        db.Integer, db.ForeignKey('subproject.id', ondelete='SET NULL')
    )
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='SET NULL')
    )

    # Fields coming from the bank
    # Some example payment values:
    # {*'alias_name': 'Highchurch',
    #  *'alias_type': 'IBAN',
    #  *'alias_value': 'NL13BUNQ9900299981',
    #  *'amount_currency': 'EUR',
    #  *'amount_value': '500.00',
    #  *'balance_after_mutation_currency': 'EUR',
    #  *'balance_after_mutation_value': '500.00',
    #  *'counterparty_alias_name': 'S. Daddy',
    #  *'counterparty_alias_type': 'IBAN',
    #  *'counterparty_alias_value': 'NL65BUNQ9900000188',
    #  *'created': '2019-09-09 14:07:38.942900',
    #  *'description': 'Requesting some spending money.',
    #  *'id': 369127,
    #  *'monetary_account_id': 27307,
    #  *'sub_type': 'REQUEST',
    #  *'type': 'BUNQ',
    #  *'updated': '2019-09-09 14:07:38.942900'}
    id = db.Column(db.Integer, primary_key=True)
    bank_payment_id = db.Column(db.Integer)
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

    # Fields coming from the user
    short_user_description = db.Column(db.String(100))
    long_user_description = db.Column(db.String(1000))
    flag_suspicious_count = db.Column(db.Integer)

    hidden = db.Column(db.Boolean, default=False)


class Funder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE')
    )
    name = db.Column(db.String(120), index=True)
    url = db.Column(db.String(2000))


class UserStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(240), index=True)
    title = db.Column(db.String(200))
    text = db.Column(db.String(200))
    hidden = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create the tables if they don't exist
db.create_all()

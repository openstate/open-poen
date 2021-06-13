from app import app, db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from time import time
import jwt
import locale


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


# Association table between Payment and File for attachments
payment_attachment = db.Table(
    'payment_attachment',
    db.Column(
        'payment_id', db.Integer, db.ForeignKey(
            'payment.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'file_id', db.Integer, db.ForeignKey('file.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('payment_id', 'file_id')
)


# Assocation table between Project and File for images
project_image = db.Table(
    'project_image',
    db.Column(
        'project_id', db.Integer, db.ForeignKey(
            'project.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'file_id', db.Integer, db.ForeignKey('file.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('project_id', 'file_id')
)


# Assocation table between Subproject and File for images
subproject_image = db.Table(
    'subproject_image',
    db.Column(
        'subproject_id', db.Integer, db.ForeignKey(
            'subproject.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'file_id', db.Integer, db.ForeignKey('file.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('subproject_id', 'file_id')
)


# Assocation table between Funder and File for images
funder_image = db.Table(
    'funder_image',
    db.Column(
        'funder_id', db.Integer, db.ForeignKey(
            'funder.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'file_id', db.Integer, db.ForeignKey('file.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('funder_id', 'file_id')
)


# Assocation table between UserStory and File for images
user_story_image = db.Table(
    'userstory_image',
    db.Column(
        'user_story_id', db.Integer, db.ForeignKey(
            'user_story.id', ondelete='CASCADE'
        )
    ),
    db.Column(
        'file_id', db.Integer, db.ForeignKey('file.id', ondelete='CASCADE')
    ),
    db.PrimaryKeyConstraint('user_story_id', 'file_id')
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    admin = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(120), index=True)
    last_name = db.Column(db.String(120), index=True)
    biography = db.Column(db.String(1000))
    hidden = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    image = db.Column(db.Integer, db.ForeignKey('file.id', ondelete='SET NULL'))

    debit_cards = db.relationship('DebitCard', backref='user', lazy='dynamic')
    payments = db.relationship('Payment', backref='user', lazy='dynamic')

    def is_active(self):
        return self.active

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
    contains_subprojects = db.Column(db.Boolean, default=True)
    hidden = db.Column(db.Boolean, default=False)
    hidden_sponsors = db.Column(db.Boolean, default=False)
    budget = db.Column(db.Integer)

    subprojects = db.relationship(
        'Subproject',
        backref='project',
        lazy='dynamic',
        order_by='Subproject.name.asc()'
    )
    users = db.relationship(
        'User',
        secondary=project_user,
        backref='projects',
        lazy='dynamic'
    )
    funders = db.relationship('Funder', backref='project', lazy='dynamic')
    ibans = db.relationship('IBAN', backref='project', lazy='dynamic')
    payments = db.relationship(
        'Payment',
        backref='project',
        lazy='dynamic',
        order_by='Payment.bank_payment_id.desc()'
    )
    images = db.relationship(
        'File',
        secondary=project_image,
        lazy='dynamic'
    )
    categories = db.relationship('Category', backref='project', lazy='dynamic')

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

    # Create IBAN select options to be shown in a dropdown menu
    def make_select_options(self):
        select_options = [('', '')]
        for iban in self.ibans:
            option = '%s - %s' % (iban.iban, iban.iban_name)
            select_options.append((option, option))
        return select_options

    # Create category select options to be shown in a dropdown menu
    def make_category_select_options(self):
        select_options = [('', '')]
        for category in Category.query.filter_by(project_id=self.id):
            select_options.append((str(category.id), category.name))
        return select_options


class Subproject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE')
    )
    iban = db.Column(db.String(34), index=True, unique=True)
    iban_name = db.Column(db.String(120), index=True)
    name = db.Column(db.String(120), index=True)
    description = db.Column(db.Text)
    hidden = db.Column(db.Boolean, default=False)
    budget = db.Column(db.Integer)

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
    images = db.relationship(
        'File',
        secondary=subproject_image,
        lazy='dynamic'
    )
    categories = db.relationship('Category', backref='subproject', lazy='dynamic')

    # Subproject names must be unique within a project
    __table_args__ = (
        db.UniqueConstraint('project_id', 'name'),
    )

    # Returns true if the subproject is linked to the given user_id
    def has_user(self, user_id):
        return self.users.filter(
            subproject_user.c.user_id == user_id
        ).count() > 0

    # Create select options to be shown in a dropdown menu
    def make_category_select_options(self):
        select_options = [('', '')]
        for category in Category.query.filter_by(subproject_id=self.id):
            select_options.append((str(category.id), category.name))
        return select_options


class DebitCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iban = db.Column(db.String(34), db.ForeignKey('subproject.iban'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    card_id = db.Column(db.Integer)


class Payment(db.Model):
    # Currently not used
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    subproject_id = db.Column(
        db.Integer, db.ForeignKey('subproject.id', ondelete='SET NULL')
    )
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='SET NULL')
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey('category.id', ondelete='SET NULL')
    )

    # Fields coming from the Bunq API
    # Some example payment values:
    # {'alias_name': 'Highchurch',
    #  'alias_type': 'IBAN',
    #  'alias_value': 'NL13BUNQ9900299981',
    #  'amount_currency': 'EUR',
    #  'amount_value': '500.00',
    #  'balance_after_mutation_currency': 'EUR',
    #  'balance_after_mutation_value': '500.00',
    #  'counterparty_alias_name': 'S. Daddy',
    #  'counterparty_alias_type': 'IBAN',
    #  'counterparty_alias_value': 'NL65BUNQ9900000188',
    #  'created': '2019-09-09 14:07:38.942900',
    #  'description': 'Requesting some spending money.',
    #  'id': 369127,
    #  'monetary_account_id': 27307,
    #  'sub_type': 'REQUEST',
    #  'type': 'BUNQ',
    #  'updated': '2019-09-09 14:07:38.942900'}
    id = db.Column(db.Integer, primary_key=True)
    bank_payment_id = db.Column(db.Integer, unique=True)
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
    # Currently 'BUNQ' or 'MANUAL'
    type = db.Column(db.String(12))
    # Can be 'inbesteding', 'aanbesteding' or 'subsidie'
    route = db.Column(db.String(12))

    # Fields coming from the user
    short_user_description = db.Column(db.String(50))
    long_user_description = db.Column(db.String(1000))
    hidden = db.Column(db.Boolean, default=False)

    # Initial idea to allow people to flag suspicous transactions, currently
    # not implemented
    flag_suspicious_count = db.Column(db.Integer)

    attachments = db.relationship(
        'File',
        secondary=payment_attachment,
        lazy='dynamic'
    )

    def get_formatted_currency(self):
        return locale.format(
            "%.2f", self.amount_value, grouping=True, monetary=True
        )

    def get_formatted_balance(self):
        return_value = ''
        # Manually added payments don't have the balance_after_mutation_value
        # field
        if self.balance_after_mutation_value:
            return_value = locale.format(
                "%.2f",
                self.balance_after_mutation_value,
                grouping=True,
                monetary=True
            )
        return return_value


class Funder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE')
    )
    name = db.Column(db.String(120), index=True)
    url = db.Column(db.String(2000))
    images = db.relationship(
        'File',
        secondary=funder_image,
        lazy='dynamic'
    )


class IBAN(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE')
    )
    iban = db.Column(db.String(34), index=True)
    iban_name = db.Column(db.String(120), index=True)


class UserStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(240), index=True)
    title = db.Column(db.String(200))
    text = db.Column(db.String(200))
    hidden = db.Column(db.Boolean, default=False)
    images = db.relationship(
        'File',
        secondary=user_story_image,
        lazy='dynamic'
    )


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), index=True)
    mimetype = db.Column(db.String(255))


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subproject_id = db.Column(
        db.Integer, db.ForeignKey('subproject.id', ondelete='CASCADE')
    )
    project_id = db.Column(
        db.Integer, db.ForeignKey('project.id', ondelete='CASCADE')
    )
    name = db.Column(db.String(120), index=True)
    payments = db.relationship('Payment', backref='category', lazy='dynamic')

    # Category names must be unique within a (sub)project
    __table_args__ = (
        db.UniqueConstraint('project_id', 'subproject_id', 'name'),
    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from app import app
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from wtforms.widgets import HiddenInput
from wtforms import (
    StringField, IntegerField, BooleanField, PasswordField, SubmitField,
    SelectField, TextAreaField
)
from wtforms.fields.html5 import EmailField


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(
        'E-mailadres', validators=[DataRequired(), Email(), Length(max=120)]
    )
    submit = SubmitField(
        'Bevestig',
        render_kw={
            'class': 'btn btn-info'
        }
    )


class ResetPasswordForm(FlaskForm):
    # Use 'Wachtwoord' instead of 'password' as the variable
    # is used in a user-facing error message when the passwords
    # don't match and we want it to show a Dutch word instead of
    # English
    Wachtwoord = PasswordField(
        'Wachtwoord',
        validators=[DataRequired(), Length(min=12)]
    )
    Wachtwoord2 = PasswordField(
        'Herhaal wachtwoord',
        validators=[DataRequired(), EqualTo('Wachtwoord')]
    )
    submit = SubmitField(
        'Bevestig',
        render_kw={
            'class': 'btn btn-info'
        }
    )


class LoginForm(FlaskForm):
    email = EmailField(
        'E-mailadres', validators=[DataRequired(), Email(), Length(max=120)]
    )
    Wachtwoord = PasswordField(
        'Wachtwoord', validators=[DataRequired(), Length(min=12)]
    )
    submit = SubmitField(
        'Inloggen',
        render_kw={
            'class': 'btn btn-info'
        }
    )


class ProjectForm(FlaskForm):
    name = StringField('Naam', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Beschrijving', validators=[DataRequired()])
    hidden = BooleanField('Project verbergen')
    iban = SelectField('IBAN', validators=[Optional()], choices=[])
    id = IntegerField(widget=HiddenInput())

    submit = SubmitField(
        'Opslaan',
        render_kw={
            'class': 'btn btn-info'
        }
    )

    remove = SubmitField(
        'Verwijderen',
        render_kw={
            'class': 'btn btn-danger'
        }
    )


class SubprojectForm(FlaskForm):
    name = StringField('Naam', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Beschrijving', validators=[DataRequired()])
    hidden = BooleanField('Initiatief verbergen')
    iban = SelectField(
        'IBAN', validators=[Optional(), Length(max=34)], choices=[]
    )
    project_id = IntegerField(widget=HiddenInput())
    id = IntegerField(widget=HiddenInput())

    submit = SubmitField(
        'Opslaan',
        render_kw={
            'class': 'btn btn-info'
        }
    )

    remove = SubmitField(
        'Verwijderen',
        render_kw={
            'class': 'btn btn-danger'
        }
    )


class PaymentForm(FlaskForm):
    short_user_description = StringField(
        'Korte beschrijving', validators=[Length(max=50)]
    )
    long_user_description = TextAreaField(
        'Lange beschrijving', validators=[Length(max=2000)]
    )
    hidden = BooleanField('Transactie verbergen')
    id = IntegerField(widget=HiddenInput())

    submit = SubmitField(
        'Opslaan',
        render_kw={
            'class': 'btn btn-info'
        }
    )

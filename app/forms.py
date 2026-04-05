# - definice formulářů pomocí rozšíření Flask-WTF
# - zajišťuje automatickou validaci dat a ochranu proti CSRF útokům

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError


# - FORMULÁŘ PRO REGISTRACI:
class RegistrationForm(FlaskForm):
    # - StringField: klasické textové pole pro jméno
    # - validators=[DataRequired()]: pole nesmí zůstat prázdné
    # - Length(min=4, max=20): jméno musí mít rozumnou délku (ochrana DB)
    username = StringField('Uživatelské jméno', validators=[DataRequired(), Length(min=4, max=20)])

    # - PasswordField: text se při psaní skrývá (tečky/hvězdičky)
    # - Length(min=6): minimální délka pro základní bezpečnost
    password = PasswordField('Heslo', validators=[DataRequired(), Length(min=6)])

    # - EqualTo('password'): kontroluje, zda se toto pole shoduje s polem 'password'
    # - pokud se neshodují, formulář vyhodí chybu a nepustí data dál
    confirm_password = PasswordField('Potvrď heslo', validators=[DataRequired(), EqualTo('password')])

    # - SubmitField: odesílací tlačítko formuláře
    submit = SubmitField('Registrovat')


# - FORMULÁŘ PRO PŘIHLÁŠENÍ:
class LoginForm(FlaskForm):
    # - pro přihlášení stačí jen ověřit přítomnost dat (DataRequired)
    username = StringField('Uživatelské jméno', validators=[DataRequired()])
    password = PasswordField('Heslo', validators=[DataRequired()])

    # - BooleanField: klasické zaškrtávací políčko (checkbox)
    # - slouží pro nastavení trvalé cookie ("Remember me"), aby user zůstal přihlášen i po zavření prohlížeče
    remember = BooleanField('Zapamatovat si mě')

    submit = SubmitField('Přihlásit')
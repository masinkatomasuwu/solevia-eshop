# - hlavní konfigurační soubor aplikace
# - inicializace Flasku, databáze (SQLAlchemy) a přihlašování (LoginManager)

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

from .config import Config

# - vytvoření instance Flask aplikace
app = Flask(__name__)
# - tajný klíč pro zabezpečení session a flash zpráv
app.secret_key = '1234'
# - načtení konfigurace (připojení k DB, atd.) z externího souboru Config
app.config.from_object(Config)

# - inicializace SQLAlchemy (ORM pro práci s databází)
db = SQLAlchemy()
db.init_app(app)

# - nastavení správy přihlášených uživatelů
login_manager = LoginManager()
login_manager.init_app(app)
# - kam má Flask hodit uživatele, když se snaží jít někam bez přihlášení
login_manager.login_view = 'auth.login'

# - vlastní česká hláška pro nepouštěné uživatele (místo anglického defaultu)
login_manager.login_message = "Pro přístup k této stránce se prosím nejprve přihlaste."
# - kategorie zprávy (červený alert v Bootstrapu)
login_manager.login_message_category = "danger"

# - dynamické zjištění absolutní cesty k projektu (důležité pro nahrávání fotek)
basedir = os.path.abspath(os.path.dirname(__file__))

# - nastavení složky pro uploady: app/static/images
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'images')

# - import modelů (tabulek), aby o nich SQLAlchemy věděla při startu
from .models import User, Product, CartItem

# - registrace blueprintů (rozdělení aplikace na logické části: main, cart, auth, admin)
from .routes.main import main_bp
from .routes.cart import cart_bp
from .routes.auth import auth_bp
from .routes.admin import admin_bp

app.register_blueprint(main_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# - USER LOADER: funkce, která Flask-Loginu řekne, jak podle ID najít usera v DB
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# - CONTEXT PROCESSOR: tato funkce zpřístupní proměnnou 'pocet_v_kosiku' ve VŠECH šablonách
# - díky tomu můžeme mít v navbaru (base.html) stále aktuální číslo u ikony košíku
@app.context_processor
def kosik_context():
    pocet_v_kosiku = 0

    # - pokud je uživatel přihlášen, sečteme kusy z tabulky CartItem v databázi
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        # - SQL SUM nad sloupcem quantity pro daného uživatele
        pocet_v_kosiku = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=current_user.id).scalar() or 0
    else:
        # - pokud není přihlášen, řešíme košík přes 'session' (dočasná paměť prohlížeče)
        if 'kosik' in session:
            new_kosik = {}
            for key in list(session['kosik']):
                try:
                    pid = int(key)
                    quantity = session['kosik'][key]
                    # - kontrola, zda produkt stále existuje v DB
                    if db.session.get(Product, pid):
                        pocet_v_kosiku += quantity
                        new_kosik[pid] = quantity
                except (ValueError, TypeError):
                    continue

            # - vyčištění session od neplatných produktů
            session['kosik'] = new_kosik
            session.modified = True

    return dict(pocet_v_kosiku=pocet_v_kosiku)

# - automatické vytvoření tabulek v databázi při spuštění aplikace (pokud neexistují)
with app.app_context():
    db.create_all()

# - spuštění aplikace v debug módu (při chybě ukáže interaktivní konzoli)
if __name__ == '__main__':
    with app.app_context():
            db.create_all()  # ← pojistka pro vytvoření všech tabulek
    app.run(debug=True)
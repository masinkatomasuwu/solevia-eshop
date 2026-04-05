# - správa uživatelů: registrace, přihlašování, profil a zabezpečení
# - blueprint 'auth' pro logické oddělení autentizace od zbytku webu

import base64
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app import db
from app.models import User, Order, OrderItem, DiscountCode, CartItem
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

# - definice blueprintu pro routování pod prefixem auth
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # - pokud už je user přihlášený, hodí ho to na hlavní stranu
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # - hledání uživatele v DB podle jména
        user = User.query.filter_by(username=username).first()

        # - check_password: ověření hesla proti hashi v databázi (bezpečnost!)
        if user and user.check_password(password):
            login_user(user) # - vytvoření session pro uživatele
            flash('Přihlášení úspěšné!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Špatné uživatelské jméno nebo heslo.', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required # - odhlásit se může jen ten, kdo je přihlášen
def logout():
    logout_user() # - zrušení uživatelské session
    flash('Byl jsi odhlášen.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # - přihlášený uživatel se nemůže registrovat znova
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # - validace: kontrola prázdných polí
        if not username or not email or not password or not confirm_password:
            flash('Všechna pole jsou povinná.', 'danger')
            return redirect(url_for('auth.register'))

        # - validace: základní formát emailu
        if '@' not in email or '.' not in email.split('@')[-1] or len(email) < 5:
            flash('Zadejte platný email (např. jmeno@priklad.cz).', 'danger')
            return redirect(url_for('auth.register'))

        # - validace: shoda hesel
        if password != confirm_password:
            flash('Hesla se neshodují.', 'danger')
            return redirect(url_for('auth.register'))

        # - politika hesel: délka, velké písmeno a číslice (dobré pro maturitu zmínit)
        if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            flash('Heslo musí mít minimálně 8 znaků, velké písmeno a číslici.', 'danger')
            return redirect(url_for('auth.register'))

        # - kontrola unikátnosti: jméno a email nesmí být v DB dvakrát
        if User.query.filter_by(username=username).first():
            flash('Uživatelské jméno již existuje.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email již existuje.', 'danger')
            return redirect(url_for('auth.register'))

        # - vytvoření usera a set_password pro zahashování hesla před uložením
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registrace úspěšná! Teď se přihlaš.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/profil')
@login_required
def profile():
    # - načtení objednávek aktuálního uživatele, řazeno od nejnovějších
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profil.html', user=current_user, orders=orders)

@auth_bp.route('/objednavka/<int:order_id>')
@login_required
def order_detail(order_id):
    # - detail konkrétní objednávky, hlídá se, aby patřila přihlášenému userovi
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    items = OrderItem.query.filter_by(order_id=order_id).all()
    return render_template('objednavka_detail.html', order=order, items=items)

@auth_bp.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    # - změna údajů uživatele v profilu
    new_email = request.form.get('new_email')
    new_password = request.form.get('new_password')

    if new_email:
        current_user.email = new_email

    if new_password and len(new_password) >= 8:
        # - pokud se mění heslo, musí se znova zahashovat
        current_user.set_password(new_password)

    db.session.commit()
    flash('Vaše údaje byly úspěšně aktualizovány.', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    # - kompletní smazání účtu a všech souvisejících dat (košík, objednávky, kódy)
    user_id = current_user.id
    user_to_delete = db.session.get(User, user_id)

    try:
        # - kaskádové mazání: nejdřív musí pryč data navázaná na cizí klíče
        DiscountCode.query.filter_by(user_id=user_id).delete()
        CartItem.query.filter_by(user_id=user_id).delete()

        orders = Order.query.filter_by(user_id=user_id).all()
        for order in orders:
            OrderItem.query.filter_by(order_id=order.id).delete()

        Order.query.filter_by(user_id=user_id).delete()

        # - odhlášení a finální smazání usera z DB
        logout_user()
        db.session.delete(user_to_delete)
        db.session.commit()

        flash('Váš účet byl trvale odstraněn.', 'success')
        return redirect(url_for('main.index'))

    except Exception as e:
        # - pokud se něco podělá, rollback vrátí DB do původního stavu
        db.session.rollback()
        print(f"DEBUG CHYBA: {e}")
        flash('Při mazání účtu došlo k technické chybě.', 'danger')
        return redirect(url_for('auth.profile'))

# - seznam povolených přípon pro obrázky
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    # - pomocná funkce pro kontrolu přípony souboru
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@auth_bp.route('/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    # - zpracování profilovky z Cropper.js (přichází jako Base64 řetězec)
    cropped_data = request.form.get('cropped_image')

    if cropped_data:
        try:
            # - rozdělení Base64 hlavičky a samotných dat obrázku
            header, encoded = cropped_data.split(",", 1)
            data = base64.b64decode(encoded)

            # - název souboru fixně podle ID uživatele (přepisuje starou fotku)
            filename = f"user_{current_user.id}.jpg"

            # - cesta do složky profilovek přes root_path aplikace
            upload_path = os.path.join(current_app.root_path, 'static', 'profile_pics')

            # - pojistka: vytvoření složky, pokud neexistuje
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)

            # - uložení binárních dat jako fyzický soubor .jpg
            with open(os.path.join(upload_path, filename), "wb") as f:
                f.write(data)

            # - uložení jména souboru k uživateli v DB
            current_user.profile_pic = filename
            db.session.commit()

            flash('Profilovka byla úspěšně oříznuta a uložena!', 'success')

        except Exception as e:
            print(f"Chyba při zpracování avataru: {e}")
            flash('Chyba při zpracování obrázku.', 'danger')
    else:
        flash('Nebyla přijata žádná obrazová data z ořezu.', 'warning')

    return redirect(url_for('auth.profile'))
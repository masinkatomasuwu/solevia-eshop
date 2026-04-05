# - mozek pro správu eshopu, řeší CRUD operace (vytvořit, číst, upravit, smazat)
# - blueprint, drží admin funkce odděleně od zbytku aplikace pro lepší přehlednost

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import app, db
from app.models import Product
from werkzeug.utils import secure_filename
import os

# - registrace admin modulu pod jménem 'admin'
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin', methods=['GET', 'POST'])
@login_required  # - přístup povolen jen přihlášeným
def admin():
    # - kontrola admin práv v DB, nepovolané to hned vykopne na index
    if not current_user.is_admin:
        flash('Nemáš oprávnění.', 'danger')
        return redirect(url_for('main.index'))

    # - získání textu z vyhledávacího pole (parametr q v URL)
    search_query = request.args.get('q', '')

    # - 'ilike' vyhledávání: ignoruje velká/malá písmena, % jsou zástupné znaky
    if search_query:
        produkty = Product.query.filter(Product.name.ilike(f'%{search_query}%')).all()
    else:
        produkty = Product.query.all()

    # - blok pro přidání nového produktu (Create)
    if request.method == 'POST' and 'add' in request.form:
        name = request.form.get('name')
        description = request.form.get('description')

        # - validace: cena a sklad musí být čísla, jinak try-except zachytí chybu a web nespadne
        try:
            price = float(request.form.get('price'))
            stock = int(request.form.get('stock'))
        except (ValueError, TypeError):
            flash('Cena a sklad musí být čísla.', 'danger')
            return redirect(url_for('admin.admin'))

        # - ošetření uploadu fotky
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                # - secure_filename: vyčistí název souboru od nebezpečných znaků (hack cesty)
                filename = secure_filename(file.filename)
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(full_path)  # - uložení souboru na disk
                image_path = 'images/' + filename  # - cesta pro DB

        # - vytvoření objektu a fyzický zápis do SQL tabulky přes commit
        new_product = Product(name=name, description=description, price=price, image=image_path, stock=stock)
        db.session.add(new_product)
        db.session.commit()
        flash('Produkt přidán!', 'success')
        return redirect(url_for('admin.admin'))

    # - smazání produktu z DB (Delete) přes ID z hidden fieldu
    if request.method == 'POST' and 'delete' in request.form:
        product_id = request.form.get('product_id')
        product = db.session.get(Product, product_id)
        if product:
            db.session.delete(product)
            db.session.commit()
            flash('Produkt smazán!', 'success')
            return redirect(url_for('admin.admin'))

    # - vykreslení admin panelu se seznamem bot
    return render_template('admin.html', produkty=produkty, search_query=search_query)


@admin_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    # - pojistka proti přímému přístupu přes URL
    if not current_user.is_admin:
        flash('Nemáš oprávnění.', 'danger')
        return redirect(url_for('main.index'))

    # - najde produkt podle ID, pokud neexistuje, hodí automaticky 404 chybu
    product = Product.query.get_or_404(id)

    # - úprava existujících dat (Update)
    if request.method == 'POST':
        product.name = request.form.get('name', product.name)
        product.description = request.form.get('description', product.description)
        product.stock = int(request.form.get('stock', product.stock))

        try:
            product.price = float(request.form.get('price', product.price))
        except (ValueError, TypeError):
            flash('Cena musí být číslo.', 'danger')
            return redirect(url_for('admin.edit_product', id=id))

        # - přepsání fotky v DB, pokud se nahrává nová
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(full_path)
                product.image = 'images/' + filename

        # - SQLAlchemy automaticky pozná změny na objektu, stačí commitnout
        db.session.commit()
        flash('Produkt upraven!', 'success')
        return redirect(url_for('admin.admin'))

    # - zobrazení formuláře s už načtenými daty k editaci
    return render_template('edit_product.html', product=product)
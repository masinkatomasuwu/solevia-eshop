# - hlavní modul aplikace: řeší úvodní stránku, katalog produktů a filtrování
# - blueprint 'main' pro základní uživatelské rozhraní a informační stránky

import datetime

from flask import Blueprint, render_template, request, session, jsonify, flash, redirect, url_for
from flask_login import current_user

from app import app, db
from app.routes.cart import cart_bp
from app.models import Product, DiscountCode
from sqlalchemy import text

# - vytvoření hlavního blueprintu
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # - kontrola připojení k DB přímo na úvodní straně (dobré pro debugování)
    db_status = "❌ Nepřipojeno k DB"
    products_count = "Nenačteno"

    try:
        # - spuštění čistého SQL dotazu pro ověření jména databáze
        result = db.session.execute(text("SELECT DATABASE()")).scalar()
        db_status = f"✅ Připojeno k: {result}"

        # - rychlý dotaz na celkový počet záznamů v tabulce produktů
        count = Product.query.count()
        products_count = f"V databázi je {count} produktů."
    except Exception as e:
        # - zachycení chyby, pokud např. neběží MySQL server
        db_status = f"❌ Chyba: {str(e)}"
        products_count = "Nelze načíst produkty"

    return render_template('index.html', db_status=db_status, products_count=products_count)

@cart_bp.route('/minihra')
def minihra():
    # - ochrana: hrát a vyhrát slevu můžou jen přihlášení
    if not current_user.is_authenticated:
        flash('Přihlaš se, abys mohl hrát!', 'warning')
        return redirect(url_for('auth.login'))

    # - kontrola příznaku 'used_minigame_discount', aby uživatel nehrál do nekonečna
    if current_user.used_minigame_discount:
        flash('Slevu z minihry jsi už využil/a. Můžeš ji použít jen jednou.', 'info')
        return redirect(url_for('main.index'))

    return render_template('minihra.html')


@main_bp.route('/boty')
def boty():
    # --- ZPRACOVÁNÍ PARAMETRŮ ---
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    in_stock = request.args.get('in_stock', type=int)
    # Parametr pro akci (např. z checkboxu)
    on_sale = request.args.get('on_sale', type=int)

    # --- ZÁKLADNÍ DOTAZ ---
    query = Product.query

    # --- DYNAMICKÉ FILTROVÁNÍ ---
    if q:
        query = query.filter(Product.name.contains(q) | Product.description.contains(q))

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if in_stock:
        query = query.filter(Product.stock > 0)

    # FILTR NA AKCI: boty v akci jsou ty, co mají slevu větší než 0 %
    if on_sale:
        query = query.filter(Product.discount_percent > 0)

    # --- PAGINACE ---
    pagination = query.order_by(Product.id.desc()).paginate(page=page, per_page=9, error_out=False)
    produkty = pagination.items

    return render_template('boty.html',
                           produkty=produkty,
                           pagination=pagination,
                           search_query=q,
                           min_price=min_price,
                           max_price=max_price,
                           in_stock=in_stock,
                           on_sale=on_sale)

@main_bp.route('/produkt/<int:id>')
def produkt_detail(id):
    # - zobrazení podrobností o jedné botě
    # - get_or_404 zajistí, že při neexistujícím ID nespadne web, ale ukáže se chyba 404
    produkt = Product.query.get_or_404(id)
    return render_template('product_detail.html', produkt=produkt)

@main_bp.route('/o-nas')
def o_nas():
    # - statická stránka s informacemi o firmě
    return render_template('o-nas.html')
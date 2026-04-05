# - kompletní správa nákupního košíku, dopravy, plateb a generování objednávek
# - obsahuje také logiku pro slevové kódy a propojení s generátorem PDF faktur

import random
import string
from datetime import datetime as dt, timedelta
from decimal import Decimal
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import Product, CartItem, Order, OrderItem, DiscountCode
from app.utils import generate_invoice_pdf

# - registrace blueprintu pod názvem 'cart'
cart_bp = Blueprint('cart', __name__)


# --- PŘIDAT DO KOŠÍKU ---
@cart_bp.route('/pridat-do-kosiku/<int:produkt_id>')
@login_required  # - nakupovat můžou jen přihlášení uživatelé
def pridat_do_kosiku(produkt_id):
    produkt = Product.query.get_or_404(produkt_id)
    # - kontrola, jestli už uživatel tuhle botu v košíku má
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=produkt_id).first()

    if cart_item:
        # - pokud ano, jen navýším množství
        cart_item.quantity += 1
    else:
        # - pokud ne, vytvořím nový záznam v tabulce CartItem
        cart_item = CartItem(user_id=current_user.id, product_id=produkt_id, quantity=1)
        db.session.add(cart_item)

    db.session.commit()
    flash('Produkt přidán do košíku!', 'success')
    # - request.referrer nás vrátí tam, odkud jsme přišli (třeba z detailu produktu)
    return redirect(request.referrer or url_for('cart.kosik'))


# --- ODEBRAT Z KOŠÍKU ---
@cart_bp.route('/odebrat-z-kosiku/<int:produkt_id>')
@login_required
def odebrat_z_kosiku(produkt_id):
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=produkt_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash('Produkt byl odebrán z košíku.', 'info')
    return redirect(url_for('cart.kosik'))


# --- VYPRÁZDNIT KOŠÍK ---
@cart_bp.route('/vyprazdnit-kosik')
@login_required
def clear_cart():
    # - smaže všechny položky v košíku pro daného uživatele
    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    # - vymaže slevy ze session, aby nebyly aktivní pro prázdný košík
    session.pop('discount_code', None)
    session.pop('discount_percent', None)
    flash('Košík byl vyprázdněn.', 'info')
    return redirect(url_for('cart.kosik'))


# --- DOPRAVA A ADRESA ---
@cart_bp.route('/doprava', methods=['GET', 'POST'])
@login_required
def doprava():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash('Váš košík je prázdný.', 'warning')
        return redirect(url_for('main.boty'))

    if request.method == 'POST':
        # - sběr dat o doručení z formuláře
        shipping_data = {
            'jmeno': request.form.get('jmeno'),
            'prijmeni': request.form.get('prijmeni'),
            'telefon': request.form.get('telefon'),
            'ulice': request.form.get('ulice'),
            'mesto': request.form.get('mesto'),
            'psc': request.form.get('psc'),
            'metoda_dopravy': request.form.get('doprava')
        }
        # - uložení adresy do session (mezipaměť prohlížeče) pro další krok (platba)
        session['order_shipping_info'] = shipping_data
        return redirect(url_for('cart.platba'))

    return render_template('doprava.html')


# --- VÝPIS KOŠÍKU ---
@cart_bp.route('/kosik', methods=['GET', 'POST'])
@login_required
def kosik():
    discount_percent = 0
    if request.method == 'POST':
        # - logika pro uplatnění slevového kódu
        if 'apply_discount' in request.form:
            code = request.form.get('discount_code', '').strip().upper()
            discount = DiscountCode.query.filter_by(code=code, user_id=current_user.id, used=False).first()
            if discount:
                session['discount_code'] = code
                session['discount_percent'] = discount.discount_percent
                flash(f'Sleva {discount.discount_percent}% byla uplatněna!', 'success')
            else:
                flash('Neplatný nebo již použitý kód.', 'danger')
            return redirect(url_for('cart.kosik'))

        # - aktualizace množství bot přímo v košíku
        if 'update_quantity' in request.form:
            p_id = request.form.get('produkt_id')
            qty = int(request.form.get('quantity', 0))
            item = CartItem.query.filter_by(user_id=current_user.id, product_id=p_id).first()
            if item:
                if qty > 0:
                    item.quantity = qty
                else:
                    db.session.delete(item)  # - pokud je množství 0, smažu to úplně
                db.session.commit()
            return redirect(url_for('cart.kosik'))

    # - kontrola, jestli slevový kód v session pořád platí (např. nebyl mezitím smazán z DB)
    if 'discount_code' in session:
        check_discount = DiscountCode.query.filter_by(code=session['discount_code'], user_id=current_user.id,
                                                      used=False).first()
        if check_discount:
            discount_percent = session.get('discount_percent', 0)
        else:
            session.pop('discount_code', None)
            session.pop('discount_percent', None)

    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    # - výpočet mezisoučtu (subtotal) pomocí Decimal pro přesné peněžní operace
    subtotal = sum(Decimal(str(item.total_price)) for item in cart_items)
    discount_amount = subtotal * (Decimal(str(discount_percent)) / Decimal('100'))
    final_price = subtotal - discount_amount

    return render_template('kosik.html', kosik_produkty=cart_items, celkova_cena=final_price,
                           discount_amount=discount_amount, discount_percent=discount_percent)


# --- PLATBA ---
@cart_bp.route('/platba')
@login_required
def platba():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    shipping = session.get('order_shipping_info')

    # - Kontrola, zda máme košík i info o dopravě
    if not cart_items or not shipping:
        flash('Chybí údaje o dopravě nebo je košík prázdný.', 'warning')
        return redirect(url_for('cart.kosik'))

    # 1. Výpočet ceny za samotné produkty
    subtotal = sum(Decimal(str(item.total_price)) for item in cart_items)

    # 2. Načtení slevy (pokud existuje)
    d_p = session.get('discount_percent', 0) if 'discount_code' in session else 0
    # Výpočet ceny po slevě (bez dopravy)
    price_after_discount = subtotal - (subtotal * (Decimal(str(d_p)) / Decimal('100')))

    # 3. LOGIKA DOPRAVY - Tady byla chyba!
    # Musíme zajistit, aby se s_price přičetlo k výsledku
    metoda = shipping.get('metoda_dopravy', 'PPL')
    if metoda == 'PPL':
        s_price = Decimal('99.00')
    else:
        s_price = Decimal('69.00')

    # 4. FINÁLNÍ SOUČET (Produkty po slevě + Doprava)
    # Tato proměnná MUSÍ obsahovat obě složky
    total_with_shipping = price_after_discount + s_price

    # - Důležité: do šablony posíláme total_with_shipping pod názvem 'celkova_cena'
    return render_template('platba.html', celkova_cena=total_with_shipping)






# --- ZAPLATIT (Vytvoření objednávky) ---
@cart_bp.route('/zaplatit', methods=['POST'])
@login_required
def zaplatit():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    shipping = session.get('order_shipping_info')
    if not cart_items or not shipping: return redirect(url_for('cart.kosik'))

    # - výpočet mezisoučtu produktů
    subtotal = sum(Decimal(str(item.total_price)) for item in cart_items)

    # - VÝPOČET CENY DOPRAVY (Nová logika)
    s_name = shipping.get('metoda_dopravy', 'PPL')
    s_price = Decimal('99.00') if s_name == 'PPL' else Decimal('69.00')

    discount_p = 0
    discount_code_val = None

    if 'discount_code' in session:
        d_code_obj = DiscountCode.query.filter_by(code=session['discount_code'], user_id=current_user.id,
                                                  used=False).first()
        if d_code_obj:
            discount_p = d_code_obj.discount_percent
            discount_code_val = d_code_obj.code
            d_code_obj.used = True

            # - FINÁLNÍ VÝPOČET: (Produkty - Sleva) + Doprava
    discount_amount = subtotal * (Decimal(str(discount_p)) / Decimal('100'))
    final_total = (subtotal - discount_amount) + s_price

    # - vytvoření záznamu v tabulce Order (přidána doprava)
    order = Order(
        user_id=current_user.id,
        total_price=final_total,
        shipping_name=s_name,  # - Uložení názvu dopravy
        shipping_price=s_price,  # - Uložení ceny dopravy
        jmeno=shipping['jmeno'], prijmeni=shipping['prijmeni'],
        telefon=shipping['telefon'], ulice=shipping['ulice'],
        mesto=shipping['mesto'], psc=shipping['psc'],
        discount_percent_used=discount_p,
        discount_code_used=discount_code_val
    )
    db.session.add(order)
    db.session.flush()  # - získáme ID objednávky před finálním commitem

    # - převod položek z košíku do položek objednávky (OrderItem)
    items_for_pdf = []
    for item in cart_items:
        price_fix = item.product.final_price
        oi = OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity, price=price_fix)
        db.session.add(oi)
        items_for_pdf.append({'produkt': item.product, 'quantity': item.quantity, 'celkem': item.quantity * price_fix})
        # - odečtení kusů ze skladu (stock management)
        item.product.stock = max(0, item.product.stock - item.quantity)

    # - vyčištění košíku po úspěšném nákupu
    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    # - generování faktury pomocí externí funkce z utils.py
    pdf_path = generate_invoice_pdf(order, current_user, items_for_pdf)
    if pdf_path: session['last_invoice_path'] = pdf_path

    # - úklid session (smazání dočasných dat)
    session.pop('discount_code', None)
    session.pop('discount_percent', None)
    session.pop('order_shipping_info', None)

    flash('Objednávka vytvořena!', 'success')
    return redirect(url_for('cart.potvrzeni'))


# --- POTVRZENÍ OBJEDNÁVKY ---
@cart_bp.route('/potvrzeni')
@login_required
def potvrzeni():
    # - zobrazení děkovné stránky s odkazem na fakturu
    pdf_path = session.get('last_invoice_path')
    return render_template('potvrzeni.html', pdf_path=pdf_path)


# --- STÁHNOUT FAKTURU ---
@cart_bp.route('/stahnout-fakturu/<int:order_id>')
@login_required
def stahnout_fakturu(order_id):
    # - umožní uživateli kdykoliv stáhnout fakturu z profilu
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    items = OrderItem.query.filter_by(order_id=order.id).all()
    items_list = [{'produkt': it.product, 'quantity': it.quantity, 'celkem': it.quantity * it.price} for it in items]

    pdf_path = generate_invoice_pdf(order, current_user, items_list)
    if pdf_path: return redirect(url_for('static', filename=pdf_path))
    return redirect(url_for('auth.profile'))


# --- MINIHRA (Získání slevy) ---
@cart_bp.route('/save-discount', methods=['POST'])
@login_required
def save_discount():
    # - AJAX endpoint pro uložení slevy po vyhrané minihře
    if current_user.used_minigame_discount: return jsonify({'success': False, 'message': 'Už jsi slevu vyhrál.'}), 400
    try:
        # - vygenerování náhodného 6místného kódu
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        new_discount = DiscountCode(code=code, user_id=current_user.id, discount_percent=10,
                                    expires_at=dt.utcnow() + timedelta(hours=24))
        current_user.used_minigame_discount = True  # - zajistí, že user může vyhrát jen jednou
        db.session.add(new_discount)
        db.session.commit()
        return jsonify({'success': True, 'code': code})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
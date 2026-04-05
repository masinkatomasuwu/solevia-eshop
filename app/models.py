# - modely databáze: definice tabulek a jejich vzájemných vztahů (relací) pomocí SQLAlchemy ORM
from datetime import datetime as dt, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db
from decimal import Decimal

# --- TABULKA UŽIVATELŮ ---
class User(db.Model, UserMixin):
    __tablename__ = 'student20_users' # - název tabulky v MySQL
    id = db.Column(db.Integer, primary_key=True) # - unikátní identifikátor (Primární klíč)
    username = db.Column(db.String(100), unique=True, nullable=False) # - unikátní jméno, nesmí být prázdné
    password = db.Column(db.String(255), nullable=False) # - hashované heslo (nikdy neukládáme v čistém textu!)
    email = db.Column(db.String(150))
    is_admin = db.Column(db.Boolean, default=False) # - rozlišení běžného uživatele a admina
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    used_minigame_discount = db.Column(db.Boolean, default=False, nullable=False) # - příznak, zda už user vyhrál slevu
    profile_pic = db.Column(db.String(100), nullable=False, default='default.png')

    # --- RELACE (Vztahy) ---
    # - db.relationship definuje logickou vazbu v Pythonu (není to sloupec v DB, ale cesta k datům)
    # - cascade="all, delete-orphan" zajišťuje, že se smažou i věci v košíku a objednávky, když smažeme uživatele
    cart_items_rel = db.relationship('CartItem', backref='owner', cascade="all, delete-orphan", passive_deletes=True)
    orders_rel = db.relationship('Order', backref='customer', cascade="all, delete-orphan", passive_deletes=True)
    discount_codes_rel = db.relationship('DiscountCode', backref='owner', cascade="all, delete-orphan", passive_deletes=True)

    # - metody pro bezpečné zahashování a ověření hesla
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


# --- TABULKA PRODUKTŮ (BOTY) ---
class Product(db.Model):
    __tablename__ = 'student20_products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    # - Numeric(10, 2): přesné desetinné číslo (10 číslic celkem, 2 za čárkou) - ideální pro peníze
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image = db.Column(db.String(255)) # - cesta k souboru s fotkou
    stock = db.Column(db.Integer, default=0) # - stav skladu
    discount_percent = db.Column(db.Integer, default=0) # - procentuální sleva

    # - @property (hybridní vlastnost): vypočítá cenu po slevě přímo v objektu
    @property
    def final_price(self):
        if self.discount_percent and self.discount_percent > 0:
            p = Decimal(str(self.price))
            d = Decimal(str(self.discount_percent))
            # - výpočet ceny: cena * (100 - sleva) / 100
            return p * (Decimal('100') - d) / Decimal('100')
        return self.price


# --- POLOŽKA V KOŠÍKU (Dočasná tabulka) ---
class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    # - Cizí klíč (ForeignKey): propojení položky s konkrétním uživatelem přes jeho ID
    user_id = db.Column(db.Integer, db.ForeignKey('student20_users.id', ondelete='CASCADE'), nullable=False)
    # - Cizí klíč: propojení s konkrétním produktem
    product_id = db.Column(db.Integer, db.ForeignKey('student20_products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    # - přístup k celému objektu produktu přes položku v košíku
    product = db.relationship('Product', backref='in_carts')

    @property
    def total_price(self):
        # - výpočet mezisoučtu za položku (množství * aktuální cena produktu)
        return self.quantity * self.product.final_price


# --- HLAVIČKA OBJEDNÁVKY ---
class Order(db.Model):
    __tablename__ = 'student20_orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('student20_users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='paid')

    # ÚDAJE O ADRESE
    jmeno = db.Column(db.String(100))
    prijmeni = db.Column(db.String(100))
    telefon = db.Column(db.String(20))
    ulice = db.Column(db.String(200))
    mesto = db.Column(db.String(100))
    psc = db.Column(db.String(10))

    # NOVÉ SLOUPCE PRO DOPRAVU
    shipping_name = db.Column(db.String(50))  # - Název dopravy (PPL / Zasilkovna)
    shipping_price = db.Column(db.Numeric(10, 2), default=0)  # - Cena dopravy uložená v DB

    discount_percent_used = db.Column(db.Integer, default=0)
    discount_code_used = db.Column(db.String(20), nullable=True)

    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan", passive_deletes=True)

# --- JEDNOTLIVÉ POLOŽKY OBJEDNÁVKY ---
# - tabulka slouží k archivaci: i když se produkt v budoucnu smaže nebo změní cenu, v objednávce zůstane tato cena fixní
class OrderItem(db.Model):
    __tablename__ = 'student20_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('student20_orders.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('student20_products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False) # - cena v době zakoupení

    product = db.relationship('Product', backref='order_items_ref', lazy=True)


# --- TABULKA SLEVOVÝCH KÓDŮ ---
class DiscountCode(db.Model):
    __tablename__ = 'discount_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False) # - vygenerovaný řetězec (např. ABC123)
    user_id = db.Column(db.Integer, db.ForeignKey('student20_users.id', ondelete='CASCADE'), nullable=False)
    discount_percent = db.Column(db.Integer, default=10)
    # - expirace: kód platí jen 24 hodin od vygenerování v minihře
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    used = db.Column(db.Boolean, default=False) # - ochrana proti vícenásobnému použití kódu
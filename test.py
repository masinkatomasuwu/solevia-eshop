# - automatizované unit testy pro ověření klíčových funkcí e-shopu Solevia
# - využívá knihovnu unittest a testovacího klienta Flasku

import unittest
import os
from app import app, db
from app.models import User, Product, CartItem


class SoleviaTesty(unittest.TestCase):

    # --- PŘÍPRAVA PROSTŘEDÍ (Setup) ---
    def setUp(self):
        """Příprava před každým testem: Izolace prostředí."""
        # - TESTING: zapne speciální režim Flasku pro odchytávání chyb
        app.config['TESTING'] = True
        # - CSRF: vypneme ochranu formulářů, aby testy mohly simulovat POST požadavky bez tokenů
        app.config['WTF_CSRF_ENABLED'] = False

        # - IZOLACE DATABÁZE: testy běží v lokální SQLite databázi (soubor .db)
        # - díky tomu testování neovlivní reálná data na školním MySQL serveru
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_database.db'

        # - test_client: simulovaný prohlížeč, který umí "klikat" na URL adresy
        self.app = app.test_client()

        with app.app_context():
            # - vytvoření prázdných tabulek v testovací databázi
            db.create_all()

    # --- ÚKLID PO TESTECH (Teardown) ---
    def tearDown(self):
        """Chirurgický úklid: Smaže pouze to, co jsme v testu vytvořili."""
        with app.app_context():
            db.session.rollback()

            # - seznamy jmen, která jsme v testech použili, abychom je po sobě smazali
            test_usernames = ['Tester_Novy', 'Test_User', 'Nakupci', 'Testovac', 'Lukas', 'Kupujici']
            test_products = ['Testovaci_Bota', 'TestBota']

            # - pročištění DB, aby byl další testovací běh v "čistém" stavu
            User.query.filter(User.username.in_(test_usernames)).delete(synchronize_session=False)
            Product.query.filter(Product.name.in_(test_products)).delete(synchronize_session=False)
            CartItem.query.delete()

            db.session.commit()
            db.session.remove()

    # --- TEST 1: REGISTRACE ---
    def test_registrace(self):
        print("\nSpouštím TEST: Registrace uživatele...")
        # - simulace odeslání registračního formuláře (POST požadavek)
        response = self.app.post('/register', data={
            'username': 'Tester_Novy',
            'email': 'tester@solevia.cz',
            'password': 'Heslo1234',
            'confirm_password': 'Heslo1234'
        }, follow_redirects=True)  # - automaticky následuje přesměrování (např. na login)

        # - assertEqual: ověření, že HTTP kód je 200 (OK)
        self.assertEqual(response.status_code, 200)
        with app.app_context():
            # - kontrola v DB, zda uživatel skutečně existuje
            user = User.query.filter_by(username='Tester_Novy').first()
            self.assertIsNotNone(user)
        print("VÝSLEDEK: OK (Tester_Novy vytvořen)")

    # --- TEST 2: PŘIHLÁŠENÍ ---
    def test_login(self):
        print("\nSpouštím TEST: Přihlášení uživatele...")
        with app.app_context():
            # - manuální vytvoření uživatele přímo v DB pro potřeby testu
            u = User(username='Test_User', email='test@seznam.cz')
            u.set_password('Heslo1234')
            db.session.add(u)
            db.session.commit()

        # - simulace pokusu o přihlášení
        response = self.app.post('/login', data={
            'username': 'Test_User',
            'password': 'Heslo1234'
        }, follow_redirects=True)

        # - assertIn: kontrola, zda se v HTML kódu stránky po přihlášení objeví jméno uživatele
        self.assertIn(b'Test_User', response.data)
        print("VÝSLEDEK: OK (Test_User přihlášen)")

    # --- TEST 3: KOŠÍK ---
    def test_kosik_pridani(self):
        print("\nSpouštím TEST: Přidání do košíku...")
        with app.app_context():
            # - příprava testovacího produktu a uživatele
            p = Product(
                name='Testovaci_Bota',
                price=1000,
                stock=5,
                description='Testovací popis produktu pro ověření funkčnosti košíku.'
            )
            u = User(username='Nakupci', email='nakup@email.cz')
            u.set_password('Heslo1234')
            db.session.add_all([p, u])
            db.session.commit()
            p_id = p.id

        # - nejdřív se přihlásíme
        self.app.post('/login', data={'username': 'Nakupci', 'password': 'Heslo1234'})

        # - zavoláme routu pro přidání do košíku
        response = self.app.get(f'/pridat-do-kosiku/{p_id}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # - ověření, že se v HTML objevila flash zpráva "přidán" (ověřujeme binární řetězec v UTF-8)
        self.assertIn(b'p\xc5\x99id\xc3\xa1n', response.data)
        print("VÝSLEDEK: OK (Produkt detekován v košíku)")


# - spuštění testovacího skriptu z terminálu
if __name__ == '__main__':
    unittest.main()
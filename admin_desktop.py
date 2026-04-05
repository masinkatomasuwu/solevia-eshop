# - desktopová administrativní aplikace pro e-shop Solevia
# - vytvořeno pomocí knihovny PyQt6 (GUI) a mysql-connector (DB)

import sys
import os
import shutil
import mysql.connector
from mysql.connector import Error
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLineEdit, QLabel,
    QMessageBox, QFileDialog, QTextEdit, QSpinBox, QDoubleSpinBox,
    QDialog, QFormLayout, QCheckBox
)
from PyQt6.QtCore import Qt
from werkzeug.security import generate_password_hash

# --- KONFIGURACE DATABÁZE ---
DB_CONFIG = {
    'host': 'dbs.spskladno.cz',
    'database': 'vyuka20',
    'user': 'student20',
    'password': 'spsnet'
}


# - funkce pro vytvoření spojení s MySQL serverem
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        QMessageBox.critical(None, "Chyba", f"DB nepřipojeno:\n{e}")
        return None


# --- DIALOG PRO PRODUKTY (Add/Edit) ---
# - QDialog je vyskakovací okno, které "zmrazí" hlavní okno, dokud se neuzavře
class ProductDialog(QDialog):
    def __init__(self, parent=None, product_id=None):
        super().__init__(parent)
        self.product_id = product_id  # - pokud ID existuje, jsme v režimu úprav (Edit)
        self.setWindowTitle("Přidat produkt" if product_id is None else "Upravit produkt")
        self.setFixedSize(550, 600)

        # - QFormLayout: ideální pro formuláře (vlevo popisek, vpravo vstupní pole)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.name_edit = QLineEdit()
        layout.addRow("Název *", self.name_edit)

        self.desc_edit = QTextEdit()
        layout.addRow("Popis", self.desc_edit)

        # - QDoubleSpinBox: číselný vstup pro desetinná čísla (Kč)
        self.price_edit = QDoubleSpinBox()
        self.price_edit.setRange(0, 999999)
        self.price_edit.setDecimals(2)
        self.price_edit.setSuffix(" Kč")
        layout.addRow("Cena *", self.price_edit)

        # - QSpinBox: číselný vstup pro celá čísla (procenta, kusy)
        self.discount_edit = QSpinBox()
        self.discount_edit.setRange(0, 99)
        self.discount_edit.setSuffix(" %")
        layout.addRow("Sleva (procenta)", self.discount_edit)

        self.stock_edit = QSpinBox()
        self.stock_edit.setRange(0, 999999)
        layout.addRow("Skladem *", self.stock_edit)

        self.photo_path = ""  # - cesta k souboru v počítači
        self.photo_label = QLabel("Fotka: žádná")
        layout.addRow(self.photo_label)

        photo_btn = QPushButton("Vybrat fotku")
        # - propojení kliknutí na tlačítko s funkcí (Signal & Slot)
        photo_btn.clicked.connect(self.select_photo)
        layout.addRow(photo_btn)

        save_btn = QPushButton("Uložit")
        save_btn.clicked.connect(self.save)
        layout.addRow(save_btn)

        self.setLayout(layout)
        if product_id:
            self.load_product()  # - pokud upravujeme, načteme data z DB

    # - funkce pro otevření systémového okna pro výběr souboru
    def select_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Vybrat fotku", "", "Obrázky (*.jpg *.jpeg *.png)")
        if file_path:
            self.photo_path = file_path
            self.photo_label.setText(f"Fotka: {os.path.basename(file_path)}")

    # - načtení existujících dat produktu do formuláře
    def load_product(self):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT name, description, price, stock, image, discount_percent FROM student20_products WHERE id = %s",
                (self.product_id,))
            product = cursor.fetchone()
            cursor.close()
            conn.close()
            if product:
                self.name_edit.setText(product['name'])
                self.desc_edit.setPlainText(product['description'] or '')
                self.price_edit.setValue(float(product['price']))
                self.discount_edit.setValue(int(product['discount_percent'] or 0))
                self.stock_edit.setValue(int(product['stock']))
                self.photo_label.setText(f"Aktuální: {product['image'] or 'žádná'}")

    # - validace a uložení dat do databáze (INSERT / UPDATE)
    def save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Chyba", "Název je povinný!")
            return

        # - LOGIKA NAHRÁVÁNÍ FOTEK:
        # - bota se vybere v PC -> zkopíruje se do složky 'static/images' webové aplikace
        db_image = None
        if self.photo_path:
            filename = os.path.basename(self.photo_path)
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dest_dir = os.path.join(BASE_DIR, 'app', 'static', 'images')
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, filename)
            try:
                shutil.copy(self.photo_path, dest)
                db_image = "images/" + filename
            except Exception as e:
                QMessageBox.warning(self, "Chyba", f"Nepodařilo se zkopírovat fotku:\n{e}")
                return

        conn = get_db_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            if self.product_id:  # - REŽIM UPDATE
                if db_image:
                    cursor.execute("""
                        UPDATE student20_products SET name = %s, description = %s, price = %s, stock = %s, image = %s, discount_percent = %s WHERE id = %s
                    """, (name, self.desc_edit.toPlainText().strip(), self.price_edit.value(), self.stock_edit.value(),
                          db_image, self.discount_edit.value(), self.product_id))
                else:
                    cursor.execute("""
                        UPDATE student20_products SET name = %s, description = %s, price = %s, stock = %s, discount_percent = %s WHERE id = %s
                    """, (name, self.desc_edit.toPlainText().strip(), self.price_edit.value(), self.stock_edit.value(),
                          self.discount_edit.value(), self.product_id))
            else:  # - REŽIM INSERT
                cursor.execute("""
                    INSERT INTO student20_products (name, description, price, stock, image, discount_percent) VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, self.desc_edit.toPlainText().strip(), self.price_edit.value(), self.stock_edit.value(),
                      db_image, self.discount_edit.value()))

            conn.commit()
            QMessageBox.information(self, "Úspěch", "Produkt uložen!")
            self.accept()  # - zavře dialog a vrátí výsledek 'Accepted'
        except Error as e:
            QMessageBox.critical(self, "Chyba", f"Chyba při ukládání:\n{e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()


# --- DIALOG PRO UŽIVATELE ---
class UserDialog(QDialog):
    def __init__(self, parent=None, user_id=None):
        super().__init__(parent)
        self.user_id = user_id
        self.setWindowTitle("Přidat uživatele" if user_id is None else "Upravit uživatele")
        self.setFixedSize(450, 400)

        layout = QFormLayout()

        self.username_edit = QLineEdit()
        layout.addRow("Uživatelské jméno *", self.username_edit)

        self.password_edit = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        layout.addRow("Heslo *" if user_id is None else "Nové heslo (prázdné = bez změny)", self.password_edit)

        self.email_edit = QLineEdit()
        layout.addRow("Email", self.email_edit)

        self.is_admin_check = QCheckBox("Je admin")
        layout.addRow(self.is_admin_check)

        save_btn = QPushButton("Uložit")
        save_btn.clicked.connect(self.save)
        layout.addRow(save_btn)

        self.setLayout(layout)
        if user_id:
            self.load_user()

    def load_user(self):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT username, email, is_admin FROM student20_users WHERE id = %s", (self.user_id,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            if user:
                self.username_edit.setText(user['username'])
                self.email_edit.setText(user['email'] or '')
                self.is_admin_check.setChecked(bool(user['is_admin']))

    def save(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        email = self.email_edit.text().strip()
        is_admin = 1 if self.is_admin_check.isChecked() else 0

        if not username:
            QMessageBox.warning(self, "Chyba", "Uživatelské jméno je povinné!")
            return

        # - KOMPATIBILITA S WEBOVOU APLIKACÍ:
        # - Hesla musíme i zde hashovat pomocí Werkzeug, jinak se uživatel na webu nepřihlásí!
        if self.user_id is None and (
                not password or len(password) < 8 or not any(c.isupper() for c in password) or not any(
                c.isdigit() for c in password)):
            QMessageBox.warning(self, "Chyba hesla", "Heslo musí mít min. 8 znaků, velké písmeno a číslici!")
            return

        conn = get_db_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            if self.user_id is None:  # - Nový uživatel
                cursor.execute("SELECT id FROM student20_users WHERE username = %s", (username,))
                if cursor.fetchone():
                    QMessageBox.warning(self, "Chyba", "Uživatelské jméno již existuje!")
                    return

                hashed_pw = generate_password_hash(password)
                cursor.execute("""
                    INSERT INTO student20_users (username, password, email, is_admin) VALUES (%s, %s, %s, %s)
                """, (username, hashed_pw, email, is_admin))
            else:  # - Úprava existujícího
                if password:  # - měníme heslo
                    hashed_pw = generate_password_hash(password)
                    cursor.execute("""
                        UPDATE student20_users SET username = %s, password = %s, email = %s, is_admin = %s WHERE id = %s
                    """, (username, hashed_pw, email, is_admin, self.user_id))
                else:  # - heslo neměníme
                    cursor.execute("""
                        UPDATE student20_users SET username = %s, email = %s, is_admin = %s WHERE id = %s
                    """, (username, email, is_admin, self.user_id))

            conn.commit()
            QMessageBox.information(self, "Úspěch", "Uživatel uložen!")
            self.accept()
        except Error as e:
            QMessageBox.critical(self, "Chyba", f"Nepodařilo se uložit:\n{e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()


# --- HLAVNÍ OKNO APLIKACE ---
class AdminApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin – Solevia Desktop")
        self.setGeometry(100, 100, 1100, 700)

        # - QTabWidget: umožňuje přepínání mezi kartami (Produkty / Uživatelé)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_products = QWidget()
        self.tabs.addTab(self.tab_products, "Produkty")

        self.tab_users = QWidget()
        self.tabs.addTab(self.tab_users, "Uživatelé")

        # - inicializace obsahu karet
        self.init_tab(self.tab_products, "Produkty")
        self.init_tab(self.tab_users, "Uživatelé")

    def init_tab(self, tab, tab_name):
        layout = QVBoxLayout()
        # - QTableWidget: tabulkové zobrazení dat z databáze
        table = QTableWidget()

        if tab_name == "Produkty":
            headers = ['ID', 'Název produktu', 'Cena', 'Sleva', 'Skladem', 'Popis', 'Fotka']
        else:
            headers = ['ID', 'Uživatelské jméno', 'Email', 'Role (Admin)', 'Datum registrace']

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)  # - poslední sloupec vyplní zbytek místa
        layout.addWidget(table)

        # - TLAČÍTKA PRO CRUD OPERACE (Create, Read, Update, Delete)
        btn_layout = QHBoxLayout()
        btn_load = QPushButton(f"Obnovit {tab_name.lower()}")
        btn_load.clicked.connect(lambda: self.load_data(tab_name, table))

        btn_add = QPushButton(f"Přidat {tab_name.lower()[:-1]}")
        btn_add.clicked.connect(lambda: self.open_add_dialog(tab_name, table))

        btn_edit = QPushButton("Upravit vybraný")
        btn_edit.clicked.connect(lambda: self.open_edit_dialog(tab_name, table))

        btn_delete = QPushButton("Smazat vybraný")
        btn_delete.clicked.connect(lambda: self.delete_selected(tab_name, table))

        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        layout.addLayout(btn_layout)

        tab.setLayout(layout)
        self.load_data(tab_name, table)

    # - načtení dat z DB do tabulky GUI
    def load_data(self, tab_name, table):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            if tab_name == "Produkty":
                cursor.execute(
                    "SELECT id, name, price, stock, description, image, discount_percent FROM student20_products ORDER BY id DESC")
                rows = cursor.fetchall()
                table.setRowCount(len(rows))
                for row_idx, r in enumerate(rows):
                    # - QTableWidgetItem: jeden řádek v GUI tabulce
                    table.setItem(row_idx, 0, QTableWidgetItem(str(r['id'])))
                    table.setItem(row_idx, 1, QTableWidgetItem(str(r['name'])))
                    table.setItem(row_idx, 2, QTableWidgetItem(f"{r['price']:.2f} Kč"))
                    table.setItem(row_idx, 3,
                                  QTableWidgetItem(f"{r['discount_percent']}%" if r['discount_percent'] else "0%"))
                    table.setItem(row_idx, 4, QTableWidgetItem(f"{r['stock']} ks"))
                    table.setItem(row_idx, 5, QTableWidgetItem(str(r['description'] or '')))
                    table.setItem(row_idx, 6, QTableWidgetItem(str(r['image'] or 'bez fotky')))
            else:
                cursor.execute("SELECT id, username, email, is_admin, created_at FROM student20_users ORDER BY id DESC")
                rows = cursor.fetchall()
                table.setRowCount(len(rows))
                for row_idx, r in enumerate(rows):
                    table.setItem(row_idx, 0, QTableWidgetItem(str(r['id'])))
                    table.setItem(row_idx, 1, QTableWidgetItem(str(r['username'])))
                    table.setItem(row_idx, 2, QTableWidgetItem(str(r['email'] or 'neuveden')))
                    table.setItem(row_idx, 3, QTableWidgetItem("Administrátor" if r['is_admin'] else "Zákazník"))
                    table.setItem(row_idx, 4, QTableWidgetItem(
                        r['created_at'].strftime('%d.%m.%Y %H:%M') if r['created_at'] else '---'))
            cursor.close()
            conn.close()

    def open_add_dialog(self, tab_name, table):
        dialog = ProductDialog(self, product_id=None) if tab_name == "Produkty" else UserDialog(self, user_id=None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data(tab_name, table)

    def open_edit_dialog(self, tab_name, table):
        selected = table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Chyba", "Vyberte položku k úpravě!")
            return
        item_id = int(table.item(selected, 0).text())
        dialog = ProductDialog(self, product_id=item_id) if tab_name == "Produkty" else UserDialog(self,
                                                                                                   user_id=item_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data(tab_name, table)

    # - kaskádové mazání záznamů v databázi přímo z desktopové aplikace
    def delete_selected(self, tab_name, table):
        selected = table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Chyba", "Vyberte položku k odstranění!")
            return

        item_id = int(table.item(selected, 0).text())
        name = table.item(selected, 1).text()

        # - potvrzení smazání (prevence nechtěného odstranění)
        reply = QMessageBox.question(self, "Smazat",
                                     f"Opravdu smazat {tab_name[:-1].lower()} {name} (ID {item_id})?\n\nPozor: Smažou se i všechny související záznamy!",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    if tab_name == "Produkty":
                        # - čištění vazebních tabulek, aby nenastala chyba Foreign Key
                        cursor.execute("DELETE FROM student20_order_items WHERE product_id = %s", (item_id,))
                        cursor.execute("DELETE FROM cart_items WHERE product_id = %s", (item_id,))
                        cursor.execute("DELETE FROM student20_products WHERE id = %s", (item_id,))
                    else:
                        cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (item_id,))
                        cursor.execute("DELETE FROM discount_codes WHERE user_id = %s", (item_id,))
                        cursor.execute(
                            "DELETE FROM student20_order_items WHERE order_id IN (SELECT id FROM student20_orders WHERE user_id = %s)",
                            (item_id,))
                        cursor.execute("DELETE FROM student20_orders WHERE user_id = %s", (item_id,))
                        cursor.execute("DELETE FROM student20_users WHERE id = %s", (item_id,))
                    conn.commit()
                    QMessageBox.information(self, "Úspěch", f"{name} byl odstraněn!")
                    self.load_data(tab_name, table)
                except Error as e:
                    conn.rollback()
                    QMessageBox.critical(self, "Chyba", f"Chyba při mazání:\n{e}")
                finally:
                    cursor.close()
                    conn.close()


# --- SPUŠTĚNÍ APLIKACE ---
if __name__ == '__main__':
    # - QApplication: spravuje životní cyklus GUI aplikace
    app = QApplication(sys.argv)
    window = AdminApp()
    window.show()
    sys.exit(app.exec())
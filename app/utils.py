# - pomocný modul pro generování dokumentů
# - využívá knihovnu ReportLab pro dynamickou tvorbu PDF souborů

import os
from os.path import join, abspath, dirname
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from decimal import Decimal


def generate_invoice_pdf(order, user, items):
    # - zjištění kořenového adresáře aplikace pro správné směrování cest
    BASE_DIR = dirname(dirname(abspath(__file__)))
    # - definice složky pro ukládání faktur: app/static/invoices/
    folder = join(BASE_DIR, 'app', 'static', 'invoices')
    # - makedirs(..., exist_ok=True): vytvoří složku, pokud ještě neexistuje (prevence chyby)
    os.makedirs(folder, exist_ok=True)

    # - název souboru je unikátní díky ID objednávky
    filename = join(folder, f"faktura_{order.id}.pdf")
    relative_path = f"invoices/faktura_{order.id}.pdf"

    # - REGISTRACE FONTŮ: PDF standardně neumí české znaky (ěščřž...),
    # - proto musíme načíst externí TrueType fonty (DejaVuSans), které diakritiku podporují
    font_path = join(BASE_DIR, 'app', 'static', 'fonts', 'DejaVuSans.ttf')
    bold_path = join(BASE_DIR, 'app', 'static', 'fonts', 'DejaVuSans-Bold.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path))

    # - inicializace plátna (Canvas) ve formátu A4
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # --- HLAVIČKA FAKTURY ---
    c.setFont("DejaVuSans-Bold", 20)
    c.drawString(50, height - 60, "FAKTURA - Solevia")
    c.setFont("DejaVuSans", 10)
    c.drawString(50, height - 90, f"Číslo faktury: {order.id}")
    c.drawString(50, height - 105, f"Datum vystavení: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    # --- ÚDAJE O ODBĚRATELI ---
    c.setFont("DejaVuSans-Bold", 12)
    c.drawString(50, height - 140, "ODBĚRATEL / DORUČOVACÍ ADRESA:")
    c.setFont("DejaVuSans", 11)
    y_addr = height - 160
    c.drawString(50, y_addr, f"{order.jmeno} {order.prijmeni}")
    c.drawString(50, y_addr - 15, f"{order.ulice}")
    c.drawString(50, y_addr - 30, f"{order.psc} {order.mesto}")
    c.drawString(50, y_addr - 45, f"Tel: {order.telefon}")
    c.drawString(50, y_addr - 60, f"Email: {user.email}")

    # --- TABULKA POLOŽEK (Definice sloupců) ---
    col_polozka = 50
    col_puvodni = 210
    col_sleva_obch = 280
    col_mnoz = 360
    col_cena_ks = 420
    col_celkem = 500

    y = height - 260
    c.setFont("DejaVuSans-Bold", 9)
    c.drawString(col_polozka, y, "Položka")
    c.drawString(col_puvodni, y, "Pův. j.")
    c.drawString(col_sleva_obch, y, "Sleva obch.")
    c.drawString(col_mnoz, y, "Množ.")
    c.drawString(col_cena_ks, y, "Cena/ks")
    c.drawString(col_celkem, y, "Celkem")
    c.line(50, y - 5, 550, y - 5)  # - oddělovací linka hlavičky tabulky

    c.setFont("DejaVuSans", 8)
    y -= 25

    soucet_puvodnich_cen = 0.0
    soucet_po_sleve_obchodu = 0.0

    # --- VÝPIS JEDNOTLIVÝCH BOT ---
    for item in items:
        # Pokud je 'item' objekt OrderItem z DB, přistupujeme k atributům přímo,
        # pokud je to slovník (z košíku), přistupujeme přes klíče.
        if isinstance(item, dict):
            p = item['produkt']
            qty = int(item['quantity'])
            prodano_celkem_radek = float(item['celkem'])
        else:
            p = item.product
            qty = item.quantity
            prodano_celkem_radek = float(item.quantity * item.price)

        puvodni_cena_ks = float(p.price)
        prodano_za_ks = prodano_celkem_radek / qty if qty > 0 else 0.0

        soucet_puvodnich_cen += (puvodni_cena_ks * qty)
        soucet_po_sleve_obchodu += prodano_celkem_radek

        # - výpis názvu (oříznuto na 30 znaků)
        c.drawString(col_polozka, y, str(p.name)[:30])
        c.drawString(col_puvodni, y, f"{puvodni_cena_ks:.2f}")

        # - vizualizace slevy obchodu (pokud bota byla v akci přímo v katalogu)
        sleva_ks = puvodni_cena_ks - prodano_za_ks
        if sleva_ks > 0.01:
            c.setFillColorRGB(0.7, 0, 0)
            c.drawString(col_sleva_obch, y, f"-{sleva_ks:.2f}")
            c.setFillColorRGB(0, 0, 0)
        else:
            c.drawString(col_sleva_obch, y, "---")

        c.drawString(col_mnoz, y, f"{qty}x")
        c.drawString(col_cena_ks, y, f"{prodano_za_ks:.2f}")
        c.drawString(col_celkem, y, f"{prodano_celkem_radek:.2f}")
        y -= 18

        # --- REKAPITULACE CELKOVÉ CENY ---
    y -= 20
    c.line(350, y + 15, 550, y + 15)
    x_text = 320
    x_val = 480

    c.setFont("DejaVuSans", 10)
    c.drawString(x_text, y, "Součet běžných cen:")
    c.drawString(x_val, y, f"{soucet_puvodnich_cen:.2f} Kč")
    y -= 18

    # - výpočet a zobrazení celkové slevy (akce obchodu)
    sleva_obchodu_total = soucet_puvodnich_cen - soucet_po_sleve_obchodu
    if sleva_obchodu_total > 0.01:
        c.setFillColorRGB(0.7, 0, 0)
        c.drawString(x_text, y, "Sleva obchodu (akce):")
        c.drawString(x_val, y, f"-{sleva_obchodu_total:.2f} Kč")
        c.setFillColorRGB(0, 0, 0)
        y -= 18

    # --- DOPRAVA (Nová sekce) ---
    # Přidáme řádek s cenou dopravy, kterou jsme uložili v Order modelu
    shipping_name = getattr(order, 'shipping_name', 'Doprava')
    shipping_price = float(getattr(order, 'shipping_price', 0))
    c.drawString(x_text, y, f"Doprava ({shipping_name}):")
    c.drawString(x_val, y, f"{shipping_price:.2f} Kč")
    y -= 18

    # - SLEVA Z MINIHRY: načtení dat z objektu objednávky
    discount_p = getattr(order, 'discount_percent_used', 0)
    discount_code = getattr(order, 'discount_code_used', None)

    if discount_p and discount_p > 0:
        # Sleva se počítá ze součtu produktů
        sleva_z_kodu = soucet_po_sleve_obchodu * (float(discount_p) / 100)
        c.setFillColorRGB(0, 0.5, 0)
        c.drawString(x_text, y, f"Sleva kód ({discount_code}):")
        c.drawString(x_val, y, f"-{sleva_z_kodu:.2f} Kč")
        c.setFillColorRGB(0, 0, 0)
        y -= 18

    # --- FINÁLNÍ SOUČET ---
    y -= 5
    c.setFont("DejaVuSans-Bold", 12)
    c.drawString(x_text, y, "CELKEM K ÚHRADĚ:")
    # Hodnota order.total_price již obsahuje (Produkty - Sleva) + Doprava
    c.drawString(x_val, y, f"{float(order.total_price):.2f} Kč")

    # - ukončení stránky a uložení souboru na disk
    c.showPage()
    c.save()
    return relative_path
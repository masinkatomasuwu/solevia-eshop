from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from app.models import User  # Import tvého modelu uživatele
from app import db  # Import databáze

# Definice Blueprintu (pokud ho už máš definovaný jinde, tento řádek přeskoč)
main = Blueprint('main', __name__)


@main.route('/api/login', methods=['POST'])
def api_login():
    # 1. Získání dat poslaných z desktopové aplikace (JSON formát)
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "Chybějící data"}), 400

    username = data.get('username')
    password = data.get('password')

    # 2. Vyhledání uživatele v databázi podle jména
    user = User.query.filter_by(username=username).first()

    # 3. Ověření existence uživatele a správnosti hesla
    if user and check_password_hash(user.password, password):
        # Přihlášení úspěšné - pošleme desktopu data o uživateli
        return jsonify({
            "status": "success",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
        }), 200
    else:
        # Přihlášení selhalo
        return jsonify({"status": "error", "message": "Nesprávné jméno nebo heslo"}), 401
"""
EcoGrid AI - Rutas de Autenticación y Control de Acceso
Universidad Tecnológica de Calvillo (UTC)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

try:
    from database import db_repo
except ImportError:
    from backend.database import db_repo

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _record_session(email, success, name="", role=""):
    """Guarda el intento de login. Si la BD falla, el login NO debe fallar."""
    try:
        db_repo.log_session(
            email=email,
            success=success,
            source_ip=request.remote_addr or "",
            user_agent=request.headers.get("User-Agent", ""),
            name=name,
            role=role,
        )
    except Exception as e:
        print(f"[AUTH] No se pudo registrar la sesión: {e}")

# Usuarios autorizados para operación del sistema SCADA / EcoGrid
AUTHORIZED_USERS = {
    "operador@utc.edu.mx": {
        "password": "utc7mo2026",
        "name": "Ing. Residente UTC",
        "role": "Operador de Subestación",
        "institution": "Universidad Tecnológica de Calvillo",
    },
    "admin@ecogrid.ai": {
        "password": "admin",
        "name": "Administrador General",
        "role": "Ingeniero en Jefe de Red",
        "institution": "UTC - 7mo Cuatrimestre",
    },
}


@auth_bp.route("/login", methods=["POST"])
def login():
    """Autenticación legítima de ingenieros y operadores del sistema."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if email in AUTHORIZED_USERS and AUTHORIZED_USERS[email]["password"] == password:
        user_info = AUTHORIZED_USERS[email]
        _record_session(email, True, user_info["name"], user_info["role"])
        return jsonify({
            "status": "success",
            "message": "Autenticación exitosa",
            "token": f"ecogrid_token_{int(datetime.now(timezone.utc).timestamp())}",
            "user": {
                "email": email,
                "name": user_info["name"],
                "role": user_info["role"],
                "institution": user_info["institution"],
            },
        }), 200

    _record_session(email, False)
    return jsonify({
        "status": "error",
        "message": "Credenciales inválidas. Verifique correo institucional y contraseña.",
    }), 401


@auth_bp.route("/verify", methods=["GET"])
def verify_token():
    """Verificación de sesión activa."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ecogrid_token_"):
        return jsonify({"authenticated": True, "user": AUTHORIZED_USERS["operador@utc.edu.mx"]})
    return jsonify({"authenticated": False}), 401
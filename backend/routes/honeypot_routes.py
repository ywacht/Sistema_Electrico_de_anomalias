from flask import Blueprint, request, jsonify
from datetime import datetime
from models.db_connection import get_db

honeypot_bp = Blueprint("honeypot", __name__)

RUTAS_SEÑUELO = ["/api/admin/login", "/api/v1/users", "/.env", "/api/backup"]

def registrar_evento(tipo, request_obj):
    db = get_db()
    evento = {
        "evento_id": f"evt_{int(datetime.now().timestamp())}",
        "tipo": tipo,
        "origen_ip": request_obj.remote_addr,
        "timestamp": datetime.now().astimezone().isoformat(),
        "severidad": "Crítico",
        "detalle": {
            "ruta": request_obj.path,
            "metodo": request_obj.method,
            "user_agent": request_obj.headers.get("User-Agent", "desconocido"),
        }
    }
    db.eventos_seguridad.insert_one(evento)
    return evento

@honeypot_bp.route("/api/admin/login", methods=["GET", "POST"])
@honeypot_bp.route("/api/v1/users", methods=["GET"])
@honeypot_bp.route("/.env", methods=["GET"])
@honeypot_bp.route("/api/backup", methods=["GET"])
def trampa():
    registrar_evento("honeypot_trigger", request)
    # Responde como si el endpoint existiera, para no delatar que es falso
    return jsonify({"error": "No autorizado"}), 401
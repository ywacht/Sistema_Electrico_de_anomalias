"""
EcoGrid AI - Plataforma Servidora Backend Principal
Universidad Tecnológica de Calvillo (UTC)
Ingeniería en Tecnologías (7mo Cuatrimestre)

Integra:
- Fundamentos de IA (Patrones de consumo y predicción de picos)
- Minería de Texto (Bitácoras e incidentes)
- Bases de Datos en la Nube (Series de tiempo no relacionales / MongoDB)
- Seguridad Informática (Syslog, SNMP, Protección DoS y Honeypot SCADA/IoT)
- Control de Actuadores ESP32 (Desconexión automatizada de cargas)
"""

import os
import sys
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Asegurar path de importación tanto desde la raíz como desde la carpeta backend
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Rutas y Blueprints
from backend.routes.telemetry import telemetry_bp
from backend.routes.actuators import actuators_bp
from backend.routes.text_mining_routes import text_mining_bp
from backend.routes.security_routes import security_bp
from backend.routes.auth_routes import auth_bp
from backend.routes.ingest_routes import ingest_bp
from backend.routes.query_routes import query_bp
from backend.services.load_control import load_control_bp

try:
    from models.db_connection import get_db
except ImportError:
    from backend.models.db_connection import get_db

try:
    from config import DB_NAME, HOST, PORT, DEBUG
except ImportError:
    try:
        from backend.config import DB_NAME, HOST, PORT, DEBUG
    except ImportError:
        DB_NAME = os.getenv("DB_NAME", "sistema_electrico")
        HOST = os.getenv("HOST", "0.0.0.0")
        PORT = int(os.getenv("PORT", "5000"))
        DEBUG = False

from security.dos_protection import dos_engine
from security.honeypot_service import honeypot

load_dotenv()


def create_app():
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    app = Flask(__name__, static_folder=frontend_dir, static_url_path="")
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # -------------------------------------------------------------
    # MIDDLEWARE DE CIBERSEGURIDAD (DOS & HONEYPOT)
    # -------------------------------------------------------------
    @app.before_request
    def security_filter():
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1")
        if "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        path = request.path

        # 1. Trampa Honeypot: Detección proactiva de intrusos
        if honeypot.is_decoy_path(path):
            captured_payload = {}
            if request.method in ["POST", "PUT"]:
                captured_payload = request.get_json(silent=True) or request.form.to_dict()

            honeypot.handle_intrusion_attempt(
                ip=client_ip,
                path=path,
                method=request.method,
                headers=dict(request.headers),
                payload=captured_payload,
            )
            # Retornar interfaz señuelo o respuesta engañosa
            if "json" in request.headers.get("Accept", ""):
                return jsonify({"status": "error", "message": "Access restricted by SCADA security policy"}), 401
            return honeypot.get_decoy_response_html(path), 200

        # 2. Motor de Protección contra Denegación de Servicio (DoS)
        # Excluir rutas de recursos estáticos de pruebas locales excesivas
        if not path.startswith("/static/") and not path.endswith((".css", ".js", ".png", ".ico")):
            allowed, reason, code = dos_engine.check_request(client_ip, path)
            if not allowed:
                return jsonify({
                    "status": "BLOCKED",
                    "error": "Security Infrastructure Protection",
                    "reason": reason,
                    "ip": client_ip,
                }), code

    # -------------------------------------------------------------
    # REGISTRO DE RUTAS API
    # -------------------------------------------------------------
    app.register_blueprint(telemetry_bp)
    app.register_blueprint(actuators_bp)
    app.register_blueprint(text_mining_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(query_bp)
    app.register_blueprint(load_control_bp)

    # -------------------------------------------------------------
    # RUTAS DE INTERFAZ Y ESTADO
    # -------------------------------------------------------------
    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/health")
    def health():
        return jsonify({
            "service": "EcoGrid AI Cloud API",
            "institution": "Universidad Tecnológica de Calvillo (UTC)",
            "status": "UP",
            "security": "ENABLED",
        })

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Verifica el estado del servidor y la conexión a MongoDB."""
        mongo_status = "desconectado"
        try:
            db = get_db()
            db.command("ping")
            mongo_status = "conectado"
        except Exception as e:
            mongo_status = f"error: {str(e)}"

        return jsonify({
            "status": "ok" if mongo_status == "conectado" else "degraded",
            "database": DB_NAME,
            "mongodb": mongo_status
        }), 200 if mongo_status == "conectado" else 503

    @app.errorhandler(404)
    def no_encontrado(e):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(500)
    def error_interno(e):
        return jsonify({"error": "Error interno del servidor"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t", "yes")
    print("=" * 70)
    print(f"  ECOGRID AI - SERVIDOR INICIADO EN http://{host}:{port}")
    print("  Asignaturas integradas: 6/6 + Honeypot + ESP32 Nodes")
    print("=" * 70)
    app.run(host=host, port=port, debug=debug)

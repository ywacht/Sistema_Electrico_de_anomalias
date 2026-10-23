import sys
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS

# Asegurar que el directorio backend esté en sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import PORT, HOST, DEBUG, DB_NAME
from routes.ingest_routes import ingest_bp
from routes.query_routes import query_bp
from services.load_control import load_control_bp
from models.db_connection import get_db


def create_app():
    """Crea y configura la aplicación Flask con CORS y Blueprints."""
    app = Flask(__name__)

    # Activar CORS para permitir comunicación con el Dashboard en Angular
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Registro de Blueprints
    app.register_blueprint(ingest_bp)
    app.register_blueprint(query_bp)
    app.register_blueprint(load_control_bp)

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "servicio": "EcoGrid API - Sistema Eléctrico y Detección de Anomalías",
            "version": "1.0.0",
            "estado": "operativo",
            "endpoints": [
                "/api/lecturas",
                "/api/bitacoras",
                "/api/lecturas/ultima",
                "/api/clasificaciones",
                "/api/predicciones",
                "/api/eventos-seguridad",
                "/api/cargas",
                "/api/cargas/accion"
            ]
        }), 200

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
    # Escucha en 0.0.0.0 para que los ESP32 y clientes en la red local puedan comunicarse
    print(f"Iniciando EcoGrid Backend en http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)

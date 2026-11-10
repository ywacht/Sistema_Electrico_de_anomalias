from datetime import datetime
import sys
from flask import Blueprint, request, jsonify
from bson import ObjectId

try:
    from models.db_connection import (
        get_lecturas_col,
        get_bitacoras_col,
        get_clasificaciones_col,
        get_predicciones_col,
        get_eventos_seguridad_col,
    )
except ImportError:
    from backend.models.db_connection import (
        get_lecturas_col,
        get_bitacoras_col,
        get_clasificaciones_col,
        get_predicciones_col,
        get_eventos_seguridad_col,
    )

# Compatibilidad con mocks en suites de pruebas unitarias
if __name__ in sys.modules:
    sys.modules.setdefault("routes.query_routes", sys.modules[__name__])
    sys.modules.setdefault("backend.routes.query_routes", sys.modules[__name__])

query_bp = Blueprint("query", __name__)


def serializar_doc(doc):
    """Convierte tipos no serializables en JSON (ObjectId, datetime) a formato serializable."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serializar_doc(item) for item in doc]
    if not isinstance(doc, dict):
        return doc

    res = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.isoformat()
        elif isinstance(v, dict):
            res[k] = serializar_doc(v)
        elif isinstance(v, list):
            res[k] = [serializar_doc(i) for i in v]
        else:
            res[k] = v
    return res


@query_bp.route("/api/lecturas", methods=["GET"])
def obtener_lecturas():
    """
    Histórico filtrado por medidor y rango de fecha.
    Parámetros de consulta (Query Params):
      - medidor_id: id del medidor (opcional)
      - desde: fecha inicial (ISO string o timestamp) (opcional)
      - hasta: fecha final (ISO string o timestamp) (opcional)
      - limite: cantidad máxima de registros a retornar (default 500)
    """
    medidor_id = request.args.get("medidor_id")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    limite = request.args.get("limite", default=500, type=int)

    filtro = {}
    if medidor_id:
        filtro["medidor_id"] = str(medidor_id).strip()

    # Filtro por rango de fecha en timestamp
    filtro_fecha = {}
    if desde:
        filtro_fecha["$gte"] = desde
    if hasta:
        filtro_fecha["$lte"] = hasta
    if filtro_fecha:
        filtro["timestamp"] = filtro_fecha

    try:
        col = get_lecturas_col()
        cursor = col.find(filtro).sort("timestamp", 1).limit(limite)
        lecturas = [serializar_doc(doc) for doc in cursor]
        return jsonify(lecturas), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar lecturas: {str(e)}"}), 500


@query_bp.route("/api/lecturas/ultima", methods=["GET"])
def obtener_ultima_lectura():
    """
    Última lectura registrada para un medidor en tiempo real.
    Parámetro de consulta (Query Param):
      - medidor_id: requerido
    """
    medidor_id = request.args.get("medidor_id")
    if not medidor_id or str(medidor_id).strip() == "":
        return jsonify({"error": "El parámetro de consulta 'medidor_id' es requerido"}), 400

    try:
        col = get_lecturas_col()
        doc = col.find_one(
            {"medidor_id": str(medidor_id).strip()},
            sort=[("timestamp", -1), ("_id", -1)]
        )
        if not doc:
            return jsonify({
                "error": f"No se encontraron lecturas para el medidor '{medidor_id}'"
            }), 404

        return jsonify(serializar_doc(doc)), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar la última lectura: {str(e)}"}), 500


@query_bp.route("/api/bitacoras", methods=["GET"])
def obtener_bitacoras():
    """
    Bitácoras asociadas a un medidor o todas las registradas.
    Parámetro de consulta (Query Param):
      - medidor_id: opcional
    """
    medidor_id = request.args.get("medidor_id")
    filtro = {}
    if medidor_id and str(medidor_id).strip() != "":
        filtro["medidor_id"] = str(medidor_id).strip()

    try:
        col = get_bitacoras_col()
        cursor = col.find(filtro).sort("timestamp", -1)
        bitacoras = [serializar_doc(doc) for doc in cursor]
        return jsonify(bitacoras), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar bitácoras: {str(e)}"}), 500


@query_bp.route("/api/clasificaciones", methods=["GET"])
def obtener_clasificaciones():
    """
    Severidad ya clasificada por el modelo de texto.
    Parámetro de consulta (Query Param):
      - medidor_id: opcional
    """
    medidor_id = request.args.get("medidor_id")
    filtro = {}
    if medidor_id and str(medidor_id).strip() != "":
        filtro["medidor_id"] = str(medidor_id).strip()

    try:
        col = get_clasificaciones_col()
        cursor = col.find(filtro).sort("timestamp", -1)
        clasificaciones = [serializar_doc(doc) for doc in cursor]
        return jsonify(clasificaciones), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar clasificaciones: {str(e)}"}), 500


@query_bp.route("/api/predicciones", methods=["GET"])
def obtener_predicciones():
    """
    Última predicción de pico del modelo de IA.
    Parámetro de consulta (Query Param):
      - medidor_id: opcional. Si se envía, retorna la última predicción de ese medidor.
    """
    medidor_id = request.args.get("medidor_id")

    try:
        col = get_predicciones_col()
        if medidor_id and str(medidor_id).strip() != "":
            # Buscar la más reciente para este medidor
            doc = col.find_one(
                {"medidor_id": str(medidor_id).strip()},
                sort=[("timestamp", -1), ("_id", -1)]
            )
            if not doc:
                return jsonify({
                    "error": f"No se encontraron predicciones para el medidor '{medidor_id}'"
                }), 404
            return jsonify(serializar_doc(doc)), 200
        else:
            # Si no especifica medidor_id, retorna las predicciones más recientes
            cursor = col.find().sort("timestamp", -1).limit(100)
            predicciones = [serializar_doc(d) for d in cursor]
            return jsonify(predicciones), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar predicciones: {str(e)}"}), 500


@query_bp.route("/api/eventos-seguridad", methods=["GET"])
def obtener_eventos_seguridad():
    """
    Eventos DoS / anomalías detectados para el Dashboard.
    """
    try:
        col = get_eventos_seguridad_col()
        cursor = col.find().sort("timestamp", -1).limit(100)
        eventos = [serializar_doc(doc) for doc in cursor]
        return jsonify(eventos), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar eventos de seguridad: {str(e)}"}), 500

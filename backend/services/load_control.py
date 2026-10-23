from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from bson import ObjectId

try:
    from models.db_connection import get_cargas_col
    from routes.query_routes import serializar_doc
except ImportError:
    from backend.models.db_connection import get_cargas_col
    from backend.routes.query_routes import serializar_doc

load_control_bp = Blueprint("load_control", __name__)

# Umbral para considerar que la probabilidad de pico es alta (70% o superior)
UMBRAL_PROBABILIDAD_ALTA = 0.70
ACCIONES_VALIDAS = {"desconectar", "reconectar"}
SEVERIDADES_CRITICAS = {"crítico", "critico"}


def evaluar_riesgo(prediccion: dict = None, clasificacion: dict = None) -> dict:
    """
    Evalúa el riesgo eléctrico y operativo basándose en:
      - prediccion: diccionario con { pico_predicho: bool, probabilidad: float, ... }
      - clasificacion: diccionario con { severidad: str, ... }

    Regla:
      Si pico_predicho == true con probabilidad alta (>= 0.70),
      o severidad == "Crítico",
      genera un comando de desconexión y lo guarda en la colección 'cargas'.

    Retorna:
      El diccionario del comando generado y guardado, o None si no hay riesgo crítico.
    """
    prediccion = prediccion or {}
    clasificacion = clasificacion or {}

    pico_flag = prediccion.get("pico_predicho")
    es_pico = pico_flag in (True, "true", "True", "1", 1)

    probabilidad = prediccion.get("probabilidad", prediccion.get("prob", 0.0))
    try:
        probabilidad = float(probabilidad)
        if probabilidad > 1.0:  # Si viene en escala 0-100%, normalizar a 0.0-1.0
            probabilidad = probabilidad / 100.0
    except (ValueError, TypeError):
        probabilidad = 0.0

    riesgo_pico = es_pico and (probabilidad >= UMBRAL_PROBABILIDAD_ALTA)

    severidad_raw = str(clasificacion.get("severidad", "")).strip().lower()
    riesgo_severidad = severidad_raw in SEVERIDADES_CRITICAS

    if not (riesgo_pico or riesgo_severidad):
        return None

    # Construir motivo descriptivo
    motivos = []
    if riesgo_pico:
        motivos.append(f"Pico de demanda predicho con alta probabilidad ({probabilidad * 100:.1f}%)")
    if riesgo_severidad:
        motivos.append("Severidad Crítica detectada en análisis de bitácora")
    motivo = " | ".join(motivos)

    # Determinar carga_id involucrada
    carga_id = (
        prediccion.get("carga_id")
        or prediccion.get("medidor_id")
        or clasificacion.get("carga_id")
        or clasificacion.get("medidor_id")
        or "carga_general"
    )
    carga_id = str(carga_id).strip()

    ahora_iso = datetime.now(timezone.utc).isoformat()

    comando = {
        "carga_id": carga_id,
        "accion": "desconectar",
        "estado": "desconectada",
        "motivo": motivo,
        "timestamp": ahora_iso,
        "origen": "automatico"
    }

    # Guardar / actualizar en la colección 'cargas'
    col = get_cargas_col()
    col.update_one(
        {"carga_id": carga_id},
        {"$set": comando},
        upsert=True
    )

    return comando


@load_control_bp.route("/api/cargas/accion", methods=["POST"])
def accionar_carga():
    """
    Endpoint manual del dashboard (módulo 6.2).
    Recibe:
      {
        "carga_id": "CARGA_01",
        "accion": "desconectar" | "reconectar",
        "motivo": "opcional..."
      }
    Actualiza el estado de la carga.
    """
    if not request.is_json:
        return jsonify({"error": "El cuerpo de la solicitud debe ser un JSON válido"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Formato JSON inválido: se esperaba un objeto"}), 400

    carga_id = data.get("carga_id")
    if not carga_id or str(carga_id).strip() == "":
        return jsonify({"error": "El campo 'carga_id' es requerido"}), 400

    accion = str(data.get("accion", "")).strip().lower()
    if accion not in ACCIONES_VALIDAS:
        return jsonify({
            "error": f"Acción '{accion}' no permitida. Valores permitidos: 'desconectar', 'reconectar'"
        }), 400

    carga_id = str(carga_id).strip()
    motivo = data.get("motivo") or f"Comando manual '{accion}' desde el dashboard"
    ahora_iso = datetime.now(timezone.utc).isoformat()
    nuevo_estado = "desconectada" if accion == "desconectar" else "conectada"

    documento = {
        "carga_id": carga_id,
        "accion": accion,
        "estado": nuevo_estado,
        "motivo": motivo,
        "timestamp": ahora_iso,
        "origen": "manual"
    }

    try:
        col = get_cargas_col()
        col.update_one(
            {"carga_id": carga_id},
            {"$set": documento},
            upsert=True
        )
        return jsonify({
            "status": "ok",
            "mensaje": f"Carga '{carga_id}' actualizada a estado '{nuevo_estado}'",
            "carga": documento
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error al actualizar estado de la carga: {str(e)}"}), 500


@load_control_bp.route("/api/cargas", methods=["GET"])
def obtener_cargas():
    """
    Estado actual de todas las cargas, para que el dashboard lo pinte.
    """
    try:
        col = get_cargas_col()
        cursor = col.find().sort("carga_id", 1)
        cargas = [serializar_doc(doc) for doc in cursor]
        return jsonify(cargas), 200
    except Exception as e:
        return jsonify({"error": f"Error al consultar cargas: {str(e)}"}), 500


@load_control_bp.route("/api/cargas/evaluar", methods=["POST"])
def endpoint_evaluar_riesgo():
    """
    Endpoint auxiliar para evaluar riesgo a demanda a partir de una predicción y clasificación.
    Recibe:
      {
        "prediccion": { "pico_predicho": true, "probabilidad": 0.85, ... },
        "clasificacion": { "severidad": "Crítico", ... }
      }
    """
    if not request.is_json:
        return jsonify({"error": "El cuerpo de la solicitud debe ser un JSON válido"}), 400

    data = request.get_json()
    prediccion = data.get("prediccion", {})
    clasificacion = data.get("clasificacion", {})

    comando = evaluar_riesgo(prediccion, clasificacion)
    if comando:
        return jsonify({
            "riesgo_detectado": True,
            "comando": comando
        }), 200
    else:
        return jsonify({
            "riesgo_detectado": False,
            "mensaje": "No se detectó riesgo que amerite desconexión"
        }), 200

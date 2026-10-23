from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

try:
    from models.db_connection import get_lecturas_col, get_bitacoras_col
except ImportError:
    from backend.models.db_connection import get_lecturas_col, get_bitacoras_col

ingest_bp = Blueprint("ingest", __name__)

ALLOWED_ORIGENES = {"esp32", "simulador"}
ALLOWED_SEVERIDADES = {"bajo", "medio", "alto", "crítico", "critico"}
CONTRATO_LECTURAS = ["medidor_id", "timestamp", "voltaje", "corriente", "potencia_kw", "origen"]

@ingest_bp.route("/api/lecturas", methods=["POST"])
def recibir_lectura():
    """
    Recibe lectura de un ESP32 o del simulador.
    Valida los 6 campos del contrato:
    (medidor_id, timestamp, voltaje, corriente, potencia_kw, origen)
    y la inserta en la colección 'lecturas'.
    """
    if not request.is_json:
        return jsonify({"error": "El cuerpo de la solicitud debe ser un JSON válido"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Formato JSON inválido: se esperaba un objeto"}), 400

    # 1. Validación de campos requeridos del contrato
    for campo in CONTRATO_LECTURAS:
        if campo not in data or data[campo] is None or (isinstance(data[campo], str) and data[campo].strip() == ""):
            return jsonify({"error": f"Falta el campo requerido del contrato: '{campo}'"}), 400

    # 2. Validación de tipos numéricos
    try:
        voltaje = float(data["voltaje"])
    except (ValueError, TypeError):
        return jsonify({"error": "El campo 'voltaje' debe ser un valor numérico"}), 400

    try:
        corriente = float(data["corriente"])
    except (ValueError, TypeError):
        return jsonify({"error": "El campo 'corriente' debe ser un valor numérico"}), 400

    try:
        potencia_kw = float(data["potencia_kw"])
    except (ValueError, TypeError):
        return jsonify({"error": "El campo 'potencia_kw' debe ser un valor numérico"}), 400

    # 3. Validación de origen permitido
    origen_raw = str(data["origen"]).strip()
    if origen_raw.lower() not in ALLOWED_ORIGENES:
        return jsonify({
            "error": f"Valor de 'origen' ('{origen_raw}') no permitido. Valores permitidos: esp32, simulador"
        }), 400

    # 4. Preparar documento a insertar
    documento = {
        "medidor_id": str(data["medidor_id"]).strip(),
        "timestamp": data["timestamp"],
        "voltaje": voltaje,
        "corriente": corriente,
        "potencia_kw": potencia_kw,
        "origen": origen_raw.lower()
    }

    try:
        col = get_lecturas_col()
        resultado = col.insert_one(documento)
        return jsonify({
            "status": "ok",
            "mensaje": "Lectura registrada correctamente",
            "id": str(resultado.inserted_id)
        }), 201
    except Exception as e:
        return jsonify({"error": f"Error al insertar en la base de datos: {str(e)}"}), 500


@ingest_bp.route("/api/bitacoras", methods=["POST"])
def recibir_bitacora():
    """
    Recibe una bitácora de falla (texto libre), la inserta sin procesar en la colección 'bitacoras'.
    Validación mínima: rechaza con 400 si falta un campo o origen/severidad trae un valor fuera de lo permitido.
    """
    if not request.is_json:
        return jsonify({"error": "El cuerpo de la solicitud debe ser un JSON válido"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Formato JSON inválido: se esperaba un objeto"}), 400

    # Validar medidor_id
    if "medidor_id" not in data or data["medidor_id"] is None or str(data["medidor_id"]).strip() == "":
        return jsonify({"error": "Falta el campo requerido: 'medidor_id'"}), 400

    # Validar que exista el texto de la bitácora
    # Se aceptan claves comunes como 'texto', 'mensaje', 'descripcion' o 'bitacora'
    texto_bitacora = (
        data.get("texto")
        or data.get("mensaje")
        or data.get("descripcion")
        or data.get("bitacora")
    )
    if not texto_bitacora or not isinstance(texto_bitacora, str) or texto_bitacora.strip() == "":
        return jsonify({"error": "Falta el campo de texto libre de la bitácora ('texto' o 'mensaje')"}), 400

    # Validar severidad si se proporciona
    severidad_raw = data.get("severidad")
    if severidad_raw is not None:
        if not isinstance(severidad_raw, str) or severidad_raw.strip().lower() not in ALLOWED_SEVERIDADES:
            return jsonify({
                "error": f"Valor de 'severidad' ('{severidad_raw}') no permitido. Valores permitidos: Bajo, Medio, Alto, Crítico"
            }), 400

    # Validar origen si se proporciona
    origen_raw = data.get("origen")
    if origen_raw is not None:
        if not isinstance(origen_raw, str) or origen_raw.strip().lower() not in ALLOWED_ORIGENES:
            return jsonify({
                "error": f"Valor de 'origen' ('{origen_raw}') no permitido. Valores permitidos: esp32, simulador"
            }), 400

    # Documento a insertar sin procesar el texto libre
    documento = dict(data)
    # Normalizar medidor_id como string
    documento["medidor_id"] = str(data["medidor_id"]).strip()

    # Si no tiene timestamp, asignamos la fecha y hora UTC actual
    if "timestamp" not in documento or not documento["timestamp"]:
        documento["timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        col = get_bitacoras_col()
        resultado = col.insert_one(documento)
        return jsonify({
            "status": "ok",
            "mensaje": "Bitácora registrada correctamente",
            "id": str(resultado.inserted_id)
        }), 201
    except Exception as e:
        return jsonify({"error": f"Error al insertar en la base de datos: {str(e)}"}), 500

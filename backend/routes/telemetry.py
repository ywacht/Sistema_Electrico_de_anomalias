from flask import Blueprint, request, jsonify
from backend.database import db_repo
from backend.services.ai_service import ai_service
from backend.services.disconnection_service import disconnection_service
from backend.services.synthetic_enrichment import enrich_telemetry
from security.snmp_service import snmp_agent
from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity

telemetry_bp = Blueprint("telemetry", __name__, url_prefix="/api/telemetry")


@telemetry_bp.route("", methods=["POST"])
def ingest_telemetry():
    """
    Ingestión de datos de telemetría de alta frecuencia provenientes de ESP32 o simuladores.
    Ejecuta en línea:
    1. Enriquecimiento sintético si la lectura es parcial (sensor de corriente único).
    2. Inferencia del modelo de IA sobre patrones de consumo.
    3. Evaluación de corte automático si detecta sobrecarga peligrosa.
    4. Persistencia en el repositorio no relacional de series de tiempo.
    5. Actualización de variables MIB de SNMP.
    """
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id", "esp32_sensor_01")

    # MÓDULO TEMPORAL: Enriquecimiento sintético para nodo con sensor único de corriente (ACS712)
    # Si la lectura no trae el vector completo, rellenar sintéticamente campos ausentes
    missing_fields = [f for f in ("voltage", "power_factor", "frequency", "thd", "temperature") if f not in data or data[f] is None]
    if missing_fields:
        data = enrich_telemetry(data)

    # Extraer variables eléctricas
    try:
        current = float(data.get("current", 0.0))
    except (ValueError, TypeError):
        current = 0.0

    try:
        voltage = float(data.get("voltage", 120.0))
    except (ValueError, TypeError):
        voltage = 120.0

    try:
        power_factor = float(data.get("power_factor", 0.95))
    except (ValueError, TypeError):
        power_factor = 0.95

    try:
        frequency = float(data.get("frequency", 60.0))
    except (ValueError, TypeError):
        frequency = 60.0

    try:
        thd = float(data.get("thd", 3.0))
    except (ValueError, TypeError):
        thd = 3.0

    try:
        temperature = float(data.get("temperature", 28.0))
    except (ValueError, TypeError):
        temperature = 28.0

    # Cálculo derivado de potencia si no viene especificada
    active_power = float(data.get("active_power", voltage * current * power_factor))
    reactive_power = float(
        data.get("reactive_power", voltage * current * ((1.0 - power_factor ** 2) ** 0.5 if power_factor <= 1.0 else 0.0))
    )

    # 1. Evaluación con Inteligencia Artificial (Redes Neuronales / KNN / SVM)
    ai_result = ai_service.evaluate_telemetry(
        voltage=voltage,
        current=current,
        active_power=active_power,
        reactive_power=reactive_power,
        power_factor=power_factor,
        frequency=frequency,
        thd=thd,
        temp=temperature,
    )

    pattern_class = ai_result["class_name"]
    should_disconnect = ai_result["should_disconnect"]

    # 2. Lógica de Desconexión Automatizada de Cargas
    relay_info = disconnection_service.get_relay_state(device_id)
    if should_disconnect and relay_info["state"] == 1:
        relay_info = disconnection_service.evaluate_automatic_cutoff(
            device_id=device_id,
            current=current,
            is_ai_anomaly=True,
            reason=f"IA clasificó patrón anómalo: {pattern_class}",
        )

    # 3. Almacenamiento en repositorio no relacional (series de tiempo)
    payload_to_store = {
        "device_id": device_id,
        "location": data.get("location", "Tablero Principal"),
        "voltage": voltage,
        "current": current,
        "active_power": active_power,
        "reactive_power": reactive_power,
        "power_factor": power_factor,
        "frequency": frequency,
        "thd": thd,
        "temperature": temperature,
        "relay_state": relay_info["state"],
        "pattern_class": pattern_class,
        "should_disconnect": should_disconnect,
        "synthetic_enrichment": data.get("_synthetic_enrichment", False),
    }
    db_repo.insert_telemetry(payload_to_store)

    # 4. Actualización del agente SNMP
    snmp_agent.update_telemetry_mib(
        voltage=voltage,
        current=current,
        power=active_power,
        relay_state=relay_info["state"],
    )

    return jsonify({
        "status": "success",
        "device_id": device_id,
        "relay_state": relay_info["state"],
        "relay_mode": relay_info["mode"],
        "ai_evaluation": ai_result,
        "stored": True,
        "synthetic_enrichment": data.get("_synthetic_enrichment", False),
        "enriched_fields": data.get("_enriched_fields", []),
    }), 201


@telemetry_bp.route("/timeseries", methods=["GET"])
def get_timeseries():
    """Consulta histórica de lecturas de series de tiempo."""
    limit = int(request.args.get("limit", 60))
    device_id = request.args.get("device_id")
    records = db_repo.query_timeseries(limit=limit, device_id=device_id)
    return jsonify({
        "total_records": len(records),
        "data": records,
    })


@telemetry_bp.route("/latest", methods=["GET"])
def get_latest():
    """Retorna la última lectura eléctrica disponible."""
    device_id = request.args.get("device_id")
    latest = db_repo.get_latest_telemetry(device_id=device_id)
    if not latest:
        # Valores de respaldo por defecto
        latest = {
            "metadata": {"device_id": device_id or "esp32_sensor_01"},
            "metrics": {
                "voltage": 120.1,
                "current": 4.5,
                "active_power": 520.0,
                "power_factor": 0.96,
                "frequency": 60.0,
                "thd": 3.2,
                "temperature": 31.0,
                "relay_state": 1,
            },
            "ai_evaluation": {"pattern_class": "Normal", "should_disconnect": False},
        }
    return jsonify(latest)


@telemetry_bp.route("/stats", methods=["GET"])
def get_stats():
    """Resumen de estadísticas energéticas y de consumo."""
    records = db_repo.query_timeseries(limit=120)
    if not records:
        return jsonify({
            "samples_count": 0,
            "avg_voltage": 120.0,
            "avg_current": 0.0,
            "total_energy_kwh": 0.0,
            "peak_power_w": 0.0,
            "anomaly_events": 0,
        })

    voltages = [r["metrics"]["voltage"] for r in records]
    currents = [r["metrics"]["current"] for r in records]
    powers = [r["metrics"]["active_power"] for r in records]
    anomalies = sum(1 for r in records if r["ai_evaluation"].get("pattern_class") in ["Pico de Demanda", "Sobrecarga / Anomalía"])

    # Estimación de energía integrada kWh (muestras espaciadas a 2 seg aprox)
    total_energy_kwh = sum(powers) * (2.0 / 3600.0) / 1000.0

    return jsonify({
        "samples_count": len(records),
        "avg_voltage": round(sum(voltages) / len(voltages), 2),
        "avg_current": round(sum(currents) / len(currents), 2),
        "peak_power_w": round(max(powers), 2),
        "total_energy_kwh": round(total_energy_kwh, 4),
        "anomaly_events": anomalies,
    })

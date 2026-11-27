"""
EcoGrid AI - Rutas de Control de Actuadores y Relés de Carga
Asignatura: Bases de Datos en la Nube (SW) & Seguridad Informática
Universidad Tecnológica de Calvillo (UTC)
"""

from flask import Blueprint, request, jsonify
from backend.services.disconnection_service import disconnection_service

actuators_bp = Blueprint("actuators", __name__, url_prefix="/api/actuators")


@actuators_bp.route("/relay/<device_id>", methods=["GET"])
def get_relay_status(device_id):
    """
    Endpoint consultado periódicamente por el firmware del ESP32
    para sincronizar el estado físico del relé.
    """
    info = disconnection_service.get_relay_state(device_id)
    return jsonify({
        "device_id": device_id,
        "relay_state": info["state"],
        "mode": info["mode"],
        "reason": info["reason"],
        "last_change": info["last_change"],
        "trip_count": info["trip_count"],
    })


@actuators_bp.route("/relay/<device_id>", methods=["POST"])
def set_relay_status(device_id):
    """
    Permite el accionamiento manual o programado del relé desde el panel web.
    """
    data = request.get_json(silent=True) or {}
    state = data.get("state", 1)
    reason = data.get("reason", "Accionamiento desde interfaz web")
    mode = data.get("mode", "MANUAL_WEB")

    info = disconnection_service.set_relay_state(
        device_id=device_id,
        state=state,
        reason=reason,
        mode=mode,
    )
    return jsonify({
        "status": "success",
        "device_id": device_id,
        "relay_state": info["state"],
        "mode": info["mode"],
        "reason": info["reason"],
    })


@actuators_bp.route("/all", methods=["GET"])
def get_all_actuators():
    """Retorna el estado de todos los actuadores registrados."""
    return jsonify(disconnection_service.device_relays)

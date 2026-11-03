"""
EcoGrid AI - Rutas de Seguridad Informática, Syslog, SNMP y Honeypot
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)
"""

from flask import Blueprint, request, jsonify
from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity
from security.snmp_service import snmp_agent
from security.dos_protection import dos_engine
from security.honeypot_service import honeypot

security_bp = Blueprint("security", __name__, url_prefix="/api/security")


@security_bp.route("/stats", methods=["GET"])
def get_security_overview():
    """Retorna el estado global de la infraestructura de seguridad."""
    dos_stats = dos_engine.get_stats()
    honeypot_stats = honeypot.get_stats()
    mib_dump = snmp_agent.get_all_mib()

    return jsonify({
        "status": "SECURE",
        "dos_protection": dos_stats,
        "honeypot": {
            "total_trapped": honeypot_stats["total_trapped_attackers"],
            "recent_count": len(honeypot_stats["recent_intrusions"]),
        },
        "snmp_status": {
            "community": snmp_agent.community,
            "mib_counters": mib_dump,
        },
        "syslog_status": {
            "buffered_logs_count": len(syslog_client.recent_logs),
            "target_host": f"{syslog_client.host}:{syslog_client.port}",
        },
    })


@security_bp.route("/syslog", methods=["GET"])
def get_syslog_events():
    """Obtiene los últimos eventos registrados en el búfer Syslog (RFC 5424)."""
    limit = int(request.args.get("limit", 50))
    events = syslog_client.get_recent_logs(limit=limit)
    return jsonify({
        "total": len(events),
        "protocol": "RFC 5424 / RFC 3164 (UDP port 514)",
        "events": events,
    })


@security_bp.route("/snmp", methods=["GET"])
def get_snmp_details():
    """Obtiene el volcado de la MIB y el historial de traps SNMP enviados."""
    return jsonify({
        "enterprise_oid": "1.3.6.1.4.1.58888",
        "mib_objects": snmp_agent.get_all_mib(),
        "recent_traps": snmp_agent.get_trap_history(limit=25),
    })


@security_bp.route("/honeypot", methods=["GET"])
def get_honeypot_records():
    """Retorna las estadísticas e historial de atacantes atrapados por el Honeypot."""
    return jsonify(honeypot.get_stats())


@security_bp.route("/honeypot/simulate", methods=["POST"])
def simulate_honeypot_attack():
    """
    Simula una intrusión cibernética contra una trampa Honeypot
    para demostración y validación en clase / evaluación académica.
    """
    data = request.get_json(silent=True) or {}
    fake_ip = data.get("ip", "192.168.1.189")
    fake_path = data.get("path", "/admin/login")
    payload = data.get("payload", {"username": "admin", "password": "' OR 1=1 --"})

    record = honeypot.handle_intrusion_attempt(
        ip=fake_ip,
        path=fake_path,
        method="POST",
        headers={"User-Agent": "Sqlmap/1.7.2#dev (Simulated Attack)"},
        payload=payload,
    )
    return jsonify({
        "status": "ATTACK_TRAPPED",
        "message": "Intrusión capturada exitosamente por el Honeypot de EcoGrid AI",
        "record": record,
    })


@security_bp.route("/dos/unban", methods=["POST"])
def unban_ip_address():
    """Permite desbloquear una IP desde la consola de administración."""
    data = request.get_json(silent=True) or {}
    ip = data.get("ip", "")
    if not ip:
        return jsonify({"error": "Debe especificar la 'ip'"}), 400

    success = dos_engine.unban_ip(ip)
    if success:
        syslog_client.send_log(
            facility=SyslogFacility.LOCAL1,
            severity=SyslogSeverity.NOTICE,
            message=f"[DOS_UNBAN] Dirección IP {ip} desbloqueada manualmente por operador",
            msg_id="IP_UNBAN",
        )
        return jsonify({"status": "success", "message": f"IP {ip} desbloqueada"})
    else:
        return jsonify({"status": "not_found", "message": f"IP {ip} no estaba en la lista negra"}), 404

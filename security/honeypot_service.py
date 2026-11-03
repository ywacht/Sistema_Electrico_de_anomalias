"""
EcoGrid AI - Sistema de Trampa Honeypot para Entornos SCADA / IoT
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)

Señuelo cibernético que emula interfaces y endpoints vulnerables de control industrial
(SCADA, Modbus, actuadores ESP32) para atrapar atacantes, registrar sus vectores
de intrusión, emitir alertas Syslog/SNMP y añadirlos automáticamente a la lista negra.
"""

import time
from datetime import datetime, timezone
from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity
from security.snmp_service import snmp_agent
from security.dos_protection import dos_engine


# Endpoints señuelo (deceptive traps)
HONEYPOT_DECOY_ROUTES = [
    "/admin",
    "/admin/login",
    "/scada/admin",
    "/scada/config",
    "/modbus/gateway",
    "/plc/control",
    "/firmware/upload",
    "/firmware/update",
    "/ota/esp32",
    "/api/v1/override_relay",
    "/api/v1/raw_control",
]


class EcoGridHoneypot:
    """
    Honeypot para protección de actuadores y telemetría de la red eléctrica.
    """

    def __init__(self):
        self.trap_history = []
        self.total_trapped_attackers = 0

    def is_decoy_path(self, path):
        """Verifica si la ruta solicitada corresponde a una trampa Honeypot."""
        cleaned_path = path.lower().rstrip("/")
        for decoy in HONEYPOT_DECOY_ROUTES:
            if cleaned_path == decoy or cleaned_path.startswith(decoy + "/"):
                return True
        return False

    def handle_intrusion_attempt(self, ip, path, method="GET", headers=None, payload=None):
        """
        Registra la intrusión en el señuelo y activa contramedidas inmediatas.
        """
        self.total_trapped_attackers += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        headers = headers or {}
        payload = payload or {}

        user_agent = headers.get("User-Agent", "Unknown")
        attempt_record = {
            "id": self.total_trapped_attackers,
            "timestamp": now_iso,
            "attacker_ip": ip,
            "target_path": path,
            "http_method": method,
            "user_agent": user_agent,
            "payload_captured": payload,
            "action_taken": "IP_AUTO_BLACKLISTED",
        }

        self.trap_history.append(attempt_record)
        if len(self.trap_history) > 150:
            self.trap_history.pop(0)

        # 1. Alerta Syslog prioritaria (Facility LOCAL0 - Seguridad)
        syslog_msg = (
            f"[HONEYPOT_INTRUSION_DETECTED] Atacante atrapado desde IP {ip} intentando acceder "
            f"a señuelo '{path}' [Método: {method}]. Carga capturada: {str(payload)[:100]}"
        )
        syslog_client.send_log(
            facility=SyslogFacility.LOCAL0,
            severity=SyslogSeverity.WARNING,
            message=syslog_msg,
            msg_id="HONEYPOT_HIT",
        )

        # 2. Despacho de SNMP Trap y actualización de contadores MIB
        snmp_agent.increment_counter("honeypot")
        snmp_agent.send_snmp_trap(
            trap_oid="1.3.6.1.4.1.58888.2.2.0",
            description=f"Honeypot activado por IP {ip} en endpoint señuelo {path}",
            severity="WARNING",
        )

        # 3. Contramedida activa: Baneo automático de la IP en el motor DoS / Firewall
        dos_engine.ban_ip(
            ip=ip,
            reason=f"Acceso a trampa Honeypot ({path})",
            duration=600,  # 10 minutos de bloqueo
        )

        return attempt_record

    def get_decoy_response_html(self, path):
        """
        Genera una interfaz señuelo HTML convincente para mantener ocupado al atacante.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>EcoGrid SCADA Gateway RTU-5000 [Restricted Access]</title>
    <style>
        body {{ background-color: #0d1117; color: #c9d1d9; font-family: monospace; padding: 40px; }}
        .box {{ max-width: 500px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 25px; }}
        h2 {{ color: #58a6ff; margin-top: 0; }}
        .badge {{ background: #f85149; color: #fff; padding: 3px 8px; border-radius: 4px; font-size: 11px; }}
        input {{ width: 100%; padding: 8px; margin: 8px 0; background: #0d1117; border: 1px solid #30363d; color: #fff; box-sizing: border-box; }}
        button {{ width: 100%; padding: 10px; background: #238636; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 10px; }}
        .footer {{ font-size: 11px; color: #8b949e; margin-top: 15px; text-align: center; }}
    </style>
</head>
<body>
    <div class="box">
        <span class="badge">SECURE INDUSTRIAL RTU</span>
        <h2>EcoGrid Modbus/SCADA Gateway</h2>
        <p>Firmware v2.4.1-build892 - ESP32 Gateway Node</p>
        <p style="color: #8b949e;">Target Unit: Subestación Central / Acometida Principal</p>
        <form method="POST" action="{path}">
            <label>Operator ID / Username:</label>
            <input type="text" name="username" placeholder="e.g. admin or operator" required autofocus>
            <label>Master Security Key:</label>
            <input type="password" name="password" placeholder="••••••••••••" required>
            <button type="submit">Authenticate to SCADA Bus</button>
        </form>
        <div class="footer">
            WARNING: Unauthorized access to critical electric infrastructure is strictly prohibited.
        </div>
    </div>
</body>
</html>"""

    def get_stats(self):
        """Retorna estadísticas consolidadas del Honeypot."""
        return {
            "total_trapped_attackers": self.total_trapped_attackers,
            "decoy_routes_active": HONEYPOT_DECOY_ROUTES,
            "recent_intrusions": self.trap_history[-30:][::-1],
        }


# Instancia singleton del Honeypot
honeypot = EcoGridHoneypot()

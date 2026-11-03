"""
EcoGrid AI - Servicio de Monitoreo Syslog (RFC 5424 / RFC 3164)
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)

Gestión de eventos de seguridad, alertas DoS y trampas Honeypot vía Syslog.
"""

import socket
import os
from datetime import datetime, timezone


class SyslogSeverity:
    EMERGENCY = 0  # Sistema no utilizable
    ALERT = 1      # Acción inmediata requerida
    CRITICAL = 2   # Condiciones críticas (ej. Arco eléctrico, Ataque DoS severo)
    ERROR = 3      # Condiciones de error
    WARNING = 4    # Advertencias (ej. Pico de demanda, Intrusión en Honeypot)
    NOTICE = 5     # Condición normal pero significativa
    INFO = 6       # Mensajes informativos
    DEBUG = 7      # Mensajes de depuración


class SyslogFacility:
    KERN = 0
    USER = 1
    DAEMON = 3
    AUTH = 4
    SYSLOG = 5
    LOCAL0 = 16  # Seguridad / Honeypot
    LOCAL1 = 17  # DoS Protection
    LOCAL2 = 18  # Subestación / Cargas
    LOCAL4 = 20  # Telemetría ESP32


class EcoGridSyslogClient:
    """
    Cliente Syslog para envío de eventos de seguridad a servidores SIEM
    o almacenamiento en búfer local de auditoría.
    """

    def __init__(self, host="127.0.0.1", port=514):
        self.host = os.getenv("SYSLOG_HOST", host)
        self.port = int(os.getenv("SYSLOG_PORT", port))
        self.hostname = socket.gethostname()
        self.app_name = "EcoGridAI"
        self.recent_logs = []

    def format_rfc5424(self, facility, severity, msg, msg_id="SEC_EVENT"):
        """Formatea un mensaje según el estándar RFC 5424."""
        pri = (facility * 8) + severity
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        header = f"<{pri}>1 {timestamp} {self.hostname} {self.app_name} {os.getpid()} {msg_id} -"
        return f"{header} {msg}"

    def send_log(self, facility, severity, message, msg_id="SEC_EVENT"):
        """
        Envía el paquete Syslog por socket UDP y lo almacena en el registro local.
        """
        formatted = self.format_rfc5424(facility, severity, message, msg_id)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "facility": facility,
            "severity": severity,
            "severity_name": self._get_severity_name(severity),
            "msg_id": msg_id,
            "message": message,
            "raw_syslog": formatted,
        }
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 200:
            self.recent_logs.pop(0)

        # Envío UDP no bloqueante
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.5)
            sock.sendto(formatted.encode("utf-8"), (self.host, self.port))
            sock.close()
        except Exception:
            # Si no hay servidor Syslog remoto escuchando en el puerto 514, el log se conserva en búfer
            pass

        return entry

    def _get_severity_name(self, sev):
        mapping = {
            0: "EMERGENCY",
            1: "ALERT",
            2: "CRITICAL",
            3: "ERROR",
            4: "WARNING",
            5: "NOTICE",
            6: "INFO",
            7: "DEBUG",
        }
        return mapping.get(sev, "INFO")

    def get_recent_logs(self, limit=50):
        """Retorna los últimos eventos Syslog registrados."""
        return self.recent_logs[-limit:][::-1]


# Instancia singleton del cliente Syslog
syslog_client = EcoGridSyslogClient()

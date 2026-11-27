"""
EcoGrid AI - Servicio de Desconexión Automatizada de Cargas
Universidad Tecnológica de Calvillo (UTC)

Gestión de estado de relés y corte automático de suministro eléctrico
ante sobrecargas, anomalías críticas y picos severos de demanda.
"""

from datetime import datetime, timezone
from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity
from security.snmp_service import snmp_agent


class LoadDisconnectionService:
    """
    Controlador central de actuadores de corte de carga para nodos ESP32.
    """

    def __init__(self):
        # Diccionario con el estado de relé por dispositivo: 1 = CONECTADO, 0 = DESCONECTADO
        self.device_relays = {
            "esp32_sensor_01": {
                "state": 1,
                "mode": "AUTOMATIC",
                "last_change": datetime.now(timezone.utc).isoformat(),
                "reason": "Operación normal del sistema",
                "trip_count": 0,
            },
            "esp32_sensor_02": {
                "state": 1,
                "mode": "AUTOMATIC",
                "last_change": datetime.now(timezone.utc).isoformat(),
                "reason": "Operación normal del sistema",
                "trip_count": 0,
            },
        }

    def get_relay_state(self, device_id):
        """Retorna el estado actual del relé del dispositivo."""
        if device_id not in self.device_relays:
            self.device_relays[device_id] = {
                "state": 1,
                "mode": "AUTOMATIC",
                "last_change": datetime.now(timezone.utc).isoformat(),
                "reason": "Dispositivo recién registrado",
                "trip_count": 0,
            }
        return self.device_relays[device_id]

    def set_relay_state(self, device_id, state, reason="Comando de usuario", mode="MANUAL"):
        """Modifica el estado del relé (1=Cerrar/Conectar, 0=Abrir/Desconectar)."""
        info = self.get_relay_state(device_id)
        old_state = info["state"]
        info["state"] = 1 if state in [1, True, "1", "ON"] else 0
        info["mode"] = mode
        info["reason"] = reason
        info["last_change"] = datetime.now(timezone.utc).isoformat()

        if old_state != info["state"]:
            if info["state"] == 0:
                info["trip_count"] += 1
                # Alerta Syslog prioritaria
                msg = f"[LOAD_DISCONNECT] Carga DESCONECTADA en '{device_id}'. Causa: {reason} (Modo: {mode})"
                syslog_client.send_log(
                    facility=SyslogFacility.LOCAL2,
                    severity=SyslogSeverity.CRITICAL,
                    message=msg,
                    msg_id="RELAY_TRIP",
                )
                # Notificación SNMP Trap
                snmp_agent.send_snmp_trap(
                    trap_oid="1.3.6.1.4.1.58888.1.4.0",
                    description=f"Desconexión de carga en {device_id}: {reason}",
                    severity="CRITICAL",
                )
            else:
                msg = f"[LOAD_RECONNECT] Carga RECONECTADA en '{device_id}'. Causa: {reason} (Modo: {mode})"
                syslog_client.send_log(
                    facility=SyslogFacility.LOCAL2,
                    severity=SyslogSeverity.NOTICE,
                    message=msg,
                    msg_id="RELAY_RESTORE",
                )

        return info

    def evaluate_automatic_cutoff(self, device_id, current, is_ai_anomaly, reason="Sobrecarga detectada"):
        """
        Evalúa si procede desconexión de emergencia basada en reglas físicas y predicción de IA.
        """
        # Si la corriente excede 35A o el modelo de IA clasifica como sobrecarga severa
        if current > 35.0 or is_ai_anomaly:
            return self.set_relay_state(
                device_id=device_id,
                state=0,
                reason=f"DESCONEXIÓN AUTOMATIZADA: {reason} (Corriente: {current:.1f}A)",
                mode="AUTOMATIC_AI",
            )
        return self.get_relay_state(device_id)


# Instancia singleton del servicio de desconexión
disconnection_service = LoadDisconnectionService()

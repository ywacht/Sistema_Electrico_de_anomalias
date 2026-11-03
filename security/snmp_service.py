"""
EcoGrid AI - Agente y Gestor de Eventos SNMP (v2c)
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)

Monitoreo de parámetros de red eléctrica y despacho de SNMP Traps ante:
- Disparo y desconexión automatizada de cargas por sobrecarga
- Ataques de Denegación de Servicio (DoS) detectados
- Activaciones de trampas Honeypot
"""

import socket
import struct
import time
from datetime import datetime, timezone


# OIDs de la MIB Privada de EcoGrid AI (Enterprise: 1.3.6.1.4.1.58888)
ECOGRID_MIB = {
    "1.3.6.1.4.1.58888.1.1.0": {"name": "gridVoltage", "type": "Gauge32", "unit": "V"},
    "1.3.6.1.4.1.58888.1.2.0": {"name": "gridCurrent", "type": "Gauge32", "unit": "A"},
    "1.3.6.1.4.1.58888.1.3.0": {"name": "gridActivePower", "type": "Gauge32", "unit": "W"},
    "1.3.6.1.4.1.58888.1.4.0": {"name": "relayStatus", "type": "Integer32", "unit": "1=ON, 0=OFF"},
    "1.3.6.1.4.1.58888.2.1.0": {"name": "dosAttackCount", "type": "Counter32", "unit": "events"},
    "1.3.6.1.4.1.58888.2.2.0": {"name": "honeypotTrapCount", "type": "Counter32", "unit": "hits"},
    "1.3.6.1.4.1.58888.2.3.0": {"name": "blockedIPCount", "type": "Counter32", "unit": "ips"},
}


class EcoGridSNMPAgent:
    """
    Agente SNMP virtual y despachador de traps para integración con software NMS
    (Nagios, Zabbix, PRTG, SolarWinds).
    """

    def __init__(self, community="public", trap_receiver="127.0.0.1", trap_port=162):
        self.community = community
        self.trap_receiver = trap_receiver
        self.trap_port = trap_port
        
        # Estado interno de la MIB
        self.mib_values = {
            "1.3.6.1.4.1.58888.1.1.0": 120.0,
            "1.3.6.1.4.1.58888.1.2.0": 5.2,
            "1.3.6.1.4.1.58888.1.3.0": 610.0,
            "1.3.6.1.4.1.58888.1.4.0": 1,
            "1.3.6.1.4.1.58888.2.1.0": 0,
            "1.3.6.1.4.1.58888.2.2.0": 0,
            "1.3.6.1.4.1.58888.2.3.0": 0,
        }
        self.trap_log = []

    def update_telemetry_mib(self, voltage, current, power, relay_state):
        """Actualiza los valores de la MIB eléctrica."""
        self.mib_values["1.3.6.1.4.1.58888.1.1.0"] = float(voltage)
        self.mib_values["1.3.6.1.4.1.58888.1.2.0"] = float(current)
        self.mib_values["1.3.6.1.4.1.58888.1.3.0"] = float(power)
        self.mib_values["1.3.6.1.4.1.58888.1.4.0"] = int(relay_state)

    def increment_counter(self, counter_name):
        """Incrementa contadores de incidentes de seguridad."""
        oid_map = {
            "dos": "1.3.6.1.4.1.58888.2.1.0",
            "honeypot": "1.3.6.1.4.1.58888.2.2.0",
            "blocked": "1.3.6.1.4.1.58888.2.3.0",
        }
        oid = oid_map.get(counter_name)
        if oid and oid in self.mib_values:
            self.mib_values[oid] += 1

    def send_snmp_trap(self, trap_oid, description, severity="CRITICAL"):
        """
        Genera y despacha un SNMP Trap v2c hacia el NMS configurado.
        """
        now = datetime.now(timezone.utc).isoformat()
        trap_entry = {
            "timestamp": now,
            "trap_oid": trap_oid,
            "severity": severity,
            "description": description,
            "community": self.community,
            "target": f"{self.trap_receiver}:{self.trap_port}",
        }
        self.trap_log.append(trap_entry)
        if len(self.trap_log) > 100:
            self.trap_log.pop(0)

        # Simulación de emisión por socket UDP 162
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.3)
            # Payload de demostración de trap SNMP
            payload = f"SNMPv2-TRAP: {trap_oid} [{severity}] {description}".encode("utf-8")
            sock.sendto(payload, (self.trap_receiver, self.trap_port))
            sock.close()
        except Exception:
            pass

        return trap_entry

    def get_all_mib(self):
        """Retorna todos los valores actuales de la MIB."""
        result = {}
        for oid, meta in ECOGRID_MIB.items():
            result[oid] = {
                "name": meta["name"],
                "value": self.mib_values.get(oid, 0),
                "type": meta["type"],
                "unit": meta["unit"],
            }
        return result

    def get_trap_history(self, limit=30):
        """Retorna el historial reciente de traps enviados."""
        return self.trap_log[-limit:][::-1]


# Instancia singleton del agente SNMP
snmp_agent = EcoGridSNMPAgent()

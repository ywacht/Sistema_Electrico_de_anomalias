"""
EcoGrid AI - Sistema de Detección y Mitigación de Ataques DoS
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)

Aseguramiento de la infraestructura contra ataques de denegación de servicio (DoS)
mediante limitación de tasa por ventana deslizante, baneo dinámico de IPs y alertas Syslog/SNMP.
"""

import time
from collections import defaultdict
from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity
from security.snmp_service import snmp_agent


class DoSProtectionEngine:
    """
    Motor de mitigación de ataques DoS en tiempo real.
    """

    def __init__(self, max_req_per_second=20, max_req_per_minute=100, ban_duration_seconds=300):
        self.max_req_per_second = max_req_per_second
        self.max_req_per_minute = max_req_per_minute
        self.ban_duration_seconds = ban_duration_seconds

        # Registros de timestamps por IP
        self.request_timestamps = defaultdict(list)
        # Diccionario de IPs bloqueadas: {ip: timestamp_fin_bloqueo}
        self.banned_ips = {}
        # Estadísticas de ataques
        self.attack_stats = {
            "total_requests_analyzed": 0,
            "total_blocked_requests": 0,
            "total_attacks_detected": 0,
            "currently_banned_ips": 0,
        }

    def is_ip_banned(self, ip):
        """Verifica si la IP se encuentra en la lista negra activa."""
        now = time.time()
        if ip in self.banned_ips:
            ban_until = self.banned_ips[ip]
            if now < ban_until:
                return True
            else:
                # El tiempo de ban expiró
                del self.banned_ips[ip]
                self.attack_stats["currently_banned_ips"] = len(self.banned_ips)
        return False

    def ban_ip(self, ip, reason="Ataque DoS por inundación de peticiones", duration=None):
        """Bloquea manualmente o automáticamente una dirección IP sospechosa."""
        duration = duration or self.ban_duration_seconds
        now = time.time()
        self.banned_ips[ip] = now + duration
        self.attack_stats["total_attacks_detected"] += 1
        self.attack_stats["currently_banned_ips"] = len(self.banned_ips)

        # 1. Alerta Syslog inmediata
        msg = f"[DOS_ATTACK_MITIGATION] IP {ip} ha sido BLOQUEADA temporalmente por {duration}s. Causa: {reason}"
        syslog_client.send_log(
            facility=SyslogFacility.LOCAL1,
            severity=SyslogSeverity.ALERT,
            message=msg,
            msg_id="DOS_BLOCK",
        )

        # 2. Despacho de SNMP Trap y contador
        snmp_agent.increment_counter("dos")
        snmp_agent.increment_counter("blocked")
        snmp_agent.send_snmp_trap(
            trap_oid="1.3.6.1.4.1.58888.2.1.0",
            description=f"DoS Flood detectado desde IP {ip}. IP agregada a lista negra.",
            severity="ALERT",
        )

    def check_request(self, ip, endpoint=""):
        """
        Analiza cada petición entrante.
        Retorna:
            (allowed: bool, reason: str, status_code: int)
        """
        self.attack_stats["total_requests_analyzed"] += 1
        now = time.time()

        # 1. Si la IP ya está bloqueada
        if self.is_ip_banned(ip):
            self.attack_stats["total_blocked_requests"] += 1
            return False, "IP Bloqueada por políticas de defensa DoS", 403

        # 2. Limpieza de ventana deslizante (último minuto)
        history = self.request_timestamps[ip]
        self.request_timestamps[ip] = [t for t in history if now - t < 60.0]
        self.request_timestamps[ip].append(now)

        timestamps = self.request_timestamps[ip]

        # 3. Verificación de tasa por segundo (último 1.0s)
        recent_second_count = sum(1 for t in timestamps if now - t <= 1.0)
        if recent_second_count > self.max_req_per_second:
            self.ban_ip(ip, reason=f"Inundación volumétrica rápida ({recent_second_count} req/seg)")
            self.attack_stats["total_blocked_requests"] += 1
            return False, "Límite de tasa por segundo superado (Posible DoS)", 429

        # 4. Verificación de tasa por minuto
        if len(timestamps) > self.max_req_per_minute:
            self.ban_ip(ip, reason=f"Tasa excesiva por minuto ({len(timestamps)} req/min)")
            self.attack_stats["total_blocked_requests"] += 1
            return False, "Límite de tasa por minuto superado (Posible DoS)", 429

        return True, "Permitido", 200

    def unban_ip(self, ip):
        """Elimina una IP de la lista de bloqueo."""
        if ip in self.banned_ips:
            del self.banned_ips[ip]
            self.attack_stats["currently_banned_ips"] = len(self.banned_ips)
            return True
        return False

    def get_stats(self):
        """Retorna estadísticas del estado de protección DoS."""
        now = time.time()
        active_bans = {}
        for ip, until in list(self.banned_ips.items()):
            remaining = int(max(0, until - now))
            if remaining > 0:
                active_bans[ip] = {"remaining_seconds": remaining}
            else:
                del self.banned_ips[ip]

        self.attack_stats["currently_banned_ips"] = len(active_bans)
        return {
            "attack_stats": self.attack_stats,
            "active_bans": active_bans,
            "thresholds": {
                "max_req_per_second": self.max_req_per_second,
                "max_req_per_minute": self.max_req_per_minute,
                "ban_duration_seconds": self.ban_duration_seconds,
            },
        }


# Instancia singleton del motor DoS
dos_engine = DoSProtectionEngine()

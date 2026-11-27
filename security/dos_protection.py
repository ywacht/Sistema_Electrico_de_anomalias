"""
EcoGrid AI - Sistema de Detección y Mitigación de Ataques DoS
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)

Mitigación de DoS por ventana deslizante, con tres mecanismos para no bloquear
tráfico legítimo de nodos ESP32 (reales y simulados):

  1. IPs de confianza (DOS_TRUSTED_IPS): gateways / simuladores conocidos. NO quedan
     exentos: tienen un multiplicador de límites (por defecto x5), así un nodo
     comprometido sigue siendo detectable.
  2. Cubeta separada para telemetría (DOS_TELEMETRY_PREFIXES): las rutas de ingesta
     tienen límites propios más altos y no consumen la cuota del resto de la API.
  3. Sistema de "strikes": superar un límite devuelve 429 (el ESP32 puede reintentar),
     pero el baneo solo ocurre tras varias violaciones repetidas en poco tiempo.
     Una ráfaga aislada ya no bloquea a nadie.

Todo se puede ajustar por variables de entorno sin tocar el código.
"""

import ipaddress
import os
import threading
import time
from collections import defaultdict, deque

from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity
from security.snmp_service import snmp_agent


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _parse_networks(raw):
    """Convierte 'ip1,192.168.1.0/24,...' en una lista de redes (acepta IP suelta o CIDR)."""
    networks = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            print(f"[DOS] Entrada inválida en DOS_TRUSTED_IPS ignorada: {item!r}")
    return networks


def _parse_prefixes(raw):
    return tuple(p.strip() for p in (raw or "").split(",") if p.strip())


class DoSProtectionEngine:
    """
    Motor de mitigación de ataques DoS en tiempo real.
    """

    def __init__(
        self,
        max_req_per_second=None,
        max_req_per_minute=None,
        ban_duration_seconds=None,
        telemetry_max_per_second=None,
        telemetry_max_per_minute=None,
        trusted_multiplier=None,
        strikes_to_ban=None,
        strike_window_seconds=None,
    ):
        # Límites generales (resto de la API) por IP
        self.max_req_per_second = max_req_per_second or _env_int("DOS_MAX_PER_SECOND", 60)
        self.max_req_per_minute = max_req_per_minute or _env_int("DOS_MAX_PER_MINUTE", 600)
        self.ban_duration_seconds = ban_duration_seconds or _env_int("DOS_BAN_SECONDS", 300)

        # Límites para rutas de telemetría por IP (varios nodos pueden compartir IP/gateway).
        # Ej.: 20 nodos a 1 req/seg = 20 req/s y 1200 req/min desde una sola IP.
        self.telemetry_max_per_second = telemetry_max_per_second or _env_int("DOS_TELEMETRY_PER_SECOND", 50)
        self.telemetry_max_per_minute = telemetry_max_per_minute or _env_int("DOS_TELEMETRY_PER_MINUTE", 2000)

        # IPs de confianza: límites multiplicados (no exentas)
        self.trusted_multiplier = trusted_multiplier or _env_int("DOS_TRUSTED_MULTIPLIER", 5)
        self.trusted_networks = _parse_networks(os.getenv("DOS_TRUSTED_IPS", "127.0.0.1,::1"))

        # Prefijos de rutas de ingesta de telemetría (AJUSTAR a tus rutas reales en app.py)
        self.telemetry_prefixes = _parse_prefixes(
            os.getenv("DOS_TELEMETRY_PREFIXES", "/api/telemetry,/api/ingest,/api/actuators/relay,/api/sensor,/api/esp32,/api/data")
        )

        # Strikes: violaciones necesarias para banear, dentro de la ventana
        self.strikes_to_ban = strikes_to_ban or _env_int("DOS_STRIKES_TO_BAN", 5)
        self.strike_window_seconds = strike_window_seconds or _env_int("DOS_STRIKE_WINDOW", 30)

        self._lock = threading.RLock()
        self._last_cleanup = time.time()

        # Timestamps por (ip, cubeta) -> deque
        self.request_timestamps = defaultdict(deque)
        # Violaciones recientes por IP
        self.violations = defaultdict(deque)
        # IPs bloqueadas: {ip: timestamp_fin_bloqueo}
        self.banned_ips = {}
        self.attack_stats = {
            "total_requests_analyzed": 0,
            "total_blocked_requests": 0,
            "total_attacks_detected": 0,
            "currently_banned_ips": 0,
        }

    # ------------------------------------------------------------------ helpers
    def is_trusted_ip(self, ip):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in self.trusted_networks)

    def _limits_for(self, ip, endpoint):
        """Devuelve (cubeta, límite_por_seg, límite_por_min) según IP y ruta."""
        if endpoint and endpoint.startswith(self.telemetry_prefixes) and self.telemetry_prefixes:
            bucket, per_sec, per_min = "telemetry", self.telemetry_max_per_second, self.telemetry_max_per_minute
        else:
            bucket, per_sec, per_min = "general", self.max_req_per_second, self.max_req_per_minute

        if self.is_trusted_ip(ip):
            per_sec *= self.trusted_multiplier
            per_min *= self.trusted_multiplier
        return bucket, per_sec, per_min

    def _cleanup(self, now):
        """Libera memoria de IPs inactivas (se ejecuta como máximo una vez por minuto)."""
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        for key in list(self.request_timestamps.keys()):
            window = self.request_timestamps[key]
            while window and now - window[0] >= 60.0:
                window.popleft()
            if not window:
                del self.request_timestamps[key]
        for ip in list(self.violations.keys()):
            strikes = self.violations[ip]
            while strikes and now - strikes[0] >= self.strike_window_seconds:
                strikes.popleft()
            if not strikes:
                del self.violations[ip]

    # ------------------------------------------------------------------ bans
    def is_ip_banned(self, ip):
        """Verifica si la IP se encuentra en la lista negra activa."""
        with self._lock:
            now = time.time()
            if ip in self.banned_ips:
                if now < self.banned_ips[ip]:
                    return True
                del self.banned_ips[ip]
                self.attack_stats["currently_banned_ips"] = len(self.banned_ips)
            return False

    def ban_ip(self, ip, reason="Ataque DoS por inundación de peticiones", duration=None):
        """Bloquea manualmente o automáticamente una dirección IP sospechosa."""
        duration = duration or self.ban_duration_seconds
        with self._lock:
            self.banned_ips[ip] = time.time() + duration
            self.attack_stats["total_attacks_detected"] += 1
            self.attack_stats["currently_banned_ips"] = len(self.banned_ips)
            self.violations.pop(ip, None)

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

    def unban_ip(self, ip):
        """Elimina una IP de la lista de bloqueo."""
        with self._lock:
            self.violations.pop(ip, None)
            if ip in self.banned_ips:
                del self.banned_ips[ip]
                self.attack_stats["currently_banned_ips"] = len(self.banned_ips)
                return True
            return False

    # ------------------------------------------------------------------ análisis
    def check_request(self, ip, endpoint=""):
        """
        Analiza cada petición entrante.
        Retorna:
            (allowed: bool, reason: str, status_code: int)
        """
        with self._lock:
            now = time.time()
            self.attack_stats["total_requests_analyzed"] += 1
            self._cleanup(now)

            # 1. IP ya bloqueada
            if self.is_ip_banned(ip):
                self.attack_stats["total_blocked_requests"] += 1
                return False, "IP Bloqueada por políticas de defensa DoS", 403

            # 2. Ventana deslizante por (IP, cubeta)
            bucket, per_sec, per_min = self._limits_for(ip, endpoint)
            window = self.request_timestamps[(ip, bucket)]
            while window and now - window[0] >= 60.0:
                window.popleft()

            recent_second = 0
            for t in reversed(window):
                if now - t > 1.0:
                    break
                recent_second += 1

            over_second = recent_second + 1 > per_sec
            over_minute = len(window) + 1 > per_min

            if not over_second and not over_minute:
                window.append(now)
                return True, "Permitido", 200

            # 3. Violación: la petición rechazada NO se registra en la ventana,
            #    así un cliente legítimo se recupera en cuanto baja su ritmo.
            self.attack_stats["total_blocked_requests"] += 1
            if over_second:
                reason = f"Tasa por segundo excedida en '{bucket}' ({recent_second + 1} req/seg, límite {per_sec})"
            else:
                reason = f"Tasa por minuto excedida en '{bucket}' ({len(window) + 1} req/min, límite {per_min})"

            strikes = self.violations[ip]
            while strikes and now - strikes[0] >= self.strike_window_seconds:
                strikes.popleft()
            strikes.append(now)

            # 4. Baneo solo ante violaciones repetidas (ataque sostenido)
            if len(strikes) >= self.strikes_to_ban:
                self.ban_ip(
                    ip,
                    reason=f"{len(strikes)} violaciones de tasa en {self.strike_window_seconds}s. Última: {reason}",
                )
                return False, "Límite de tasa superado de forma sostenida (Posible DoS)", 429

            return False, "Límite de tasa superado, reduzca la frecuencia de envío", 429

    def get_stats(self):
        """Retorna estadísticas del estado de protección DoS."""
        with self._lock:
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
                "attack_stats": dict(self.attack_stats),
                "active_bans": active_bans,
                "thresholds": {
                    "max_req_per_second": self.max_req_per_second,
                    "max_req_per_minute": self.max_req_per_minute,
                    "telemetry_max_per_second": self.telemetry_max_per_second,
                    "telemetry_max_per_minute": self.telemetry_max_per_minute,
                    "trusted_multiplier": self.trusted_multiplier,
                    "strikes_to_ban": self.strikes_to_ban,
                    "strike_window_seconds": self.strike_window_seconds,
                    "ban_duration_seconds": self.ban_duration_seconds,
                },
                "trusted_networks": [str(n) for n in self.trusted_networks],
                "telemetry_prefixes": list(self.telemetry_prefixes),
            }


# Instancia singleton del motor DoS
dos_engine = DoSProtectionEngine()
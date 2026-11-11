"""
EcoGrid AI - Herramienta de Demostración de Seguridad Cibernética
Asignatura: Seguridad Informática (SW)
Universidad Tecnológica de Calvillo (UTC)

Ejecuta pruebas automatizadas de:
1. Intrusión en Trampa Honeypot (Acceso a falsas interfaces SCADA/Modbus)
2. Ataque volumétrico DoS (Inundación de peticiones HTTP para activar el baneo)
3. Consulta del estado de Syslog y Traps SNMP generados
"""

import time
import requests
import sys

API_BASE = "http://127.0.0.1:5000"


def test_honeypot():
    print("\n" + "=" * 65)
    print("  [PRUEBA 1] ACTIVACIÓN DE TRAMPA HONEYPOT SCADA / IOT")
    print("=" * 65)

    decoy_urls = [
        f"{API_BASE}/admin",
        f"{API_BASE}/scada/admin",
        f"{API_BASE}/firmware/update",
    ]

    for url in decoy_urls:
        print(f"\n[ATACANTE SIMULADO] Sondeando endpoint señuelo: {url}")
        try:
            resp = requests.post(
                url,
                data={"username": "admin", "password": "' OR '1'='1"},
                headers={"User-Agent": "Nmap-Scripting-Engine / Metasploit"},
                timeout=3,
            )
            print(f"  -> Código HTTP recibido: {resp.status_code}")
            print(f"  -> Respuesta recibida (primeros 120 caracteres): {resp.text[:120].strip()}...")
        except Exception as e:
            print(f"  -> Error: {e}")

    # Verificar que el Honeypot registró la intrusión
    time.sleep(0.5)
    try:
        r_hp = requests.get(f"{API_BASE}/api/security/honeypot", timeout=3)
        if r_hp.status_code == 200:
            stats = r_hp.json()
            print(f"\n[DEFENSA HONEYPOT] Total de atacantes atrapados: {stats['total_trapped_attackers']}")
            if stats["recent_intrusions"]:
                latest = stats["recent_intrusions"][0]
                print(f"  -> Último atacante registrado: IP={latest['attacker_ip']}, Ruta={latest['target_path']}")
                print(f"  -> Acción ejecutada: {latest['action_taken']}")
    except Exception as e:
        print(f"Error consultando estadísticas del Honeypot: {e}")


def test_dos_flood():
    print("\n" + "=" * 65)
    print("  [PRUEBA 2] PRUEBA DE ATAQUE DE DENEGACIÓN DE SERVICIO (DOS)")
    print("=" * 65)
    print("Enviando ráfaga rápida de 25 peticiones en < 1 segundo para disparar protección...")

    blocked_count = 0
    success_count = 0

    for i in range(1, 26):
        try:
            r = requests.get(f"{API_BASE}/api/telemetry/latest", timeout=2)
            if r.status_code == 200:
                success_count += 1
            elif r.status_code in [403, 429]:
                blocked_count += 1
                if blocked_count == 1:
                    print(f"  [BLOQUEO ACTIVADO] En petición #{i}: Código HTTP {r.status_code} ({r.json().get('reason', '')})")
        except Exception:
            pass

    print(f"\n[RESULTADO DOS] Peticiones permitidas: {success_count} | Peticiones BLOQUEADAS: {blocked_count}")


def show_security_status():
    print("\n" + "=" * 65)
    print("  [AUDITORÍA] ESTADO DE EVENTOS SYSLOG Y SNMP")
    print("=" * 65)
    try:
        r_syslog = requests.get(f"{API_BASE}/api/security/syslog?limit=5", timeout=3)
        if r_syslog.status_code == 200:
            events = r_syslog.json().get("events", [])
            print(f"\nÚltimos {len(events)} eventos Syslog (RFC 5424):")
            for ev in events:
                print(f"  [{ev['severity_name']:8}] {ev['timestamp']} | {ev['message']}")

        r_snmp = requests.get(f"{API_BASE}/api/security/snmp", timeout=3)
        if r_snmp.status_code == 200:
            snmp_data = r_snmp.json()
            print("\nValores de la MIB SNMP (1.3.6.1.4.1.58888):")
            for oid, item in snmp_data["mib_objects"].items():
                print(f"  - {item['name']:18} ({oid}): {item['value']} {item['unit']}")
    except Exception as e:
        print(f"Error consultando auditoría: {e}")


if __name__ == "__main__":
    test_honeypot()
    test_dos_flood()
    show_security_status()

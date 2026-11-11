"""
EcoGrid AI - Validación de Trampa Honeypot con Herramientas de Ciberseguridad (BlackArch)
Universidad Tecnológica de Calvillo (UTC)
"""

import os
import sys
import time
import subprocess
import requests
import json
from threading import Thread

# Asegurar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app

PORT = 5055
BASE_URL = f"http://127.0.0.1:{PORT}"


def run_test_server():
    app = create_app()
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


def main():
    print("=" * 70)
    print("  ECOGRID AI - VALIDACIÓN DE HONEYPOT Y SEGURIDAD INFORMÁTICA")
    print("=" * 70)

    # 1. Iniciar servidor en hilo secundario
    server_thread = Thread(target=run_test_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    # Verificar que el servidor responde
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        print(f"[SERVIDOR] EcoGrid AI escuchando en {BASE_URL} (Status: {r.status_code})")
    except Exception as e:
        print(f"[ERROR] No se pudo iniciar el servidor de prueba: {e}")
        return 1

    # 2. Crear diccionario para escaneo de directorios
    wordlist_path = "/tmp/ecogrid_honeypot_wordlist.txt"
    with open(wordlist_path, "w", encoding="utf-8") as f:
        f.write("\n".join([
            "index",
            "admin",
            "admin/login",
            "scada/admin",
            "scada/config",
            "modbus/gateway",
            "plc/control",
            "firmware/update",
            "ota/esp32",
            "api/telemetry",
            "health",
            "robots.txt"
        ]) + "\n")

    # 3. Validar con GOBUSTER (si está disponible)
    gobuster_bin = "/usr/sbin/gobuster"
    if os.path.exists(gobuster_bin):
        print("\n" + "-" * 70)
        print(f"[BLACKARCH TOOL] Ejecutando Gobuster: descubrimiento de rutas señuelo...")
        print("-" * 70)
        cmd = [
            gobuster_bin, "dir",
            "-u", BASE_URL,
            "-w", wordlist_path,
            "-t", "2",
            "--delay", "50ms",
            "-q"
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            print(res.stdout.strip() if res.stdout else "[Gobuster completó escaneo]")
            if res.stderr:
                print(f"[Gobuster stderr]: {res.stderr.strip()}")
        except Exception as e:
            print(f"[Gobuster info]: {e}")
    else:
        print("\n[INFO] Gobuster no encontrado en /usr/sbin/gobuster.")

    # 4. Validar con HYDRA (fuerza bruta contra /admin/login)
    hydra_bin = "/usr/sbin/hydra"
    user_file = "/tmp/hydra_users.txt"
    pass_file = "/tmp/hydra_passes.txt"
    with open(user_file, "w") as f:
        f.write("admin\nroot\noperator\n")
    with open(pass_file, "w") as f:
        f.write("123456\nadmin\nscada2026\n")

    if os.path.exists(hydra_bin):
        print("\n" + "-" * 70)
        print(f"[BLACKARCH TOOL] Ejecutando Hydra: fuerza bruta HTTP contra /admin/login...")
        print("-" * 70)
        # Formato hydra para http-post-form
        cmd_hydra = [
            hydra_bin,
            "-L", user_file,
            "-P", pass_file,
            "-s", str(PORT),
            "127.0.0.1",
            "http-post-form",
            "/admin/login:username=^USER^&password=^PASS^:F=invalid",
            "-t", "1"
        ]
        try:
            res_hydra = subprocess.run(cmd_hydra, capture_output=True, text=True, timeout=10)
            print(res_hydra.stdout.strip() if res_hydra.stdout else "[Hydra completó el intento de intrusión]")
        except Exception as e:
            print(f"[Hydra info]: {e}")

    from security.dos_protection import dos_engine

    # Desbloquear 127.0.0.1 para permitir consultar la auditoría
    dos_engine.unban_ip("127.0.0.1")

    # 5. Simulación directa vía endpoint POST /api/security/honeypot/simulate
    print("\n" + "-" * 70)
    print("[ENDPOINT SIMULATE] Inyectando vector de ataque directo vía POST /api/security/honeypot/simulate...")
    print("-" * 70)
    sim_payload = {
        "ip": "45.33.12.9",
        "path": "/scada/admin",
        "payload": {"action": "override_safety", "relay_bypass": True}
    }
    r_sim = requests.post(f"{BASE_URL}/api/security/honeypot/simulate", json=sim_payload, timeout=3)
    print(f"Respuesta simulate ({r_sim.status_code}): {r_sim.json()}")

    # Desbloquear nuevamente si hiciera falta
    dos_engine.unban_ip("127.0.0.1")

    # 6. Consultar evidencia en GET /api/security/honeypot
    print("\n" + "-" * 70)
    print("[EVIDENCIA AUDITORÍA] Consultando registros capturados en GET /api/security/honeypot:")
    print("-" * 70)
    r_hp = requests.get(f"{BASE_URL}/api/security/honeypot", timeout=3)
    hp_data = r_hp.json()
    print(f"Total de atacantes atrapados: {hp_data.get('total_trapped_attackers')}")
    recent = hp_data.get("recent_intrusions", [])
    print(f"Número de intrusiones recientes en el registro: {len(recent)}")
    for i, intr in enumerate(recent[:8], 1):
        print(f"  [{i}] IP: {intr.get('attacker_ip'):15} | Ruta: {intr.get('target_path'):18} | "
              f"Método: {intr.get('http_method'):4} | Agente: {intr.get('user_agent')[:30]:30} | "
              f"Acción: {intr.get('action_taken')}")

    print("=" * 70)
    print("  VALIDACIÓN DEL HONEYPOT COMPLETADA EXITOSAMENTE")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    exit(main())

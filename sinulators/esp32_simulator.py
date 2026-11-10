"""
===================================================================================
EcoGrid AI - Simulador Virtual de Nodos ESP32
Universidad Tecnológica de Calvillo (UTC)
===================================================================================

Permite ejecutar telemetría continua de nodos ESP32 con inyección interactiva de anomalías:
- normal: operación estable (4.0 - 8.5 A)
- pico: picos de demanda (20.0 - 26.5 A)
- sobrecarga: sobrecarga severa (> 35 A, provoca desconexión automatizada)
- fuga: fuga / consumo parásito
- minimal / single_esp32: emula exactamente el ESP32 físico único (solo current + relay_state),
  validando el enriquecimiento sintético del backend.

Uso por línea de comandos:
  python esp32_simulator.py normal
  python esp32_simulator.py sobrecarga
  python esp32_simulator.py minimal
  python esp32_simulator.py pico --minimal
"""

import time
import random
import requests
import sys

API_BASE = "http://127.0.0.1:5000"


def simulate_node(device_id="esp32_sensor_01", location="Subestación Acometida - ACS712",
                  mode="normal", iterations=15, minimal_payload=False):
    print(f"\n[SIMULADOR_ESP32] Iniciando transmisión para '{device_id}' ({location})")
    print(f"[SIMULADOR_ESP32] Modo: {mode.upper()} | Carga mínima (Solo HW real): {minimal_payload}")
    print(f"[SIMULADOR_ESP32] Destino: {API_BASE}/api/telemetry")
    print("-" * 75)

    relay_state = 1

    for step in range(1, iterations + 1):
        # Primero consultar si el relé fue cortado por la nube
        try:
            r_rel = requests.get(f"{API_BASE}/api/actuators/relay/{device_id}", timeout=2)
            if r_rel.status_code == 200:
                relay_state = r_rel.json().get("relay_state", 1)
        except Exception:
            pass

        # Generar valores eléctricos según el modo y estado de relé
        if relay_state == 0:
            # Carga desconectada por el actuador de seguridad
            voltage = round(random.uniform(120.0, 122.0), 1)
            current = 0.0
            pf = 0.98
            thd = 1.5
            temp = round(random.uniform(26.0, 28.0), 1)
            state_label = "[CARGA DESCONECTADA]"
        elif mode in ("normal", "minimal", "single_esp32"):
            voltage = round(random.uniform(118.5, 122.5), 1)
            current = round(random.uniform(4.0, 8.5), 2)
            pf = round(random.uniform(0.92, 0.97), 2)
            thd = round(random.uniform(2.5, 4.5), 1)
            temp = round(random.uniform(30.0, 34.0), 1)
            state_label = "NORMAL"
        elif mode == "pico":
            voltage = round(random.uniform(115.0, 118.5), 1)
            current = round(random.uniform(20.0, 26.5), 2)
            pf = round(random.uniform(0.88, 0.94), 2)
            thd = round(random.uniform(5.0, 8.0), 1)
            temp = round(random.uniform(46.0, 52.0), 1)
            state_label = "PICO DE DEMANDA"
        elif mode == "sobrecarga":
            voltage = round(random.uniform(108.0, 114.0), 1)
            current = round(random.uniform(36.0, 48.0), 2)  # Dispara corte
            pf = round(random.uniform(0.70, 0.82), 2)
            thd = round(random.uniform(15.0, 26.0), 1)
            temp = round(random.uniform(68.0, 82.0), 1)
            state_label = "¡SOBRECARGA CRÍTICA!"
        elif mode == "fuga":
            voltage = round(random.uniform(120.0, 122.0), 1)
            current = round(random.uniform(1.2, 2.8), 2)
            pf = round(random.uniform(0.55, 0.72), 2)
            thd = round(random.uniform(9.0, 14.0), 1)
            temp = round(random.uniform(28.0, 31.0), 1)
            state_label = "FUGA / PARÁSITO"
        else:
            voltage = 120.0
            current = round(random.uniform(3.0, 7.0), 2)
            pf = 0.95
            thd = 3.0
            temp = 29.0
            state_label = mode.upper()

        active_power = round(voltage * current * pf, 1)

        # Si está activado minimal_payload, solo enviamos current + relay_state
        # (exactamente igual al hardware físico real con sensor único ACS712)
        if minimal_payload or mode in ("minimal", "single_esp32"):
            payload = {
                "device_id": device_id,
                "location": location,
                "current": current,
                "relay_state": relay_state,
            }
        else:
            payload = {
                "device_id": device_id,
                "location": location,
                "voltage": voltage,
                "current": current,
                "active_power": active_power,
                "power_factor": pf,
                "frequency": 60.0,
                "thd": thd,
                "temperature": temp,
                "relay_state": relay_state,
            }

        try:
            resp = requests.post(f"{API_BASE}/api/telemetry", json=payload, timeout=3)
            if resp.status_code == 201:
                res_data = resp.json()
                ai_class = res_data.get("ai_evaluation", {}).get("class_name", "N/A")
                new_relay = res_data.get("relay_state", 1)
                is_enriched = res_data.get("synthetic_enrichment", False)
                relay_state = new_relay

                enrich_tag = "[SINTÉTICO]" if is_enriched else "[COMPLETO]"
                print(
                    f"[{step:02d}/{iterations}] {device_id} | I={current:5.2f}A | "
                    f"Modo: {state_label:20} -> IA: {ai_class:20} | Relé: {new_relay} | {enrich_tag}"
                )
            else:
                print(f"[{step:02d}] Código HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[{step:02d}] Error conectando al backend: {e}")

        time.sleep(1.0)


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]
    minimal = any(a in ("--minimal", "-m", "--single-esp32", "minimal", "single_esp32") for a in args)

    target_mode = "normal"
    for a in args:
        if a not in ("--minimal", "-m", "--single-esp32"):
            target_mode = a
            break

    simulate_node(
        device_id="esp32_sensor_01",
        location="Subestación Acometida - ACS712",
        mode=target_mode,
        iterations=15,
        minimal_payload=minimal,
    )

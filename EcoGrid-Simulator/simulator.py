#!/usr/bin/env python3
"""EcoGrid AI - simulador de nodo ESP32. Requiere Python 3 y requests."""
import argparse
import json
import random
import threading
import time
import tkinter as tk
from tkinter import ttk

import requests

parser = argparse.ArgumentParser(description="Simula un nodo ESP32 de EcoGrid AI")
parser.add_argument("--id", default="esp32_virtual_01")
parser.add_argument("--host", default="http://127.0.0.1:5000", help="URL base de Flask")
parser.add_argument("--load", default="Ventilador")
parser.add_argument("--amps", type=float, default=0.45, help="Corriente normal de la carga, en amperios")
parser.add_argument("--threshold", type=float, default=1.5, help="Umbral de corte local en amperios")
parser.add_argument("--interval", type=float, default=2.0, help="Intervalo entre peticiones, segundos")
args = parser.parse_args()

DEVICE_ID, HOST, LOAD = args.id, args.host.rstrip("/"), args.load
BASE_AMPS, THRESHOLD, INTERVAL = args.amps, args.threshold, args.interval

state = {"relay": 1, "amps": BASE_AMPS, "wifi": True, "anomaly": False,
         "running": True, "last_message": "Inicializando", "last_http": "--"}
lock = threading.Lock()


def set_relay(on, reason):
    with lock:
        state["relay"] = 1 if on else 0
        state["last_message"] = reason


def simulate_current():
    with lock:
        enabled, anomalous = state["relay"], state["anomaly"]
    if not enabled:
        return max(0.0, random.gauss(0.008, 0.006))
    value = BASE_AMPS + random.gauss(0, max(0.01, BASE_AMPS * 0.04))
    if anomalous:
        value += max(THRESHOLD * 0.8, BASE_AMPS * 1.5)
    return max(0.0, value)


def network_worker():
    while state["running"]:
        current = simulate_current()
        # Fail-safe local, equivalente al corte local del firmware.
        with lock:
            relay = state["relay"]
        if current >= THRESHOLD and relay:
            set_relay(False, "Corte local: umbral excedido")

        with lock:
            relay = state["relay"]
            wifi = state["wifi"]
        if wifi:
            try:
                payload = {"device_id": DEVICE_ID, "current": round(current, 3),
                           "relay_state": relay}
                r = requests.post(HOST + "/api/telemetry", json=payload, timeout=2.5)
                with lock:
                    state["last_http"] = f"POST {r.status_code}"
                if r.status_code in (200, 201):
                    try:
                        answer = r.json()
                        if answer.get("should_disconnect") is True:
                            set_relay(False, "Orden de IA/servidor")
                        elif answer.get("should_disconnect") is False:
                            set_relay(True, "IA: sin anomalía")
                    except (ValueError, AttributeError):
                        pass

                # Consulta de órdenes del dashboard, como en el firmware.
                g = requests.get(HOST + f"/api/actuators/relay/{DEVICE_ID}", timeout=2.5)
                if g.status_code == 200:
                    data = g.json()
                    desired = data.get("relay_state")
                    with lock:
                        actual = state["relay"]
                    if desired in (0, 1) and desired != actual:
                        set_relay(bool(desired), "Orden del dashboard")
            except requests.RequestException as exc:
                with lock:
                    state["last_http"] = "Error de conexión"
                    state["last_message"] = str(exc)[:70]
        time.sleep(max(0.2, INTERVAL))


# GUI OLED (pixel grid) y representación simplificada de placa/protoboard.
root = tk.Tk()
root.title(f"EcoGrid AI | {DEVICE_ID}")
root.geometry("700x500")
root.configure(bg="#17212b")
root.protocol("WM_DELETE_WINDOW", lambda: (state.update(running=False), root.destroy()))

style = ttk.Style()
style.theme_use("clam")
style.configure("TFrame", background="#17212b")
style.configure("TLabel", background="#17212b", foreground="#e6edf3", font=("Arial", 11))
style.configure("Header.TLabel", font=("Arial", 16, "bold"))
style.configure("TButton", font=("Arial", 10))

frame = ttk.Frame(root, padding=16)
frame.pack(fill="both", expand=True)
title = ttk.Label(frame, text=f"NODO VIRTUAL | {DEVICE_ID}", style="Header.TLabel")
title.pack(pady=(0, 10))

middle = ttk.Frame(frame)
middle.pack(fill="both", expand=True)

board = tk.Canvas(middle, width=270, height=300, bg="#17212b", highlightthickness=0)
board.pack(side="left", padx=10)
# Placa ESP32 estilizada
board.create_rectangle(45, 30, 225, 255, fill="#146b52", outline="#69d5a5", width=2)
board.create_text(135, 45, text="ESP32  •  DEV BOARD", fill="white", font=("Arial", 11, "bold"))
board.create_rectangle(100, 85, 170, 155, fill="#273746", outline="#91a4b7", width=2)
board.create_text(135, 120, text="ESP32\nCPU", fill="#d7e5f2", font=("Arial", 10, "bold"))
for y in range(60, 230, 18):
    board.create_oval(55, y, 63, y+8, fill="#e6c65c", outline="")
    board.create_oval(207, y, 215, y+8, fill="#e6c65c", outline="")
board.create_rectangle(35, 265, 235, 292, fill="#d0d7de", outline="#718096")
board.create_text(135, 278, text="PROTOBOARD VIRTUAL", fill="#17212b", font=("Arial", 10, "bold"))
board.create_text(135, 20, text=f"Carga: {LOAD}  |  ACS712", fill="#8bd9ff", font=("Arial", 10))

panel = ttk.Frame(middle)
panel.pack(side="left", fill="both", expand=True, padx=10)
# OLED render con pixel font y fondo oscuro
screen = tk.Canvas(panel, width=256, height=128, bg="#001b12", highlightthickness=3,
                   highlightbackground="#4d8270")
screen.pack(pady=5)
info = ttk.Label(panel, text="", justify="left")
info.pack(pady=8, anchor="w")

buttons = ttk.Frame(frame)
buttons.pack(fill="x", pady=(12, 0))


def toggle_load():
    with lock:
        on = not bool(state["relay"])
    set_relay(on, "Interruptor local del simulador")


def toggle_anomaly():
    with lock:
        state["anomaly"] = not state["anomaly"]
        active = state["anomaly"]
    with lock:
        state["last_message"] = "Anomalía simulada activada" if active else "Anomalía simulada desactivada"


def toggle_wifi():
    with lock:
        state["wifi"] = not state["wifi"]
        active = state["wifi"]
        state["last_message"] = "WiFi simulado conectado" if active else "WiFi simulado desconectado"

ttk.Button(buttons, text="Conectar / desconectar carga", command=toggle_load).pack(side="left", padx=4)
ttk.Button(buttons, text="Simular anomalía", command=toggle_anomaly).pack(side="left", padx=4)
ttk.Button(buttons, text="WiFi ON/OFF", command=toggle_wifi).pack(side="left", padx=4)


def update_display():
    if not root.winfo_exists():
        return
    current = simulate_current()
    with lock:
        relay, wifi, anomaly, message, http_status = (state["relay"], state["wifi"],
            state["anomaly"], state["last_message"], state["last_http"])
    screen.delete("all")
    screen.create_text(8, 8, anchor="nw", text="EcoGrid | Corriente", fill="#5cffb0", font=("Courier", 11, "bold"))
    screen.create_text(8, 34, anchor="nw", text=f"{current:0.2f} A", fill="#5cffb0", font=("Courier", 24, "bold"))
    screen.create_text(8, 76, anchor="nw", text=f"Carga: {'ON' if relay else 'OFF'}", fill="#5cffb0", font=("Courier", 12))
    screen.create_text(8, 98, anchor="nw", text=f"WiFi: {'OK' if wifi else 'OFF'}", fill="#5cffb0", font=("Courier", 10))
    info.configure(text=f"Carga: {'CONECTADA' if relay else 'DESCONECTADA'}\n"
                       f"Sensor: ACS712 simulado | {BASE_AMPS:.2f} A nominal\n"
                       f"Umbral local: {THRESHOLD:.2f} A | PWM: {170 if relay else 0}\n"
                       f"HTTP: {http_status} | anomalía: {'sí' if anomaly else 'no'}\n"
                       f"Estado: {message}")
    root.after(400, update_display)

threading.Thread(target=network_worker, daemon=True).start()
update_display()
root.mainloop()
state["running"] = False

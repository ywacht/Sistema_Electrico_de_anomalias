"""
===================================================================================
EcoGrid AI - Módulo de Enriquecimiento Sintético de Telemetría Eléctrica
Universidad Tecnológica de Calvillo (UTC) - 7mo Cuatrimestre
===================================================================================

[AVISO DE ARQUITECTURA TEMPORAL / HARDWARE FAIL-OVER]:
-----------------------------------------------------------------------------------
Este módulo es una solución de contingencia TEMPORAL implementada debido a que uno
de los microcontroladores ESP32 sufrió una avería física (se quemó) durante las
pruebas de laboratorio. En consecuencia, el sistema opera actualmente con UN SOLO
nodo ESP32 físico equipado EXCLUSIVAMENTE con un sensor de corriente por efecto
Hall ACS712 y el actuador de relé para desconexión de cargas.

Al no contarse físicamente con sensores de tensión (PZEM-004T / ZMPT101B), sondas
de temperatura DS18B20/termocupla, ni analizador de red para frecuencia y THD, este
módulo intercepta la lectura parcial recibida ({'current', 'relay_state'}) y
completa sintéticamente las variables faltantes con valores plausibles basados en
principios de ingeniería eléctrica y en la correlación física observada con la
corriente.

IMPORTANTE:
Este enriquecimiento sintético DEBE SER REMOVIDO o DESACTIVADO en cuanto se
sustituya el hardware dañado y se integren sensores reales de voltaje, potencia,
temperatura y distorsión armónica.
===================================================================================
"""

import math
import random
from typing import Dict, Any


def enrich_telemetry(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriquece una lectura de telemetría parcial completando únicamente los campos
    ausentes o nulos para preservar la compatibilidad con el pipeline de IA
    (EcoGridConsumptionPredictor, AIService, base de datos de series de tiempo y SNMP).

    Campos sintéticamente generados (si no vienen en data):
      - voltage: ~120V nominal con variación estocástica y caída de tensión por carga.
      - power_factor: derivado del nivel de corriente (0.92 a 0.97 en régimen normal).
      - active_power: V * I * FP.
      - reactive_power: V * I * sqrt(1 - FP^2).
      - frequency: ~60Hz con ruido mínimo.
      - thd: correlacionado con la corriente (mayor corriente -> mayor distorsión armónica).
      - temperature: correlacionada térmicamente con la corriente disipada.

    Parámetros:
      data: Diccionario con la lectura entrante (debe incluir al menos 'current').

    Retorna:
      Diccionario enriquecido con el vector completo de 8 variables eléctricas.
    """
    enriched = dict(data)

    # 1. Extracción segura de variables base reales
    try:
        current = float(enriched.get("current", 0.0))
    except (ValueError, TypeError):
        current = 0.0

    try:
        relay_state = int(enriched.get("relay_state", 1))
    except (ValueError, TypeError):
        relay_state = 1

    # Si el relé está abierto (0 = desconectado), la corriente que fluye a la carga es 0
    if relay_state == 0 and current > 0.1:
        current = 0.0
        enriched["current"] = 0.0

    enriched_fields = []

    # 2. Voltaje (Voltage): ~120V nominal con caída según nivel de carga
    if "voltage" not in enriched or enriched["voltage"] is None:
        if relay_state == 0:
            # Tensión nominal presente en barraje pero sin carga conectada
            voltage = round(120.0 + random.uniform(-0.5, 0.5), 1)
        elif current <= 0.1:
            voltage = round(120.0 + random.uniform(-0.8, 0.8), 1)
        elif current <= 16.0:
            # Régimen normal: 118.5 a 121.5 V
            voltage_sag = (current / 16.0) * 1.5
            voltage = round(120.5 - voltage_sag + random.uniform(-0.6, 0.6), 1)
        elif current <= 32.0:
            # Pico de demanda: caída de tensión a 115.0 - 118.5 V
            fraction = (current - 16.0) / 16.0
            voltage = round(118.5 - (fraction * 3.5) + random.uniform(-0.5, 0.5), 1)
        else:
            # Sobrecarga crítica: caída severa a 108.0 - 114.0 V
            over_excess = min(1.0, (current - 32.0) / 16.0)
            voltage = round(114.0 - (over_excess * 6.0) + random.uniform(-0.8, 0.8), 1)

        enriched["voltage"] = float(voltage)
        enriched_fields.append("voltage")
    else:
        voltage = float(enriched["voltage"])

    # 3. Factor de Potencia (Power Factor): razonable en función de la carga
    if "power_factor" not in enriched or enriched["power_factor"] is None:
        if relay_state == 0 or current <= 0.1:
            pf = 0.98
        elif current <= 16.0:
            # Rango 0.92 - 0.97 en operación inductiva típica residencial/comercial
            pf = round(random.uniform(0.93, 0.97), 2)
        elif current <= 32.0:
            # Rango 0.88 - 0.94 en picos con motores o transformadores saturándose
            pf = round(random.uniform(0.88, 0.94), 2)
        else:
            # Rango 0.70 - 0.82 en sobrecarga severa con distorsión reactiva
            pf = round(random.uniform(0.70, 0.82), 2)

        enriched["power_factor"] = float(pf)
        enriched_fields.append("power_factor")
    else:
        pf = float(enriched["power_factor"])

    # 4. Potencia Activa (Active Power en Watts): P = V * I * FP
    if "active_power" not in enriched or enriched["active_power"] is None:
        active_power = round(voltage * current * pf, 2)
        enriched["active_power"] = float(active_power)
        enriched_fields.append("active_power")
    else:
        active_power = float(enriched["active_power"])

    # 5. Potencia Reactiva (Reactive Power en VAR): Q = V * I * sin(phi)
    if "reactive_power" not in enriched or enriched["reactive_power"] is None:
        sin_phi = math.sqrt(max(0.0, 1.0 - (pf ** 2))) if abs(pf) <= 1.0 else 0.0
        reactive_power = round(voltage * current * sin_phi, 2)
        enriched["reactive_power"] = float(reactive_power)
        enriched_fields.append("reactive_power")

    # 6. Frecuencia (Frequency en Hz): red nominal ~60 Hz con micro-fluctuación
    if "frequency" not in enriched or enriched["frequency"] is None:
        if current > 32.0:
            # Leve caída de frecuencia en perturbación severa
            freq = round(60.0 - random.uniform(0.05, 0.25), 2)
        else:
            freq = round(60.0 + random.uniform(-0.05, 0.05), 2)
        enriched["frequency"] = float(freq)
        enriched_fields.append("frequency")

    # 7. Distorsión Armónica Total (THD en %): correlacionada con current
    # Reutiliza y mapea la lógica de sinulators/esp32_simulator.py
    if "thd" not in enriched or enriched["thd"] is None:
        if relay_state == 0 or current <= 0.1:
            thd = round(random.uniform(1.2, 1.8), 1)
        elif current <= 16.0:
            # Modo normal: THD bajo 2.5 - 4.5 %
            thd = round(2.5 + (current / 16.0) * 1.5 + random.uniform(-0.3, 0.4), 1)
        elif current <= 32.0:
            # Modo pico: THD moderado 5.0 - 8.0 %
            fraction = (current - 16.0) / 16.0
            thd = round(5.0 + (fraction * 3.0) + random.uniform(-0.4, 0.4), 1)
        else:
            # Modo sobrecarga: THD crítico 15.0 - 26.0 % (dispara anomalía en IA si > 15%)
            excess = min(1.0, (current - 32.0) / 16.0)
            thd = round(15.0 + (excess * 10.0) + random.uniform(0.0, 1.5), 1)

        enriched["thd"] = float(max(0.5, thd))
        enriched_fields.append("thd")

    # 8. Temperatura (Temperature en °C): disipación térmica Joule ~ I^2 * R
    if "temperature" not in enriched or enriched["temperature"] is None:
        if relay_state == 0 or current <= 0.1:
            temp = round(random.uniform(25.0, 27.5), 1)
        elif current <= 16.0:
            # Modo normal: 28.0 - 34.0 °C
            temp = round(28.0 + (current / 16.0) * 5.0 + random.uniform(-0.8, 0.8), 1)
        elif current <= 32.0:
            # Modo pico: 46.0 - 52.0 °C
            fraction = (current - 16.0) / 16.0
            temp = round(46.0 + (fraction * 6.0) + random.uniform(-1.0, 1.0), 1)
        else:
            # Modo sobrecarga: 68.0 - 82.0 °C (dispara corte por umbral térmico > 70°C)
            excess = min(1.0, (current - 32.0) / 16.0)
            temp = round(68.0 + (excess * 13.0) + random.uniform(-1.0, 2.0), 1)

        enriched["temperature"] = float(round(temp, 1))
        enriched_fields.append("temperature")

    # Metadata de auditoría
    if enriched_fields:
        enriched["_synthetic_enrichment"] = True
        enriched["_enriched_fields"] = enriched_fields

    return enriched


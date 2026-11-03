# EcoGrid AI — Standard Operating Manual & User Guide
## Subject: English VI (Team Project)
**Institution:** Universidad Tecnológica de Calvillo (UTC)  
**Degree:** Software Development Engineering (7th Quarter)  
**System:** Intelligent Electrical Energy & Efficiency Management Platform (EcoGrid AI)

---

## 1. Safety Directives and Precautions

Read this manual thoroughly before operating the electrical monitoring system. The following instructions utilize **Affirmative and Negative Imperatives** to ensure personal safety and equipment integrity.

### 1.1 Critical Safety Instructions (Imperatives)

#### Affirmative Imperatives:
- **Always de-energize** the main circuit breaker before installing, handling, or inspecting sensors.
- **Wear** certified Personal Protective Equipment (PPE), including insulated dielectric gloves and safety goggles.
- **Ensure** that the ground wire is securely fastened to the grounding bus bar.
- **Verify** voltage and current ratings on the distribution panel before mounting the ESP32 sensing module.
- **Keep** a certified Class C dry chemical fire extinguisher near the electrical cabinet.
- **Report** any burning odors or scorched wiring to the electrical engineering staff immediately.

#### Negative Imperatives:
- **Do not touch** uninsulated high-voltage AC conductors under any circumstances.
- **Never bypass** or disable the automatic relay cutoff mechanism.
- **Do not exceed** the maximum current rating of 35 Amperes on the SCT-013 sensing branch.
- **Never operate** the ESP32 microcontroller inside damp or moisture-condensing environments.
- **Do not ignore** high-priority Syslog security alerts or continuous breaker trip events.
- **Never connect** the AC voltage transformer (ZMPT101B) in reverse polarity.

---

## 2. Hardware Installation and Wiring Guide

```
+-------------------------------------------------------------+
|                     ELECTRICAL MAINS (AC)                   |
|       Line (Phase) -----------------------------------> Load |
|         ^                                                |  |
|         | [SCT-013 Clamp]                                |  |
|         v                                                v  |
|   +-----------+                                     +-----+ |
|   |  ESP32    | ---> [GPIO 26: Relay Cutoff] -----> |Relay| |
|   | Controller| <--- [ADC 35: ZMPT101B Voltage] <--- +-----+ |
|   +-----------+                                             |
+-------------------------------------------------------------+
```

### Step-by-Step Installation Instructions:

1. **Turn off** the main power supply before beginning the mechanical installation.
2. **Mount** the ESP32 DevKit enclosure inside an industrial IP65-rated distribution box.
3. **Clamp** the non-invasive current sensor (SCT-013) firmly around the main phase conductor.
   - **Do not clamp** both phase and neutral wires together; clamp only one conductor.
4. **Connect** the analog output of the current sensor conditioning circuit to **GPIO 34**.
5. **Connect** the voltage sensor module (ZMPT101B) output pin to **GPIO 35**.
6. **Wire** the solid-state or electromechanical relay signal pin to **GPIO 26**.
7. **Inspect** all screw terminals and ensure that no loose wire strands remain exposed.
8. **Energize** the 5V DC low-voltage power supply to start the microcontroller.

---

## 3. Microcontroller (ESP32) Configuration

### Firmware Setup Directives:

- **Open** the Arduino IDE or PlatformIO workspace.
- **Select** `DOIT ESP32 DEVKIT V1` as the active target board.
- **Enter** the local Wi-Fi SSID and password in the `WIFI_SSID` and `WIFI_PASS` variables.
- **Specify** the target EcoGrid AI server IP address in the `API_HOST` variable (e.g., `http://192.168.1.100:5000`).
- **Upload** the firmware to the ESP32 via USB-C or micro-USB cable.
- **Open** the Serial Monitor at **115200 baud** to verify network connection and initial telemetry readings.
- **Do not disconnect** the programming cable while flashing the firmware.

---

## 4. Web Platform & Real-Time Monitoring Instructions

```
URL: http://localhost:5000/
Supported Browsers: Google Chrome, Mozilla Firefox, Microsoft Edge, Safari
```

### Operational Procedures:

1. **Launch** your web browser and navigate to `http://localhost:5000/`.
2. **Observe** the system status indicator at the top right of the dashboard.
   - **Ensure** that the status pill displays **"Sistema Activo"** with a green pulsing dot.
3. **Monitor** real-time RMS Voltage, RMS Current, Active Power (Watts), and Power Factor gauges.
4. **Check** the AI Classification badge:
   - `Normal`: Standard operation within scheduled baseline.
   - `Pico de Demanda`: Heavy load detected; prepare non-critical load shedding.
   - `Sobrecarga / Anomalía`: Dangerous overcurrent; system will trigger automatic disconnection.
   - `Fuga / Consumo Parásito`: Inspect grounding wire for current leakage.
5. **Do not close** the browser tab during critical industrial peak hours.

---

## 5. Automated Load Shedding & Relay Management Protocol

EcoGrid AI features an automated load disconnection mechanism to prevent electrical fires and transformator breakdown.

### Disconnection & Restoration Directives:

- **Allow** the artificial intelligence engine to disconnect loads automatically when severe overload is detected.
- **Check** the physical relay status badge on the **"Desconexión de Cargas"** tab.
- **Investigate** the physical cause of any automated breaker trip before restoring power.
- **Click** the **"Reconectar Carga"** button only after verifying that the line is clear of short circuits.
- **Use** the **"Desconectar Manualmente"** emergency button whenever abnormal sparking occurs.
- **Do not force** immediate reconnection if the conductor temperature exceeds 65°C.

---

## 6. Cybersecurity, Honeypot & Incident Response

EcoGrid AI protects industrial infrastructure against cyberattacks, telemetry tampering, and Denial of Service (DoS) floods.

### Security Directives:

- **Review** the Syslog console periodically under the **"Ciberseguridad & Honeypot"** tab.
- **Check** the Honeypot decoy table to identify trapped intruder IP addresses.
  - The system deploys honey-tokens and fake SCADA endpoints at `/admin`, `/scada/admin`, and `/firmware/update`.
  - Intruders targeting these decoys are **blacklisted immediately**.
- **Do not unban** unknown foreign IP addresses from the firewall blacklist without supervisor authorization.
- **Confirm** that SNMP v2c traps are reaching your Network Management Station (NMS/Zabbix) on UDP port 162.
- **Never share** master administrative API credentials over unencrypted communication channels.

---

## 7. Preventive Maintenance & Troubleshooting Matrix

| Symptom / Event | Possible Cause | Mandatory Directive (Imperatives) |
| :--- | :--- | :--- |
| **Current reads 0.0A with load on** | Sensor clamp improperly closed or disconnected wire | **Check** sensor clamp closure. **Reconnect** ADC pin 34. **Do not use** broken cables. |
| **Sudden Relay Cutoff** | Overcurrent (>35A) or AI anomaly detection | **Inspect** branch conductors for short circuit. **Do not reconnect** without fault clearance. |
| **Wi-Fi LED blinking continuously** | Invalid Wi-Fi credentials or router out of range | **Reset** the router. **Update** SSID and password in firmware. **Do not modify** core ADC code. |
| **HTTP 429 / 403 API Error** | Rate limiter triggered (suspected DoS flood) | **Wait** for the ban duration to expire. **Do not spam** API requests rapidly. |
| **Honeypot Alert Triggered** | Unauthorized scanner probed decoy endpoint | **Verify** attacker IP origin. **Keep** the intruder on the permanent blacklist. |
| **Abnormal High Voltage (>135V)** | Grid voltage swell or failed AVR regulator | **Disconnect** sensitive electronic equipment immediately. **Call** utility provider. |

---

## 8. Summary of Essential Imperatives for Operators

```
+-------------------------------------------------------------------------+
|                  OPERATOR'S GOLDEN RULES OF CONDUCT                     |
+-------------------------------------------------------------------------+
|  [DO's]                                                                 |
|   1. Always inspect sensors before energizing the circuit.              |
|   2. Check real-time power factor and harmonic distortion daily.        |
|   3. Investigate the cause of every automated trip before reset.        |
|   4. Follow all safety warnings emitted by the Syslog server.           |
|                                                                         |
|  [DON'Ts]                                                               |
|   1. Do not exceed the nominal 35A safety threshold.                    |
|   2. Never operate electrical components with wet hands.                |
|   3. Do not bypass the software or hardware relay protections.          |
|   4. Never ignore critical maintenance tickets flagged by the NLP tool. |
+-------------------------------------------------------------------------+
```

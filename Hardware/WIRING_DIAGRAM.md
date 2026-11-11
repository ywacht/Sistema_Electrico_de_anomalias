# EcoGrid AI — Especificaciones de Hardware y Diagrama de Conexiones (ESP32)

**Universidad Tecnológica de Calvillo (UTC)**  
**Carrera:** Ingeniería en Tecnologías — Área Desarrollo de Software (7mo Cuatrimestre)  
**Proyecto:** Plataforma Inteligente Gestora de Energía Eléctrica y Eficiencia Energética (EcoGrid AI)

---

## 1. Arquitectura de Hardware (Nodo Único Consolidado)

> [!NOTE]
> **Aviso de Arquitectura Hardware:**  
> Tras la avería física de uno de los microcontroladores ESP32 en laboratorio, el proyecto opera con **UN SOLO nodo ESP32 DevKit V1** físico que concentra el monitoreo de corriente (mediante sensor de efecto Hall ACS712) y el control de desconexión mediante módulo relé.  
> Los parámetros no medidos físicamente (tensión, factor de potencia, armónicos y temperatura) son completados temporalmente en el backend mediante el módulo `backend/servises/synthetic_enrichment.py`.

```
[Red Eléctrica AC ~120V]
        |
        +-----> [Sensor ACS712 (Efecto Hall)] ----> [ESP32 ADC Pin GPIO 36 (VP)]
        |
        +-----> [Módulo Relé 5V (Actuador)] <------ [ESP32 GPIO 26] (Corte de Cargas)
                                                         |
                                                    (WiFi / HTTP REST / Syslog UDP)
                                                         |
                                                         v
                                            [EcoGrid AI Backend / API REST]
                                                         |
                                                         v
                                       [Enriquecimiento Sintético + Modelos IA]
```

---

## 2. Diagrama de Pines — Nodo ESP32 DevKit V1

| Componente | Pin del Componente | Pin ESP32 DevKit V1 | Función |
| :--- | :--- | :--- | :--- |
| **ACS712 (Corriente Hall 30A)** | VOUT (Señal analógica) | **GPIO 36 (ADC1_CH0 / VP)** | Muestreo de corriente RMS (0 - 30A) |
| **ACS712** | VCC / GND | **VIN (5V) / GND** | Alimentación del módulo Hall |
| **Módulo Relé 5V** | Entrada señal IN | **GPIO 26** | Control de apertura/cierre de la carga |
| **Módulo Relé 5V** | VCC / GND | **VIN (5V) / GND** | Alimentación de la bobina del relé |
| **LED Estado (Heartbeat)** | Ánodo (+) | **GPIO 2** | Pulso de latido y parpadeo de actividad WiFi |
| **LED Alerta Sobrecarga** | Ánodo (+) | **GPIO 4** | Indicador lumínico de sobrecarga / corte físico |
| **Alimentación ESP32** | Micro-USB / VIN | **5V Regulado / GND** | Bus de alimentación principal |

---

## 3. Calibración del Sensor ACS712

El módulo ACS712 entrega una salida de tensión proporcional a la corriente que fluye a través de sus terminales con un offset de reposo en $V_{CC} / 2$ ($\approx 2.5\text{V}$):

- **Sensibilidad nominal:** $66\text{ mV/A}$ (para modelo ACS712ELCTR-30A-T).
- **Lectura en ESP32:** Se toman 300 muestras en ventanas de $100\,\mu\text{s}$ para calcular el valor eficaz RMS cuadrático:
  $$I_{RMS} = \frac{\sqrt{\frac{1}{N}\sum (V_i - V_{offset})^2}}{\text{Sensibilidad}}$$
- **Filtro de ruido:** Lecturas inferiores a $0.15\text{ A}$ se truncan a cero para suprimir el ruido intrínseco del conversor ADC en vacío.

---

## 4. Política de Seguridad y Fail-Safe en Hardware

1. **Corte Local de Emergencia (Hardware Trip Autónomo):**  
   Si la corriente instantánea supera los $28.0\text{ A}$, el firmware del microcontrolador abre el relé inmediatamente ($\text{GPIO } 26 \to \text{LOW}$) en menos de 10 milisegundos, protegiendo las líneas e instalaciones independientemente de la conectividad de red.
2. **Sincronización Bidireccional:**  
   El ESP32 transmite periódicamente (`POST /api/telemetry`) el payload mínimo `{device_id, location, current, relay_state}`. Si el backend emite `"should_disconnect": true` (por detección de anomalía de la IA), el ESP32 ejecuta el corte. Asimismo, consulta periódicamente (`GET /api/actuators/relay/{id}`) para aplicar comandos remotos del operador.
3. **Alerta Syslog Directa (RFC 5424):**  
   Ante un disparo por sobrecarga local, el ESP32 emite un datagrama UDP en el puerto 514 hacia el servidor SIEM/Syslog para auditoría de seguridad.

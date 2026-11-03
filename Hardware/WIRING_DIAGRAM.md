# EcoGrid AI — Especificaciones de Hardware y Diagrama de Conexiones (ESP32)

**Universidad Tecnológica de Calvillo (UTC)**  
**Carrera:** Ingeniería en Tecnologías — Área Desarrollo de Software (7mo Cuatrimestre)  
**Proyecto:** Plataforma Inteligente Gestora de Energía Eléctrica y Eficiencia Energética

---

## 1. Arquitectura de Nodos Hardware

El sistema implementa dos nodos inteligentes basados en el microcontrolador **ESP32 DevKit V1 (38 pines)**:

```
[Red Eléctrica AC ~120V / 220V]
        |
        +-----> [Sensor SCT-013 / ACS712] ----> [ESP32 ADC Pin 34/36]
        |
        +-----> [Sensor ZMPT101B] ----------> [ESP32 ADC Pin 35/39]
        |
        +-----> [Módulo Relé (Actuador)] <--- [ESP32 GPIO 26/27] (Corte de Cargas)
                                                     |
                                                (WiFi / HTTP / Syslog)
                                                     |
                                                     v
                                         [EcoGrid AI Cloud Backend]
```

---

## 2. Diagrama de Pines — Nodo 1 (Subestación / Línea Industrial)

| Componente | Pin del Componente | Pin ESP32 | Función |
| :--- | :--- | :--- | :--- |
| **SCT-013 (Corriente)** | Salida señal acondicionada | **GPIO 34 (ADC1_CH6)** | Muestreo de corriente RMS (0 - 100A) |
| **ZMPT101B (Voltaje)** | Salida analógica | **GPIO 35 (ADC1_CH7)** | Muestreo de onda senoidal de tensión |
| **Módulo Relé 5V** | Entrada IN | **GPIO 26** | Control de apertura/cierre de carga |
| **LED Estado** | Ánodo (+) | **GPIO 2** | Pulso de latido y actividad WiFi |
| **LED Alerta** | Ánodo (+) | **GPIO 4** | Indicador rojo de sobrecarga crítica / corte |
| **Alimentación** | VCC / GND | **VIN (5V) / GND** | Bus común de alimentación regulada |

### Circuito Acondicionador para Sensor SCT-013:
Dado que el sensor SCT-013 entrega una señal de corriente alterna proporcional, se implementa un divisor de tensión con dos resistencias de $10\text{ k}\Omega$ alimentado a $3.3\text{V}$ para montar una referencia continua de $+1.65\text{V}$ (offset DC), junto a un condensador electrolítico de $10\mu\text{F}$ de desacoplo y una resistencia de carga (burden resistor) de $33\Omega$ para calibración a 30A/1V.

---

## 3. Diagrama de Pines — Nodo 2 (Ramal Secundario / Residencial)

| Componente | Pin del Componente | Pin ESP32 | Función |
| :--- | :--- | :--- | :--- |
| **ACS712 (Corriente Hall)** | Salida VOUT | **GPIO 36 (ADC1_CH0 / VP)** | Lectura de corriente hasta 30A |
| **ZMPT101B / Divisor** | Salida analógica | **GPIO 39 (ADC1_CH3 / VN)** | Lectura de voltaje residencial |
| **Módulo Relé 5V** | Entrada IN | **GPIO 27** | Desconexión de línea secundaria |
| **LED Estado** | Ánodo (+) | **GPIO 2** | Indicador de conexión de red |

---

## 4. Política de Seguridad y Fail-Safe en Hardware

1. **Corte Local de Emergencia (Hardware Trip):**  
   Si la corriente instantánea supera los $35.0\text{ A}$, el código del ESP32 dispara el relé a nivel bajo en menos de 10 milisegundos, protegiendo conductores e instalaciones aún si se pierde la conexión WiFi con la nube.
2. **Sincronización Bidireccional:**  
   El ESP32 transmite telemetría cada 2 segundos a la API REST (`POST /api/telemetry`) y recibe en la misma respuesta o mediante polling (`GET /api/actuators/relay/{id}`) la directiva de corte preventivo emitida por los modelos de IA cuando predicen picos de demanda o patrones anómalos.
3. **Telemetría de Alerta Syslog Directa:**  
   En caso de disparo por sobrecarga local, el ESP32 transmite inmediatamente un paquete UDP Syslog en el puerto 514 hacia el servidor SIEM.

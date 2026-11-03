# EcoGrid AI — Plataforma Inteligente Gestora de Energía Eléctrica y Eficiencia Energética

![UTC Logo](https://img.shields.io/badge/Universidad%20Tecnol%C3%B3gica%20de%20Calvillo-UTC-blue?style=for-the-badge)
![Term](https://img.shields.io/badge/Cuatrimestre-7mo%20Ingenier%C3%ADa%20en%20Tecnolog%C3%ADas-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-yellow?style=for-the-badge)
![ESP32](https://img.shields.io/badge/Hardware-ESP32%20DevKit%20V1-red?style=for-the-badge)

---

## 📌 Descripción General

**EcoGrid AI** es una plataforma integral web y nube diseñada para el **monitoreo en tiempo real del consumo eléctrico industrial y residencial**, la **predicción inteligente de picos de demanda** y la **desconexión automatizada de cargas** para protección de activos y eficiencia energética.

El proyecto incorpora sensado de campo mediante microcontroladores **ESP32**, modelos de Machine Learning optimizados mediante **Algoritmos Genéticos**, procesamiento de lenguaje natural (NLP) para bitácoras técnicas, almacenamiento no relacional de series de tiempo y una robusta infraestructura de ciberseguridad con **Syslog**, **SNMP v2c**, **mitigación DoS** y un **Honeypot señuelo para entornos SCADA / IoT**.

---

## 🎓 Integración de las 6 Asignaturas (UTC - 7mo Cuatrimestre)

| # | Asignatura | Área | Implementación Técnica en el Repositorio |
| :-: | :--- | :---: | :--- |
| **1** | **Fundamentos de IA** | IA | Modelos supervisados (**Redes Neuronales MLP**, **KNN**, **SVM**) y no supervisados (**K-Means**, **Self-Organizing Maps / SOM**) optimizados con **Algoritmos Genéticos** (`ai_engine/genetic/` y `ai_engine/models/`). |
| **2** | **Minería de Texto** | IA | Pipeline NLP con **TF-IDF + LinearSVC** para clasificar severidad de bitácoras e incidentes eléctricos no estructurados, reportando métricas de **Accuracy (100%)** y **F1-Score (1.000)** (`ai_engine/models/text_mining_classifier.py`). |
| **3** | **Bases de Datos en la Nube** | SW | Repositorio no relacional para ingestión masiva de series de tiempo con soporte nativo de **MongoDB Atlas / Cloud NoSQL** y fallback local de alta velocidad (`backend/database.py`). |
| **4** | **Seguridad Informática** | SW | Monitoreo continuo mediante **Syslog (RFC 5424)**, **SNMP v2c con Traps y MIB privada**, blindaje contra ataques **DoS**, e implementación activa de un **Honeypot señuelo** (`security/`). |
| **5** | **Formulación de Proyectos de Tecnología** | SW/IA | Justificación con enfoque en **Innovación Socialmente Responsable (ODS 7, 9, 12 y 13)**, gestión de recursos humanos (**Matriz RACI**), materiales y estimación detallada de costos cloud (`docs/FORMULACION_PROYECTO.md`). |
| **6** | **Inglés VI** | Equipo | Manual operativo técnico y guía de usuario redactado completamente en inglés haciendo uso intensivo de **Imperativos (Afirmativos y Negativos)** para la operación segura del sistema (`docs/OPERATIONAL_MANUAL_EN.md`). |

---

## 🍯 Ciberseguridad & Implementación del Honeypot (SCADA / IoT)

Para salvaguardar la infraestructura crítica contra atacantes y sondas maliciosas, EcoGrid AI despliega un **Honeypot cibernético**:

1. **Rutas Señuelo Expuestas:** Emula interfaces administrativas vulnerables en `/admin`, `/scada/admin`, `/scada/config`, `/modbus/gateway` y `/firmware/update`.
2. **Engaño Activo:** Cuando un atacante intenta inyecciones SQL o autenticación forzada, el señuelo responde con interfaces SCADA ficticias para retenerlo.
3. **Contramedida Inmediata:**  
   - Se captura la IP, User-Agent y payload del atacante.
   - Se despacha una alerta **Syslog prioritaria (Facility LOCAL0)** al servidor SIEM.
   - Se emite un **SNMP Trap** (`1.3.6.1.4.1.58888.2.2.0`).
   - El motor de defensa añade automáticamente la IP a la **Lista Negra del Firewall**, bloqueando cualquier acceso futuro a la API y a los ESP32.

---

## 🔌 Hardware y Nodos ESP32

El sistema integra dos nodos microcontroladores en campo:
- **`Hardware/escp32_sensor_1/`**: Subestación / Línea Industrial. Integra sensor no invasivo **SCT-013-000** (0-100A), transformador **ZMPT101B** (AC 0-250V), relé de corte en GPIO 26 y fail-safe local en hardware ante sobrecargas mayores a 35A.
- **`Hardware/esp_sensor_2/`**: Ramal Secundario / Residencial. Integra sensor de efecto Hall **ACS712** y relé en GPIO 27.
- **Diagrama de Conexiones:** Disponible en [`Hardware/WIRING_DIAGRAM.md`](Hardware/WIRING_DIAGRAM.md).

---

## 📂 Estructura del Repositorio

```
Sistema_Electrico_de_anomalias/
│
├── ai_engine/                         # Eje de Inteligencia Artificial
│   ├── genetic/
│   │   └── genetic_optimizer.py       # Algoritmo Genético para optimización de hiperparámetros
│   ├── models/
│   │   ├── consumption_classifier.py  # KNN, SVM, Red Neuronal, K-Means, SOM
│   │   ├── text_mining_classifier.py  # Pipeline NLP TF-IDF + Clasificador de Bitácoras
│   │   └── saved/                     # Pesos entrenados (.joblib) y métricas (.json)
│   ├── notebooks/
│   │   └── EcoGrid_AI_Models_Demo.ipynb # Demostración interactiva en Jupyter Notebook
│   └── scripts/
│       └── train_models.py            # Script maestro de entrenamiento y optimización
│
├── backend/                           # Servidor Cloud REST API
│   ├── app.py                         # Aplicación Flask y middlewares de seguridad
│   ├── database.py                    # Repositorio NoSQL para Series de Tiempo
│   ├── routes/
│   │   ├── telemetry.py               # Ingestión de datos ESP32 y series de tiempo
│   │   ├── actuators.py               # Control y desconexión de relés
│   │   ├── text_mining_routes.py      # Endpoints de clasificación de reportes
│   │   └── security_routes.py         # Endpoints de Syslog, SNMP, DoS y Honeypot
│   └── servises/
│       ├── ai_service.py              # Servicio de inferencia en tiempo real
│       └── disconnection_service.py   # Lógica de corte automatizado de cargas
│
├── security/                          # Módulo de Ciberseguridad
│   ├── syslog_service.py              # Cliente Syslog RFC 5424 / RFC 3164 (Puerto 514)
│   ├── snmp_service.py                # Agente SNMP v2c con Traps y MIB privada
│   ├── dos_protection.py              # Limitador de tasa y baneo dinámico de IPs
│   └── honeypot_service.py            # Trampa señuelo SCADA / IoT y auto-bloqueo
│
├── frontend/                          # Dashboard Web en Tiempo Real
│   ├── index.html                     # Interfaz de usuario interactiva
│   ├── app.js                         # Lógica cliente y gráficos Chart.js
│   └── styles.css                     # Estilos tema oscuro industrial
│
├── Hardware/                          # Código Firmware para ESP32
│   ├── escp32_sensor_1/               # Nodo 1 (Subestación / SCT-013 + ZMPT101B)
│   ├── esp_sensor_2/                  # Nodo 2 (Residencial / ACS712)
│   └── WIRING_DIAGRAM.md              # Diagramas esquemáticos y pines
│
├── sinulators/                        # Simuladores y Generadores de Pruebas
│   ├── esp32_simulator.py             # Emulador de nodos ESP32 con inyección de fallas
│   └── dos_and_honeypot_tester.py     # Herramienta de pruebas de ataque DoS y Honeypot
│
├── docs/                              # Documentación Académica Oficial
│   ├── FORMULACION_PROYECTO.md        # Formulación, ODS, RACI y Costos Cloud
│   └── OPERATIONAL_MANUAL_EN.md       # Manual operativo en Inglés con Imperativos
│
├── tests/                             # Pruebas Unitarias Automatizadas
│   └── test_all_modules.py            # Test suite integral de todos los módulos
│
├── .github/workflows/ci.yml           # Pipeline de Integración Continua (CI/CD)
├── requirements.txt                   # Dependencias de Python
├── run_server.py                      # Lanzador del servidor backend
├── start.bat                          # Script de ejecución para Windows
└── README.md                          # Documentación del proyecto
```

---

## 🚀 Guía de Instalación y Ejecución Rápida

### 1. Clonar el Repositorio
```bash
git clone https://github.com/ywacht/Sistema_Electrico_de_anomalias.git
cd Sistema_Electrico_de_anomalias
```

### 2. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 3. Entrenar y Optimizar Modelos de IA
*(Ejecuta el Algoritmo Genético y entrena las Redes Neuronales, KNN, SVM, K-Means, SOM y Minería de Texto)*:
```bash
python ai_engine/scripts/train_models.py
```

### 4. Ejecutar las Pruebas Unitarias
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 5. Iniciar la Plataforma Web
```bash
python run_server.py
```
O simplemente haz doble clic en `start.bat` en Windows.  
Abre tu navegador en: **`http://localhost:5000/`**

---

## 🧪 Pruebas y Simulación en Vivo

- **Para simular telemetría continua de un ESP32 con anomalías:**
  ```bash
  python sinulators/esp32_simulator.py sobrecarga
  ```
- **Para ejecutar la suite de ataque DoS y activación de Honeypot:**
  ```bash
  python sinulators/dos_and_honeypot_tester.py
  ```

---

## 👥 Equipo de Desarrollo y Créditos
- **Universidad Tecnológica de Calvillo (UTC)**
- **Ingeniería en Tecnologías — Área Desarrollo de Software**
- Proyecto Integrador de 7mo Cuatrimestre.

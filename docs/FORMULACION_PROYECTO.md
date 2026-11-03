# Formulación de Proyectos de Tecnología (SW/IA)
## Documento Maestro de Justificación, Gestión de Recursos y Estimación de Costos

**Institución:** Universidad Tecnológica de Calvillo (UTC)  
**Programa Educativo:** Ingeniería en Tecnologías — Área Desarrollo de Software  
**Nivel Académico:** 7mo Cuatrimestre  
**Proyecto Integrador:** EcoGrid AI — Plataforma Inteligente Gestora de Energía Eléctrica y Eficiencia Energética  

---

## 1. Justificación bajo el Marco de Innovación Socialmente Responsable

### 1.1 Contexto y Problemática
En el sector industrial y residencial actual, la falta de visibilidad en tiempo real sobre los patrones de consumo eléctrico provoca:
- **Picos de demanda no controlados**, los cuales generan penalizaciones severas en la facturación eléctrica de media y alta tensión impuestas por suministradores como CFE (Comisión Federal de Electricidad).
- **Sobrecargas térmicas y arcos eléctricos**, ocasionando incendios, averías catastróficas de transformadores y riesgos directos para la vida de los operarios.
- **Pérdidas de energía parásitas e ineficiencia**, contribuyendo a una huella de carbono elevada y desperdicio evitable de recursos no renovables.

**EcoGrid AI** se formula como una solución de **innovación tecnológica socialmente responsable**, combinando sensado IoT de bajo costo (ESP32), Inteligencia Artificial en el borde y en la nube para predicción de picos, minería de texto para mantenimiento predictivo y desconexión automatizada de cargas para salvaguardar la vida humana y los activos industriales.

### 1.2 Alineación con los Objetivos de Desarrollo Sostenible (ODS de la ONU)

| ODS | Nombre del Objetivo | Impacto y Aporte de EcoGrid AI |
| :---: | :--- | :--- |
| **ODS 7** | *Energía Asequible y No Contaminante* | Optimiza la eficiencia energética hasta en un 18% mediante desconexión automatizada de cargas en horario pico y detección de pérdidas parásitas. |
| **ODS 9** | *Industria, Innovación e Infraestructura* | Dota a micro, pequeñas y medianas empresas (MIPYMES) de tecnología SCADA/IoT accesible con estándares de ciberseguridad industrial y Honeypots defensivos. |
| **ODS 12** | *Producción y Consumo Responsables* | Fomenta una cultura de consumo eléctrico sustentable mediante dashboards en tiempo real y alertas de mantenimiento preventivo continuo. |
| **ODS 13** | *Acción por el Clima* | La reducción en la demanda punta previene el encendido de turbinas termoeléctricas fósiles de respaldo, mitigando directamente emisiones de CO₂. |

---

## 2. Gestión Integral de Recursos

### 2.1 Recursos Humanos (RRHH) y Matriz RACI
El equipo de proyecto está conformado por ingenieros en formación con roles especializados:

* **Project Manager / Líder de Proyecto:** Coordinación general, presupuesto y cumplimiento de cronograma.
* **Lead AI & Data Scientist:** Modelado supervisado/no supervisado, algoritmos genéticos y minería de texto NLP.
* **Cloud & Backend Architect:** API REST, repositorios de series de tiempo NoSQL y escalabilidad.
* **Embedded & Hardware Engineer:** Firmware ESP32, acondicionamiento de señales analógicas y relés de corte.
* **Security & Network Specialist:** Protocolos Syslog RFC 5424, SNMP v2c, mitigación DoS y arquitectura Honeypot.

#### Matriz RACI:
*(**R**esponsable, **A**ccountable / Aprobador, **C**onsultado, **I**nformado)*

| Entregable / Hito | Project Manager | Lead AI | Cloud Arch | Embedded Eng | Security Spec |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Modelos IA & Algoritmo Genético | A | **R** | C | I | I |
| Minería de Texto NLP & Métricas F1 | A | **R** | C | I | I |
| Base de Datos Series de Tiempo NoSQL | A | C | **R** | C | I |
| Firmware ESP32 & Calibración ADC | A | C | C | **R** | C |
| Desconexión Automatizada de Carga | A | C | **R** | **R** | C |
| Syslog, SNMP, DoS & Honeypot | A | I | C | C | **R** |
| Manuales Operativos en Inglés | **R** | C | C | C | C |

---

### 2.2 Recursos Materiales (Hardware de Laboratorio y Pruebas)

| Ítem | Descripción Técnica | Cantidad | Costo Unitario (MXN) | Costo Total (MXN) |
| :--- | :--- | :---: | :---: | :---: |
| **ESP32 DevKit V1** | Dual Core 240MHz, 4MB Flash, WiFi + BLE | 2 | \$160.00 | \$320.00 |
| **SCT-013-000** | Sensor de corriente no invasivo 0-100A | 1 | \$145.00 | \$145.00 |
| **ACS712-30A** | Módulo de corriente de efecto Hall hasta 30A | 1 | \$85.00 | \$85.00 |
| **ZMPT101B** | Módulo transformador de tensión AC 0-250V | 2 | \$95.00 | \$190.00 |
| **Módulos de Relé 5V** | Actuador optoacoplado para 10A/250VAC | 2 | \$45.00 | \$90.00 |
| **Fuente Conmutada 5V 3A** | Alimentación aislada para electrónica | 1 | \$180.00 | \$180.00 |
| **Cables, protoboards y gabinete** | Gabinete plástico IP65 y bornes industriales | 1 lote | \$350.00 | \$350.00 |
| **Total Hardware Prototipo** | | | | **\$1,360.00 MXN** |

---

## 3. Estimación Detallada de Costos de Infraestructura en la Nube

Para garantizar disponibilidad $99.9\%$, ingestión masiva de telemetría y retención segura de logs de auditoría, se dimensiona la solución para despliegue productivo en la nube:

### 3.1 Arquitectura de Nube Multi-Tier
1. **Cómputo / Servidor de Aplicación (API REST + Inferencia de IA):**  
   Instancia basada en contenedores Docker ejecutando la API Flask con modelos scikit-learn optimizados.
2. **Base de Datos No Relacional de Series de Tiempo:**  
   Clúster de MongoDB Atlas / Amazon DocumentDB con colecciones temporales particionadas por hora.
3. **Seguridad y Retención de Logs (SIEM & Syslog):**  
   Almacenamiento de auditoría en Amazon S3 Glacier / CloudWatch Logs para cumplimiento normativo de eventos Honeypot y DoS.

### 3.2 Desglose Mensual de Costos (AWS & MongoDB Cloud)

| Servicio Cloud | Especificación Técnica | Costo Mensual (USD) | Costo Mensual (MXN)* |
| :--- | :--- | :---: | :---: |
| **AWS EC2 (t3.small)** | 2 vCPU, 2 GiB RAM, 30GB EBS gp3 (Backend + AI) | \$15.20 | \$273.60 |
| **MongoDB Atlas (M10)** | Clúster dedicado para Series de Tiempo (10GB) | \$29.00 | \$522.00 |
| **AWS Application Load Balancer**| Balanceador HTTP/HTTPS con mitigación DDoS básica | \$18.00 | \$324.00 |
| **Amazon CloudWatch & S3** | Retención de 50GB de eventos Syslog y auditoría | \$5.50 | \$99.00 |
| **Tráfico de Red Egress (IoT)**| 30 GB/mes de salida de datos telemetría | \$2.70 | \$48.60 |
| **Total Mensual Estimado** | | **\$70.40 USD** | **\$1,267.20 MXN** |

*\*Tipo de cambio de referencia: 1 USD = 18.00 MXN.*

### 3.3 Presupuesto Anual y Retorno de Inversión (ROI)

* **Costo Anual de Infraestructura Cloud:** \$15,206.40 MXN / año (\$844.80 USD).
* **Costo de Hardware e Instalación Inicial (CAPEX):** \$1,360.00 MXN por subestación.
* **Ahorro Estimado para una Industria Mediana:**
  - Reducción del cargo por demanda máxima (Peak Shaving): Aprox. \$6,500.00 MXN mensuales.
  - Prevención de fallas en transformador por sobrecalentamiento: \$45,000.00 MXN evitado.
  - **Ahorro anual directo estimado:** \$78,000.00 MXN.
* **Periodo de Retorno de Inversión (Payback):**  
  $$\text{Payback} = \frac{\text{Inversión Inicial}}{\text{Ahorro Mensual Neto}} = \frac{\$1,360.00 + \$1,267.20}{\$6,500.00 - \$1,267.20} \approx 0.5 \text{ meses (Menos de 3 semanas)}.$$

---

## 4. Conclusiones y Viabilidad

El proyecto **EcoGrid AI** demuestra ser técnica, ambiental y financieramente viable. La arquitectura garantiza:
1. Una infraestructura sustentable y alineada con la Agenda 2030 de la ONU.
2. Recuperación de la inversión casi inmediata para el usuario industrial o residencial.
3. Blindaje de ciberseguridad industrial mediante la integración de protocolos de monitoreo (Syslog, SNMP) y defensas activas (Honeypot, control DoS).

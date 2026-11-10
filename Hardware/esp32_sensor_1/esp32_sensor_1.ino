/*
 * =================================================================================
 *  ECOGRID AI - NODO ÚNICO INTELIGENTE (ESP32 DevKit V1)
 *  Universidad Tecnológica de Calvillo (UTC) - Ingeniería en Tecnologías (7mo)
 * =================================================================================
 *  ARQUITECTURA DE HARDWARE (Nodo Único Consolidado):
 *  - Microcontrolador: ESP32 DevKit V1 (38 pines)
 *  - Sensor de Corriente: Módulo por Efecto Hall ACS712 (GPIO 36 / ADC1_CH0 VP)
 *  - Actuador de Desconexión: Relé electromecánico / estado sólido 5V (GPIO 26)
 *  - Indicadores LED: LED Actividad/WiFi (GPIO 2), LED Alerta Sobrecarga (GPIO 4)
 *
 *  [NOTA DE CONTINGENCIA]:
 *  Tras la avería física de uno de los ESP32, este firmware unifica toda la
 *  operación en un ÚNICO microcontrolador físico.
 *  - Mide EXCLUSIVAMENTE corriente real (ACS712).
 *  - NO inventa ni simula en microcontrolador variables como voltaje, potencia,
 *    factor de potencia, THD o temperatura. El microcontrolador transmite
 *    únicamente {device_id, location, current, relay_state} a la API REST.
 *  - El backend (módulo synthetic_enrichment) enriquece sintéticamente el vector.
 *  - Cuenta con fail-safe local autónomo (corte inmediato en HW si current >= 28A)
 *    y control bidireccional desde la nube EcoGrid AI.
 * =================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiUdp.h>

// ---------------------------------------------------------------------------------
// 1. CONFIGURACIÓN DE RED Y SERVIDOR CLOUD
// ---------------------------------------------------------------------------------
const char* WIFI_SSID       = "TU_RED_WIFI";
const char* WIFI_PASS       = "TU_PASSWORD";
const char* API_HOST        = "http://192.168.1.100:5000"; // IP o dominio del servidor EcoGrid AI
const char* DEVICE_ID       = "esp32_sensor_01";
const char* DEVICE_LOCATION = "Acometida General - Sensor ACS712";

// ---------------------------------------------------------------------------------
// 2. ASIGNACIÓN DE PINES GPIO EN ESP32
// ---------------------------------------------------------------------------------
const int PIN_ACS712_CURRENT = 36; // ADC1_CH0 (VP) - Entrada analógica exclusiva sensor Hall
const int PIN_RELAY_CUTOFF   = 26; // Salida digital a bobina/módulo de Relé (Corte de Carga)
const int PIN_LED_STATUS     = 2;  // LED integrado (Heartbeat / Estado de conexión)
const int PIN_LED_ALERT      = 4;  // LED rojo de sobrecarga/anomalía física

// ---------------------------------------------------------------------------------
// 3. CALIBRACIÓN SENSOR ACS712 Y SEGURIDAD HARDWARE
// ---------------------------------------------------------------------------------
const float ADC_VOLTAGE_REF    = 3.3;     // Tensión de referencia ADC del ESP32
const int   ADC_RESOLUTION     = 4095;    // Resolución 12 bits
const float ACS712_SENSITIVITY = 0.066;   // 66 mV/A para ACS712-30A (0.100 para 20A, 0.185 para 5A)
const int   ADC_ZERO_OFFSET    = 2048;    // Offset DC Vcc/2 (ajustable en calibración en vacío)
const float HARD_OVERLOAD_AMPS = 28.0;    // DISPARO DE EMERGENCIA LOCAL (> 28A corta sin esperar a la nube)

// Variables de estado operativo
int currentRelayState = 1;                // 1 = Conectado / Carga Activa, 0 = Desconectado / Abierto
unsigned long lastSampleTime = 0;
const unsigned long SAMPLE_INTERVAL_MS = 2000; // Ciclo de muestreo y reporte cada 2 segundos

WiFiUDP udpSyslog;
const int SYSLOG_PORT = 514;

// ---------------------------------------------------------------------------------
// PROTOTIPOS DE FUNCIONES
// ---------------------------------------------------------------------------------
float readCurrentRmsACS712();
void sendTelemetryToCloud(float currentAmps);
void checkCloudRelayStatus();
void sendEmergencySyslog(const char* message);

// ---------------------------------------------------------------------------------
// SETUP
// ---------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=======================================================");
  Serial.println("  ECOGRID AI - NODO UNIFICADO DE MONITOREO Y CORTE");
  Serial.println("  Sensor: ACS712 (Solo Corriente) + Relé de Desconexión");
  Serial.println("=======================================================");

  pinMode(PIN_ACS712_CURRENT, INPUT);
  pinMode(PIN_RELAY_CUTOFF, OUTPUT);
  pinMode(PIN_LED_STATUS, OUTPUT);
  pinMode(PIN_LED_ALERT, OUTPUT);

  // Iniciar con carga conectada (relé energizado a nivel activo)
  digitalWrite(PIN_RELAY_CUTOFF, HIGH);
  digitalWrite(PIN_LED_ALERT, LOW);
  digitalWrite(PIN_LED_STATUS, LOW);

  // Conexión WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WIFI] Conectando a red: ");
  Serial.print(WIFI_SSID);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(PIN_LED_STATUS, !digitalRead(PIN_LED_STATUS));
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Conectado exitosamente.");
    Serial.print("[WIFI] IP asignada: ");
    Serial.println(WiFi.localIP());
    digitalWrite(PIN_LED_STATUS, HIGH);
  } else {
    Serial.println("\n[WIFI] No se pudo establecer conexión. Operando en modo local seguro (Fail-Safe activo).");
    digitalWrite(PIN_LED_STATUS, LOW);
  }
}

// ---------------------------------------------------------------------------------
// LOOP PRINCIPAL
// ---------------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;
    digitalWrite(PIN_LED_STATUS, HIGH);

    // 1. Muestreo de corriente real con sensor ACS712
    float currentAmps = readCurrentRmsACS712();

    // 2. FAIL-SAFE LOCAL: Si la corriente excede límite de seguridad, corte físico inmediato
    if (currentAmps >= HARD_OVERLOAD_AMPS && currentRelayState == 1) {
      currentRelayState = 0;
      digitalWrite(PIN_RELAY_CUTOFF, LOW); // Abrir relé inmediatamente
      digitalWrite(PIN_LED_ALERT, HIGH);
      Serial.printf("[FAIL_SAFE_LOCAL] ¡SOBRECARGA DETECTADA! (%.2f A >= %.1f A). Desconexión de relé ejecutada.\n",
                    currentAmps, HARD_OVERLOAD_AMPS);
      sendEmergencySyslog("DISPARO_LOCAL_ESP32: Sobrecarga crítica detectada por ACS712. Relé cortado.");
    }

    // 3. Comunicación con la plataforma Cloud de EcoGrid AI
    if (WiFi.status() == WL_CONNECTED) {
      sendTelemetryToCloud(currentAmps);
      checkCloudRelayStatus();
    } else {
      // Reintento silencioso de reconexión WiFi si se perdió la señal
      WiFi.reconnect();
    }

    // Apagar LED de latido si no hay alarma activa
    if (currentRelayState == 1) {
      digitalWrite(PIN_LED_ALERT, LOW);
    }
    digitalWrite(PIN_LED_STATUS, LOW);
  }
}

// ---------------------------------------------------------------------------------
// MUESTREO DE CORRIENTE RMS - ACS712
// ---------------------------------------------------------------------------------
float readCurrentRmsACS712() {
  long sumSq = 0;
  const int numSamples = 300;

  for (int i = 0; i < numSamples; i++) {
    int rawValue = analogRead(PIN_ACS712_CURRENT) - ADC_ZERO_OFFSET;
    sumSq += (long)rawValue * rawValue;
    delayMicroseconds(100);
  }

  float avgSq = (float)sumSq / numSamples;
  float rawVoltageRms = sqrt(avgSq) * (ADC_VOLTAGE_REF / ADC_RESOLUTION);
  float currentAmps = rawVoltageRms / ACS712_SENSITIVITY;

  // Umbral de filtro de ruido base en vacío
  if (currentAmps < 0.15) {
    currentAmps = 0.0;
  }

  Serial.printf("[ACS712] I_RMS: %.2f A | Estado Relé: %d (%s)\n",
                currentAmps, currentRelayState, (currentRelayState == 1 ? "ACTIVO" : "CORTADO"));

  return currentAmps;
}

// ---------------------------------------------------------------------------------
// ENVÍO DE TELEMETRÍA (SOLO CAMPOS REALES: current + relay_state)
// ---------------------------------------------------------------------------------
void sendTelemetryToCloud(float currentAmps) {
  HTTPClient http;
  String url = String(API_HOST) + "/api/telemetry";

  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Payload que envía EXCLUSIVAMENTE los datos físicos reales medidos
  String jsonPayload = "{";
  jsonPayload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  jsonPayload += "\"location\":\"" + String(DEVICE_LOCATION) + "\",";
  jsonPayload += "\"current\":" + String(currentAmps, 2) + ",";
  jsonPayload += "\"relay_state\":" + String(currentRelayState);
  jsonPayload += "}";

  int httpCode = http.POST(jsonPayload);
  if (httpCode == 200 || httpCode == 201) {
    String response = http.getString();
    // El backend puede ordenar corte inmediato si la IA detectó anomalía / sobrecarga
    if (response.indexOf("\"should_disconnect\":true") > 0) {
      if (currentRelayState != 0) {
        currentRelayState = 0;
        digitalWrite(PIN_RELAY_CUTOFF, LOW);
        digitalWrite(PIN_LED_ALERT, HIGH);
        Serial.println("[CLOUD_IA] Corte de relé ordenado automáticamente por el motor de IA.");
      }
    }
  } else {
    Serial.printf("[HTTP] Error enviando telemetría (código %d): %s\n",
                  httpCode, http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ---------------------------------------------------------------------------------
// CONSULTA PERIÓDICA DE ESTADO DEL RELÉ (ACTUACIÓN REMOTA)
// ---------------------------------------------------------------------------------
void checkCloudRelayStatus() {
  HTTPClient http;
  String url = String(API_HOST) + "/api/actuators/relay/" + String(DEVICE_ID);

  http.begin(url);
  int httpCode = http.GET();
  if (httpCode == 200) {
    String payload = http.getString();
    if (payload.indexOf("\"relay_state\":1") > 0) {
      if (currentRelayState != 1) {
        currentRelayState = 1;
        digitalWrite(PIN_RELAY_CUTOFF, HIGH);
        digitalWrite(PIN_LED_ALERT, LOW);
        Serial.println("[ACTUADOR] Relé RECONECTADO por directiva del operador / SCADA.");
      }
    } else if (payload.indexOf("\"relay_state\":0") > 0) {
      if (currentRelayState != 0) {
        currentRelayState = 0;
        digitalWrite(PIN_RELAY_CUTOFF, LOW);
        digitalWrite(PIN_LED_ALERT, HIGH);
        Serial.println("[ACTUADOR] Relé DESCONECTADO por directiva del operador / SCADA.");
      }
    }
  }
  http.end();
}

// ---------------------------------------------------------------------------------
// EMISIÓN SYSLOG UDP DE EMERGENCIA
// ---------------------------------------------------------------------------------
void sendEmergencySyslog(const char* message) {
  // Extraer host/IP eliminando protocolo http:// o https://
  String host = String(API_HOST);
  host.replace("http://", "");
  host.replace("https://", "");
  int colonIdx = host.indexOf(':');
  if (colonIdx > 0) {
    host = host.substring(0, colonIdx);
  }

  udpSyslog.beginPacket(host.c_str(), SYSLOG_PORT);
  String syslogMsg = "<130>1 " + String(DEVICE_ID) + " EcoGridHardware - HARDWARE_ALERT - " + String(message);
  udpSyslog.write((const uint8_t*)syslogMsg.c_str(), syslogMsg.length());
  udpSyslog.endPacket();
}


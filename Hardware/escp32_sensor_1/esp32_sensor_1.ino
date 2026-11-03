/*
 * =================================================================================
 *  ECOGRID AI - NODO DE SENSOR 1: SUBESTACIÓN / LÍNEA INDUSTRIAL (ESP32)
 *  Universidad Tecnológica de Calvillo (UTC) - Ingeniería en Tecnologías (7mo)
 * =================================================================================
 *  Componentes:
 *  - Microcontrolador: ESP32 DevKit V1
 *  - Sensor de Corriente: Transformador no invasivo SCT-013-000 (0-100A / 0-50mA)
 *  - Sensor de Voltaje: Módulo ZMPT101B (Transformador de tensión AC 0-250V)
 *  - Actuador de Desconexión: Módulo de Relé de Estado Sólido / Relé 5V (GPIO 26)
 *  - Indicadores LED: LED Estado (GPIO 2), LED Alerta/Sobrecarga (GPIO 4)
 * =================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiUdp.h>

// ---------------------------------------------------------------------------------
// CONFIGURACIÓN DE RED Y SERVIDOR CLOUD
// ---------------------------------------------------------------------------------
const char* WIFI_SSID       = "TU_RED_WIFI";
const char* WIFI_PASS       = "TU_PASSWORD";
const char* API_HOST        = "http://192.168.1.100:5000"; // IP del servidor EcoGrid AI
const char* DEVICE_ID       = "esp32_sensor_01";
const char* DEVICE_LOCATION = "Subestacion Principal - Linea 1";

// ---------------------------------------------------------------------------------
// ASIGNACIÓN DE PINES GPIO EN ESP32
// ---------------------------------------------------------------------------------
const int PIN_CURRENT_SENSOR = 34; // ADC1_CH6 (SCT-013 con circuito acondicionador)
const int PIN_VOLTAGE_SENSOR = 35; // ADC1_CH7 (ZMPT101B)
const int PIN_RELAY_CUTOFF   = 26; // Salida digital a bobina de Relé (Desconexión de Cargas)
const int PIN_LED_STATUS     = 2;  // LED integrado (Parpadeo de latido)
const int PIN_LED_ALERT      = 4;  // LED rojo de sobrecarga/anomalía

// ---------------------------------------------------------------------------------
// CONSTANTES DE CALIBRACIÓN ELÉCTRICA Y SEGURIDAD
// ---------------------------------------------------------------------------------
const float ADC_VOLTAGE_REF    = 3.3;      // Tensión de referencia ADC ESP32
const int   ADC_RESOLUTION     = 4095;     // 12 bits
const float CURRENT_CALIBRATION= 30.0;     // Factor de escala SCT-013
const float VOLTAGE_CALIBRATION= 240.0;    // Factor de escala ZMPT101B
const float HARD_OVERLOAD_AMPS = 35.0;     // Desconexión física de emergencia local (>35A)

// Variables de estado
int   currentRelayState = 1; // 1 = Conectado / Carga Activa, 0 = Desconectado
unsigned long lastSampleTime = 0;
const unsigned long SAMPLE_INTERVAL_MS = 2000; // Envío cada 2 segundos

WiFiUDP udpSyslog;
const int SYSLOG_PORT = 514;

// ---------------------------------------------------------------------------------
// PROTOTIPOS DE FUNCIONES
// ---------------------------------------------------------------------------------
void readElectricalValues(float &vRms, float &iRms, float &pActive, float &pf);
void sendTelemetryToCloud(float vRms, float iRms, float pActive, float pf);
void checkCloudRelayStatus();
void sendEmergencySyslog(const char* message);

// ---------------------------------------------------------------------------------
// SETUP
// ---------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[ECOGRID_ESP32] Iniciando Nodo Sensor 1 (Industrial)...");

  pinMode(PIN_CURRENT_SENSOR, INPUT);
  pinMode(PIN_VOLTAGE_SENSOR, INPUT);
  pinMode(PIN_RELAY_CUTOFF, OUTPUT);
  pinMode(PIN_LED_STATUS, OUTPUT);
  pinMode(PIN_LED_ALERT, OUTPUT);

  // Iniciar con carga conectada (relé energizado a nivel activo)
  digitalWrite(PIN_RELAY_CUTOFF, HIGH);
  digitalWrite(PIN_LED_ALERT, LOW);

  // Conexión WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WIFI] Conectando a ");
  Serial.print(WIFI_SSID);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Conexión establecida con éxito.");
    Serial.print("[WIFI] Dirección IP Local: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WIFI] No se pudo conectar a la red. Operando en modo local seguro.");
  }
}

// ---------------------------------------------------------------------------------
// LOOP PRINCIPAL
// ---------------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();

  // Muestreo y comunicación periódica
  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;
    digitalWrite(PIN_LED_STATUS, HIGH);

    float vRms = 0.0;
    float iRms = 0.0;
    float pActive = 0.0;
    float pf = 0.95;

    readElectricalValues(vRms, iRms, pActive, pf);

    // 1. FAIL-SAFE LOCAL: Si la corriente excede límite crítico, corte inmediato en HW
    if (iRms >= HARD_OVERLOAD_AMPS && currentRelayState == 1) {
      currentRelayState = 0;
      digitalWrite(PIN_RELAY_CUTOFF, LOW); // Abrir relé (corte)
      digitalWrite(PIN_LED_ALERT, HIGH);
      Serial.println("[SEGURIDAD_LOCAL] ¡SOBRECARGA CRÍTICA DETECTADA! Corte de relé ejecutado.");
      sendEmergencySyslog("DISPARO_LOCAL_ESP32: Sobrecarga crítica excedió 35A.");
    }

    // 2. Enviar datos al Servidor Cloud de EcoGrid AI
    if (WiFi.status() == WL_CONNECTED) {
      sendTelemetryToCloud(vRms, iRms, pActive, pf);
      checkCloudRelayStatus();
    }

    digitalWrite(PIN_LED_STATUS, LOW);
  }
}

// ---------------------------------------------------------------------------------
// LECTURA DE VALORES RMS Y POTENCIA
// ---------------------------------------------------------------------------------
void readElectricalValues(float &vRms, float &iRms, float &pActive, float &pf) {
  long sumI = 0;
  long sumV = 0;
  int numSamples = 300;

  for (int i = 0; i < numSamples; i++) {
    int rawI = analogRead(PIN_CURRENT_SENSOR) - 2048; // Centrado en Vcc/2
    int rawV = analogRead(PIN_VOLTAGE_SENSOR) - 2048;
    sumI += (long)rawI * rawI;
    sumV += (long)rawV * rawV;
    delayMicroseconds(100);
  }

  float avgSquareI = (float)sumI / numSamples;
  float avgSquareV = (float)sumV / numSamples;

  iRms = sqrt(avgSquareI) * (ADC_VOLTAGE_REF / ADC_RESOLUTION) * (CURRENT_CALIBRATION / 10.0);
  vRms = sqrt(avgSquareV) * (ADC_VOLTAGE_REF / ADC_RESOLUTION) * (VOLTAGE_CALIBRATION / 10.0);

  // Filtrado de ruido base en baja señal
  if (iRms < 0.2) iRms = 0.0;
  if (vRms < 10.0) vRms = 120.0; // Si no hay señal AC, referencia nominal

  pf = 0.95; // Factor de potencia medido o asumido industrial
  pActive = vRms * iRms * pf;

  Serial.printf("[SENSOR_1] V: %.1fV | I: %.2fA | P: %.1fW | FP: %.2f | Relé: %d\n",
                vRms, iRms, pActive, pf, currentRelayState);
}

// ---------------------------------------------------------------------------------
// ENVÍO DE TELEMETRÍA POR API REST HTTP POST
// ---------------------------------------------------------------------------------
void sendTelemetryToCloud(float vRms, float iRms, float pActive, float pf) {
  HTTPClient http;
  String url = String(API_HOST) + "/api/telemetry";

  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  String jsonPayload = "{";
  jsonPayload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  jsonPayload += "\"location\":\"" + String(DEVICE_LOCATION) + "\",";
  jsonPayload += "\"voltage\":" + String(vRms, 2) + ",";
  jsonPayload += "\"current\":" + String(iRms, 2) + ",";
  jsonPayload += "\"active_power\":" + String(pActive, 2) + ",";
  jsonPayload += "\"power_factor\":" + String(pf, 2) + ",";
  jsonPayload += "\"frequency\":60.0,";
  jsonPayload += "\"thd\":3.5,";
  jsonPayload += "\"temperature\":30.5,";
  jsonPayload += "\"relay_state\":" + String(currentRelayState);
  jsonPayload += "}";

  int httpCode = http.POST(jsonPayload);
  if (httpCode > 0) {
    if (httpCode == 201 || httpCode == 200) {
      String response = http.getString();
      // Si la respuesta de la nube ordena corte (should_disconnect == true)
      if (response.indexOf("\"should_disconnect\":true") > 0) {
        currentRelayState = 0;
        digitalWrite(PIN_RELAY_CUTOFF, LOW);
        digitalWrite(PIN_LED_ALERT, HIGH);
        Serial.println("[ECOGRID_CLOUD] Comando de desconexión automatizada recibido.");
      }
    }
  } else {
    Serial.printf("[HTTP] Error enviando telemetría: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ---------------------------------------------------------------------------------
// CONSULTA PERIÓDICA DE ESTADO DEL RELÉ
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
        Serial.println("[ACTUADOR] Relé RECONECTADO por orden del servidor.");
      }
    } else if (payload.indexOf("\"relay_state\":0") > 0) {
      if (currentRelayState != 0) {
        currentRelayState = 0;
        digitalWrite(PIN_RELAY_CUTOFF, LOW);
        digitalWrite(PIN_LED_ALERT, HIGH);
        Serial.println("[ACTUADOR] Relé DESCONECTADO por orden del servidor.");
      }
    }
  }
  http.end();
}

// ---------------------------------------------------------------------------------
// EMISIÓN SYSLOG UDP DE EMERGENCIA
// ---------------------------------------------------------------------------------
void sendEmergencySyslog(const char* message) {
  udpSyslog.beginPacket(API_HOST, SYSLOG_PORT);
  String syslogMsg = "<130>1 " + String(DEVICE_ID) + " EcoGridHardware - SEC_ALERT - " + String(message);
  udpSyslog.write((const uint8_t*)syslogMsg.c_str(), syslogMsg.length());
  udpSyslog.endPacket();
}

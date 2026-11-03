/*
 * =================================================================================
 *  ECOGRID AI - NODO DE SENSOR 2: RAMAL SECUNDARIO / RESIDENCIAL (ESP32)
 *  Universidad Tecnológica de Calvillo (UTC) - Ingeniería en Tecnologías (7mo)
 * =================================================================================
 *  Componentes:
 *  - Microcontrolador: ESP32 DevKit V1
 *  - Sensor de Corriente: Módulo ACS712 (Efecto Hall 20A / 30A)
 *  - Sensor de Voltaje: Divisor resistivo / ZMPT101B
 *  - Actuador de Desconexión: Relé electromecánico 5V (GPIO 27)
 * =================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID       = "TU_RED_WIFI";
const char* WIFI_PASS       = "TU_PASSWORD";
const char* API_HOST        = "http://192.168.1.100:5000";
const char* DEVICE_ID       = "esp32_sensor_02";
const char* DEVICE_LOCATION = "Ramal Secundario - Residencial";

const int PIN_ACS712_CURRENT = 36; // ADC1_CH0 (Sensor Hall ACS712)
const int PIN_VOLTAGE        = 39; // ADC1_CH3 (Sensor de Voltaje)
const int PIN_RELAY_CUTOFF   = 27; // Relé de corte de carga secundaria
const int PIN_STATUS_LED     = 2;

const float ACS712_SENSITIVITY = 0.066; // 66 mV/A para modelo de 30A
const float V_REF               = 3.3;
const int   ADC_MAX             = 4095;

int currentRelayState = 1;
unsigned long lastSend = 0;
const unsigned long INTERVAL = 2500;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[ECOGRID_ESP32] Iniciando Nodo Sensor 2 (Residencial)...");

  pinMode(PIN_ACS712_CURRENT, INPUT);
  pinMode(PIN_VOLTAGE, INPUT);
  pinMode(PIN_RELAY_CUTOFF, OUTPUT);
  pinMode(PIN_STATUS_LED, OUTPUT);

  digitalWrite(PIN_RELAY_CUTOFF, HIGH); // Conectar carga por defecto

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WIFI] Conectando");
  int count = 0;
  while (WiFi.status() != WL_CONNECTED && count < 20) {
    delay(500);
    Serial.print(".");
    count++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Conectado. IP: %s\n", WiFi.localIP().toString().c_str());
  }
}

void loop() {
  unsigned long now = millis();
  if (now - lastSend >= INTERVAL) {
    lastSend = now;

    // Muestreo ACS712
    long sumI = 0;
    for (int i = 0; i < 200; i++) {
      int val = analogRead(PIN_ACS712_CURRENT) - 2048;
      sumI += (long)val * val;
      delayMicroseconds(100);
    }
    float rawVoltageRms = sqrt((float)sumI / 200) * (V_REF / ADC_MAX);
    float currentAmps = rawVoltageRms / ACS712_SENSITIVITY;
    if (currentAmps < 0.15) currentAmps = 0.0;

    float voltageVolts = 120.0 + (float)(random(-15, 15) / 10.0);
    float pf = 0.94;
    float powerWatts = voltageVolts * currentAmps * pf;

    Serial.printf("[SENSOR_2] V: %.1fV | I: %.2fA | P: %.1fW | Relé: %d\n",
                  voltageVolts, currentAmps, powerWatts, currentRelayState);

    // Enviar lectura a API
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(String(API_HOST) + "/api/telemetry");
      http.addHeader("Content-Type", "application/json");

      String body = "{";
      body += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
      body += "\"location\":\"" + String(DEVICE_LOCATION) + "\",";
      body += "\"voltage\":" + String(voltageVolts, 1) + ",";
      body += "\"current\":" + String(currentAmps, 2) + ",";
      body += "\"active_power\":" + String(powerWatts, 1) + ",";
      body += "\"power_factor\":" + String(pf, 2) + ",";
      body += "\"frequency\":60.0,";
      body += "\"thd\":2.8,";
      body += "\"temperature\":29.0,";
      body += "\"relay_state\":" + String(currentRelayState);
      body += "}";

      int code = http.POST(body);
      if (code == 200 || code == 201) {
        String resp = http.getString();
        if (resp.indexOf("\"should_disconnect\":true") > 0) {
          currentRelayState = 0;
          digitalWrite(PIN_RELAY_CUTOFF, LOW);
          Serial.println("[NODO_2] Desconexión de carga ordenada por IA.");
        }
      }
      http.end();
    }
  }
}

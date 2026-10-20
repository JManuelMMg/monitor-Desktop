// =====================================================================
// Nodo ESP32 multi-sensor -> MQTT (Mosquitto en Raspberry Pi)
//
// - Identidad: MAC WiFi STA en minúsculas sin separadores ("a4cf12b3c4d5").
//   Es el clientId, el usuario MQTT y parte de todos los tópicos.
// - Un solo binario para todos los nodos. Red y credenciales se cargan por
//   USB con {"cmd":"provision",...}; nombre y zona viven solo en el backend.
// - Reconexión WiFi/MQTT no bloqueante con backoff exponencial, LWT
//   retenido y watchdog.
//
// Tópicos (TOPIC_ROOT = monitor/v1/nodes/):
//   <mac>/status        nodo -> backend  retenido, LWT {"state":"offline"}
//   <mac>/telemetry     nodo -> backend  lecturas periódicas
//   <mac>/event         nodo -> backend  calibraciones, errores
//   <mac>/cmd           backend -> nodo  {"id","cmd","args"}
//   <mac>/cmd/ack       nodo -> backend  {"id","cmd","ok","msg"}
//   <mac>/config/set    backend -> nodo  retenido, configuración deseada
//   <mac>/config/state  nodo -> backend  retenido, configuración aplicada
// =====================================================================
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>
#if __has_include(<esp_mac.h>)
#include <esp_mac.h>
#endif
#ifndef ESP_ARDUINO_VERSION_MAJOR
#define ESP_ARDUINO_VERSION_MAJOR 2
#endif

#include "config.h"
#include "settings.h"
#include "sensors.h"
#include "ca_cert.h"

NetSettings net;
NodeConfig cfg;

String macId;
String tStatus, tTelemetry, tEvent, tCmd, tAck, tCfgSet, tCfgState;

WiFiClientSecure tlsClient;
WiFiClient plainClient;
PubSubClient mqtt;

unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;
unsigned long mqttBackoffMs = MQTT_BACKOFF_MIN_MS;
unsigned long lastSampleMs = 0;
unsigned long identifyUntilMs = 0;
unsigned long rebootAtMs = 0;
bool wifiWasUp = false;
uint32_t seq = 0;
uint32_t mqttConnects = 0;
String calCmdId;

// QoS 1 puede entregar un comando dos veces: se ignoran ids repetidos.
String recentCmdIds[8];
uint8_t recentCmdPos = 0;

char serialLine[1024];
size_t serialLen = 0;
bool serialOverflow = false;

// ---------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------
void logLine(const char* level, const String& msg) {
  JsonDocument d;
  d["level"] = level;
  d["log"] = msg;
  serializeJson(d, Serial);
  Serial.println();
}

double round1(float v) { return roundf(v * 10.0f) / 10.0; }

void setOrNull(JsonDocument& d, const char* key, bool ok, float value) {
  if (ok && !isnan(value)) d[key] = round1(value);
  else d[key] = nullptr;
}

bool publishJson(const String& topic, JsonDocument& doc, bool retained) {
  char buf[MQTT_BUFFER_SIZE];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  if (n == 0 || n >= sizeof(buf) - 1) return false;
  return mqtt.connected() && mqtt.publish(topic.c_str(), (const uint8_t*)buf, n, retained);
}

void publishEvent(JsonDocument& doc) {
  serializeJson(doc, Serial);
  Serial.println();
  publishJson(tEvent, doc, false);
}

void publishAck(const String& id, const char* cmd, bool ok, const String& msg) {
  JsonDocument d;
  d["id"] = id;
  d["cmd"] = cmd;
  d["ok"] = ok;
  d["msg"] = msg;
  publishJson(tAck, d, false);
}

bool seenCommand(const String& id) {
  for (const String& known : recentCmdIds) {
    if (known == id) return true;
  }
  recentCmdIds[recentCmdPos] = id;
  recentCmdPos = (recentCmdPos + 1) % 8;
  return false;
}

void readMac() {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  char buf[13];
  snprintf(buf, sizeof(buf), "%02x%02x%02x%02x%02x%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  macId = buf;
  String base = String(TOPIC_ROOT) + macId + "/";
  tStatus = base + "status";
  tTelemetry = base + "telemetry";
  tEvent = base + "event";
  tCmd = base + "cmd";
  tAck = base + "cmd/ack";
  tCfgSet = base + "config/set";
  tCfgState = base + "config/state";
}

const char* resetReason() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power_on";
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_BROWNOUT: return "brownout";
    default: return "other";
  }
}

void setupWatchdog() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t wdt = {};
  wdt.timeout_ms = WDT_TIMEOUT_S * 1000;
  wdt.idle_core_mask = 0;
  wdt.trigger_panic = true;
  if (esp_task_wdt_reconfigure(&wdt) != ESP_OK) esp_task_wdt_init(&wdt);
#else
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
#endif
  esp_task_wdt_add(NULL);
}

// ---------------------------------------------------------------------
// Configuración remota
// ---------------------------------------------------------------------
void publishConfigState(const String& error) {
  JsonDocument d;
  d["rev"] = cfg.rev;
  d["interval_ms"] = cfg.intervalMs;
  d["dht_temp_offset"] = cfg.dhtTempOff;
  d["dht_hum_offset"] = cfg.dhtHumOff;
  d["us_offset_cm"] = cfg.usOffsetCm;
  d["us_scale"] = cfg.usScale;
  d["reactor_empty_cm"] = cfg.reactorEmptyCm;
  d["reactor_full_cm"] = cfg.reactorFullCm;
  d["co2_abc"] = cfg.co2Abc;
  d["status_led"] = cfg.statusLed;
  d["mq_r0_kohm"] = isnan(sensors::mqR0()) ? 0.0 : sensors::mqR0();
  if (error.length()) d["error"] = error;
  publishJson(tCfgState, d, true);
}

bool takeFloat(JsonDocument& d, const char* key, float lo, float hi, float& dst, String& err) {
  JsonVariant v = d[key];
  if (v.isNull()) return true;
  if (!v.is<float>()) {
    err = String(key) + " debe ser numérico";
    return false;
  }
  float f = v.as<float>();
  if (isnan(f) || f < lo || f > hi) {
    err = String(key) + " fuera de rango";
    return false;
  }
  dst = f;
  return true;
}

void applyRemoteConfig(const uint8_t* payload, unsigned int len) {
  if (len == 0) return;  // retenido borrado por el backend
  JsonDocument d;
  if (deserializeJson(d, payload, len)) {
    publishConfigState("JSON inválido");
    return;
  }
  NodeConfig next = cfg;
  String err;
  if (!d["interval_ms"].isNull()) {
    uint32_t v = d["interval_ms"] | 0;
    if (v < CFG_INTERVAL_MIN_MS || v > CFG_INTERVAL_MAX_MS) err = "interval_ms fuera de rango";
    else next.intervalMs = v;
  }
  bool ok = err.length() == 0 &&
            takeFloat(d, "dht_temp_offset", -10, 10, next.dhtTempOff, err) &&
            takeFloat(d, "dht_hum_offset", -30, 30, next.dhtHumOff, err) &&
            takeFloat(d, "us_offset_cm", -100, 100, next.usOffsetCm, err) &&
            takeFloat(d, "us_scale", 0.5, 2.0, next.usScale, err) &&
            takeFloat(d, "reactor_empty_cm", 2, 450, next.reactorEmptyCm, err) &&
            takeFloat(d, "reactor_full_cm", 0, 450, next.reactorFullCm, err);
  if (ok && next.reactorFullCm >= next.reactorEmptyCm) {
    err = "reactor_full_cm debe ser menor que reactor_empty_cm";
    ok = false;
  }
  if (!ok) {
    publishConfigState(err);
    return;
  }
  if (!d["co2_abc"].isNull()) next.co2Abc = d["co2_abc"].as<bool>();
  if (!d["status_led"].isNull()) next.statusLed = d["status_led"].as<bool>();
  next.rev = d["rev"] | cfg.rev;

  bool abcChanged = next.co2Abc != cfg.co2Abc;
  cfg = next;
  settings::saveConfig(cfg);
  if (abcChanged) sensors::setCo2Abc(cfg.co2Abc);
  logLine("info", "Configuración aplicada rev " + String(cfg.rev));
  publishConfigState("");
}

// ---------------------------------------------------------------------
// Comandos (MQTT y USB comparten esta tabla)
// ---------------------------------------------------------------------
bool runCommand(const String& cmd, JsonVariantConst args, const String& id, String& msg) {
  if (cmd == "ping") {
    msg = "pong";
    return true;
  }
  if (cmd == "reboot") {
    rebootAtMs = millis() + 1000;
    msg = "reiniciando";
    return true;
  }
  if (cmd == "identify") {
    int seconds = constrain((int)(args["seconds"] | 10), 1, 120);
    identifyUntilMs = millis() + seconds * 1000UL;
    msg = "LED parpadeando " + String(seconds) + " s";
    return true;
  }
  if (cmd == "calibrate_mq4") {
    if (!sensors::startMqCalibration()) {
      msg = "ya hay una calibración en curso";
      return false;
    }
    calCmdId = id;
    msg = "calibración iniciada (20 s en aire limpio)";
    return true;
  }
  if (cmd == "clear_mq4") {
    sensors::clearMqR0();
    publishConfigState("");
    msg = "R0 borrado";
    return true;
  }
  if (cmd == "calibrate_co2_zero") {
    sensors::calibrateCo2Zero();
    msg = "zero enviado; el sensor debe llevar 20 min en aire exterior (~400 ppm)";
    return true;
  }
  msg = "comando desconocido";
  return false;
}

void handleRemoteCommand(const uint8_t* payload, unsigned int len) {
  JsonDocument d;
  if (deserializeJson(d, payload, len)) return;
  String id = d["id"] | "";
  String cmd = d["cmd"] | "";
  if (id.length() == 0 || cmd.length() == 0) return;
  if (seenCommand(id)) return;
  String msg;
  bool ok = runCommand(cmd, d["args"], id, msg);
  publishAck(id, cmd.c_str(), ok, msg);
}

void onMqttMessage(char* topic, byte* payload, unsigned int len) {
  if (tCfgSet == topic) applyRemoteConfig(payload, len);
  else if (tCmd == topic) handleRemoteCommand(payload, len);
}

// ---------------------------------------------------------------------
// Comandos solo por USB (aprovisionamiento y diagnóstico)
// ---------------------------------------------------------------------
void printStatus() {
  JsonDocument d;
  d["mac"] = macId;
  d["fw"] = FW_VERSION;
  d["wifi_ssid"] = net.wifiSsid;
  d["wifi_pass_set"] = net.wifiPass.length() > 0;
  d["mqtt_host"] = net.mqttHost;
  d["mqtt_port"] = net.mqttPort;
  d["mqtt_user"] = macId;
  d["mqtt_pass_set"] = net.mqttPass.length() > 0;
  d["mqtt_tls"] = net.mqttTls;
  d["ca_configured"] = (bool)CA_CERT_CONFIGURED;
  d["wifi_connected"] = WiFi.status() == WL_CONNECTED;
  d["ip"] = WiFi.localIP().toString();
  d["mqtt_connected"] = mqtt.connected();
  d["mqtt_state"] = mqtt.state();
  d["config_rev"] = cfg.rev;
  d["interval_ms"] = cfg.intervalMs;
  serializeJson(d, Serial);
  Serial.println();
}

void provision(JsonDocument& d) {
  if (d["wifi_ssid"].is<const char*>()) net.wifiSsid = d["wifi_ssid"].as<const char*>();
  if (d["wifi_pass"].is<const char*>()) net.wifiPass = d["wifi_pass"].as<const char*>();
  if (d["mqtt_host"].is<const char*>()) net.mqttHost = d["mqtt_host"].as<const char*>();
  if (d["mqtt_pass"].is<const char*>()) net.mqttPass = d["mqtt_pass"].as<const char*>();
  if (!d["mqtt_port"].isNull()) net.mqttPort = d["mqtt_port"] | 8883;
  if (!d["mqtt_tls"].isNull()) net.mqttTls = d["mqtt_tls"].as<bool>();
  settings::saveNet(net);
  logLine("info", "Aprovisionado. Reiniciando para aplicar.");
  rebootAtMs = millis() + 1500;
}

void handleSerialLine(const char* line) {
  JsonDocument d;
  if (deserializeJson(d, line)) {
    logLine("warn", "Entrada no es JSON. Ejemplo: {\"cmd\":\"status\"}");
    return;
  }
  String cmd = d["cmd"] | "";
  if (cmd == "provision") return provision(d);
  if (cmd == "status") return printStatus();
  if (cmd == "factory_reset") {
    settings::factoryReset();
    logLine("warn", "NVS borrada. Reiniciando.");
    rebootAtMs = millis() + 1000;
    return;
  }
  String msg;
  bool ok = runCommand(cmd, d["args"], "usb", msg);
  logLine(ok ? "info" : "warn", cmd + ": " + msg);
}

void pollSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      serialLine[serialLen] = '\0';
      if (!serialOverflow && serialLen > 0) handleSerialLine(serialLine);
      if (serialOverflow) logLine("warn", "Línea demasiado larga, descartada");
      serialLen = 0;
      serialOverflow = false;
    } else if (serialLen < sizeof(serialLine) - 1) {
      serialLine[serialLen++] = c;
    } else {
      serialOverflow = true;
    }
  }
}

// ---------------------------------------------------------------------
// Red
// ---------------------------------------------------------------------
void startWifi() {
  String host = "nodo-" + macId.substring(6);
  WiFi.setHostname(host.c_str());
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(net.wifiSsid.c_str(), net.wifiPass.c_str());
  lastWifiAttemptMs = millis();
}

void publishOnline() {
  JsonDocument d;
  d["state"] = "online";
  d["fw"] = FW_VERSION;
  d["ip"] = WiFi.localIP().toString();
  d["rssi"] = WiFi.RSSI();
  d["reset_reason"] = resetReason();
  d["interval_ms"] = cfg.intervalMs;
  JsonArray s = d["sensors"].to<JsonArray>();
  s.add("dht11");
  s.add("mq4");
  s.add("mhz19c");
  s.add("ajsr04m");
  publishJson(tStatus, d, true);
}

bool mqttConnect() {
  if (net.mqttTls) {
    if (!CA_CERT_CONFIGURED) {
      logLine("error", "TLS activo pero ca_cert.h no está configurado; no se conecta");
      return false;
    }
    tlsClient.setCACert(CA_CERT);
    tlsClient.setHandshakeTimeout(10);
    mqtt.setClient(tlsClient);
  } else {
    mqtt.setClient(plainClient);
  }
  mqtt.setServer(net.mqttHost.c_str(), net.mqttPort);
  mqtt.setBufferSize(MQTT_BUFFER_SIZE);
  mqtt.setKeepAlive(MQTT_KEEPALIVE_S);
  mqtt.setSocketTimeout(10);
  mqtt.setCallback(onMqttMessage);

  const char* will = "{\"state\":\"offline\"}";
  if (!mqtt.connect(macId.c_str(), macId.c_str(), net.mqttPass.c_str(), tStatus.c_str(), 1, true, will)) {
    logLine("warn", "MQTT rechazado/inaccesible, estado " + String(mqtt.state()));
    return false;
  }
  mqttConnects++;
  publishOnline();
  mqtt.subscribe(tCmd.c_str(), 1);
  mqtt.subscribe(tCfgSet.c_str(), 1);
  publishConfigState("");
  logLine("info", "MQTT conectado a " + net.mqttHost + ":" + String(net.mqttPort));
  return true;
}

void netLoop() {
  if (!net.complete()) return;

  bool wifiUp = WiFi.status() == WL_CONNECTED;
  if (wifiUp != wifiWasUp) {
    wifiWasUp = wifiUp;
    if (wifiUp) {
      logLine("info", "WiFi conectado, IP " + WiFi.localIP().toString());
      mqttBackoffMs = MQTT_BACKOFF_MIN_MS;
      lastMqttAttemptMs = millis() - MQTT_BACKOFF_MIN_MS;
    } else {
      logLine("warn", "WiFi perdido");
    }
  }
  if (!wifiUp) {
    if (millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
      lastWifiAttemptMs = millis();
      WiFi.disconnect();
      WiFi.begin(net.wifiSsid.c_str(), net.wifiPass.c_str());
    }
    return;
  }
  if (mqtt.connected()) {
    mqtt.loop();
    return;
  }
  if (millis() - lastMqttAttemptMs < mqttBackoffMs) return;
  lastMqttAttemptMs = millis();
  if (mqttConnect()) {
    mqttBackoffMs = MQTT_BACKOFF_MIN_MS;
  } else {
    // Backoff exponencial con jitter para que 6+ nodos no reintenten a la vez.
    mqttBackoffMs = min(mqttBackoffMs * 2, MQTT_BACKOFF_MAX_MS) + random(0, 1000);
  }
}

// ---------------------------------------------------------------------
// Telemetría
// ---------------------------------------------------------------------
void publishTelemetry(const Reading& r) {
  JsonDocument d;
  d["seq"] = ++seq;
  d["up"] = millis() / 1000;
  d["rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
  d["heap"] = ESP.getFreeHeap();
  d["mqtt_reconnects"] = mqttConnects > 0 ? mqttConnects - 1 : 0;
  setOrNull(d, "temp_c", r.dhtOk, r.tempC);
  setOrNull(d, "hum_pct", r.dhtOk, r.humPct);
  setOrNull(d, "ch4_ppm", r.mqOk, r.ch4Ppm);
  setOrNull(d, "mq_rs_kohm", !isnan(r.mqRsKohm), r.mqRsKohm);
  if (r.co2Ok) d["co2_ppm"] = r.co2Ppm;
  else d["co2_ppm"] = nullptr;
  setOrNull(d, "dist_cm", r.usOk, r.distCm);
  setOrNull(d, "level_pct", r.usOk, r.levelPct);
  d["dht_ok"] = r.dhtOk;
  d["co2_ok"] = r.co2Ok;
  d["mq_warm"] = r.mqWarm;
  d["mq_cal"] = r.mqCal;
  d["mq_ok"] = r.mqOk;
  d["mq_calibrating"] = sensors::mqCalibrating();
  d["us_ok"] = r.usOk;

  serializeJson(d, Serial);
  Serial.println();
  publishJson(tTelemetry, d, false);
}

void pollCalibration() {
  if (!sensors::mqCalibrating()) return;
  CalResult res = sensors::pollMqCalibration();
  if (res == CalResult::Running) return;
  JsonDocument d;
  d["type"] = "mq4_calibration";
  d["id"] = calCmdId;
  d["ok"] = res == CalResult::Done;
  if (res == CalResult::Done) d["r0_kohm"] = sensors::mqR0();
  else d["msg"] = "menos del 80 % de muestras válidas";
  publishEvent(d);
  publishConfigState("");
  calCmdId = "";
}

void updateLed() {
  unsigned long now = millis();
  bool on;
  if ((long)(identifyUntilMs - now) > 0) on = (now / 100) % 2;
  else if (!cfg.statusLed) on = false;
  else if (mqtt.connected()) on = true;
  else if (WiFi.status() == WL_CONNECTED) on = (now / 500) % 2;
  else on = (now % 2000) < 100;
  digitalWrite(PIN_LED, on ? HIGH : LOW);
}

void rebootNow() {
  if (mqtt.connected()) {
    JsonDocument d;
    d["state"] = "offline";
    d["reason"] = "reboot";
    publishJson(tStatus, d, true);
    mqtt.disconnect();
  }
  delay(200);
  ESP.restart();
}

// ---------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  setupWatchdog();
  readMac();
  randomSeed(esp_random());

  settings::loadNet(net);
  settings::loadConfig(cfg);
  sensors::begin();
  sensors::setCo2Abc(cfg.co2Abc);

  logLine("info", String("Nodo ") + macId + " fw " + FW_VERSION + " reset " + resetReason());
  if (!net.complete()) {
    logLine("warn", "Sin aprovisionar. Envía por USB: {\"cmd\":\"provision\",\"wifi_ssid\":\"...\","
                    "\"wifi_pass\":\"...\",\"mqtt_host\":\"IP_PI\",\"mqtt_pass\":\"...\"}");
  } else {
    startWifi();
  }
  if (isnan(sensors::mqR0())) logLine("warn", "MQ-4 sin calibrar (comando calibrate_mq4)");
}

void loop() {
  esp_task_wdt_reset();
  pollSerial();
  netLoop();
  pollCalibration();

  if (millis() - lastSampleMs >= cfg.intervalMs) {
    lastSampleMs = millis();
    Reading r;
    sensors::read(cfg, r);
    publishTelemetry(r);
  }

  updateLed();
  if (rebootAtMs && (long)(millis() - rebootAtMs) >= 0) rebootNow();
  delay(2);
}

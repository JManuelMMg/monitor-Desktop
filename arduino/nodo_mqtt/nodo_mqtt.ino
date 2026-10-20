// Nodo ESP32 genérico: identidad por MAC, MQTT sobre TLS, config remota.
// Librerías: PubSubClient, ArduinoJson (v7), DHT sensor library, WiFiManager (tzapu).
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <DHT.h>

// ---------- Ajustes de compilación (no incluyen nombre ni zona) ----------
#define FW_VERSION "3.0.0"
#define MQTT_PORT 8883
// Se pueden cambiar desde el portal cautivo y se guardan en NVS.
#define DEFAULT_MQTT_HOST "192.168.1.50"

// ---------- Pines ----------
#define DHT_PIN 23
#define MQ4_PIN 34
#define TRIG_PIN 5
#define ECHO_PIN 18
#define CO2_RX 16
#define CO2_TX 17

DHT dht(DHT_PIN, DHT11);
HardwareSerial co2Serial(2);
WiFiClientSecure net;
PubSubClient mqtt(net);
Preferences prefs;

// ---------- Estado ----------
String deviceId;             // MAC sin separadores
String mqttHost, mqttUser, mqttPass;
String topicBase;
// Configuración remota (valores por defecto hasta recibir .../config)
String cfgName = "sin-asignar", cfgZone = "";
uint32_t cfgIntervalMs = 2000;
float cfgReactorEmpty = 100, cfgReactorFull = 10;
uint32_t seq = 0, lastPublish = 0, lastReconnect = 0;

// ---------- Interfaz de sensor: añadir uno nuevo = una clase ----------
struct Sensor {
  const char* key;
  virtual bool read(JsonObject out) = 0;  // devuelve true si la lectura es válida
};

struct DhtSensor : Sensor {
  DhtSensor() { key = "dht"; }
  bool read(JsonObject out) override {
    float h = dht.readHumidity(), t = dht.readTemperature();
    if (isnan(h) || isnan(t)) return false;
    out["temp"] = t;
    out["hum"] = h;
    return true;
  }
};

struct Mq4Sensor : Sensor {
  Mq4Sensor() { key = "mq4"; }
  bool read(JsonObject out) override {
    int raw = analogRead(MQ4_PIN);
    // TODO: portar calcularPPM_CH4() de mgas.ino con R0 guardado en NVS.
    out["mq4_raw"] = raw;
    return raw > 0;
  }
};

struct UltrasonicSensor : Sensor {
  UltrasonicSensor() { key = "us"; }
  bool read(JsonObject out) override {
    digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    unsigned long d = pulseIn(ECHO_PIN, HIGH, 30000);
    if (d == 0) return false;
    float cm = d * 0.0343f / 2.0f;
    float span = cfgReactorEmpty - cfgReactorFull;
    out["dist_cm"] = cm;
    if (span > 0) out["level_pct"] = constrain((cfgReactorEmpty - cm) / span * 100.0f, 0.0f, 100.0f);
    return true;
  }
};

struct Co2Sensor : Sensor {
  Co2Sensor() { key = "co2"; }
  bool read(JsonObject out) override {
    const byte cmd[9] = {0xFF, 0x01, 0x86, 0, 0, 0, 0, 0, 0x79};
    while (co2Serial.available()) co2Serial.read();
    co2Serial.write(cmd, 9);
    byte r[9];
    if (co2Serial.readBytes(r, 9) != 9 || r[0] != 0xFF || r[1] != 0x86) return false;
    out["co2_ppm"] = r[2] * 256 + r[3];
    return true;
  }
};

DhtSensor sDht; Mq4Sensor sMq4; UltrasonicSensor sUs; Co2Sensor sCo2;
Sensor* sensors[] = {&sDht, &sMq4, &sUs, &sCo2};

// ---------- Config persistente ----------
void loadConfig() {
  prefs.begin("node", true);
  mqttHost = prefs.getString("mqtt_host", DEFAULT_MQTT_HOST);
  mqttUser = prefs.getString("mqtt_user", deviceId);
  mqttPass = prefs.getString("mqtt_pass", "");
  cfgName = prefs.getString("name", cfgName);
  cfgZone = prefs.getString("zone", cfgZone);
  cfgIntervalMs = prefs.getUInt("interval", cfgIntervalMs);
  cfgReactorEmpty = prefs.getFloat("rx_empty", cfgReactorEmpty);
  cfgReactorFull = prefs.getFloat("rx_full", cfgReactorFull);
  prefs.end();
}

void applyRemoteConfig(JsonDocument& d) {
  prefs.begin("node", false);
  if (d["name"].is<const char*>()) { cfgName = d["name"].as<String>(); prefs.putString("name", cfgName); }
  if (d["zone"].is<const char*>()) { cfgZone = d["zone"].as<String>(); prefs.putString("zone", cfgZone); }
  if (d["interval_ms"].is<uint32_t>()) {
    cfgIntervalMs = max<uint32_t>(500, d["interval_ms"].as<uint32_t>());
    prefs.putUInt("interval", cfgIntervalMs);
  }
  if (d["reactor_empty_cm"].is<float>()) { cfgReactorEmpty = d["reactor_empty_cm"]; prefs.putFloat("rx_empty", cfgReactorEmpty); }
  if (d["reactor_full_cm"].is<float>()) { cfgReactorFull = d["reactor_full_cm"]; prefs.putFloat("rx_full", cfgReactorFull); }
  prefs.end();
}

// ---------- MQTT ----------
String topic(const char* leaf) { return topicBase + "/" + leaf; }

void publishMeta() {
  JsonDocument d;
  d["fw"] = FW_VERSION;
  d["ip"] = WiFi.localIP().toString();
  d["rssi"] = WiFi.RSSI();
  JsonArray caps = d["sensors"].to<JsonArray>();
  for (Sensor* s : sensors) caps.add(s->key);
  String out; serializeJson(d, out);
  mqtt.publish(topic("meta").c_str(), out.c_str(), true);
}

void publishEvent(const char* name, const char* detail) {
  JsonDocument d;
  d["event"] = name; d["detail"] = detail;
  String out; serializeJson(d, out);
  mqtt.publish(topic("event").c_str(), out.c_str(), false);
}

void handleCommand(JsonDocument& d) {
  const char* id = d["id"] | "";
  const char* cmd = d["cmd"] | "";
  bool ok = true;
  if (strcmp(cmd, "reboot") == 0) {
    JsonDocument a; a["id"] = id; a["ok"] = true;
    String out; serializeJson(a, out);
    mqtt.publish(topic("cmd/ack").c_str(), out.c_str());
    delay(200);
    ESP.restart();
  }
  // TODO: calibrate_mq4, calibrate_co2_zero, relay, etc.
  else ok = false;
  JsonDocument a; a["id"] = id; a["ok"] = ok;
  String out; serializeJson(a, out);
  mqtt.publish(topic("cmd/ack").c_str(), out.c_str());
}

void onMessage(char* t, byte* payload, unsigned int len) {
  JsonDocument d;
  if (deserializeJson(d, payload, len)) return;
  String tp(t);
  if (tp.endsWith("/config")) applyRemoteConfig(d);
  else if (tp.endsWith("/cmd")) handleCommand(d);
}

bool mqttConnect() {
  String lwt = topic("status");
  bool ok = mqtt.connect(deviceId.c_str(), mqttUser.c_str(), mqttPass.c_str(),
                         lwt.c_str(), 1, true, "offline");
  if (!ok) return false;
  mqtt.publish(lwt.c_str(), "online", true);
  mqtt.subscribe(topic("config").c_str(), 1);
  mqtt.subscribe(topic("cmd").c_str(), 1);
  publishMeta();
  return true;
}

// ---------- Setup / loop ----------
void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  co2Serial.begin(9600, SERIAL_8N1, CO2_RX, CO2_TX);
  co2Serial.setTimeout(200);
  dht.begin();

  deviceId = WiFi.macAddress();
  deviceId.replace(":", "");
  deviceId.toLowerCase();
  topicBase = "monitor/v1/" + deviceId;
  loadConfig();

  // Portal cautivo la primera vez (AP "Nodo-<mac>"); luego reconecta solo.
  WiFiManager wm;
  WiFiManagerParameter pHost("mqtt_host", "Host MQTT (Raspberry Pi)", mqttHost.c_str(), 64);
  WiFiManagerParameter pPass("mqtt_pass", "Clave MQTT del nodo", mqttPass.c_str(), 64);
  wm.addParameter(&pHost);
  wm.addParameter(&pPass);
  wm.setConfigPortalTimeout(180);
  if (!wm.autoConnect(("Nodo-" + deviceId).c_str())) ESP.restart();
  prefs.begin("node", false);
  prefs.putString("mqtt_host", pHost.getValue());
  prefs.putString("mqtt_pass", pPass.getValue());
  prefs.end();
  mqttHost = pHost.getValue();
  mqttPass = pPass.getValue();

  // TODO producción: net.setCACert(<CA de la Pi>); con setInsecure() solo cifra, no autentica.
  net.setInsecure();
  mqtt.setServer(mqttHost.c_str(), MQTT_PORT);
  mqtt.setBufferSize(1024);
  mqtt.setCallback(onMessage);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(1000);
    return;
  }
  if (!mqtt.connected()) {
    if (millis() - lastReconnect > 5000) {
      lastReconnect = millis();
      mqttConnect();
    }
  } else {
    mqtt.loop();
  }

  if (millis() - lastPublish >= cfgIntervalMs) {
    lastPublish = millis();
    JsonDocument d;
    d["seq"] = seq++;
    d["uptime"] = millis() / 1000;
    JsonObject ok = d["ok"].to<JsonObject>();
    for (Sensor* s : sensors) ok[s->key] = s->read(d.as<JsonObject>());
    if (mqtt.connected()) {
      String out; serializeJson(d, out);
      mqtt.publish(topic("telemetry").c_str(), out.c_str());
    }
  }
}

#pragma once
#include <Arduino.h>

// Datos de red y credenciales. Se cargan una vez por USB ("provision") y
// nunca viajan por MQTT. El usuario MQTT es siempre la MAC del nodo: la ACL
// del broker solo le deja publicar bajo su propia MAC.
struct NetSettings {
  String wifiSsid;
  String wifiPass;
  String mqttHost;
  uint16_t mqttPort = 8883;
  String mqttPass;
  bool mqttTls = true;

  bool complete() const { return wifiSsid.length() > 0 && mqttHost.length() > 0; }
};

// Configuración operativa. El backend la publica (retenida) en
// <nodo>/config/set y el nodo responde con <nodo>/config/state.
struct NodeConfig {
  uint32_t rev = 0;
  uint32_t intervalMs = 5000;
  float dhtTempOff = 0.0f;
  float dhtHumOff = 0.0f;
  float usOffsetCm = 0.0f;
  float usScale = 1.0f;
  float reactorEmptyCm = 100.0f;
  float reactorFullCm = 10.0f;
  bool co2Abc = false;     // ABC apagado: recomendado en biogás
  bool statusLed = true;
};

namespace settings {
void loadNet(NetSettings& net);
void saveNet(const NetSettings& net);
void loadConfig(NodeConfig& cfg);
void saveConfig(const NodeConfig& cfg);
float loadR0();
void saveR0(float r0);
void clearR0();
void factoryReset();
}

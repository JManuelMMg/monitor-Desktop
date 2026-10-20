#include "settings.h"
#include <Preferences.h>

namespace {
Preferences prefs;
const char* NS_NET = "net";
const char* NS_CFG = "cfg";
const char* NS_CAL = "cal";
}

namespace settings {

void loadNet(NetSettings& net) {
  prefs.begin(NS_NET, true);
  net.wifiSsid = prefs.getString("ssid", "");
  net.wifiPass = prefs.getString("pass", "");
  net.mqttHost = prefs.getString("host", "");
  net.mqttPort = prefs.getUShort("port", 8883);
  net.mqttPass = prefs.getString("mpass", "");
  net.mqttTls = prefs.getBool("tls", true);
  prefs.end();
}

void saveNet(const NetSettings& net) {
  prefs.begin(NS_NET, false);
  prefs.putString("ssid", net.wifiSsid);
  prefs.putString("pass", net.wifiPass);
  prefs.putString("host", net.mqttHost);
  prefs.putUShort("port", net.mqttPort);
  prefs.putString("mpass", net.mqttPass);
  prefs.putBool("tls", net.mqttTls);
  prefs.end();
}

void loadConfig(NodeConfig& cfg) {
  prefs.begin(NS_CFG, true);
  cfg.rev = prefs.getULong("rev", 0);
  cfg.intervalMs = prefs.getULong("int", 5000);
  cfg.dhtTempOff = prefs.getFloat("dt", 0.0f);
  cfg.dhtHumOff = prefs.getFloat("dh", 0.0f);
  cfg.usOffsetCm = prefs.getFloat("uo", 0.0f);
  cfg.usScale = prefs.getFloat("us", 1.0f);
  cfg.reactorEmptyCm = prefs.getFloat("re", 100.0f);
  cfg.reactorFullCm = prefs.getFloat("rf", 10.0f);
  cfg.co2Abc = prefs.getBool("abc", false);
  cfg.statusLed = prefs.getBool("led", true);
  prefs.end();
}

void saveConfig(const NodeConfig& cfg) {
  prefs.begin(NS_CFG, false);
  prefs.putULong("rev", cfg.rev);
  prefs.putULong("int", cfg.intervalMs);
  prefs.putFloat("dt", cfg.dhtTempOff);
  prefs.putFloat("dh", cfg.dhtHumOff);
  prefs.putFloat("uo", cfg.usOffsetCm);
  prefs.putFloat("us", cfg.usScale);
  prefs.putFloat("re", cfg.reactorEmptyCm);
  prefs.putFloat("rf", cfg.reactorFullCm);
  prefs.putBool("abc", cfg.co2Abc);
  prefs.putBool("led", cfg.statusLed);
  prefs.end();
}

float loadR0() {
  prefs.begin(NS_CAL, true);
  float r0 = prefs.getFloat("r0", NAN);
  prefs.end();
  return r0;
}

void saveR0(float r0) {
  prefs.begin(NS_CAL, false);
  prefs.putFloat("r0", r0);
  prefs.end();
}

void clearR0() {
  prefs.begin(NS_CAL, false);
  prefs.remove("r0");
  prefs.end();
}

void factoryReset() {
  for (const char* ns : {NS_NET, NS_CFG, NS_CAL}) {
    prefs.begin(ns, false);
    prefs.clear();
    prefs.end();
  }
}

}  // namespace settings

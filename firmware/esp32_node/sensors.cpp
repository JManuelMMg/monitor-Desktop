#include "sensors.h"
#include "config.h"
#include <DHT.h>
#include <HardwareSerial.h>
#include <math.h>

namespace {

DHT dht(PIN_DHT, DHT11);
HardwareSerial co2Serial(2);

const uint8_t CMD_READ_CO2[9] = {0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79};
const uint8_t CMD_ZERO_CAL[9] = {0xFF, 0x01, 0x87, 0x00, 0x00, 0x00, 0x00, 0x00, 0x78};
const uint8_t CMD_ABC_OFF[9] = {0xFF, 0x01, 0x79, 0x00, 0x00, 0x00, 0x00, 0x00, 0x86};
const uint8_t CMD_ABC_ON[9] = {0xFF, 0x01, 0x79, 0xA0, 0x00, 0x00, 0x00, 0x00, 0xE6};

unsigned long bootMs = 0;
float r0Kohm = NAN;

constexpr int US_FILTER = 10;
float usSamples[US_FILTER];
int usIndex = 0;
int usCount = 0;

// Calibración MQ-4 no bloqueante: una muestra por iteración del loop para
// no cortar la sesión MQTT durante los 20 s que dura.
bool calRunning = false;
int calTaken = 0;
int calValid = 0;
float calSum = 0;
unsigned long calLastMs = 0;

float mqRs() {
  float v = analogReadMilliVolts(PIN_MQ4) / 1000.0f;
  if (v <= 0.05f || v >= (MQ4_V_SENSOR - 0.05f)) return NAN;
  return MQ4_RL_KOHM * ((MQ4_V_SENSOR / v) - 1.0f);
}

bool rsPlausible(float rs) { return !isnan(rs) && rs > 1.0f && rs < 1000.0f; }

float mqRsAverage(int samples) {
  float sum = 0;
  int valid = 0;
  for (int i = 0; i < samples; i++) {
    float rs = mqRs();
    if (rsPlausible(rs)) {
      sum += rs;
      valid++;
    }
    delay(5);
  }
  return valid > 0 ? sum / valid : NAN;
}

float ch4FromRs(float rs) {
  if (isnan(rs) || isnan(r0Kohm) || r0Kohm <= 0) return NAN;
  float ratio = rs / r0Kohm;
  if (ratio <= 0.05f) return 50000.0f;
  return constrain(powf(10.0f, (log10f(ratio) - MQ4_CH4_B) / MQ4_CH4_M), 0.0f, 50000.0f);
}

bool readCo2(int& ppm) {
  while (co2Serial.available()) co2Serial.read();
  co2Serial.write(CMD_READ_CO2, 9);
  unsigned long t0 = millis();
  while (co2Serial.available() < 9) {
    if (millis() - t0 > 150) return false;
    delay(1);
  }
  uint8_t r[9];
  co2Serial.readBytes(r, 9);
  uint8_t cs = 0;
  for (int i = 1; i < 8; i++) cs += r[i];
  cs = 0xFF - cs + 1;
  if (r[0] != 0xFF || r[1] != 0x86 || r[8] != cs) return false;
  ppm = (r[2] << 8) + r[3];
  return ppm > 0 && ppm <= 10000;
}

float measureDistanceCm() {
  digitalWrite(PIN_US_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_US_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_US_TRIG, LOW);
  long us = pulseIn(PIN_US_ECHO, HIGH, 30000);
  if (us == 0) return NAN;
  float cm = us * 0.0343f / 2.0f;
  if (cm < 2.0f || cm > 450.0f) return NAN;
  return cm;
}

float filterDistance(float cm) {
  usSamples[usIndex] = cm;
  usIndex = (usIndex + 1) % US_FILTER;
  if (usCount < US_FILTER) usCount++;
  float sum = 0;
  for (int i = 0; i < usCount; i++) sum += usSamples[i];
  return sum / usCount;
}

}  // namespace

namespace sensors {

void begin() {
  bootMs = millis();
  co2Serial.begin(9600, SERIAL_8N1, PIN_CO2_RX, PIN_CO2_TX);
  pinMode(PIN_US_TRIG, OUTPUT);
  pinMode(PIN_US_ECHO, INPUT);
  digitalWrite(PIN_US_TRIG, LOW);
  analogSetPinAttenuation(PIN_MQ4, ADC_11db);
  dht.begin();
  r0Kohm = settings::loadR0();
}

void setCo2Abc(bool on) { co2Serial.write(on ? CMD_ABC_ON : CMD_ABC_OFF, 9); }

void calibrateCo2Zero() { co2Serial.write(CMD_ZERO_CAL, 9); }

void read(const NodeConfig& cfg, Reading& out) {
  out = Reading();

  out.co2Ok = readCo2(out.co2Ppm);

  out.mqWarm = millis() - bootMs >= MQ4_WARMUP_MS;
  out.mqCal = !isnan(r0Kohm) && r0Kohm > 0;
  if (!calRunning) {
    out.mqRsKohm = mqRsAverage(5);
    if (out.mqCal && out.mqWarm && rsPlausible(out.mqRsKohm)) {
      out.ch4Ppm = ch4FromRs(out.mqRsKohm);
      out.mqOk = !isnan(out.ch4Ppm);
    }
  }

  float raw = measureDistanceCm();
  if (!isnan(raw)) {
    float cm = filterDistance(raw) * cfg.usScale + cfg.usOffsetCm;
    out.distCm = cm < 0 ? 0 : cm;
    out.usOk = true;
    float span = cfg.reactorEmptyCm - cfg.reactorFullCm;
    if (span > 0) {
      out.levelPct = constrain((cfg.reactorEmptyCm - out.distCm) / span * 100.0f, 0.0f, 100.0f);
    }
  }

  float h = dht.readHumidity();
  float t = dht.readTemperature();
  if (!isnan(h) && !isnan(t)) {
    out.dhtOk = true;
    out.tempC = t + cfg.dhtTempOff;
    out.humPct = constrain(h + cfg.dhtHumOff, 0.0f, 100.0f);
  }
}

float mqR0() { return r0Kohm; }

void clearMqR0() {
  settings::clearR0();
  r0Kohm = NAN;
}

bool startMqCalibration() {
  if (calRunning) return false;
  calRunning = true;
  calTaken = 0;
  calValid = 0;
  calSum = 0;
  calLastMs = 0;
  return true;
}

bool mqCalibrating() { return calRunning; }

CalResult pollMqCalibration() {
  if (!calRunning) return CalResult::Done;
  if (millis() - calLastMs < MQ4_CAL_PERIOD_MS) return CalResult::Running;
  calLastMs = millis();

  float rs = mqRs();
  if (rsPlausible(rs)) {
    calSum += rs;
    calValid++;
  }
  if (++calTaken < MQ4_CAL_SAMPLES) return CalResult::Running;

  calRunning = false;
  // Se exige al menos 80 % de muestras válidas para aceptar el R0.
  if (calValid < (MQ4_CAL_SAMPLES * 8) / 10) return CalResult::Failed;
  r0Kohm = (calSum / calValid) / MQ4_CLEAN_AIR_FACTOR;
  settings::saveR0(r0Kohm);
  return CalResult::Done;
}

}  // namespace sensors

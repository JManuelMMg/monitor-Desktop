#pragma once
#include <Arduino.h>
#include "settings.h"

// Una lectura completa. Cada sensor trae su propia bandera *_ok: un valor
// inválido se publica como null, nunca se rellena con el último valor bueno.
struct Reading {
  bool dhtOk = false;
  float tempC = NAN;
  float humPct = NAN;

  bool co2Ok = false;
  int co2Ppm = 0;

  bool mqWarm = false;     // terminó el calentamiento
  bool mqCal = false;      // tiene R0 guardado
  bool mqOk = false;       // lectura válida
  float ch4Ppm = NAN;
  float mqRsKohm = NAN;

  bool usOk = false;
  float distCm = NAN;
  float levelPct = NAN;
};

enum class CalResult { Running, Done, Failed };

namespace sensors {
void begin();
void setCo2Abc(bool on);
void calibrateCo2Zero();
void read(const NodeConfig& cfg, Reading& out);

float mqR0();
void clearMqR0();
bool startMqCalibration();   // false si ya hay una en curso
bool mqCalibrating();
CalResult pollMqCalibration();   // llamar en cada loop()
}

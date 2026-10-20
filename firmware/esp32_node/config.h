#pragma once

// =====================================================
// IDENTIDAD DEL FIRMWARE
// =====================================================
#define FW_VERSION "3.0.0"

// Raíz de tópicos. Debe coincidir con backend/app/topics.py y con la ACL
// de Mosquitto (deploy/mosquitto/acl).
#define TOPIC_ROOT "monitor/v1/nodes/"

// =====================================================
// PINES (iguales en todos los nodos)
// =====================================================
#define PIN_CO2_RX 16      // MH-Z19C TX -> ESP32 RX2
#define PIN_CO2_TX 17      // MH-Z19C RX <- ESP32 TX2
#define PIN_MQ4 34         // MQ-4 salida analógica (ADC1, válido con WiFi)
#define PIN_US_TRIG 5      // AJ-SR04M TRIG
#define PIN_US_ECHO 18     // AJ-SR04M ECHO
#define PIN_DHT 23         // DHT11 datos
#define PIN_LED 2          // LED integrado

// =====================================================
// MQ-4
// =====================================================
#define MQ4_V_SENSOR 5.0f
#define MQ4_RL_KOHM 10.0f
#define MQ4_CH4_M -0.354f
#define MQ4_CH4_B 1.062f
#define MQ4_CLEAN_AIR_FACTOR 4.85f
#define MQ4_WARMUP_MS 180000UL            // 3 minutos
#define MQ4_CAL_SAMPLES 100               // 100 muestras x 200 ms = 20 s
#define MQ4_CAL_PERIOD_MS 200UL

// =====================================================
// RED / MQTT
// =====================================================
#define MQTT_KEEPALIVE_S 30
#define MQTT_BUFFER_SIZE 1024
#define MQTT_BACKOFF_MIN_MS 2000UL
#define MQTT_BACKOFF_MAX_MS 60000UL
#define WIFI_RETRY_MS 15000UL
#define WDT_TIMEOUT_S 30

// Límites de la configuración remota (se validan antes de aplicarla).
#define CFG_INTERVAL_MIN_MS 2000UL        // DHT11 no admite menos de 1 s
#define CFG_INTERVAL_MAX_MS 600000UL

# Graph Report - monitor Desktop  (2026-10-26)

## Corpus Check
- 203 files · ~102,584 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 103 file(s) not represented in the graph (top: .ino 62, (none) 9, .properties 9)

## Summary
- 1689 nodes · 3113 edges · 127 communities (83 shown, 44 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 235 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Backend DB layer
- MQ sensor library
- FastAPI app + Postgres
- Dashboard app.js
- FakeDB test double
- LZSS OTA decompress
- Backend tests
- Adafruit Unified Sensor
- Demo server
- ArduinoHttpClient
- Arduino DebugUtils
- Energy simulation
- ESP32 OTA library
- Devices router
- Fork DB layer
- WebSocket client
- DebugUtils docs
- MQTT service + hub
- Auth security
- Web UI scripts
- App lifecycle
- Auth dependencies
- Add-node wizard
- Deployment + desktop app
- MQTT bridge tests
- Firmware sensors
- DHT11 library
- Node settings UI
- Fork devices router
- Firmware settings
- DHT library
- Admin CLI
- Page routes
- Node state
- Node registry
- MQTT credentials
- MQTT service
- URL parser
- Node.js examples
- Network client base
- Data router
- API schemas
- OTA errors
- Fork users router
- Config loader
- MQTT bridge
- Persistence writer
- Backend architecture
- Reading model
- DHT unified
- OTA decoder
- Bonezegei DHT11
- Auth router
- Connection + offline UI
- Bonezegei DHT11 (v1.0.1)
- HTTP parser
- Live hub
- Fork auth router
- PCB v2 commercial
- PCB v2 interface
- MQ-4 calibration
- Users router
- Hub + persistence docs
- Multi-node architecture
- Node config model
- Node detail page
- Dashboard script
- Node script
- Adafruit sensor types
- Base64 + auth
- MQ-4 detector (legacy)
- CO2 MH-Z19C
- Legacy ESP32 flow
- Network security + WireGuard
- Sensor board 1
- Calibration types
- OTA utility
- ESP32 TLS provisioning
- Deployment overview
- ML integration
- Precision calibration
- Adafruit_Sensor class
- ESP32 simulator
- Login throttle
- Fork app lifecycle
- Fork hub
- Legacy backend fork
- Requirements
- ParsedUrl
- ESP32 pinout
- PKI script
- OTA download states
- URL encoder
- Humidity sensor
- Temperature sensor
- Admin UI
- Connection UI
- ESP32 board
- Misc: DHT.h
- Misc: list_users()
- Misc: sw.js
- Misc: firewall.sh
- Misc: install.sh
- Misc: provision_node.sh

## God Nodes (most connected - your core abstractions)
1. `HttpClient` - 74 edges
2. `MQUnifiedsensor` - 44 edges
3. `FakeDB` - 35 edges
4. `run()` - 33 edges
5. `Arduino_ESP32_OTA` - 28 edges
6. `LZSSDecoder` - 27 edges
7. `Registry` - 24 edges
8. `WebSocketClient` - 24 edges
9. `Arduino_DebugUtils` - 24 edges
10. `q()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Backend Raspberry Pi (FastAPI + paho-mqtt + Neon)` --semantically_similar_to--> `Backend Raspberry Pi (fork) FastAPI + MQTT + Neon`  [INFERRED] [semantically similar]
  backend/README.md → backend_fork/README.md
- `Red y servidor panel (WiFi credentials, REST endpoint, auto IP detect)` --semantically_similar_to--> `ESP32 provisioning line (WiFi SSID, Pi IP, MQTT TLS port)`  [INFERRED] [semantically similar]
  web/templates/index.html → backend/app/templates/_add_node.html
- `web/templates/index.html (legacy single-node IoT dashboard)` --semantically_similar_to--> `dashboard.html (Panel general page)`  [INFERRED] [semantically similar]
  web/templates/index.html → backend/app/templates/dashboard.html
- `Configuracion ESP32 + sistema IoT (legado)` --semantically_similar_to--> `Mapeo de pines ESP32 (DHT11=23, MQ-4=34, TRIG/ECHO=5/18, MH-Z19C=16/17, LED=2)`  [INFERRED] [semantically similar]
  ARDUINO_SETUP.md → firmware/README.md
- `Comandos JSON (calibrate, set_intervals, led, reboot, set_wifi, set_server)` --semantically_similar_to--> `Comandos USB (status, provision, factory_reset, calibrate_mq4, calibrate_co2_zero, identify, reboot)`  [INFERRED] [semantically similar]
  ARDUINO_SETUP.md → firmware/README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Documentacion del sistema legado de un solo nodo** — arduino_setup_esp32_iot_config, comandos_ejecucion_run_guide, guia_calibracion_precision_guide, implementation_plan_iot_monitor_plan [EXTRACTED 0.95]
- **Flujos de calibracion de sensores (MQ-4, CO2, DHT11, ultrasonido)** — guia_calibracion_precision_mq4_r0, guia_calibracion_precision_mhz19z_zero, guia_calibracion_precision_dht11_offset, guia_calibracion_precision_ultrasonic_two_point [EXTRACTED 0.95]
- **Componentes del sistema multi-nodo** — firmware_readme_esp32_firmware, backend_readme_backend_pi, desktop_readme_windows_app, readme_raspberry_pi_broker [EXTRACTED 0.90]
- **Pipeline de telemetría ESP32 a Neon** — docs_arquitectura_firmware_esp32, docs_arquitectura_mosquitto, backend_app_mqtt_bridge, docs_arquitectura_state, docs_arquitectura_persistence, docs_arquitectura_neon [EXTRACTED 1.00]
- **Cadena de alimentación y protección PCB v2** — hardware_pcb_v2_comercial_cargador_cn3767, hardware_pcb_v2_comercial_lvd, hardware_pcb_v2_comercial_proteccion_inversion, hardware_pcb_v2_comercial_arquitectura_alimentacion [EXTRACTED 1.00]
- **Acondicionamiento de sensores en placa 2** — hardware_placa2_interfaz_mq4, hardware_placa2_interfaz_mhz19c, hardware_placa2_interfaz_ajsr04m, hardware_placa2_interfaz_dht11, hardware_placa2_interfaz_cable_w1 [EXTRACTED 1.00]
- **Add-node provisioning flow** — backend_app_templates__add_node_identify_form, backend_app_templates__add_node_mqtt_credentials, backend_app_templates__add_node_provisioning_line, backend_app_templates__add_node_waiting_connection [EXTRACTED 0.95]
- **Node detail page tabs** — backend_app_templates_node_tab_resumen, backend_app_templates_node_tab_historico, backend_app_templates_node_tab_ajustes, backend_app_templates_node_tab_acciones, backend_app_templates_node_tab_admin [EXTRACTED 0.95]
- **Pages extending base.html** — backend_app_templates_dashboard, backend_app_templates_node, backend_app_templates_admin, backend_app_templates_account, backend_app_templates_connection, backend_app_templates_login, backend_app_templates_offline [EXTRACTED 0.95]
- **Temperature/humidity (DHT) sensor libraries** — libraries_dht11_readme_dht11_arduino_library, libraries_dht_sensor_library_readme_dht_sensor_library, libraries_bonezegei_dht11_readme_bonezegei_dht11 [INFERRED 0.85]
- **HTTP client and OTA update stack for networked boards** — libraries_arduinohttpclient_readme_arduinohttpclient, libraries_arduino_esp32_ota_readme_arduino_esp32_ota, libraries_arduinohttpclient_src_utility_urlparser_readme_http_parser [INFERRED 0.65]
- **Sensor connectors on sensor board** — hardware_placa2_placa2_pcb_mq4_connector, hardware_placa2_placa2_pcb_mhz19c_connector, hardware_placa2_placa2_pcb_ajsr04m_connector, hardware_placa2_placa2_pcb_dht11_connector [EXTRACTED 1.00]
- **ESP32 DevKit pin function groups** — libraries_mqunifiedsensor_3_0_0_examples_esp32_esp32_wroom_32d_images_esp32_wroom_32d_pinout_adc_pins, libraries_mqunifiedsensor_3_0_0_examples_esp32_esp32_wroom_32d_images_esp32_wroom_32d_pinout_touch_pins, libraries_mqunifiedsensor_3_0_0_examples_esp32_esp32_wroom_32d_images_esp32_wroom_32d_pinout_vspi_bus, libraries_mqunifiedsensor_3_0_0_examples_esp32_esp32_wroom_32d_images_esp32_wroom_32d_pinout_uart0 [EXTRACTED 1.00]

## Communities (127 total, 44 thin omitted)

### Community 0 - "Backend DB layer"
Cohesion: 0.07
Nodes (38): ack_commands(), count_active_admins(), count_users(), q(), create_device(), q(), create_user(), q() (+30 more)

### Community 1 - "MQ sensor library"
Cohesion: 0.07
Nodes (19): MQUnifiedsensor, _a, _adc, _ADC_Bit_Resolution, _b, _firstFlag, MQUnifiedsensor::MQUnifiedsensor(), _pin (+11 more)

### Community 2 - "FastAPI app + Postgres"
Cohesion: 0.08
Nodes (26): clear_history(), get_db(), get_history(), get_latest_reading(), init_db(), save_reading(), broadcast_to_clients(), export_csv() (+18 more)

### Community 3 - "Dashboard app.js"
Cohesion: 0.10
Nodes (38): activeAlarms, appendHistoryRow(), appendReadingToCharts(), charts, chartSeries, checkAlarmsAndAlerts(), checkServerUrlMismatch(), connectWebSocket() (+30 more)

### Community 4 - "FakeDB test double"
Cohesion: 0.08
Nodes (3): FakeDB, _iso(), _now()

### Community 5 - "LZSS OTA decompress"
Cohesion: 0.07
Nodes (27): FSM_STATES, FSM_0, FSM_1, FSM_2, FSM_3, FSM_EOF, LZSSDecoder, available (+19 more)

### Community 6 - "Backend tests"
Cohesion: 0.11
Nodes (23): client(), fake(), login(), make_user(), PublishRecorder, recorder(), wait_for(), feed_node() (+15 more)

### Community 7 - "Adafruit Unified Sensor"
Cohesion: 0.06
Nodes (34): Apache License 2.0 (Adafruit Unified Sensor), Adafruit_Sensor base class (getEvent, getSensor), Adafruit Unified Sensor Driver (library), sensor_t (sensor details struct), sensors_event_t (unified sensor event type), sensors_type_t (sensor type enum incl. gas, CO2, TVOC, humidity, temperature), Bonezegei_DHT11 v1.0.1 (library for DHT11/DHT22), Bonezegei_DHT11 (library for DHT11/DHT22) (+26 more)

### Community 8 - "Demo server"
Cohesion: 0.09
Nodes (11): echo(), simulate(), telemetry(), Bridge, load_config(), main(), normalize_server(), pick_server() (+3 more)

### Community 9 - "ArduinoHttpClient"
Cohesion: 0.06
Nodes (26): HttpClient, iBodyLengthConsumed, iChunkLength, iClient, iConnectionClose, iContentLength, iContentLengthPtr, iHeaderLine (+18 more)

### Community 10 - "Arduino DebugUtils"
Cohesion: 0.11
Nodes (8): Arduino_DebugUtils, Arduino_DebugUtils::Arduino_DebugUtils(), _debug_level, _debug_output_stream, _format_timestamp_on, _newline_on, _print_debug_label, _timestamp_on

### Community 11 - "Energy simulation"
Cohesion: 0.11
Nodes (19): autonomy(), charging(), dividers(), Load, main(), node_budget(), node_peak(), raspberry() (+11 more)

### Community 12 - "ESP32 OTA library"
Cohesion: 0.11
Nodes (10): Arduino_ESP32_OTA, Arduino_ESP32_OTA::Arduino_ESP32_OTA(), _ca_cert, _ca_cert_bundle, _ca_cert_bundle_size, _client, _context, Arduino_ESP32_OTA::Context::Context() (+2 more)

### Community 13 - "Devices router"
Cohesion: 0.13
Nodes (19): get_device(), zones(), command_log(), create_device(), _credentials(), delete_device(), get_device(), history() (+11 more)

### Community 14 - "Fork DB layer"
Cohesion: 0.17
Nodes (24): count_active_admins(), count_users(), create_user(), cursor(), delete_device(), delete_user(), ensure_device(), get_device() (+16 more)

### Community 15 - "WebSocket client"
Cohesion: 0.12
Nodes (11): WebSocketClient, iRxMasked, iRxMaskIndex, iRxMaskKey, iRxOpCode, iRxSize, iTxBuffer, iTxMessageType (+3 more)

### Community 16 - "DebugUtils docs"
Cohesion: 0.08
Nodes (27): Arduino_DebugUtils keywords (Debug, DEBUG_* macros, DBG_* constants), Arduino_DebugUtils (library), Debug levels (DBG_NONE, ERROR, WARNING, INFO, DEBUG, VERBOSE), Debug.print (printf-style), Debug.setDebugLevel, Debug.setDebugOutputStream, Debug timestampOn/Off and newlineOn/Off, Arduino_ESP32_OTA Error codes (UrlParseError, OtaHeaderCrc, OtaDownload...) (+19 more)

### Community 17 - "MQTT service + hub"
Cohesion: 0.14
Nodes (6): watchdog(), _append_buffer(), flush_buffer(), _read_buffer(), save(), to_row()

### Community 18 - "Auth security"
Cohesion: 0.16
Nodes (10): require(), dependency(), _b64(), decode_access_token(), has_role(), hash_password(), verify_password(), test_jwt_roundtrip_and_tamper() (+2 more)

### Community 19 - "Web UI scripts"
Cohesion: 0.11
Nodes (15): App, Net, _icons.html (SVG icon sprite), _macros.html (icon and hint Jinja macros), hint() collapsible help macro, icon() macro, account.html (Mi cuenta page), Change password form (with strength meter) (+7 more)

### Community 20 - "App lifecycle"
Cohesion: 0.12
Nodes (6): close_pool(), database_unavailable(), healthz(), lifespan(), security_headers(), _watch_connections()

### Community 21 - "Auth dependencies"
Cohesion: 0.15
Nodes (7): authenticate_token(), current_user(), _extract_token(), _load_user(), live(), _same_origin(), connection_info()

### Community 22 - "Add-node wizard"
Cohesion: 0.14
Nodes (18): AddNode, NodeCard, _add_node.html (Add node wizard modal), Node identify form (MAC, name, zone, description), One-time MQTT credentials (user = MAC, generated password), ESP32 provisioning line (WiFi SSID, Pi IP, MQTT TLS port), Waiting for first node connection / success state, 3-step wizard: Identificar / Credenciales / Conectar (+10 more)

### Community 23 - "Deployment + desktop app"
Cohesion: 0.14
Nodes (19): monitor-cli.sh script, desktop requirements (pywebview, pyinstaller), App de escritorio pywebview, CA local y certificados en clientes, Panel web instalable (PWA), Despliegue en la Raspberry Pi 4B (copia), Despliegue en la Raspberry Pi 4B, install.sh (instalador) (+11 more)

### Community 24 - "MQTT bridge tests"
Cohesion: 0.14
Nodes (6): FakeClient, FakeWriter, make_bridge(), message(), test_on_connect_subscribes_and_handles_refusal(), test_on_message_routes_and_filters()

### Community 25 - "Firmware sensors"
Cohesion: 0.16
Nodes (9): ch4FromRs(), filterDistance(), measureDistanceCm(), mqRs(), mqRsAverage(), pollMqCalibration(), read(), readCo2() (+1 more)

### Community 26 - "DHT11 library"
Cohesion: 0.19
Nodes (6): DHT11, _delayMS, ERROR_CHECKSUM, ERROR_TIMEOUT, _pin, TIMEOUT_DURATION

### Community 27 - "Node settings UI"
Cohesion: 0.12
Nodes (18): ESP32 remote config form (retained MQTT config, sync status), Meta form (name, zone, description), Node tab: Ajustes (meta, thresholds, ESP32 config forms), Alarm thresholds form (temp, CH4, CO2, level max), MQ-4 methane sensor (warmup, R0 calibration), static/css/style.css and dashboard-fixes.css, static/js/app.js (legacy dashboard script), web/templates/index.html (legacy single-node IoT dashboard) (+10 more)

### Community 28 - "Fork devices router"
Cohesion: 0.22
Nodes (9): _check_id(), CommandIn, delete_device(), DevicePatch, get_device(), list_devices(), _merge_live(), patch_device() (+1 more)

### Community 29 - "Firmware settings"
Cohesion: 0.12
Nodes (11): loadConfig(), loadNet(), NetSettings, mqttHost, mqttPass, mqttPort, mqttTls, wifiPass (+3 more)

### Community 30 - "DHT library"
Cohesion: 0.21
Nodes (8): DHT, data, _lastreadtime, _lastresult, _maxcycles, _pin, pullTime, _type

### Community 31 - "Admin CLI"
Cohesion: 0.27
Nodes (12): add_node(), _ask_password(), create_admin(), init_db(), list_users(), main(), mqtt_sync(), reset_password() (+4 more)

### Community 32 - "Page routes"
Cohesion: 0.32
Nodes (11): optional_user(), account_page(), admin_page(), connection_page(), dashboard(), login_page(), manifest(), node_page() (+3 more)

### Community 33 - "Node state"
Cohesion: 0.18
Nodes (6): _is_uuid(), _iso(), NodeState, normalize_telemetry(), format_mac(), test_normalize_telemetry_rejects_garbage()

### Community 35 - "MQTT credentials"
Cohesion: 0.19
Nodes (9): set_mqtt_credentials(), _backend_entry(), generate_password(), hash_password(), issue_credentials(), render(), revoke_credentials(), sync_password_file() (+1 more)

### Community 36 - "MQTT service"
Cohesion: 0.27
Nodes (3): build_node_config(), device_topic(), MqttService

### Community 37 - "URL parser"
Cohesion: 0.12
Nodes (13): http_parser_url, field_data, field_set, http_parser_url_fields, UF_FRAGMENT, UF_HOST, UF_MAX, UF_PATH (+5 more)

### Community 38 - "Node.js examples"
Cohesion: 0.17
Nodes (13): author, name, dependencies, body-parser@>=1.11.0, express@>=4.0.0, multer@*, ws@^1.1.1, name (+5 more)

### Community 40 - "Data router"
Cohesion: 0.26
Nodes (8): export_csv(), _check(), events(), export_csv(), health(), history(), live(), websocket_endpoint()

### Community 41 - "API schemas"
Cohesion: 0.22
Nodes (10): CommandIn, DeviceCreate, DevicePatch, LoginIn, NodeConfigIn, PasswordChangeIn, Strict, Thresholds (+2 more)

### Community 42 - "OTA errors"
Cohesion: 0.13
Nodes (15): Error, HttpHeaderError, HttpResponse, None, NoOtaStorage, OtaDownload, OtaHeaderCrc, OtaHeaderLength (+7 more)

### Community 43 - "Fork users router"
Cohesion: 0.25
Nodes (6): create_user(), delete_user(), list_users(), patch_user(), UserIn, UserPatch

### Community 44 - "Config loader"
Cohesion: 0.20
Nodes (6): _bool(), _float(), _int(), _load_dotenv(), _origins(), Settings

### Community 45 - "MQTT bridge"
Cohesion: 0.20
Nodes (3): MqttBridge, node_topic(), parse()

### Community 47 - "Backend architecture"
Cohesion: 0.15
Nodes (13): API REST y WebSocket /ws, db.py (pool psycopg2), hub.py (WebSocket), Neon (PostgreSQL), persistence.py (lotes y spool JSONL), Roles viewer / operator / admin, security.py / deps.py (scrypt, JWT, CSRF), state.py (estado en vivo) (+5 more)

### Community 48 - "Reading model"
Cohesion: 0.14
Nodes (14): Reading, ch4Ppm, co2Ok, co2Ppm, dhtOk, distCm, humPct, levelPct (+6 more)

### Community 49 - "DHT unified"
Cohesion: 0.22
Nodes (9): sensor_t, DHT_Unified, _dht, DHT_Unified::Humidity::getSensor(), DHT_Unified::Humidity::Humidity(), _temp, DHT_Unified::Temperature::getSensor(), DHT_Unified::Temperature::Temperature() (+1 more)

### Community 50 - "OTA decoder"
Cohesion: 0.14
Nodes (13): Context, buf_len, buffer, calculatedCrc32, decoder, downloadedSize, downloadState, error (+5 more)

### Community 51 - "Bonezegei DHT11"
Cohesion: 0.19
Nodes (7): Bonezegei_DHT11, data, _humidity, _pin, prevtime, _temperatureDeg, _temperatureFar

### Community 52 - "Auth router"
Cohesion: 0.35
Nodes (8): change_password(), _client_ip(), login(), logout(), me(), public_user(), _set_session_cookie(), create_access_token()

### Community 53 - "Connection + offline UI"
Cohesion: 0.22
Nodes (12): check(), row(), Admin tab: Sistema (server health, provisioning info), connection.html (Conexión y app page), Server address list with auto-switch failover, offline.html (Sin conexión page), desktop/setup.html (desktop app server setup screen), pywebview API: get_config, save_servers, retry (+4 more)

### Community 55 - "Bonezegei DHT11 (v1.0.1)"
Cohesion: 0.19
Nodes (7): Bonezegei_DHT11, data, _humidity, _pin, prevtime, _temperatureDeg, _temperatureFar

### Community 56 - "HTTP parser"
Cohesion: 0.21
Nodes (4): http_parse_host(), http_parse_host_char(), http_parser_parse_url(), parse_url_char()

### Community 58 - "Fork auth router"
Cohesion: 0.29
Nodes (6): login(), LoginIn, me(), _public(), refresh(), RefreshIn

### Community 59 - "PCB v2 commercial"
Cohesion: 0.24
Nodes (12): Arquitectura de alimentación, biogas_v2.lbr (biblioteca de huellas), BOM_v2.csv, Cargador CC/CV CN3767 (U2), Protección ESD TPD4E1U06 (U5, U6), Desconexión por bajo voltaje LVD (U3, U4, Q2), PCB v2 nodo BiogasEmbebido (modelo comercial), Protección contra inversión (XT60, crowbar D1, F2) (+4 more)

### Community 60 - "PCB v2 interface"
Cohesion: 0.21
Nodes (10): Sensor AJ-SR04M (ultrasónico, buffers AHCT), Alimentación 12 V a 5 V local (TSR 1-2450), Arneses W2-W5 a sensores, Cable W1 placa 1 a placa 2 (12 polos), Cambios en placa 1 (J4A/J4B, F4, Q3), Sensor DHT11 (bus un hilo, Q3 BSS138), Gabinetes y sellado (G1 IP65, G2 IP67), Sensor MH-Z19C (UART CO2) (+2 more)

### Community 61 - "MQ-4 calibration"
Cohesion: 0.24
Nodes (9): calcularPPM_CH4(), calcularPPM_Propano(), calcularRs(), calibrarR0(), guardarR0()/cargarR0()/borrarR0() (Preferences), loop() y clasificacion de estado por Rs/R0, promedioRs(), Timestamp sin NTP/RTC (inicializarTimestamp, obtenerTimestamp) (+1 more)

### Community 62 - "Users router"
Cohesion: 0.31
Nodes (7): invalidate_user(), _check_password(), create_user(), delete_user(), update_user(), _would_remove_last_admin(), password_problems()

### Community 64 - "Multi-node architecture"
Cohesion: 0.24
Nodes (10): Escalabilidad (nodos, sensores, carga), Firmware esp32_node, Identidad por MAC (clientId = usuario MQTT), Arquitectura Monitor multi-nodo (ESP32 + Pi + Windows), Mosquitto broker, Tópicos MQTT monitor/v1/nodes/<mac>, ACL de Mosquitto por MAC, Parte C: Broker MQTT y lista de verificación (+2 more)

### Community 65 - "Node config model"
Cohesion: 0.18
Nodes (11): NodeConfig, co2Abc, dhtHumOff, dhtTempOff, intervalMs, reactorEmptyCm, reactorFullCm, rev (+3 more)

### Community 66 - "Node detail page"
Cohesion: 0.22
Nodes (9): LineChart, Node filters (zone chips, state chips, search) and grouped node list, node.html (single node detail page), Device commands: identify, ping, calibrate_mq4, calibrate_co2_zero, clear_mq4, reboot, Node tab: Acciones (device commands and command log), Node tab: Administración (MQTT credentials rotate/revoke, disable/delete node), Node tab: Histórico (range picker, 4 charts, CSV export), Node tab: Resumen (live metric tiles, sensor health) (+1 more)

### Community 67 - "Dashboard script"
Cohesion: 0.36
Nodes (8): average(), matches(), render(), renderSummary(), renderZoneChips(), scheduleRender(), syncChildren(), updateGuide()

### Community 68 - "Node script"
Cohesion: 0.33
Nodes (9): drawCharts(), fillForm(), fillForms(), healthItem(), loadCommands(), loadHistory(), patch(), render() (+1 more)

### Community 69 - "Adafruit sensor types"
Cohesion: 0.20
Nodes (6): sensors_color_t, sensors_event_t, sensors_type_t, sensors_vec_t, DHT_Unified::Humidity::getEvent(), DHT_Unified::Temperature::getEvent()

### Community 71 - "MQ-4 detector (legacy)"
Cohesion: 0.22
Nodes (8): Detector MQ-4 (metano/propano) v4.1, Flujo de datos ESP32 -> FastAPI -> PostgreSQL -> Dashboard, Configuracion ESP32 + sistema IoT (legado), Precalentamiento MQ-4 60 s, Almacenamiento persistente Preferences (wifi, srv_url, mq_r0, intervalos), Secuencia de muestreo (US 50ms, MQ 200ms, DHT 2.5s, envio 1s), Mapeo de pines ESP32 (DHT11=23, MQ-4=34, TRIG/ECHO=5/18, MH-Z19C=16/17, LED=2), Nodo ESP32 (DHT11, MQ-4, MH-Z19C, AJ-SR04M)

### Community 72 - "CO2 MH-Z19C"
Cohesion: 0.31
Nodes (8): calibrarZero(), Reloj persistido en Preferences ('ultima_hora'), controlarABC(), leerSensorConFechaHora(), Monitor CO2 MH-Z19C, parseFechaHora()/leerFechaHoraSerial()/actualizarHora(), Comandos UART MH-Z19C (lectura 0x86, cero 0x87, ABC 0x79), MH-Z19Z NDIR: calibracion de cero (400 ppm)

### Community 73 - "Legacy ESP32 flow"
Cohesion: 0.28
Nodes (9): Token opcional ESP32_API_TOKEN / X-API-Key, test_esp32_sim.py (simulador ESP32), Cola de reintento de POST (12 muestras), Comandos para ejecutar el sistema (legado), Operacion solo WiFi y diagnostico /api/devices, Dashboard cyberpunk con Chart.js y alertas Web Audio, Plan de implementacion Monitor IoT (ESP32 + FastAPI), web/serial_handler.py (reconexion serial automatica) (+1 more)

### Community 74 - "Network security + WireGuard"
Cohesion: 0.31
Nodes (7): die(), wireguard.sh script, Seguridad (cortafuegos, credenciales por nodo, sesiones), Conectividad híbrida local y remota, Tailscale (alternativa CGNAT), WireGuard VPN (UDP 51820), Parte G: VPN fuera de casa

### Community 75 - "Sensor board 1"
Cohesion: 0.25
Nodes (9): AJ-SR04M sensor connector (4 pin), BiogasInterfaz v1 - placa de sensores, Cable terminals to central unit (J1A 1-6, J13 7-12), DHT11 sensor connector (3 pin), MH-Z19C sensor connector (4 pin), MQ-4 sensor connector (4 pin), 12V power input with polarity protection diode, Regulator/converter module (3-pin footprint) (+1 more)

### Community 76 - "Calibration types"
Cohesion: 0.29
Nodes (4): CalResult, Done, Failed, Running

### Community 78 - "ESP32 TLS provisioning"
Cohesion: 0.29
Nodes (8): Comandos JSON (calibrate, set_intervals, led, reboot, set_wifi, set_server), Mosquitto (broker MQTT, ACL, usuario=MAC), Instalacion de la CA de la Pi (instalar_ca.ps1), ca_cert.h (CA exportada desde la Pi), Firmware del nodo ESP32 (MQTT TLS), Aprovisionamiento por USB (cmd provision), Estados del LED de estado, Comandos USB (status, provision, factory_reset, calibrate_mq4, calibrate_co2_zero, identify, reboot)

### Community 79 - "Deployment overview"
Cohesion: 0.32
Nodes (8): Backend Raspberry Pi (FastAPI + paho-mqtt + Neon), Servidor demo con 6 nodos simulados, Cambio automatico LAN <-> VPN WireGuard, Panel web como PWA (alternativa), App de escritorio Windows (pywebview + WebView2), Monitor multi-nodo (ESP32 + Raspberry Pi + Windows), Neon (PostgreSQL), Raspberry Pi 4B (broker y servidor local)

### Community 80 - "ML integration"
Cohesion: 0.29
Nodes (7): Contrato JSON de predicción v1, Inferencia ligera en la Pi (ONNX, scikit-learn), Integración del modelo de ML, #ml-panel en dashboard.html, Tabla monitor.ml_predictions, Opción A: resultados por lotes en Neon, Opción B: predicciones en tiempo real por MQTT

### Community 81 - "Precision calibration"
Cohesion: 0.32
Nodes (7): Ajuste de offset DHT11 (sesgo, +-2C/+-5%RH), Guia de calibracion de precision, Calibracion multipunto MQ-4 (ajuste log-log de A y B), Comandos nuevos de calibracion (add_calibration_point, fit_calibration_curve, reset_*), Compensacion velocidad del sonido por temperatura (331.3+0.606T), Calibracion ultrasonido 2 puntos (scale/offset), Ultrasonido no bloqueante (buffer circular, mediana de 9)

### Community 87 - "Legacy backend fork"
Cohesion: 0.29
Nodes (7): Backend bifurcado archivado (incompleto), Faltan app/config.py y app/security.py, Firmware arduino/nodo_mqtt, Backend Raspberry Pi (fork) FastAPI + MQTT + Neon, Flujo de alta de nodo (pending -> active, config retenida), API REST con JWT y roles viewer<operator<admin, Sistema legado (web/, arduino/mgas, backend_fork)

### Community 88 - "Requirements"
Cohesion: 0.29
Nodes (7): backend_fork requirements (aiomqtt, argon2), backend requirements (versiones exactas), backend dev deps (pytest, httpx), Backend FastAPI (backend/app), Instalación con verificación de hashes, Parte H: Probar sin Raspberry Pi (demo_server), web requirements (fastapi, pyserial, requests)

### Community 90 - "ESP32 pinout"
Cohesion: 0.29
Nodes (7): ESP32 ADC-capable GPIO pins (ADC0-ADC19), ESP32 DevKit (WROOM-32D) Pinout Diagram, Internal SPI flash pins (GPIO6-11, not for user use), Power pins (3.3V, 5V, GND, EN/RESET), ESP32 Touch sensor pins (TOUCH0-TOUCH9), UART0 (GPIO1 TX0, GPIO3 RX0), VSPI bus (GPIO23 MOSI, GPIO19 MISO, GPIO18 SCK, GPIO5 SS)

### Community 91 - "PKI script"
Cohesion: 0.67
Nodes (5): die(), fingerprint(), make_ca(), make_server(), pki.sh script

### Community 92 - "OTA download states"
Cohesion: 0.33
Nodes (6): OTADownloadState, OtaDownloadCompleted, OtaDownloadError, OtaDownloadFile, OtaDownloadHeader, OtaDownloadMagicNumberMismatch

### Community 95 - "Humidity sensor"
Cohesion: 0.33
Nodes (3): Humidity, _id, _parent

### Community 96 - "Temperature sensor"
Cohesion: 0.33
Nodes (3): Temperature, _id, _parent

### Community 98 - "Connection UI"
Cohesion: 0.60
Nodes (3): renderCurrent(), testAll(), testRow()

### Community 100 - "ESP32 board"
Cohesion: 0.40
Nodes (5): EN and Boot buttons, ESP32-WROOM-32D development board, Espressif ESP32-WROOM-32D module (WiFi/Bluetooth), GPIO pin headers (two rows, labeled pins), Micro-USB port

## Knowledge Gaps
- **290 isolated node(s):** `dhtOk`, `tempC`, `humPct`, `co2Ok`, `co2Ppm` (+285 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 626 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **44 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DHT` connect `DHT library` to `Firmware sensors`, `Adafruit_Sensor class`, `Misc: DHT.h`, `DHT unified`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **What connects `dhtOk`, `tempC`, `humPct` to the rest of the system?**
  _290 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Backend DB layer` be split into smaller, more focused modules?**
  _Cohesion score 0.06715063520871144 - nodes in this community are weakly interconnected._
- **Why does `Tópicos MQTT monitor/v1/nodes/<mac>` connect `Multi-node architecture` to `ML integration`, `Hub + persistence docs`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Should `MQ sensor library` be split into smaller, more focused modules?**
  _Cohesion score 0.06547619047619048 - nodes in this community are weakly interconnected._
- **Why does `LZSSDecoder` connect `LZSS OTA decompress` to `OTA decoder`, `Adafruit_Sensor class`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Should `FastAPI app + Postgres` be split into smaller, more focused modules?**
  _Cohesion score 0.0841813135985199 - nodes in this community are weakly interconnected._
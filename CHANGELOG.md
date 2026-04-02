# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MQTT as a fourth connection type alongside TCP, Bluetooth, and Serial
- MQTT broker connection with configurable host, port, TLS, and authentication
- MQTT message decoding with AES-CTR decryption of encrypted `ServiceEnvelope` payloads
- Automatic node discovery from MQTT traffic (NODEINFO_APP, POSITION_APP, TELEMETRY_APP)
- Virtual gateway node synthesis for MQTT connections
- Dual-mode operation supporting device-based and MQTT connections simultaneously
- Send messages via MQTT publish (text, direct, broadcast)
- Config flow step for MQTT broker settings and channel key management
- Options flow for editing MQTT settings and adding/removing channel keys
- Channel key validation with base64 decoding and AES key preparation
- OpenAPI 3.0+ specification (`docs/api/openapi.yaml`) documenting all service endpoints and schemas
- Swagger UI (`docs/api/index.html`) for interactive API documentation
- Comprehensive test suite with Hypothesis property-based tests (17 properties)
- CI/CD pipeline with GitHub Actions (tests, lint, type check, coverage)
- Developer tooling: Makefile, VS Code debug configurations, `.env.example`
- Repository documentation: README, user guide, developer guide, features guide
- CONTRIBUTING guide with branching strategy and PR process
- Renovate configuration for automated dependency updates
- GitHub issue templates (bug report, feature request, security vulnerability)
- GitHub pull request template

### Changed
- Extended `MeshtasticApiClient` to route `connection_type=mqtt` to `MqttConnection`
- Extended `async_setup_entry` to handle MQTT mode with passive node discovery
- Extended `ConnectionType` enum with `MQTT = "mqtt"` value
- Added MQTT configuration constants to `const.py`

## [0.1.0] - TBD

### Added
- Initial release of Meshtastic Home Assistant MQTT integration
- Support for TCP, Bluetooth, Serial, and MQTT connection types
- Protobuf-based message decoding with `aiomeshtastic` package
- Home Assistant device and entity creation for discovered Meshtastic nodes
- Sensor entities for battery, voltage, channel utilization, air utilization, temperature, humidity, and pressure
- Device tracker entities for nodes reporting position data
- Home Assistant events for text messages (`meshtastic_event`, `meshtastic_message_log`)
- MIT license

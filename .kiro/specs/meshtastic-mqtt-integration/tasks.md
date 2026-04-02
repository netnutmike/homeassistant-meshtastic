# Implementation Plan: Meshtastic MQTT Integration

## Overview

This plan implements MQTT as a fourth connection type for the Meshtastic Home Assistant integration, along with repository infrastructure (CI/CD, docs, developer tooling). Tasks are ordered so foundational components (decoder, connection class) come first, followed by integration points (config flow, API client, setup entry), then infrastructure (CI, docs).

## Tasks

- [ ] 1. Implement MqttPacketDecoder
  - [ ] 1.1 Create `home-assistant/custom_components/meshtastic/aiomeshtastic/connection/decoder.py` with `MqttPacketDecoder` class
    - Implement `__init__(self, channel_keys: dict[str, str])` that decodes and caches base64 channel keys
    - Implement `prepare_key(self, raw_key: bytes) -> bytes` with key padding/expansion rules (0x01 → default key, <16 pad to 16, 17-31 pad to 32, >32 truncate to 32)
    - Implement `build_nonce(self, packet_id: int, from_node_id: int) -> bytes` returning 16-byte nonce (packet_id LE 8 bytes + from_node_id LE 8 bytes)
    - Implement `decrypt_payload(self, encrypted: bytes, channel: str, packet_id: int, from_node_id: int) -> bytes | None` using AES-CTR from `cryptography` library
    - Implement `extract_channel_from_topic(self, topic: str) -> str` that locates type indicator (`e`, `c`, `json`) and returns next segment, defaulting to `"unknown"`
    - Implement `decode_to_mesh_packet(self, topic: str, payload: bytes) -> mesh_pb2.MeshPacket | None` with ServiceEnvelope parsing, fallback to direct MeshPacket, JSON handling, and decryption
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4_

  - [ ] 1.2 Write property test: ServiceEnvelope round-trip (Property 1)
    - **Property 1: ServiceEnvelope round-trip**
    - **Validates: Requirements 2.3, 7.2, 7.6**

  - [ ] 1.3 Write property test: Direct MeshPacket fallback parsing (Property 2)
    - **Property 2: Direct MeshPacket fallback parsing**
    - **Validates: Requirements 7.3**

  - [ ] 1.4 Write property test: AES-CTR encryption/decryption round-trip (Property 3)
    - **Property 3: AES-CTR encryption/decryption round-trip**
    - **Validates: Requirements 2.4, 8.1, 8.7**

  - [ ] 1.5 Write property test: Key preparation produces valid AES key length (Property 4)
    - **Property 4: Key preparation produces valid AES key length**
    - **Validates: Requirements 8.3, 8.4, 8.5**

  - [ ] 1.6 Write property test: Nonce construction produces 16 bytes (Property 5)
    - **Property 5: Nonce construction produces 16 bytes with correct layout**
    - **Validates: Requirements 8.1**

  - [ ] 1.7 Write property test: Channel name extraction from MQTT topics (Property 6)
    - **Property 6: Channel name extraction from MQTT topics**
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ] 1.8 Write property test: JSON message field extraction (Property 15)
    - **Property 15: JSON message field extraction**
    - **Validates: Requirements 7.5**

  - [ ] 1.9 Write property test: FromRadio output validity (Property 16)
    - **Property 16: FromRadio output validity**
    - **Validates: Requirements 2.2, 2.6**

- [ ] 2. Implement MqttConnection class
  - [ ] 2.1 Create `home-assistant/custom_components/meshtastic/aiomeshtastic/connection/mqtt.py` with `MqttConnection` class extending `ClientApiConnection`
    - Implement `__init__` accepting broker_host, broker_port, username, password, use_tls, topic_pattern, channel_keys, region
    - Implement `_connect()` using `aiomqtt.Client` to connect and subscribe to topic pattern
    - Implement `_disconnect()` to unsubscribe and close MQTT client cleanly
    - Implement `is_connected` property
    - Implement `_packet_stream()` async generator: receive MQTT messages, decode via `MqttPacketDecoder`, wrap `MeshPacket` in `FromRadio`, yield
    - Implement `_send_packet()` to construct `ServiceEnvelope` and publish to MQTT topic
    - Implement `request_config()` override to synthesize virtual gateway node and return immediately
    - Implement reconnection with exponential backoff (1s to 60s) using aiomqtt's reconnection
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ] 2.2 Export `MqttConnection` from `aiomeshtastic/connection/__init__.py` and `aiomeshtastic/__init__.py`
    - _Requirements: 2.1_

  - [ ] 2.3 Write unit tests for MqttConnection lifecycle (connect, subscribe, receive, disconnect)
    - Test connect/disconnect lifecycle with mocked aiomqtt client
    - Test packet stream yields FromRadio from decoded MQTT messages
    - Test reconnection behavior
    - _Requirements: 2.1, 2.7, 2.8_

- [ ] 3. Checkpoint - Ensure decoder and connection tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Extend constants and config flow for MQTT
  - [ ] 4.1 Add MQTT constants to `home-assistant/custom_components/meshtastic/const.py`
    - Add `MQTT = "mqtt"` to `ConnectionType` enum
    - Add MQTT config key constants: `CONF_CONNECTION_MQTT_HOST`, `CONF_CONNECTION_MQTT_PORT`, `CONF_CONNECTION_MQTT_USERNAME`, `CONF_CONNECTION_MQTT_PASSWORD`, `CONF_CONNECTION_MQTT_TLS`, `CONF_CONNECTION_MQTT_TOPIC`, `CONF_CONNECTION_MQTT_CHANNEL_KEYS`, `CONF_CONNECTION_MQTT_REGION`
    - _Requirements: 1.1, 1.2, 5.3_

  - [ ] 4.2 Add MQTT config flow steps to `home-assistant/custom_components/meshtastic/config_flow.py`
    - Add `"manual_mqtt"` to `async_step_user()` menu options
    - Implement `async_step_manual_mqtt()` with form for broker host, port (default 1883), username (optional), password (optional), TLS toggle (default off), topic pattern (default `msh/US/2/e/#`), region
    - Implement `async_step_mqtt_channels()` for adding channel name + encryption key pairs
    - Implement test connection logic within 10 seconds timeout
    - Add validation: non-empty host, port 1-65535, valid base64 channel keys
    - Display error messages on connection failure
    - Create config entry with `connection_type=mqtt` on success
    - Add MQTT options flow support for editing settings and channel keys
    - Add MQTT branch to `async_step_reconfigure()`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.2, 6.3, 6.4_

  - [ ] 4.3 Add MQTT translation strings to `home-assistant/custom_components/meshtastic/translations/en.json`
    - Add step titles and field descriptions for manual_mqtt and mqtt_channels steps
    - Add error messages for MQTT connection failures
    - _Requirements: 1.1, 1.2_

  - [ ] 4.4 Write property test: MQTT broker validation (Property 12)
    - **Property 12: MQTT broker validation**
    - **Validates: Requirements 1.6**

  - [ ] 4.5 Write property test: Invalid base64 channel key rejection (Property 13)
    - **Property 13: Invalid base64 channel key rejection**
    - **Validates: Requirements 6.4**

  - [ ] 4.6 Write unit tests for MQTT config flow
    - Test happy path: MQTT setup wizard end-to-end with mocked broker
    - Test error cases: invalid inputs, connection failures, auth failures
    - Test options flow: edit MQTT settings, add/remove channel keys
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.2, 6.3, 6.4_

- [ ] 5. Extend API client and setup entry for MQTT
  - [ ] 5.1 Add MQTT connection routing to `home-assistant/custom_components/meshtastic/api.py`
    - Add `MqttConnection` import
    - Add `ConnectionType.MQTT` branch in `__init__` to instantiate `MqttConnection` with config entry data
    - Handle MQTT-mode limitations for request_telemetry, request_position, request_traceroute (raise `MeshtasticApiClientError("Not supported in MQTT mode")`)
    - _Requirements: 5.3_

  - [ ] 5.2 Modify `home-assistant/custom_components/meshtastic/__init__.py` for MQTT setup entry handling
    - For MQTT mode: skip node selection step (no `CONF_OPTION_FILTER_NODES` required)
    - Auto-discover all nodes from MQTT traffic
    - Create virtual gateway device
    - Coordinator's `_async_update_data` includes all discovered nodes when in MQTT mode
    - Handle MQTT config entry unload: disconnect MQTT connection, remove exclusive entities
    - _Requirements: 5.1, 5.2, 5.4_

  - [ ] 5.3 Write property test: Connection type routing (Property 11)
    - **Property 11: Connection type routing**
    - **Validates: Requirements 5.3**

  - [ ] 5.4 Write property test: Latitude/longitude fixed-point conversion (Property 7)
    - **Property 7: Latitude/longitude fixed-point conversion**
    - **Validates: Requirements 3.6**

  - [ ] 5.5 Write property test: Node database update from decoded packets (Property 8)
    - **Property 8: Node database update from decoded packets**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ] 5.6 Write property test: Stub node creation for unknown senders (Property 9)
    - **Property 9: Stub node creation for unknown senders**
    - **Validates: Requirements 3.5**

  - [ ] 5.7 Write property test: Text message event contains correct fields (Property 10)
    - **Property 10: Text message event contains correct fields**
    - **Validates: Requirements 3.4**

  - [ ] 5.8 Write property test: Device identifier consistency (Property 14)
    - **Property 14: Device identifier consistency across connection types**
    - **Validates: Requirements 5.2**

  - [ ] 5.9 Write property test: Device model from hwModel (Property 17)
    - **Property 17: Device model from hwModel**
    - **Validates: Requirements 4.5**

  - [ ] 5.10 Write unit tests for MQTT API client and setup entry
    - Test MqttConnection instantiation from config entry data
    - Test virtual gateway node synthesis
    - Test service routing in MQTT mode (send works, request_* raises)
    - Test dual-mode coexistence (TCP + MQTT config entries for same node)
    - Test MQTT config entry unload
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4_

- [ ] 6. Checkpoint - Ensure all core integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Create test configuration and shared fixtures
  - [ ] 7.1 Create `tests/conftest.py` with shared fixtures and Hypothesis settings
    - Register Hypothesis profiles: `ci` (max_examples=200), `dev` (max_examples=100)
    - Create shared fixtures for mocked MQTT broker, sample protobuf messages, channel keys, config entry data
    - _Requirements: 20.2_

- [ ] 8. API Documentation (OpenAPI/Swagger)
  - [ ] 8.1 Create `docs/api/openapi.yaml` with OpenAPI 3.0+ specification
    - Document all service endpoints: send_text, send_direct_message, broadcast_channel_message, request_telemetry, request_position, request_traceroute
    - Document request/response schemas with data types, required fields, example values
    - Document MQTT message schemas (ServiceEnvelope, MeshPacket, Data) as JSON Schema equivalents
    - Document Home Assistant event payloads (meshtastic_event, meshtastic_message_log)
    - Document MQTT connection configuration schema
    - Include authentication requirements and error response schemas
    - Support both JSON and YAML export formats
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6, 10.7, 10.8, 10.10_

  - [ ] 8.2 Create `docs/api/index.html` with Swagger UI
    - Render the OpenAPI spec using Swagger UI CDN
    - Allow testing API endpoints from the browser
    - _Requirements: 10.5, 10.9_

- [ ] 9. CI/CD workflows
  - [ ] 9.1 Create `.github/workflows/ci.yml`
    - Trigger on PRs and commits to `dev` and `main` branches
    - Run unit tests, integration tests, linting (ruff), type checking (mypy), security scanning
    - Generate code coverage reports, fail if below 80%
    - Validate OpenAPI specification
    - Run on Python 3.12+
    - Comment on PRs with test results and coverage summary
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

- [-] 10. Repository structure and documentation
  - [x] 10.1 Create/update `README.md` at repository root
    - Project overview, features list, quick start guide
    - Installation instructions (HACS and manual)
    - Troubleshooting guidance
    - Links to `docs/` directory and API documentation
    - _Requirements: 10.11, 11.1, 11.12_

  - [ ] 10.2 Create `CONTRIBUTING.md`
    - Contribution guidelines, code style (ruff), PR process
    - Branching strategy: `main`/`dev` with feature branches from `dev`, hotfix from `main`
    - Branch protection guidance (CI checks, code review, no force push, no branch deletion)
    - Development workflow description
    - _Requirements: 14.2, 19.1, 19.2, 19.3, 19.4_

  - [x] 10.3 Create `LICENSE` file with MIT license
    - _Requirements: 14.3_

  - [ ] 10.4 Create `CHANGELOG.md` following Keep a Changelog format
    - _Requirements: 14.4, 16.5, 16.6, 19.5_

  - [ ] 10.5 Create `.env.example` with documented environment variables
    - _Requirements: 14.5, 17.2_

  - [ ] 10.6 Create documentation files in `docs/` directory
    - `docs/README.md` as index page linking to all docs
    - `docs/user-guide.md` with configuration and usage instructions
    - `docs/developer-guide.md` with architecture, contributing, testing, debugging
    - `docs/features.md` with feature descriptions and usage examples
    - _Requirements: 14.6, 14.7, 14.8, 14.9, 14.10, 14.11, 18.5_

- [-] 11. Developer environment and tooling
  - [x] 11.1 Create `.gitignore` at repository root
    - Exclude: `__pycache__/`, `*.pyc`, `*.pyo`, `*.egg-info/`, `dist/`, `build/`, `.eggs/`, `.env`, `.env.local`, `.env.*.local`, `venv/`, `.venv/`, `*.venv/`, `.idea/`, `.vscode/settings.json`, `*.swp`, `*.swo`, `*~`, `.DS_Store`, `Thumbs.db`, `coverage/`, `.coverage`, `htmlcov/`, `*.log`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `tmp/`, `temp/`, `config/secrets.yaml`, `config/.storage/`, `config/home-assistant_v2.db`
    - _Requirements: 12.1, 12.2_

  - [ ] 11.2 Create `requirements-dev.txt` with development dependencies
    - Include pytest, hypothesis, ruff, mypy, coverage, and documentation tools
    - _Requirements: 17.3_

  - [ ] 11.3 Create `Makefile` with automation targets
    - Targets: `setup`, `install`, `test`, `test-watch`, `lint`, `lint-fix`, `type-check`, `verify-setup`
    - _Requirements: 14.4, 14.5, 15.4_

  - [ ] 11.4 Create `.vscode/launch.json` with debug configurations
    - Debug integration within Home Assistant, debug tests, attach to running processes
    - Source map and breakpoint support
    - _Requirements: 18.3, 18.4_

- [ ] 12. Repository maintenance tools
  - [ ] 12.1 Create `renovate.json` for automated dependency updates targeting `dev` branch
    - _Requirements: 13.1_

  - [ ] 12.2 Create GitHub issue templates
    - `.github/ISSUE_TEMPLATE/bug_report.md`
    - `.github/ISSUE_TEMPLATE/feature_request.md`
    - `.github/ISSUE_TEMPLATE/security_vulnerability.md`
    - _Requirements: 13.3_

  - [ ] 12.3 Create `.github/PULL_REQUEST_TEMPLATE.md`
    - Guide contributors to target `dev` branch, include description, testing steps, related issues
    - _Requirements: 13.4_

- [ ] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- The design uses Python throughout, so all implementation tasks use Python

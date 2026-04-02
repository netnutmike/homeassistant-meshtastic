# Requirements Document

## Introduction

This feature extends the existing Meshtastic Home Assistant custom integration to support MQTT as an alternative connection method alongside the existing TCP, Bluetooth, and Serial device connections. Instead of requiring a physical Meshtastic node connected to the Home Assistant host, users can subscribe to a Meshtastic MQTT broker to receive mesh network traffic, decode encrypted protobuf messages, and create Home Assistant devices and entities for each discovered Meshtastic node. The integration reuses the existing protobuf definitions already present in the `aiomeshtastic` package and adapts the decoding and node-management logic from the companion `meshtastic-mqtt-monitor` project.

In addition to the MQTT integration feature, this project establishes a production-ready repository with OpenAPI/Swagger API documentation, a developer environment with setup automation, a `main`/`dev` branching strategy with Renovate for dependency management, and CI/CD pipelines for quality gates. The integration is distributed via HACS (Home Assistant Community Store) and manual installation, following standard HA custom component conventions.

## Glossary

- **Integration**: The Meshtastic Home Assistant custom component located at `custom_components/meshtastic/`.
- **Config_Flow**: The Home Assistant UI-driven setup wizard that collects connection parameters from the user.
- **MQTT_Connection**: A new connection class that subscribes to a Meshtastic MQTT broker and yields decoded `FromRadio`-compatible packets to the existing `MeshInterface` pipeline.
- **ServiceEnvelope**: The outer protobuf wrapper (`mqtt_pb2.ServiceEnvelope`) used by Meshtastic to transport `MeshPacket` messages over MQTT.
- **MeshPacket**: The core Meshtastic protobuf message containing routing metadata and an encrypted or decoded `Data` payload.
- **Channel_Key**: A base64-encoded AES encryption key associated with a specific Meshtastic channel, used for AES-CTR decryption of `MeshPacket` payloads.
- **Nonce**: A 16-byte value constructed from the packet ID (8 bytes little-endian) and the sender node ID (8 bytes little-endian), used as the AES-CTR counter block.
- **Topic_Pattern**: The MQTT topic string following the Meshtastic convention `msh/{region}/2/e/{channel}/{gateway_id}`, supporting MQTT wildcards (`+`, `#`).
- **Node_Database**: The in-memory dictionary (`MeshInterface._node_database`) that stores discovered Meshtastic node information keyed by node number.
- **Coordinator**: The `MeshtasticDataUpdateCoordinator` that listens to API events and updates Home Assistant entity state.
- **Gateway_Node**: In device-based mode, the physically connected Meshtastic node. In MQTT mode, a virtual node representing the MQTT connection itself.
- **Decoder**: The component responsible for parsing `ServiceEnvelope` protobuf messages, decrypting encrypted payloads, and extracting typed application data (position, telemetry, text, node info).
- **OpenAPI_Spec**: The OpenAPI 3.0+ YAML file (`docs/api/openapi.yaml`) that documents all integration service endpoints, MQTT message schemas, and event payloads using the Swagger specification format.
- **Dev_Branch**: The `dev` Git branch used for active development; feature branches are merged here before being promoted to `main` for release.
- **Swagger_UI**: An interactive web-based documentation viewer that renders the OpenAPI specification and allows testing API endpoints directly from the browser.
- **Renovate**: An automated dependency update tool that creates pull requests when new versions of project dependencies are available.
- **Semantic_Versioning**: A versioning scheme using `x.y.z` format where x = major (breaking changes), y = minor (new features, backward compatible), z = patch (bug fixes).

## Requirements

### Requirement 1: MQTT Connection Type in Config Flow

**User Story:** As a Home Assistant user, I want to select MQTT as a connection type during integration setup, so that I can monitor Meshtastic mesh traffic without a physical device.

#### Acceptance Criteria

1. WHEN the user opens the Meshtastic integration setup, THE Config_Flow SHALL display "MQTT" as a selectable connection option alongside TCP, Bluetooth, and Serial.
2. WHEN the user selects the MQTT connection type, THE Config_Flow SHALL present a form requesting: broker host, broker port (default 1883), username (optional), password (optional), TLS toggle (default off), topic pattern (default `msh/US/2/e/#`), and at least one channel name with its corresponding Channel_Key.
3. WHEN the user submits valid MQTT configuration, THE Config_Flow SHALL attempt a test connection to the MQTT broker within 10 seconds.
4. IF the test connection to the MQTT broker fails, THEN THE Config_Flow SHALL display an error message indicating the connection failure reason.
5. WHEN the test connection succeeds, THE Config_Flow SHALL create a config entry with `connection_type` set to `mqtt` and store all MQTT parameters in the entry data.
6. THE Config_Flow SHALL validate that the broker host is non-empty and the broker port is between 1 and 65535.

### Requirement 2: MQTT Connection Class

**User Story:** As a developer, I want an MQTT connection class that implements the same interface as TCP/Bluetooth/Serial connections, so that the existing MeshInterface can process MQTT-sourced packets without modification.

#### Acceptance Criteria

1. THE MQTT_Connection SHALL subscribe to the configured Topic_Pattern on the MQTT broker upon calling `connect()`.
2. THE MQTT_Connection SHALL yield `FromRadio`-compatible protobuf messages through the `listen()` async iterator, matching the interface of `ClientApiConnection`.
3. WHEN a `ServiceEnvelope` message is received on a subscribed topic, THE MQTT_Connection SHALL parse the envelope and extract the contained `MeshPacket`.
4. WHEN the `MeshPacket` contains an encrypted payload, THE Decoder SHALL decrypt the payload using AES-CTR with the Channel_Key corresponding to the channel extracted from the MQTT topic, and a Nonce constructed from the packet ID and sender node ID.
5. IF decryption fails or no Channel_Key is configured for the channel, THEN THE MQTT_Connection SHALL skip the packet and log a debug-level message.
6. WHEN the `MeshPacket` contains a decoded (unencrypted) payload, THE MQTT_Connection SHALL pass the packet through without decryption.
7. THE MQTT_Connection SHALL reconnect to the MQTT broker with exponential backoff (starting at 1 second, maximum 60 seconds) when the connection is lost unexpectedly.
8. WHEN `disconnect()` is called, THE MQTT_Connection SHALL unsubscribe from all topics and close the MQTT connection cleanly.

### Requirement 3: MQTT Message Decoding and Node Discovery

**User Story:** As a Home Assistant user, I want the integration to automatically discover Meshtastic nodes from MQTT traffic, so that I see devices and sensors for each node heard on the mesh.

#### Acceptance Criteria

1. WHEN a decoded `MeshPacket` with portnum `NODEINFO_APP` is received via MQTT, THE Integration SHALL create or update an entry in the Node_Database with the node's ID, long name, short name, and hardware model.
2. WHEN a decoded `MeshPacket` with portnum `POSITION_APP` is received via MQTT, THE Integration SHALL update the corresponding node's position data (latitude, longitude, altitude) in the Node_Database.
3. WHEN a decoded `MeshPacket` with portnum `TELEMETRY_APP` is received via MQTT, THE Integration SHALL update the corresponding node's telemetry data (battery level, voltage, channel utilization, air utilization, environment metrics) in the Node_Database.
4. WHEN a decoded `MeshPacket` with portnum `TEXT_MESSAGE_APP` is received via MQTT, THE Integration SHALL fire a Home Assistant event containing the message text, sender node ID, and destination.
5. WHEN a packet is received from a node ID not yet in the Node_Database, THE Integration SHALL create a stub node entry using the hex-formatted node ID as the default name.
6. THE Integration SHALL convert `latitudeI` and `longitudeI` fixed-point integer fields to floating-point degrees by multiplying by 1e-7.

### Requirement 4: Home Assistant Device and Entity Creation for MQTT Nodes

**User Story:** As a Home Assistant user, I want devices and entities created for each Meshtastic node discovered via MQTT, so that I can view node data on my dashboard.

#### Acceptance Criteria

1. WHEN a node is discovered or updated via MQTT, THE Integration SHALL create or update a Home Assistant device with identifiers `(meshtastic, {node_num})`, matching the same identifier scheme used by device-based connections.
2. THE Integration SHALL create sensor entities for each MQTT-discovered node covering: battery level, voltage, channel utilization, air utilization TX, temperature, humidity, and barometric pressure, consistent with the entity types created for device-based connections.
3. THE Integration SHALL create a `device_tracker` entity for each MQTT-discovered node that has reported position data.
4. WHEN telemetry or position data is updated for a node, THE Coordinator SHALL propagate the updated data to the corresponding Home Assistant entities.
5. THE Integration SHALL set the device model based on the `hwModel` field from `NODEINFO_APP` packets when available.

### Requirement 5: Dual-Mode Operation

**User Story:** As a Home Assistant user, I want to run both device-based and MQTT-based Meshtastic connections simultaneously, so that I can combine local device control with broader MQTT mesh monitoring.

#### Acceptance Criteria

1. THE Integration SHALL support multiple config entries, allowing one or more device-based connections and one or more MQTT-based connections to coexist.
2. WHEN the same Meshtastic node is seen by both a device-based connection and an MQTT-based connection, THE Integration SHALL merge the node into a single Home Assistant device using the shared identifier `(meshtastic, {node_num})`.
3. THE Integration SHALL route the `connection_type` value from the config entry data to select either a device-based connection (TCP, Bluetooth, Serial) or the MQTT_Connection class in the `MeshtasticApiClient`.
4. WHEN an MQTT config entry is unloaded, THE Integration SHALL disconnect the MQTT_Connection and remove entities that are exclusively associated with that config entry.

### Requirement 6: MQTT Configuration Validation and Options Flow

**User Story:** As a Home Assistant user, I want to reconfigure my MQTT connection settings after initial setup, so that I can change brokers or update encryption keys without removing the integration.

#### Acceptance Criteria

1. WHEN the user opens the options flow for an MQTT-based config entry, THE Config_Flow SHALL display the current MQTT settings (broker host, port, username, TLS, topic pattern, channel keys) for editing.
2. WHEN the user submits updated MQTT options, THE Integration SHALL validate the new settings and reload the config entry to apply changes.
3. THE Config_Flow SHALL allow adding and removing channel name and Channel_Key pairs in the options flow.
4. IF the user provides an invalid base64 Channel_Key, THEN THE Config_Flow SHALL display a validation error for that field.

### Requirement 7: ServiceEnvelope Protobuf Parsing

**User Story:** As a developer, I want robust protobuf parsing of MQTT messages, so that the integration handles both well-formed and malformed messages gracefully.

#### Acceptance Criteria

1. WHEN a binary payload is received from MQTT, THE Decoder SHALL first attempt to parse the payload as a `ServiceEnvelope` protobuf message.
2. IF `ServiceEnvelope` parsing succeeds and the envelope contains a `packet` field, THEN THE Decoder SHALL extract the `MeshPacket` from the envelope.
3. IF `ServiceEnvelope` parsing fails, THEN THE Decoder SHALL attempt to parse the payload directly as a `MeshPacket`.
4. IF both parsing attempts fail, THEN THE Decoder SHALL log a warning and discard the message.
5. THE Decoder SHALL handle JSON-formatted messages on `msh/{region}/2/json/{channel}` topics by parsing the JSON payload and extracting equivalent fields.
6. FOR ALL valid `ServiceEnvelope` messages, serializing the extracted `MeshPacket` back into a `ServiceEnvelope` and re-parsing SHALL produce an equivalent `MeshPacket` (round-trip property).

### Requirement 8: AES-CTR Decryption of Encrypted Packets

**User Story:** As a developer, I want correct AES-CTR decryption of Meshtastic packets, so that encrypted mesh traffic is readable by the integration.

#### Acceptance Criteria

1. THE Decoder SHALL construct the AES-CTR Nonce as 16 bytes: the packet ID as 8 bytes little-endian followed by the sender node ID as 8 bytes little-endian.
2. WHEN the Channel_Key decodes to a single byte `0x01`, THE Decoder SHALL expand the key to the default Meshtastic key by decoding `1PG7OiApB1nwvP+rz05pAQ==` from base64.
3. WHEN the Channel_Key decodes to fewer than 16 bytes (and is not the single-byte `0x01` case), THE Decoder SHALL pad the key with zero bytes to 16 bytes.
4. WHEN the Channel_Key decodes to between 17 and 31 bytes, THE Decoder SHALL pad the key with zero bytes to 32 bytes.
5. WHEN the Channel_Key decodes to more than 32 bytes, THE Decoder SHALL truncate the key to 32 bytes.
6. THE Decoder SHALL use the `cryptography` library's AES-CTR cipher for decryption.
7. FOR ALL plaintext payloads, encrypting with a known Channel_Key and Nonce and then decrypting with the same key and Nonce SHALL produce the original plaintext (round-trip property).

### Requirement 9: MQTT Topic Parsing

**User Story:** As a developer, I want correct extraction of channel names from MQTT topics, so that the integration applies the right decryption key per channel.

#### Acceptance Criteria

1. WHEN the MQTT topic follows the pattern `msh/{region}/2/e/{channel_name}` or `msh/{region}/2/e/{channel_name}/{gateway_id}`, THE Decoder SHALL extract `{channel_name}` as the channel identifier.
2. WHEN the MQTT topic contains additional path segments between the region and the protocol version (e.g., `msh/{region}/{area}/{network}/2/e/{channel_name}`), THE Decoder SHALL still correctly extract `{channel_name}` by locating the type indicator (`e`, `c`, or `json`) and taking the next path segment.
3. WHEN the MQTT topic uses the JSON format indicator (`json` instead of `e`), THE Decoder SHALL extract the channel name using the same positional logic.
4. IF the channel name cannot be determined from the topic, THEN THE Decoder SHALL use `"unknown"` as the channel identifier.

### Requirement 10: API Documentation with OpenAPI/Swagger

**User Story:** As a developer or integrator, I want all integration APIs documented using OpenAPI/Swagger, so that I can understand available endpoints, data models, and message formats without reading source code.

#### Acceptance Criteria

1. THE repository SHALL contain an OpenAPI 3.0+ specification file (`docs/api/openapi.yaml`) documenting all REST-like service endpoints exposed by the integration (send_text, send_direct_message, broadcast_channel_message, request_telemetry, request_position, request_traceroute).
2. THE OpenAPI specification SHALL document all request and response schemas including data types, required fields, and example values for each service call.
3. THE OpenAPI specification SHALL document the MQTT message schemas including the ServiceEnvelope, MeshPacket, and Data protobuf structures as JSON Schema equivalents.
4. THE OpenAPI specification SHALL document the Home Assistant event payloads fired by the integration (meshtastic_event, meshtastic_message_log).
5. THE repository SHALL include a Swagger UI static page or configuration that renders the OpenAPI spec, accessible via `docs/api/index.html` or a served endpoint.
6. THE OpenAPI specification SHALL document the MQTT connection configuration schema including broker settings, channel keys, and topic patterns.
7. THE OpenAPI specification SHALL include authentication requirements for each endpoint where applicable.
8. THE OpenAPI specification SHALL include error response schemas for all endpoints.
9. THE Swagger UI SHALL allow testing API endpoints directly from the browser where the Home Assistant instance is accessible.
10. THE OpenAPI specification file SHALL be exportable in both JSON and YAML formats.
11. THE API documentation SHALL be linked from the main README.

### Requirement 11: Repository Structure and Documentation

**User Story:** As a developer or user, I want comprehensive documentation and a well-structured repository, so that I can understand, use, and contribute to the project.

#### Acceptance Criteria

1. THE repository SHALL include a detailed `README.md` with: project overview, features list, quick start guide, installation instructions for all dependencies, troubleshooting guidance for common issues, and links to the `docs/` directory for detailed documentation.
2. THE repository SHALL include a `CONTRIBUTING.md` file with: contribution guidelines, code style requirements (ruff configuration), pull request process, and development workflow.
3. THE repository SHALL include a `LICENSE` file with the MIT open source license.
4. THE repository SHALL include a `CHANGELOG.md` file following Keep a Changelog format tracking: version number, release date, added features, changed features, fixed bugs, and breaking changes.
5. THE repository SHALL include a `.env.example` file with all required environment variables documented with descriptions and example values.
6. THE repository SHALL include a `docs/` directory with comprehensive documentation.
7. THE `docs/` directory SHALL include a `README.md` as the index page linking to all documentation files.
8. THE `docs/` directory SHALL include a `user-guide.md` explaining: how to configure the integration, how to use the integration, common workflows, and all configuration options.
9. THE `docs/` directory SHALL include a `developer-guide.md` explaining: architecture overview, how to contribute, development setup, testing guidelines, and debugging instructions.
10. THE `docs/` directory SHALL include a `features.md` document detailing: all integration features, feature descriptions, usage examples, and diagrams where applicable.
11. THE `docs/` directory SHALL include API documentation (`docs/api/openapi.yaml` and `docs/api/index.html` for Swagger UI).
12. THE main `README.md` SHALL link to the `docs/` directory for detailed documentation.

### Requirement 12: .gitignore Configuration

**User Story:** As a developer, I want a properly configured .gitignore file, so that build artifacts, secrets, and IDE files are never committed to the repository.

#### Acceptance Criteria

1. THE repository SHALL include a `.gitignore` file at the repository root.
2. THE `.gitignore` SHALL exclude at minimum: `__pycache__/`, `*.pyc`, `*.pyo`, `*.egg-info/`, `dist/`, `build/`, `.eggs/`, `.env`, `.env.local`, `.env.*.local`, `venv/`, `.venv/`, `*.venv/`, `.idea/`, `.vscode/settings.json`, `*.swp`, `*.swo`, `*~`, `.DS_Store`, `Thumbs.db`, `coverage/`, `.coverage`, `htmlcov/`, `*.log`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `tmp/`, `temp/`, `config/secrets.yaml`, `config/.storage/`, `config/home-assistant_v2.db`.

### Requirement 13: Repository Maintenance Tools

**User Story:** As a maintainer, I want automated dependency management and issue/PR templates, so that the project stays up to date and contributions are structured.

#### Acceptance Criteria

1. THE repository SHALL include a Renovate configuration (`renovate.json`) for automated dependency updates targeting the `dev` branch.
2. THE repository SHALL include GitHub Actions workflows (`.github/workflows/`) for continuous integration.
3. THE repository SHALL include issue templates (`.github/ISSUE_TEMPLATE/`) for: bug reports, feature requests, and security vulnerabilities.
4. THE repository SHALL include a pull request template (`.github/PULL_REQUEST_TEMPLATE.md`) that guides contributors to target the `dev` branch, include a description, testing steps, and related issue references.
5. THE repository SHALL use semantic versioning (x.y.z) where: x = major version (breaking changes), y = minor version (new features, backward compatible), z = patch version (bug fixes, backward compatible).
6. THE repository SHALL use semantic versioning for release tags (e.g., `v1.0.0`).

### Requirement 14: Developer Environment and Setup

**User Story:** As a new developer, I want clear setup instructions and tooling, so that I can start contributing to the project quickly.

#### Acceptance Criteria

1. THE repository SHALL include detailed setup instructions in `README.md` covering: list of all required dependencies with versions, steps for installing Python 3.12+ and pip, steps for creating a virtual environment, steps for installing development tools, steps for configuring environment variables, steps for running the application locally, steps for running tests, and troubleshooting guidance for common setup issues.
2. THE repository SHALL include a `.env.example` file with all required environment variables documented.
3. THE repository SHALL include a `requirements-dev.txt` or equivalent (`pyproject.toml` dev dependencies) listing all development dependencies including pytest, ruff, mypy, and documentation tools.
4. THE repository SHALL include a `Makefile` or equivalent script (`scripts/dev-setup.sh`) that automates: environment setup, dependency installation, running tests, linting, and type checking.
5. THE `Makefile` SHALL include a `verify-setup` target that checks all prerequisites are correctly installed.

### Requirement 15: Development Mode and Debugging

**User Story:** As a developer, I want debugging support during development, so that I can troubleshoot issues efficiently.

#### Acceptance Criteria

1. THE repository SHALL include VS Code launch configurations (`.vscode/launch.json`) supporting: debugging the integration within Home Assistant, debugging tests, and attaching to running processes.
2. THE debugging configuration SHALL include breakpoint support in Python code.
3. THE repository SHALL document how to use the debugger in `docs/developer-guide.md`.
4. THE `Makefile` SHALL include targets: `test` (run tests), `test-watch` (run tests in watch mode), `lint` (run linter), `lint-fix` (run linter with auto-fix), and `type-check` (run mypy).

### Requirement 16: Development Branch Strategy

**User Story:** As a maintainer, I want a clear branching strategy, so that development work is organized and production code remains stable.

#### Acceptance Criteria

1. THE repository SHALL use a branching strategy with: `main` branch for production-ready code, `dev` branch for ongoing development work, feature branches created from `dev`, and hotfix branches created from `main`.
2. THE repository SHALL require: all feature development to branch from `dev`, all feature branches to merge back to `dev` via pull request, and pull requests for all merges to `dev` and `main`.
3. THE repository SHALL include branch protection guidance in `CONTRIBUTING.md` for both `main` and `dev` branches recommending: require passing CI checks before merge, require code review approval before merge, prevent force pushes, and prevent branch deletion.
4. THE `CONTRIBUTING.md` SHALL document the branching strategy with a clear workflow diagram or description.
5. THE repository SHALL use semantic versioning for release tags.

### Requirement 17: Continuous Integration and Quality Gates

**User Story:** As a developer, I want automated testing and quality checks on all branches, so that I can catch issues early before they reach production.

#### Acceptance Criteria

1. THE CI pipeline SHALL run on: all pull requests to `dev` branch, all pull requests to `main` branch, all commits to `dev` branch, and all commits to `main` branch.
2. THE CI pipeline SHALL run: all unit tests, all integration tests, linting checks (ruff), type checking (mypy), and security scanning for dependencies.
3. THE CI pipeline SHALL generate code coverage reports.
4. THE CI pipeline SHALL fail if code coverage drops below a configured threshold (80%).
5. THE CI pipeline SHALL validate the OpenAPI specification file for correctness.
6. THE CI pipeline SHALL run on Python 3.12+ to match Home Assistant's minimum Python version requirement.
7. THE CI pipeline SHALL comment on pull requests with test results and coverage summary where supported by the CI platform.
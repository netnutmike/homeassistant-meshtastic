# Features

## Connection Types

The integration supports four connection methods to Meshtastic mesh networks:

```
                     ┌──────────────────────┐
                     │    Home Assistant     │
                     │   Meshtastic Integ.   │
                     └──────┬───────────────┘
                            │
           ┌────────┬───────┼────────┬─────────┐
           │        │       │        │         │
        ┌──▼──┐  ┌──▼──┐ ┌─▼──┐  ┌──▼───┐    │
        │ TCP │  │ BLE │ │USB │  │ MQTT │    │
        └──┬──┘  └──┬──┘ └─┬──┘  └──┬───┘    │
           │        │      │        │         │
        ┌──▼────────▼──────▼──┐  ┌──▼───────┐│
        │  Physical Meshtastic│  │MQTT Broker││
        │       Node          │  │           ││
        └─────────┬───────────┘  └──┬───────┘│
                  │                 │         │
                  └────────┬────────┘         │
                           │                  │
                  ┌────────▼────────┐         │
                  │  Meshtastic     │         │
                  │  Mesh Network   │◄────────┘
                  └─────────────────┘
```

### MQTT Connection

Subscribe to a Meshtastic MQTT broker to receive mesh network traffic without a physical device.

**How it works**: The integration connects to an MQTT broker, subscribes to Meshtastic topics (e.g., `msh/US/2/e/#`), decodes `ServiceEnvelope` protobuf messages, decrypts encrypted payloads using AES-CTR, and creates Home Assistant devices for each discovered node.

**Usage**: Select "MQTT" during integration setup and provide broker details and channel encryption keys.

**Example**:
```yaml
# After setup, nodes appear automatically. Send a message via MQTT:
service: meshtastic.send_text
data:
  text: "Hello from HA via MQTT!"
```

### TCP Connection

Connect directly to a Meshtastic node over the network using its IP address or hostname.

### Bluetooth Connection

Connect to a nearby Meshtastic node via Bluetooth Low Energy.

### Serial Connection

Connect to a Meshtastic node plugged into the Home Assistant host via USB.

## Automatic Node Discovery

Nodes are automatically discovered from mesh traffic. Each node becomes a Home Assistant device with sensors.

**Supported packet types**:

| Packet Type | Data Extracted |
|-------------|---------------|
| `NODEINFO_APP` | Node identity — long name, short name, hardware model |
| `POSITION_APP` | GPS coordinates — latitude, longitude, altitude |
| `TELEMETRY_APP` | Battery, voltage, channel utilization, environment data |
| `TEXT_MESSAGE_APP` | Text messages (fired as HA events) |

**Node discovery flow**:

```
  MQTT/Device Traffic
        |
        v
  Packet received from node !abcd1234
        |
        +-- Node in database? --> Yes --> Update existing entry
        |
        +-- No --> Create stub entry with hex ID as name
                   (updated when NODEINFO_APP arrives)
```

**Example**: When a node broadcasts its position, the integration creates or updates a `device_tracker` entity with the GPS coordinates. Position values are converted from Meshtastic's fixed-point integer format (`latitudeI * 1e-7`) to floating-point degrees.

## AES-CTR Decryption

Encrypted Meshtastic channel traffic is decrypted using configurable channel keys.

**Decryption flow**:

```
  Encrypted MeshPacket
        |
        v
  Extract channel name from MQTT topic
        |
        v
  Look up channel key --> Not found? --> Skip packet (log debug)
        |
        v
  Prepare key (pad/expand/truncate)
        |
        v
  Build nonce: packet_id (8 bytes LE) + from_node_id (8 bytes LE)
        |
        v
  AES-CTR decrypt --> Failure? --> Skip packet (log debug)
        |
        v
  Parse decrypted payload as Data protobuf
```

**Key handling**:

| Input | Action |
|-------|--------|
| Single byte `0x01` (key `AQ==`) | Expand to default Meshtastic key (`1PG7OiApB1nwvP+rz05pAQ==`) |
| < 16 bytes | Zero-pad to 16 bytes (AES-128) |
| 16 bytes | Use as-is (AES-128) |
| 17-31 bytes | Zero-pad to 32 bytes (AES-256) |
| 32 bytes | Use as-is (AES-256) |
| > 32 bytes | Truncate to 32 bytes (AES-256) |

**Nonce construction**: 16 bytes = `packet_id` as 8 bytes little-endian + `from_node_id` as 8 bytes little-endian.

## Dual-Mode Operation

Run MQTT and device-based connections (TCP/Bluetooth/Serial) simultaneously.

```
  +---------------------------------------------+
  |              Home Assistant                   |
  |                                               |
  |  Config Entry 1: MQTT                         |
  |    +-> MqttConnection -> mqtt.meshtastic.org  |
  |         Discovers: Node A, Node B, Node C     |
  |                                               |
  |  Config Entry 2: TCP                          |
  |    +-> TcpConnection -> 192.168.1.50          |
  |         Discovers: Node A (gateway), Node B   |
  |                                               |
  |  Device Registry:                             |
  |    Node A --> Single device (merged)          |
  |    Node B --> Single device (merged)          |
  |    Node C --> MQTT-only device                |
  +---------------------------------------------+
```

**Node merging**: If the same Meshtastic node is seen by both an MQTT connection and a device connection, it appears as a single Home Assistant device using the shared identifier `(meshtastic, {node_num})`.

**Usage**: Add multiple integration entries -- one for MQTT, one for your local device. This gives you broad mesh monitoring via MQTT plus direct device control (telemetry requests, traceroutes) via the local connection.

## Send Messages via MQTT

Send text messages through the MQTT broker without a physical device.

**Available services**:

```yaml
# Channel broadcast
service: meshtastic.send_text
data:
  text: "Hello mesh!"

# Direct message
service: meshtastic.send_direct_message
data:
  to: "!abcd1234"
  text: "Hello node!"

# Channel-specific broadcast
service: meshtastic.broadcast_channel_message
data:
  channel: "LongFast"
  text: "Channel message"
```

**MQTT-only limitations**: Request-response services are not available in MQTT-only mode because there's no direct device to send the request through:

| Service | MQTT Mode | Device Mode |
|---------|-----------|-------------|
| `send_text` | Yes | Yes |
| `send_direct_message` | Yes | Yes |
| `broadcast_channel_message` | Yes | Yes |
| `request_telemetry` | No | Yes |
| `request_position` | No | Yes |
| `request_traceroute` | No | Yes |

## Entity Support

Each discovered node gets these entities:

| Entity Type | Entities |
|-------------|----------|
| Sensors | Battery level, voltage, channel utilization, airtime TX, SNR, hops |
| Environment | Temperature, humidity, barometric pressure |
| Device Tracker | GPS position (latitude, longitude, altitude) |
| Binary Sensor | Online/offline status |
| Notify | Send text messages to the node |

The device model is set from the `hwModel` field in `NODEINFO_APP` packets when available (e.g., "TBEAM", "HELTEC_V3", "RAK4631").

## Config Flow and Options Flow

Full UI-driven setup and reconfiguration:

- **Setup**: Select connection type, enter connection details, add channel keys (MQTT), test connection, create entry
- **Options**: Edit broker settings, add/remove channel keys, change topic pattern
- **Validation**: Connection testing (10s timeout), base64 key validation, port range checks (1-65535), non-empty host validation
- **Reconfigure**: Update any connection settings without removing and re-adding the integration

## OpenAPI Documentation

Interactive API documentation is available at [`docs/api/index.html`](api/index.html) using Swagger UI. The raw OpenAPI 3.0 specification is at [`docs/api/openapi.yaml`](api/openapi.yaml).

The spec documents:
- All service endpoints (send_text, send_direct_message, broadcast_channel_message, request_telemetry, request_position, request_traceroute)
- Request/response schemas with data types, required fields, and examples
- MQTT message schemas (ServiceEnvelope, MeshPacket, Data)
- Home Assistant event payloads (meshtastic_event, meshtastic_message_log)
- MQTT connection configuration schema
- Authentication requirements (HA long-lived access tokens)
- Error response schemas

The spec is available in YAML format and can be converted to JSON using standard tools (`yq`, `swagger-cli`, or any YAML-to-JSON converter).

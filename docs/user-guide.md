# User Guide

## Installation

### HACS (Recommended)

1. Install [HACS](https://hacs.xyz/) if you haven't already.
2. Go to HACS → Integrations → ⋮ → Custom repositories.
3. Add this repository URL, select "Integration".
4. Install "Meshtastic" from HACS.
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/meshtastic/` to your HA `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

### Adding the Integration

Go to **Settings → Devices & Services → Add Integration → Meshtastic**.

You'll be prompted to choose a connection type:

| Type | Description |
|------|-------------|
| TCP | Connect to a Meshtastic node via IP/hostname |
| Bluetooth | Connect via Bluetooth LE |
| Serial | Connect via USB serial |
| MQTT | Subscribe to a Meshtastic MQTT broker |

### TCP Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| Host | IP address or hostname of the Meshtastic node | — |
| Port | TCP port | `4403` |

### Bluetooth Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| Device | Select a discovered Bluetooth LE Meshtastic device | — |

### Serial Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| Device | Serial port path (e.g., `/dev/ttyUSB0`) | — |

### MQTT Configuration

When selecting MQTT, provide:

| Setting | Description | Default |
|---------|-------------|---------|
| Broker Host | Hostname or IP of the MQTT broker (e.g., `mqtt.meshtastic.org`) | — |
| Broker Port | MQTT broker port | `1883` |
| Username | MQTT username (optional) | — |
| Password | MQTT password (optional) | — |
| TLS | Enable TLS/SSL for encrypted broker connections | Off |
| Topic Pattern | MQTT topic to subscribe to (supports `+` and `#` wildcards) | `msh/US/2/e/#` |
| Region | Meshtastic region code used for topic construction | `US` |
| Channel Keys | Map of channel names to base64-encoded AES encryption keys | — |

The default key `AQ==` decodes to the standard Meshtastic `LongFast` channel key.

#### MQTT Broker Setup

To use the MQTT connection, you need access to an MQTT broker that receives Meshtastic traffic. Options include:

1. **Public Meshtastic broker**: Connect to `mqtt.meshtastic.org` with username `meshdev` and password `large4cats`. This receives traffic from all Meshtastic nodes that have MQTT uplink enabled.
2. **Self-hosted broker**: Run your own MQTT broker (e.g., Mosquitto) and configure one or more Meshtastic nodes as MQTT gateways that forward mesh traffic to your broker.
3. **Home Assistant Mosquitto add-on**: If you already run the Mosquitto add-on in HA, configure a Meshtastic node to publish to it.

#### Channel Key Configuration

Each Meshtastic channel uses an AES encryption key. You must provide the correct base64-encoded key for each channel you want to decode.

| Channel | Typical Key | Notes |
|---------|-------------|-------|
| LongFast | `AQ==` | Default Meshtastic key (single byte `0x01` → expanded to default key) |
| Custom channels | Your key | The base64-encoded key configured on your Meshtastic devices |

To find your channel key:
1. Open the Meshtastic app on your phone.
2. Go to the channel settings.
3. Copy the encryption key (it's already base64-encoded).

#### Topic Pattern

The topic pattern determines which MQTT messages the integration subscribes to. The Meshtastic MQTT topic convention is:

```
msh/{region}/2/e/{channel}/{gateway_id}
```

Common patterns:

| Pattern | Description |
|---------|-------------|
| `msh/US/2/e/#` | All encrypted traffic in the US region |
| `msh/EU_868/2/e/#` | All encrypted traffic in the EU 868 MHz region |
| `msh/US/2/e/LongFast/#` | Only the LongFast channel in the US |
| `msh/+/2/e/#` | All regions, all channels |

### Editing Settings After Setup

Go to **Settings → Devices & Services → Meshtastic → Configure** to update settings. For MQTT connections, you can:

- Change broker host, port, username, password, and TLS settings
- Update the topic pattern
- Add or remove channel name and encryption key pairs
- Change the region

Changes take effect after the config entry is reloaded.

## Usage

### Viewing Nodes

Each Meshtastic node discovered via MQTT (or connected directly) appears as a device in Home Assistant with sensors for:

- Battery level and voltage
- Channel utilization and airtime TX
- Temperature, humidity, barometric pressure (if reported by the node)
- GPS position (device tracker entity)
- Online/offline status

Navigate to **Settings → Devices & Services → Meshtastic** to see all discovered devices and their entities.

### Sending Messages

Use the built-in services to send messages through the mesh:

```yaml
# Send a text message to a channel
service: meshtastic.send_text
data:
  text: "Hello from Home Assistant!"

# Send a direct message to a specific node
service: meshtastic.send_direct_message
data:
  to: "!abcd1234"
  text: "Direct message"

# Broadcast to a specific channel
service: meshtastic.broadcast_channel_message
data:
  channel: "LongFast"
  text: "Channel broadcast"
```

### Requesting Data (Device Mode Only)

These services require a direct device connection (TCP, Bluetooth, or Serial) and are not available in MQTT-only mode:

```yaml
# Request telemetry from a node
service: meshtastic.request_telemetry
data:
  to: "!abcd1234"
  type: "device_metrics"

# Request position from a node
service: meshtastic.request_position
data:
  to: "!abcd1234"

# Request traceroute to a node
service: meshtastic.request_traceroute
data:
  to: "!abcd1234"
```

### Dual-Mode Operation

You can run both device-based and MQTT connections simultaneously. If the same node is seen by both, it's merged into a single HA device using the shared identifier `(meshtastic, {node_num})`.

To set up dual-mode:
1. Add an MQTT integration entry (Settings → Devices & Services → Add Integration → Meshtastic → MQTT).
2. Add a device-based integration entry (Settings → Devices & Services → Add Integration → Meshtastic → TCP/Bluetooth/Serial).
3. Nodes seen by both connections appear as a single device with combined data.

This gives you broad mesh monitoring via MQTT plus direct device control (telemetry requests, traceroutes) via the local connection.

## Common Workflows

### Monitor a Remote Mesh Network

1. Set up an MQTT broker (or use the public `mqtt.meshtastic.org`).
2. Add the Meshtastic integration with MQTT connection type.
3. Enter broker details and channel keys.
4. Nodes will appear automatically as they transmit on the mesh.

### Alert When a Node Goes Offline

```yaml
automation:
  - alias: "Meshtastic node offline alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.meshtastic_node_abcd1234_online
        to: "off"
        for: "00:10:00"
    action:
      - service: notify.mobile_app
        data:
          message: "Meshtastic node abcd1234 went offline"
```

### Track Node Positions on a Map

1. Ensure nodes are reporting GPS position (`POSITION_APP` packets).
2. Each node with position data gets a `device_tracker` entity.
3. Add a Map card to your dashboard and select the Meshtastic device tracker entities.

### Forward Mesh Messages to Another Service

```yaml
automation:
  - alias: "Forward Meshtastic messages to Telegram"
    trigger:
      - platform: event
        event_type: meshtastic_event
        event_data:
          event_type: text_message
    action:
      - service: telegram_bot.send_message
        data:
          message: >
            Mesh message from {{ trigger.event.data.from }}:
            {{ trigger.event.data.message }}
```

### Monitor Environment Sensors

Nodes with environment sensors (BME280, BME680, etc.) report temperature, humidity, and barometric pressure. These appear as sensor entities that you can add to dashboards, use in automations, or log to a database.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No nodes appearing | Check broker connectivity, topic pattern, and channel keys. Enable debug logging to see incoming messages. |
| Decryption errors in logs | Verify the channel key matches the channel name exactly. The key must be the correct base64-encoded AES key. |
| Connection drops | Check broker stability. The integration reconnects automatically with exponential backoff (1s to 60s). |
| "Not supported in MQTT mode" | Request services (telemetry, position, traceroute) require a direct device connection. Add a TCP/BLE/Serial entry. |
| Invalid base64 key error | Ensure the channel key is valid base64. Copy it directly from the Meshtastic app. |
| Port validation error | Broker port must be between 1 and 65535. Default is 1883 (or 8883 for TLS). |
| Empty broker host error | The broker host field cannot be empty. Provide a hostname or IP address. |
| TLS connection failures | Ensure the broker supports TLS on the configured port (typically 8883). Check certificate validity. |

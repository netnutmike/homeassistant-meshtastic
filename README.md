# Meshtastic Home Assistant Integration (with MQTT Support)

A Home Assistant custom integration for [Meshtastic](https://meshtastic.org/) mesh networking devices. This integration extends the [upstream Meshtastic HA integration](https://github.com/meshtastic/home-assistant) with **MQTT as a first-class connection method** — allowing you to monitor your entire Meshtastic mesh network without a physical device connected to your Home Assistant host.

## Features

- **MQTT Connection** — Subscribe to a Meshtastic MQTT broker and automatically discover all nodes on the mesh. No physical device required.
- **Device Connections** — Connect directly to Meshtastic nodes via TCP, Bluetooth, or Serial (inherited from upstream).
- **Dual-Mode Operation** — Run MQTT and device-based connections simultaneously. Nodes seen by both are merged into a single HA device.
- **Automatic Node Discovery** — Nodes are automatically created as HA devices with sensors for battery, voltage, signal strength, position, telemetry, and environment data.
- **Encrypted Traffic Decoding** — AES-CTR decryption of encrypted Meshtastic channels using configurable channel keys.
- **Send Messages via MQTT** — Send text messages, direct messages, and channel broadcasts through the MQTT broker.
- **Full Entity Support** — Sensors, binary sensors, device trackers, and notify platform for each discovered node.

## Quick Start

### Option 1: HACS (Recommended)

1. Install [HACS](https://hacs.xyz/) if you haven't already.
2. In HACS, go to Integrations → three-dot menu → Custom repositories.
3. Add this repository URL and select "Integration" as the category.
4. Install the "Meshtastic" integration from HACS.
5. Restart Home Assistant.
6. Go to Settings → Devices & Services → Add Integration → Meshtastic.

### Option 2: Manual Installation

1. Copy the `custom_components/meshtastic/` directory into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to Settings → Devices & Services → Add Integration → Meshtastic.

## MQTT Setup

When adding the integration, select **MQTT** as the connection type and provide:

| Setting | Description | Default |
|---------|-------------|---------|
| Broker Host | MQTT broker hostname or IP | — |
| Broker Port | MQTT broker port | `1883` |
| Username | MQTT username (optional) | — |
| Password | MQTT password (optional) | — |
| TLS | Enable TLS/SSL encryption | Off |
| Topic Pattern | MQTT topic to subscribe to | `msh/US/2/e/#` |
| Channel Keys | Channel name → base64 encryption key pairs | `LongFast: AQ==` |

The default channel key `AQ==` is the standard Meshtastic encryption key for the `LongFast` channel.

## Entities Created Per Node

Each discovered Meshtastic node gets a Home Assistant device with these entities:

- **Sensors**: Battery level, voltage, channel utilization, airtime, uptime, SNR, hops away, role, short/long name
- **Environment Sensors**: Temperature, humidity, barometric pressure (when reported)
- **Device Tracker**: GPS position (latitude, longitude, altitude)
- **Binary Sensor**: Online/offline status
- **Notify**: Send text messages to the node

## Services

| Service | MQTT Mode | Device Mode |
|---------|-----------|-------------|
| `meshtastic.send_text` | ✅ | ✅ |
| `meshtastic.send_direct_message` | ✅ | ✅ |
| `meshtastic.broadcast_channel_message` | ✅ | ✅ |
| `meshtastic.request_telemetry` | ❌ | ✅ |
| `meshtastic.request_position` | ❌ | ✅ |
| `meshtastic.request_traceroute` | ❌ | ✅ |

Request-response services require a direct device connection and are not available in MQTT-only mode.

## Development

### Prerequisites

- Python 3.12+

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/homeassistant-meshtastic.git
cd homeassistant-meshtastic

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Or use the Makefile
make setup
```

### Common Commands

```bash
make test          # Run test suite
make lint          # Run linter (ruff)
make lint-fix      # Auto-fix lint issues
make type-check    # Run type checker (mypy)
make verify-setup  # Verify all prerequisites are installed
```

### Running Tests

```bash
# All tests
make test

# With coverage
pytest --cov=custom_components/meshtastic tests/

# Watch mode
make test-watch
```

## Project Structure

```
homeassistant-meshtastic/
├── custom_components/meshtastic/      # The HA integration
│   └── aiomeshtastic/                 # Async Meshtastic library
│       ├── connection/                # Connection implementations
│       │   ├── mqtt.py                # MQTT connection
│       │   ├── decoder.py             # MQTT message decoder
│       │   ├── errors.py              # Connection error classes
│       │   ├── listener.py            # Packet stream listener
│       │   └── streaming.py           # Base streaming transport
│       ├── protobuf/                  # Meshtastic protobuf definitions
│       ├── interface.py               # Mesh network interface
│       ├── packet.py                  # Packet utilities
│       ├── errors.py                  # Base error classes
│       └── const.py                   # Library constants
├── tests/                             # Test suite
├── docs/                              # Documentation
│   ├── api/                           # OpenAPI spec + Swagger UI
│   ├── user-guide.md
│   ├── developer-guide.md
│   └── features.md
├── .github/                           # CI workflows, issue/PR templates
├── .vscode/launch.json                # VS Code debug configurations
├── Makefile                           # Dev automation
├── requirements-dev.txt               # Dev dependencies
├── renovate.json                      # Automated dependency updates
├── CONTRIBUTING.md                    # Contribution guidelines
├── CHANGELOG.md                       # Version history
├── LICENSE                            # MIT License
└── README.md                          # This file
```

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- [User Guide](docs/user-guide.md) — Configuration, usage, and common workflows
- [Developer Guide](docs/developer-guide.md) — Architecture, contributing, testing, debugging
- [Features](docs/features.md) — Detailed feature descriptions and examples
- [API Documentation](docs/api/index.html) — Interactive Swagger UI for service endpoints

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute, including branching strategy, code style, and the pull request process.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Meshtastic](https://meshtastic.org/) — The open-source mesh networking project
- [Meshtastic HA Integration](https://github.com/meshtastic/home-assistant) — The upstream integration by [@broglep](https://github.com/broglep)

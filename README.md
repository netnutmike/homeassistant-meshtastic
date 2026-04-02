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
- **Docker Distribution** — Pre-built Docker images on Docker Hub for easy deployment.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/homeassistant-meshtastic.git
cd homeassistant-meshtastic

# Start with Docker Compose
docker compose up -d
```

Access Home Assistant at `http://localhost:8123`, then add the Meshtastic integration from Settings → Devices & Services.

### Option 2: Manual Installation

1. Copy the `custom_components/meshtastic/` directory into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to Settings → Devices & Services → Add Integration → Meshtastic.

### Option 3: Docker Hub

```bash
docker pull your-username/homeassistant-meshtastic:latest
docker run -d \
  --name homeassistant \
  -p 8123:8123 \
  -v ./config:/config \
  your-username/homeassistant-meshtastic:latest
```

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
- Docker and Docker Compose (for containerized development)

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
make dev           # Start dev environment with Docker Compose
make docker-build  # Build Docker image locally
make verify-setup  # Verify all prerequisites are installed
```

### Docker Development

```bash
# Start development environment (hot-reload enabled)
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

The development docker-compose mounts `custom_components/` as a volume, so code changes are reflected without rebuilding.

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
├── custom_components/meshtastic/     # The HA integration
│   ├── aiomeshtastic/                # Async Meshtastic library
│   │   ├── connection/               # Connection implementations
│   │   │   ├── mqtt.py               # MQTT connection (new)
│   │   │   ├── decoder.py            # MQTT message decoder (new)
│   │   │   ├── tcp.py                # TCP connection
│   │   │   ├── bluetooth.py          # Bluetooth connection
│   │   │   ├── serial.py             # Serial connection
│   │   │   └── streaming.py          # Base streaming transport
│   │   ├── protobuf/                 # Meshtastic protobuf definitions
│   │   └── interface.py              # Mesh network interface
│   ├── api.py                        # HA API client
│   ├── config_flow.py                # Setup wizard
│   ├── coordinator.py                # Data update coordinator
│   ├── sensor.py                     # Sensor entities
│   ├── const.py                      # Constants
│   └── ...
├── config/                           # HA config directory (runtime)
├── tests/                            # Test suite
├── docs/                             # Documentation
│   ├── api/                          # OpenAPI spec + Swagger UI
│   ├── user-guide.md
│   ├── developer-guide.md
│   └── features.md
├── Dockerfile                        # Multi-stage Docker build
├── docker-compose.yaml               # Development deployment
├── docker-compose.prod.yaml          # Production deployment
├── Makefile                          # Dev automation
├── requirements-dev.txt              # Dev dependencies
├── CONTRIBUTING.md                   # Contribution guidelines
├── CHANGELOG.md                      # Version history
├── LICENSE                           # MIT License
└── README.md                         # This file
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
- [Meshtastic MQTT Monitor](https://github.com/your-username/meshtastic-mqtt-monitor) — MQTT decoding reference implementation

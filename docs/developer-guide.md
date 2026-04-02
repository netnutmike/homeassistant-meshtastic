# Developer Guide

## Architecture Overview

The integration follows Home Assistant's custom component pattern with four connection types sharing a common interface:

```
custom_components/meshtastic/
├── aiomeshtastic/              # Async Meshtastic library
│   ├── connection/
│   │   ├── mqtt.py             # MQTT connection (subscribes to broker)
│   │   ├── decoder.py          # Protobuf decoding + AES-CTR decryption
│   │   ├── tcp.py              # TCP connection
│   │   ├── bluetooth.py        # Bluetooth LE connection
│   │   ├── serial.py           # Serial/USB connection
│   │   ├── streaming.py        # Base streaming transport
│   │   └── listener.py         # Connection listener base
│   ├── protobuf/               # Meshtastic protobuf definitions
│   ├── interface.py            # MeshInterface (packet processing)
│   ├── packet.py               # Packet utilities
│   └── const.py                # Library constants
├── api.py                      # MeshtasticApiClient (routes connection types)
├── config_flow.py              # Setup wizard + options flow
├── coordinator.py              # Data update coordinator
├── sensor.py                   # Sensor entities
├── binary_sensor.py            # Binary sensor entities
├── device_tracker.py           # Device tracker entities
├── notify.py                   # Notify platform
└── const.py                    # Constants and enums
```

### Data Flow

```
                    ┌─────────────────────────────────────────────────┐
                    │                Home Assistant                    │
                    │                                                  │
  MQTT Broker ──►  aiomqtt.Client ──► MqttConnection._packet_stream() │
                    │   │                                              │
                    │   ▼                                              │
                    │  MqttPacketDecoder.decode_to_mesh_packet()       │
                    │   │  ServiceEnvelope parsing                     │
                    │   │  MeshPacket extraction                       │
                    │   │  AES-CTR decryption (if encrypted)           │
                    │   ▼                                              │
                    │  FromRadio wrapper                               │
                    │   │                                              │
                    │   ▼                                              │
                    │  MeshInterface (packet processing pipeline)      │
                    │   │  Node database updates                       │
                    │   │  App-specific listeners                      │
                    │   ▼                                              │
                    │  HA bus events ──► Coordinator ──► Entities      │
                    └─────────────────────────────────────────────────┘
```

### Key Classes

- **`MqttConnection`** (`connection/mqtt.py`): Extends `ClientApiConnection`. Manages MQTT subscription, delegates decoding to `MqttPacketDecoder`, yields `FromRadio` messages. Handles reconnection with exponential backoff.
- **`MqttPacketDecoder`** (`connection/decoder.py`): Stateless decoder. Parses `ServiceEnvelope`/`MeshPacket` protobufs, handles AES-CTR decryption with channel key lookup, extracts channel names from MQTT topics.
- **`MeshtasticApiClient`** (`api.py`): Routes `connection_type` from the config entry to the appropriate connection class (TCP, Bluetooth, Serial, or MQTT).
- **`MeshInterface`** (`interface.py`): Processes decoded packets, maintains the node database, fires HA bus events.
- **`MeshtasticDataUpdateCoordinator`** (`coordinator.py`): Listens to API events and propagates updates to HA entities.

### Connection Type Routing

The `MeshtasticApiClient.__init__` method selects the connection class based on `connection_type`:

| `connection_type` | Connection Class | Base Class |
|-------------------|-----------------|------------|
| `tcp` | `TcpConnection` | `StreamingClientTransport` → `ClientApiConnection` |
| `bluetooth` | `BluetoothConnection` | `StreamingClientTransport` → `ClientApiConnection` |
| `serial` | `SerialConnection` | `StreamingClientTransport` → `ClientApiConnection` |
| `mqtt` | `MqttConnection` | `ClientApiConnection` (direct) |

MQTT bypasses `StreamingClientTransport` because MQTT delivers complete protobuf messages per topic — no byte-stream framing is needed.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution guide, including:

- Branching strategy (`main`/`dev` with feature branches)
- Code style (ruff)
- Pull request process
- Commit message conventions

## Development Setup

### Prerequisites

- Python 3.12+
- pip
- Git

### Quick Start

```bash
git clone https://github.com/your-username/homeassistant-meshtastic.git
cd homeassistant-meshtastic
make setup          # Creates venv and installs deps
make verify-setup   # Checks everything is ready
```

Or manually:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Environment Variables

```bash
cp .env.example .env
```

See `.env.example` for all available variables with descriptions.

### Verify Your Setup

```bash
make verify-setup
```

This checks that Python, the virtual environment, and all required tools (ruff, mypy, pytest) are correctly installed.

## Testing

### Running Tests

```bash
make test                    # All tests with coverage
pytest tests/ -v             # Verbose output
pytest tests/ -k "decoder"   # Filter by name
pytest tests/ --cov          # With coverage report
```

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Create virtual environment and install dependencies |
| `make install` | Install/update dependencies |
| `make test` | Run all tests with coverage |
| `make test-watch` | Run tests in watch mode |
| `make lint` | Check code style with ruff |
| `make lint-fix` | Auto-fix linting issues |
| `make type-check` | Run mypy type checking |
| `make verify-setup` | Verify all prerequisites are installed |

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures, Hypothesis profiles
├── test_mqtt_connection.py      # MqttConnection lifecycle tests
├── test_mqtt_decoder.py         # Decoder unit + property tests
├── test_mqtt_encryption.py      # AES-CTR property tests
├── test_mqtt_topic_parsing.py   # Topic parsing property tests
├── test_mqtt_config_flow.py     # Config flow tests
└── test_mqtt_api_client.py      # API client routing, node discovery, dual-mode tests
```

### Property-Based Tests

We use [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing. Each property test validates a correctness property from the [design document](../.kiro/specs/meshtastic-mqtt-integration/design.md).

Hypothesis profiles control the number of examples generated:

| Profile | Examples per Test | Usage |
|---------|-------------------|-------|
| `dev` (default) | 100 | Local development |
| `ci` | 200 | CI pipeline |

```bash
# Run with CI profile (200 examples per test)
HYPOTHESIS_PROFILE=ci pytest tests/

# Run with dev profile (100 examples, default)
pytest tests/
```

### Writing Tests

When adding new functionality:

1. Write unit tests for specific examples and edge cases.
2. Write property-based tests for universal correctness properties.
3. Ensure coverage stays above 80%.

Example property test:

```python
from hypothesis import given, strategies as st

@given(packet_id=st.integers(min_value=0, max_value=2**32 - 1),
       node_id=st.integers(min_value=0, max_value=2**32 - 1))
def test_nonce_is_16_bytes(packet_id: int, node_id: int) -> None:
    """Property 5: Nonce construction produces 16 bytes."""
    decoder = MqttPacketDecoder({})
    nonce = decoder.build_nonce(packet_id, node_id)
    assert len(nonce) == 16
```

## Debugging

### VS Code

Launch configurations are provided in `.vscode/launch.json`. Available configurations:

| Configuration | Description |
|---------------|-------------|
| Home Assistant (with Meshtastic) | Launch Home Assistant with the integration loaded, debugger attached |
| Debug Tests | Run the full pytest suite with the debugger attached |
| Debug Current Test File | Run the currently open test file with the debugger |
| Attach to Running Process | Attach to an already-running process via debugpy on port 5678 |

#### Using the Debugger

1. Open the project in VS Code.
2. Set breakpoints by clicking in the gutter next to line numbers in any Python file.
3. Open the Run and Debug panel (Ctrl+Shift+D / Cmd+Shift+D).
4. Select a launch configuration from the dropdown:
   - **Home Assistant (with Meshtastic)**: Launches HA with the integration loaded. Breakpoints work across the integration code as it handles real events.
   - **Debug Tests**: Runs the full test suite with breakpoints active. Execution will pause at any breakpoint hit during test runs.
   - **Debug Current Test File**: Runs the currently focused test file with the debugger. Useful for iterating on a single test.
   - **Attach to Running Process**: Connects to an already-running Python process that has `debugpy` listening on port 5678. Add `import debugpy; debugpy.listen(5678); debugpy.wait_for_client()` to the target process to enable this.
5. Press F5 (or the green play button) to start debugging.
6. When execution hits a breakpoint, use the debug toolbar to:
   - **Continue** (F5): Resume execution until the next breakpoint.
   - **Step Over** (F10): Execute the current line and move to the next.
   - **Step Into** (F11): Step into a function call.
   - **Step Out** (Shift+F11): Step out of the current function.
7. Inspect variables in the Variables panel, add watch expressions, and use the Debug Console to evaluate expressions at the current breakpoint.

#### Debugging Tips

- Set breakpoints in `decoder.py` to inspect protobuf parsing and decryption steps.
- Set breakpoints in `mqtt.py` `_packet_stream()` to see raw MQTT messages as they arrive.
- Use conditional breakpoints (right-click a breakpoint → Edit Condition) to break only on specific packet types or node IDs.
- The Debug Console supports evaluating arbitrary Python expressions in the current scope.

### Logging

Enable debug logging for the integration in HA's `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.meshtastic: debug
    custom_components.meshtastic.aiomeshtastic.connection.mqtt: debug
    custom_components.meshtastic.aiomeshtastic.connection.decoder: debug
```

This will show:

- Incoming MQTT messages and their topics
- Protobuf parsing results (ServiceEnvelope, MeshPacket)
- Decryption attempts and results
- Node database updates
- Skipped packets (wrong key, parse failures)

### Common Debug Scenarios

| Issue | Debug Steps |
|-------|-------------|
| Protobuf decode errors | Enable debug logging on `decoder`, inspect the raw payload hex in logs |
| MQTT connection failures | Check broker host/port, credentials, TLS settings. Look for `aiomqtt` error messages in logs |
| Missing entities | Verify channel keys match the channels in use. Check node database entries in debug logs |
| Test failures | Run `make verify-setup` to check environment. Ensure Python 3.12+. Run individual tests with `-v` for details |
| Decryption producing garbage | Verify the channel key is correct for the channel. Check that the nonce construction matches (packet_id + from_node_id) |

### API Documentation

Interactive API documentation is available at [`docs/api/index.html`](api/index.html) using Swagger UI. The raw OpenAPI 3.0 specification is at [`docs/api/openapi.yaml`](api/openapi.yaml).

The spec documents all service endpoints, MQTT message schemas (ServiceEnvelope, MeshPacket, Data), Home Assistant event payloads, and the MQTT connection configuration schema.

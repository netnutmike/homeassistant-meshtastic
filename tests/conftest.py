"""Shared test configuration and fixtures for Meshtastic MQTT integration tests."""

import sys
import types
from pathlib import Path

import pytest
from hypothesis import settings as hypothesis_settings

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------
hypothesis_settings.register_profile("ci", max_examples=200)
hypothesis_settings.register_profile("dev", max_examples=100)
hypothesis_settings.load_profile("dev")

# ---------------------------------------------------------------------------
# sys.path / module bootstrapping
# ---------------------------------------------------------------------------
# The aiomeshtastic package lives inside the Home Assistant custom component
# tree.  Its top-level ``__init__.py`` eagerly imports connection classes that
# pull in heavy HA-specific dependencies (``homeassistant``, ``aiomqtt``, …).
# To let the *protobuf* and *decoder* modules be imported in a lightweight
# test environment we pre-register stub namespace packages so Python never
# executes those ``__init__.py`` files.

_MESHTASTIC_PKG = (
    Path(__file__).resolve().parent.parent
    / "home-assistant"
    / "custom_components"
    / "meshtastic"
)

sys.path.insert(0, str(_MESHTASTIC_PKG))

# Stub out the aiomeshtastic and aiomeshtastic.connection packages so their
# __init__.py files (which import TcpConnection → google, etc.) are skipped.
for _mod_name, _rel_path in [
    ("aiomeshtastic", "aiomeshtastic"),
    ("aiomeshtastic.connection", "aiomeshtastic/connection"),
]:
    _pkg = types.ModuleType(_mod_name)
    _pkg.__path__ = [str(_MESHTASTIC_PKG / _rel_path)]
    _pkg.__package__ = _mod_name
    sys.modules.setdefault(_mod_name, _pkg)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_channel_keys():
    """Sample channel keys for testing."""
    return {
        "LongFast": "AQ==",
        "ShortSlow": "1PG7OiApB1nwvP+rz05pAQ==",
    }


@pytest.fixture
def mqtt_config_entry_data():
    """Sample MQTT config entry data."""
    return {
        "connection_type": "mqtt",
        "mqtt_host": "mqtt.meshtastic.org",
        "mqtt_port": 1883,
        "mqtt_username": "meshdev",
        "mqtt_password": "large4cats",
        "mqtt_tls": False,
        "mqtt_topic": "msh/US/2/e/#",
        "mqtt_region": "US",
        "mqtt_channel_keys": {
            "LongFast": "AQ==",
        },
    }


@pytest.fixture
def sample_service_envelope_bytes():
    """Build a sample serialized ServiceEnvelope for testing."""
    from aiomeshtastic.protobuf import mesh_pb2, mqtt_pb2

    pkt = mesh_pb2.MeshPacket()
    pkt.__setattr__("from", 42)
    pkt.to = 0xFFFFFFFF
    pkt.id = 100
    pkt.decoded.payload = b"hello mesh"

    env = mqtt_pb2.ServiceEnvelope()
    env.packet.CopyFrom(pkt)
    env.channel_id = "LongFast"
    env.gateway_id = "!aabbccdd"
    return env.SerializeToString()

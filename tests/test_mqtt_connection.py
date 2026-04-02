"""Unit tests for MqttConnection lifecycle (connect, subscribe, receive, disconnect).

Validates Requirements 2.1, 2.7, 2.8:
- Connect/disconnect lifecycle with mocked aiomqtt client
- Packet stream yields FromRadio from decoded MQTT messages
- Reconnection behavior (connection interrupted raises ClientApiConnectionInterruptedError)
"""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub the ``aiomqtt`` module before importing MqttConnection.
# The real library is not installed in the test environment.
# ---------------------------------------------------------------------------

if "aiomqtt" not in sys.modules:
    _aiomqtt_stub = types.ModuleType("aiomqtt")

    class _FakeClient:
        """Minimal stand-in for ``aiomqtt.Client``."""

        def __init__(self, **kwargs):
            self._kwargs = kwargs
            self.subscribe = AsyncMock()
            self.unsubscribe = AsyncMock()
            self.publish = AsyncMock()
            self._messages_iter = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def messages(self):
            return self._messages_iter

    class _FakeMqttError(Exception):
        """Stand-in for ``aiomqtt.MqttError``."""

    _aiomqtt_stub.Client = _FakeClient
    _aiomqtt_stub.MqttError = _FakeMqttError
    sys.modules["aiomqtt"] = _aiomqtt_stub
else:
    _aiomqtt_stub = sys.modules["aiomqtt"]

# Always resolve from the registered module so class identity is consistent
# across test files regardless of import order.
_FakeClient = _aiomqtt_stub.Client
_FakeMqttError = _aiomqtt_stub.MqttError

# ---------------------------------------------------------------------------
# Ensure the ``aiomeshtastic.connection`` stub exposes the base class and
# error types that ``mqtt.py`` imports via ``from . import …``.
# ---------------------------------------------------------------------------

# errors.py uses ``from custom_components.meshtastic.aiomeshtastic.errors import …``
# Stub the custom_components namespace so that import chain resolves.
for _ns in [
    "custom_components",
    "custom_components.meshtastic",
    "custom_components.meshtastic.aiomeshtastic",
]:
    if _ns not in sys.modules:
        _m = types.ModuleType(_ns)
        _m.__path__ = []
        _m.__package__ = _ns
        sys.modules[_ns] = _m

# Point custom_components.meshtastic.aiomeshtastic.errors at the real module
from aiomeshtastic import errors as _real_errors  # noqa: E402
sys.modules["custom_components.meshtastic.aiomeshtastic.errors"] = _real_errors

from aiomeshtastic.protobuf import mesh_pb2, mqtt_pb2  # noqa: E402

# Import the errors module directly so it's available in the stub package
import aiomeshtastic.connection.errors  # noqa: E402

# The base class lives in __init__.py which has heavy HA deps.  We need to
# make it importable.  The conftest already stubs the package; we just need
# to populate the ``ClientApiConnection`` name.  Import it from the real file
# by loading the module source directly.
import importlib.util as _ilu
from pathlib import Path as _Path

_conn_init = (
    _Path(__file__).resolve().parent.parent
    / "home-assistant"
    / "custom_components"
    / "meshtastic"
    / "aiomeshtastic"
    / "connection"
    / "__init__.py"
)

# We can't exec the real __init__.py (it imports homeassistant, google, etc.).
# Instead, create a minimal stub of ClientApiConnection with the interface
# that MqttConnection actually uses.
_conn_pkg = sys.modules["aiomeshtastic.connection"]

# Only add the stub if the real class isn't already there
if not hasattr(_conn_pkg, "ClientApiConnection"):
    class _StubClientApiConnection:
        """Minimal stub of ClientApiConnection for test imports."""
        _CONFIG_ID_MINIMAL = 69420

        def __init__(self):
            self._packet_stream_listeners = []
            self._on_demand_streaming_task = None
            self._pending_config_requests = {}
            self._processing_packets_consumer_count = 0
            self._processing_packets_consumer_lock = asyncio.Lock()
            self._on_demand_streaming_processing_lock = asyncio.Lock()
            self._on_demand_streaming_processing_stop = asyncio.Event()
            self._current_packet_id = None
            self._queue_status = None
            self._queue_status_update = asyncio.Event()
            import logging
            self._logger = logging.getLogger(self.__class__.__name__)
            self._reconnect_lock = asyncio.Lock()
            self._reconnect_in_progress = asyncio.Event()
            self._reconnect_completed = asyncio.Event()
            self._reconnect_failed = asyncio.Event()
            self._reconnect_status_lock = asyncio.Lock()

        async def connect(self):
            try:
                await self._connect()
            except Exception as e:
                from aiomeshtastic.connection.errors import ClientApiConnectFailedError
                raise ClientApiConnectFailedError from e

        async def disconnect(self):
            for listener in self._packet_stream_listeners:
                listener.close()
            try:
                await self._disconnect()
            except Exception:
                pass

        async def _connect(self):
            raise NotImplementedError

        async def _disconnect(self):
            raise NotImplementedError

        @property
        def is_connected(self):
            raise NotImplementedError

        async def _notify_packet_stream_listeners(self, packet, *, sequential=False):
            pass

    _conn_pkg.ClientApiConnection = _StubClientApiConnection

# Now safe to import MqttConnection and related modules
from aiomeshtastic.connection.mqtt import MqttConnection  # noqa: E402
from aiomeshtastic.connection.errors import (  # noqa: E402
    ClientApiConnectionInterruptedError,
    ClientApiNotConnectedError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mqtt_message(topic: str, payload: bytes) -> MagicMock:
    """Create a mock MQTT message with the given topic and payload."""
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload
    return msg


async def _async_iter(items):
    """Turn a list into an async iterator."""
    for item in items:
        yield item


def _build_service_envelope(
    from_id: int = 1,
    to_id: int = 0xFFFFFFFF,
    packet_id: int = 100,
    channel: int = 0,
    payload: bytes = b"hello",
    channel_id: str = "LongFast",
    gateway_id: str = "!aabbccdd",
) -> bytes:
    """Build a serialized ServiceEnvelope containing a decoded MeshPacket."""
    pkt = mesh_pb2.MeshPacket()
    pkt.__setattr__("from", from_id)
    pkt.to = to_id
    pkt.id = packet_id
    pkt.channel = channel
    pkt.decoded.payload = payload

    env = mqtt_pb2.ServiceEnvelope()
    env.packet.CopyFrom(pkt)
    env.channel_id = channel_id
    env.gateway_id = gateway_id
    return env.SerializeToString()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMqttConnectionLifecycle:
    """Test connect / disconnect lifecycle with mocked aiomqtt client."""

    @pytest.mark.asyncio
    async def test_connect_sets_connected(self):
        """After connect(), is_connected should be True."""
        conn = MqttConnection(broker_host="localhost", broker_port=1883)
        assert not conn.is_connected

        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=_FakeClient()):
            await conn.connect()

        assert conn.is_connected

    @pytest.mark.asyncio
    async def test_connect_subscribes_to_topic_pattern(self):
        """connect() should subscribe to the configured topic pattern."""
        fake = _FakeClient()
        conn = MqttConnection(
            broker_host="localhost",
            topic_pattern="msh/US/2/e/#",
        )

        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        fake.subscribe.assert_awaited_once_with("msh/US/2/e/#")

    @pytest.mark.asyncio
    async def test_disconnect_unsubscribes_and_clears(self):
        """disconnect() should unsubscribe and set is_connected to False."""
        fake = _FakeClient()
        conn = MqttConnection(broker_host="localhost", topic_pattern="msh/US/2/e/#")

        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        assert conn.is_connected

        await conn.disconnect()

        fake.unsubscribe.assert_awaited_once_with("msh/US/2/e/#")
        assert not conn.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected_is_safe(self):
        """disconnect() on a never-connected instance should not raise."""
        conn = MqttConnection(broker_host="localhost")
        await conn.disconnect()  # should not raise
        assert not conn.is_connected

    @pytest.mark.asyncio
    async def test_connect_disconnect_connect_cycle(self):
        """A full connect → disconnect → connect cycle should work."""
        conn = MqttConnection(broker_host="localhost")

        fake1 = _FakeClient()
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake1):
            await conn.connect()
        assert conn.is_connected

        await conn.disconnect()
        assert not conn.is_connected

        fake2 = _FakeClient()
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake2):
            await conn.connect()
        assert conn.is_connected

        await conn.disconnect()


class TestMqttConnectionPacketStream:
    """Test that _packet_stream yields FromRadio from decoded MQTT messages."""

    @pytest.mark.asyncio
    async def test_packet_stream_yields_from_radio(self):
        """_packet_stream should yield FromRadio with the decoded MeshPacket."""
        envelope_bytes = _build_service_envelope(
            from_id=42, to_id=100, packet_id=999, payload=b"test-data",
            channel_id="LongFast",
        )
        mqtt_msg = _make_mqtt_message("msh/US/2/e/LongFast", envelope_bytes)

        fake = _FakeClient()
        fake._messages_iter = _async_iter([mqtt_msg])

        conn = MqttConnection(broker_host="localhost")
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        packets = []
        async for from_radio in conn._packet_stream():
            packets.append(from_radio)

        assert len(packets) == 1
        fr = packets[0]
        assert fr.HasField("packet")
        assert getattr(fr.packet, "from") == 42
        assert fr.packet.to == 100
        assert fr.packet.id == 999
        assert fr.packet.decoded.payload == b"test-data"
        assert fr.packet.via_mqtt is True

        await conn.disconnect()

    @pytest.mark.asyncio
    async def test_packet_stream_skips_empty_payload(self):
        """Messages with empty payload should be skipped."""
        msg_empty = _make_mqtt_message("msh/US/2/e/LongFast", b"")
        msg_valid = _make_mqtt_message(
            "msh/US/2/e/LongFast",
            _build_service_envelope(from_id=1, packet_id=1),
        )

        fake = _FakeClient()
        fake._messages_iter = _async_iter([msg_empty, msg_valid])

        conn = MqttConnection(broker_host="localhost")
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        packets = []
        async for from_radio in conn._packet_stream():
            packets.append(from_radio)

        # Only the valid message should produce a packet
        assert len(packets) == 1

        await conn.disconnect()

    @pytest.mark.asyncio
    async def test_packet_stream_skips_undecipherable_payload(self):
        """Messages with garbage payload should be skipped (not raise)."""
        msg_garbage = _make_mqtt_message("msh/US/2/e/LongFast", b"\xff\xfe\xfd")
        msg_valid = _make_mqtt_message(
            "msh/US/2/e/LongFast",
            _build_service_envelope(from_id=7, packet_id=7),
        )

        fake = _FakeClient()
        fake._messages_iter = _async_iter([msg_garbage, msg_valid])

        conn = MqttConnection(broker_host="localhost")
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        packets = []
        async for from_radio in conn._packet_stream():
            packets.append(from_radio)

        # Garbage is silently skipped; valid message still comes through
        assert len(packets) >= 1

        await conn.disconnect()

    @pytest.mark.asyncio
    async def test_packet_stream_not_connected_raises(self):
        """_packet_stream should raise ClientApiNotConnectedError when not connected."""
        conn = MqttConnection(broker_host="localhost")

        with pytest.raises(ClientApiNotConnectedError):
            async for _ in conn._packet_stream():
                pass


class TestMqttConnectionReconnection:
    """Test reconnection behavior — MqttError raises ClientApiConnectionInterruptedError."""

    @pytest.mark.asyncio
    async def test_mqtt_error_raises_connection_interrupted(self):
        """When aiomqtt raises MqttError during message iteration,
        _packet_stream should raise ClientApiConnectionInterruptedError
        and set is_connected to False."""

        async def _exploding_iter():
            raise _FakeMqttError("broker gone")
            yield  # make it a generator  # noqa: unreachable

        fake = _FakeClient()
        fake._messages_iter = _exploding_iter()

        conn = MqttConnection(broker_host="localhost")
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        assert conn.is_connected

        with pytest.raises(ClientApiConnectionInterruptedError):
            async for _ in conn._packet_stream():
                pass

        # Connection should be marked as disconnected after the error
        assert not conn.is_connected

    @pytest.mark.asyncio
    async def test_mqtt_error_mid_stream_raises_interrupted(self):
        """If MqttError occurs after some successful messages, the error
        should still surface as ClientApiConnectionInterruptedError."""
        valid_msg = _make_mqtt_message(
            "msh/US/2/e/LongFast",
            _build_service_envelope(from_id=5, packet_id=5),
        )

        async def _partial_then_error():
            yield valid_msg
            raise _FakeMqttError("connection reset")

        fake = _FakeClient()
        fake._messages_iter = _partial_then_error()

        conn = MqttConnection(broker_host="localhost")
        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        packets = []
        with pytest.raises(ClientApiConnectionInterruptedError):
            async for from_radio in conn._packet_stream():
                packets.append(from_radio)

        # We should have received the one valid packet before the error
        assert len(packets) == 1
        assert not conn.is_connected


class TestMqttConnectionSendPacket:
    """Test _send_packet publishes ServiceEnvelope to MQTT."""

    @pytest.mark.asyncio
    async def test_send_packet_publishes_envelope(self):
        """_send_packet should construct a ServiceEnvelope and publish it."""
        fake = _FakeClient()
        conn = MqttConnection(
            broker_host="localhost",
            channel_keys={"LongFast": "AQ=="},
            region="US",
        )

        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        # Build a ToRadio with a MeshPacket
        to_radio = mesh_pb2.ToRadio()
        to_radio.packet.decoded.payload = b"outbound"
        to_radio.packet.to = 0xFFFFFFFF
        to_radio.packet.id = 42

        result = await conn._send_packet(to_radio.SerializeToString())

        assert result is True
        fake.publish.assert_awaited_once()
        call_args = fake.publish.call_args
        topic = call_args[0][0] if call_args[0] else call_args[1].get("topic")
        assert topic.startswith("msh/US/2/e/")

        await conn.disconnect()

    @pytest.mark.asyncio
    async def test_send_packet_not_connected_raises(self):
        """_send_packet should raise when not connected."""
        conn = MqttConnection(broker_host="localhost")

        to_radio = mesh_pb2.ToRadio()
        to_radio.packet.decoded.payload = b"test"

        with pytest.raises(ClientApiNotConnectedError):
            await conn._send_packet(to_radio.SerializeToString())

    @pytest.mark.asyncio
    async def test_send_non_packet_succeeds_silently(self):
        """Non-packet ToRadio messages (heartbeat, disconnect) should succeed silently."""
        fake = _FakeClient()
        conn = MqttConnection(broker_host="localhost")

        with patch("aiomeshtastic.connection.mqtt.aiomqtt.Client", return_value=fake):
            await conn.connect()

        # A heartbeat ToRadio has no packet field
        to_radio = mesh_pb2.ToRadio()
        to_radio.heartbeat.CopyFrom(mesh_pb2.Heartbeat())

        result = await conn._send_packet(to_radio.SerializeToString())
        assert result is True
        fake.publish.assert_not_awaited()

        await conn.disconnect()


class TestMqttConnectionVirtualGateway:
    """Test the virtual gateway node synthesis."""

    def test_gateway_node_num_is_deterministic(self):
        """Same broker params should produce the same gateway node num."""
        conn1 = MqttConnection(broker_host="mqtt.example.com", broker_port=1883)
        conn2 = MqttConnection(broker_host="mqtt.example.com", broker_port=1883)
        assert conn1._gateway_node_num == conn2._gateway_node_num

    def test_different_brokers_produce_different_node_nums(self):
        """Different broker params should produce different gateway node nums."""
        conn1 = MqttConnection(broker_host="broker-a.example.com", broker_port=1883)
        conn2 = MqttConnection(broker_host="broker-b.example.com", broker_port=1883)
        assert conn1._gateway_node_num != conn2._gateway_node_num

    def test_gateway_node_num_not_zero_or_broadcast(self):
        """Gateway node num should never be 0 or 0xFFFFFFFF."""
        conn = MqttConnection(broker_host="localhost")
        assert conn._gateway_node_num != 0
        assert conn._gateway_node_num != 0xFFFFFFFF

# Feature: meshtastic-mqtt-integration, Property 1: ServiceEnvelope round-trip
# **Validates: Requirements 2.3, 7.2, 7.6**
"""Property-based test: ServiceEnvelope round-trip.

For any valid MeshPacket with a decoded (unencrypted) payload, wrapping it in a
ServiceEnvelope with a channel_id and gateway_id, serializing to bytes, and then
parsing those bytes back through MqttPacketDecoder.decode_to_mesh_packet() should
produce an equivalent MeshPacket with the same ``from``, ``to``, ``id``,
``channel``, and ``decoded.payload`` fields.
"""

from hypothesis import given, settings, strategies as st

from aiomeshtastic.connection.decoder import MqttPacketDecoder
from aiomeshtastic.protobuf import mesh_pb2, mqtt_pb2


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Protobuf uint32 fields are 0 .. 2**32-1.  We use the full range for
# ``from``, ``to``, and ``id``.  ``channel`` is a small index (0-7 in
# practice) but the protobuf field is uint32, so we keep a realistic range.
_uint32 = st.integers(min_value=0, max_value=2**32 - 1)
_channel_index = st.integers(min_value=0, max_value=7)

# Payload: arbitrary bytes up to the Meshtastic DATA_PAYLOAD_LEN (233 bytes).
_payload = st.binary(min_size=0, max_size=233)

# channel_id and gateway_id are short ASCII-safe strings.
_channel_id = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
)
_gateway_id = st.from_regex(r"![0-9a-f]{8}", fullmatch=True)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    from_id=_uint32,
    to_id=_uint32,
    packet_id=_uint32,
    channel=_channel_index,
    payload=_payload,
    channel_id=_channel_id,
    gateway_id=_gateway_id,
)
def test_service_envelope_round_trip(
    from_id: int,
    to_id: int,
    packet_id: int,
    channel: int,
    payload: bytes,
    channel_id: str,
    gateway_id: str,
) -> None:
    """Serializing a MeshPacket inside a ServiceEnvelope and decoding it back
    through the decoder must preserve from, to, id, channel, and
    decoded.payload."""

    # -- Build the original MeshPacket with a decoded (unencrypted) payload --
    original = mesh_pb2.MeshPacket()
    original.__setattr__("from", from_id)
    original.to = to_id
    original.id = packet_id
    original.channel = channel
    original.decoded.payload = payload

    # -- Wrap in ServiceEnvelope and serialize --
    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.packet.CopyFrom(original)
    envelope.channel_id = channel_id
    envelope.gateway_id = gateway_id
    serialized = envelope.SerializeToString()

    # -- Decode through MqttPacketDecoder --
    # Use a topic that matches the pattern msh/US/2/e/{channel_id}
    topic = f"msh/US/2/e/{channel_id}"
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.decode_to_mesh_packet(topic, serialized)

    # -- Verify round-trip equivalence --
    assert result is not None, "Decoder returned None for a valid ServiceEnvelope"
    assert getattr(result, "from") == from_id
    assert result.to == to_id
    assert result.id == packet_id
    assert result.channel == channel
    assert result.decoded.payload == payload


# Feature: meshtastic-mqtt-integration, Property 2: Direct MeshPacket fallback parsing
# **Validates: Requirements 7.3**
"""Property-based test: Direct MeshPacket fallback parsing.

For any valid MeshPacket serialized directly (not wrapped in a ServiceEnvelope),
the decoder should still successfully extract an equivalent MeshPacket.
"""


# We need at least one of ``from`` or ``id`` to be non-zero so the decoder's
# fallback parser considers the result meaningful.
_nonzero_uint32 = st.integers(min_value=1, max_value=2**32 - 1)


@settings(max_examples=200)
@given(
    from_id=_nonzero_uint32,
    to_id=_uint32,
    packet_id=_uint32,
    channel=_channel_index,
    payload=_payload,
)
def test_direct_mesh_packet_fallback_parsing(
    from_id: int,
    to_id: int,
    packet_id: int,
    channel: int,
    payload: bytes,
) -> None:
    """Serializing a MeshPacket directly (no ServiceEnvelope wrapper) and
    decoding it through the decoder must still extract an equivalent
    MeshPacket with matching from, to, and id fields."""

    # -- Build the original MeshPacket with a decoded (unencrypted) payload --
    original = mesh_pb2.MeshPacket()
    original.__setattr__("from", from_id)
    original.to = to_id
    original.id = packet_id
    original.channel = channel
    original.decoded.payload = payload

    # -- Serialize directly as MeshPacket bytes (NOT wrapped in ServiceEnvelope) --
    serialized = original.SerializeToString()

    # -- Decode through MqttPacketDecoder --
    topic = "msh/US/2/e/LongFast"
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.decode_to_mesh_packet(topic, serialized)

    # -- Verify the decoder extracted an equivalent MeshPacket --
    assert result is not None, "Decoder returned None for a valid direct MeshPacket"
    assert getattr(result, "from") == from_id
    assert result.to == to_id
    assert result.id == packet_id


# Feature: meshtastic-mqtt-integration, Property 15: JSON message field extraction
# **Validates: Requirements 7.5**
"""Property-based test: JSON message field extraction.

For any valid JSON payload containing type, from, to, and payload fields received
on a json-format MQTT topic, the decoder should extract the packet type, sender,
destination, and payload fields correctly.
"""


# Strategy for text payloads – printable ASCII strings that survive UTF-8 round-trip.
_text_payload = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), min_codepoint=32, max_codepoint=126),
    min_size=0,
    max_size=200,
)

# Channel names for the JSON topic
_json_channel = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
)


@settings(max_examples=200)
@given(
    from_id=_uint32,
    to_id=_uint32,
    packet_id=_uint32,
    text_payload=_text_payload,
    channel_name=_json_channel,
)
def test_json_message_field_extraction(
    from_id: int,
    to_id: int,
    packet_id: int,
    text_payload: str,
    channel_name: str,
) -> None:
    """A JSON payload on a /json/ topic should produce a MeshPacket with
    the correct from, to, and payload fields extracted."""

    import json as _json

    # -- Construct a JSON payload with the required fields --
    json_data = {
        "from": from_id,
        "to": to_id,
        "id": packet_id,
        "type": "TEXT_MESSAGE_APP",
        "payload": text_payload,
    }
    payload_bytes = _json.dumps(json_data).encode("utf-8")

    # -- Use a json-format topic --
    topic = f"msh/US/2/json/{channel_name}"

    # -- Decode through MqttPacketDecoder --
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.decode_to_mesh_packet(topic, payload_bytes)

    # -- Verify the extracted MeshPacket fields --
    assert result is not None, "Decoder returned None for a valid JSON payload"
    assert getattr(result, "from") == from_id
    assert result.to == to_id
    assert result.id == packet_id
    assert result.decoded.payload == text_payload.encode("utf-8")


# Feature: meshtastic-mqtt-integration, Property 16: FromRadio output validity
# **Validates: Requirements 2.2, 2.6**
"""Property-based test: FromRadio output validity.

For any valid MQTT message that the decoder successfully processes (either from a
ServiceEnvelope or direct MeshPacket), the yielded FromRadio message should have
the packet field set with the decoded MeshPacket.

The decoder itself returns MeshPacket, not FromRadio. The MqttConnection wraps it
in FromRadio. This test verifies that a decoded MeshPacket can be correctly placed
into a FromRadio message and the packet field is accessible.
"""


@settings(max_examples=200)
@given(
    from_id=_uint32,
    to_id=_uint32,
    packet_id=_uint32,
    channel=_channel_index,
    payload=_payload,
    channel_id=_channel_id,
    gateway_id=_gateway_id,
)
def test_from_radio_output_validity(
    from_id: int,
    to_id: int,
    packet_id: int,
    channel: int,
    payload: bytes,
    channel_id: str,
    gateway_id: str,
) -> None:
    """A decoded MeshPacket wrapped in a FromRadio message should have the
    packet field set and contain the correct MeshPacket data."""

    # -- Build the original MeshPacket with a decoded (unencrypted) payload --
    original = mesh_pb2.MeshPacket()
    original.__setattr__("from", from_id)
    original.to = to_id
    original.id = packet_id
    original.channel = channel
    original.decoded.payload = payload

    # -- Wrap in ServiceEnvelope and serialize --
    envelope = mqtt_pb2.ServiceEnvelope()
    envelope.packet.CopyFrom(original)
    envelope.channel_id = channel_id
    envelope.gateway_id = gateway_id
    serialized = envelope.SerializeToString()

    # -- Decode through MqttPacketDecoder --
    topic = f"msh/US/2/e/{channel_id}"
    decoder = MqttPacketDecoder(channel_keys={})
    mesh_packet = decoder.decode_to_mesh_packet(topic, serialized)
    assert mesh_packet is not None, "Decoder returned None for a valid ServiceEnvelope"

    # -- Wrap in FromRadio (as MqttConnection._packet_stream() would do) --
    from_radio = mesh_pb2.FromRadio()
    from_radio.packet.CopyFrom(mesh_packet)

    # -- Verify FromRadio has the packet field set --
    assert from_radio.HasField("packet"), "FromRadio should have the packet field set"

    # -- Verify the packet field contains the correct MeshPacket data --
    result_packet = from_radio.packet
    assert getattr(result_packet, "from") == from_id
    assert result_packet.to == to_id
    assert result_packet.id == packet_id
    assert result_packet.channel == channel
    assert result_packet.decoded.payload == payload

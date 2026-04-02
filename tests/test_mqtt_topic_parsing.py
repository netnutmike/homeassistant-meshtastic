# Feature: meshtastic-mqtt-integration, Property 6: Channel name extraction from MQTT topics
# **Validates: Requirements 9.1, 9.2, 9.3**
"""Property-based test: Channel name extraction from MQTT topics.

For any MQTT topic string containing a type indicator (e, c, or json) followed
by a channel name segment, the extract_channel_from_topic function should return
that channel name segment.  This holds regardless of whether the topic has the
standard format (msh/{region}/2/e/{channel}), extended format
(msh/{region}/{area}/{network}/2/e/{channel}), or JSON format
(msh/{region}/2/json/{channel}).
"""

from hypothesis import given, settings, strategies as st

from aiomeshtastic.connection.decoder import MqttPacketDecoder

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Channel names: non-empty alphanumeric strings (Meshtastic channel names).
_channel_name = st.from_regex(r"[A-Za-z0-9]{1,20}", fullmatch=True)

# Region codes: short uppercase strings like "US", "EU_868", "ANZ".
_region = st.from_regex(r"[A-Z]{2,5}(_[0-9]{3})?", fullmatch=True)

# Gateway IDs follow the Meshtastic convention: !xxxxxxxx
_gateway_id = st.from_regex(r"![0-9a-f]{8}", fullmatch=True)

# Extra path segments for extended topics (area, network).
_path_segment = st.from_regex(r"[A-Za-z0-9]{1,10}", fullmatch=True)

# Type indicators used in MQTT topics.
_type_indicator = st.sampled_from(["e", "c", "json"])


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    channel=_channel_name,
    region=_region,
    type_ind=_type_indicator,
)
def test_standard_topic_channel_extraction(
    channel: str,
    region: str,
    type_ind: str,
) -> None:
    """Standard format: msh/{region}/2/{type}/{channel}
    The decoder must return the generated channel name."""

    topic = f"msh/{region}/2/{type_ind}/{channel}"
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.extract_channel_from_topic(topic)

    assert result == channel, (
        f"Expected channel '{channel}' from topic '{topic}', got '{result}'"
    )


@settings(max_examples=200)
@given(
    channel=_channel_name,
    region=_region,
    type_ind=_type_indicator,
    gateway=_gateway_id,
)
def test_standard_topic_with_gateway_channel_extraction(
    channel: str,
    region: str,
    type_ind: str,
    gateway: str,
) -> None:
    """Standard format with gateway: msh/{region}/2/{type}/{channel}/{gateway_id}
    The decoder must return the generated channel name, not the gateway."""

    topic = f"msh/{region}/2/{type_ind}/{channel}/{gateway}"
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.extract_channel_from_topic(topic)

    assert result == channel, (
        f"Expected channel '{channel}' from topic '{topic}', got '{result}'"
    )


@settings(max_examples=200)
@given(
    channel=_channel_name,
    region=_region,
    area=_path_segment,
    network=_path_segment,
    type_ind=_type_indicator,
)
def test_extended_topic_channel_extraction(
    channel: str,
    region: str,
    area: str,
    network: str,
    type_ind: str,
) -> None:
    """Extended format: msh/{region}/{area}/{network}/2/{type}/{channel}
    The decoder must still correctly extract the channel name by locating
    the type indicator and taking the next segment."""

    topic = f"msh/{region}/{area}/{network}/2/{type_ind}/{channel}"
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.extract_channel_from_topic(topic)

    assert result == channel, (
        f"Expected channel '{channel}' from topic '{topic}', got '{result}'"
    )


@settings(max_examples=200)
@given(
    channel=_channel_name,
    region=_region,
)
def test_json_format_topic_channel_extraction(
    channel: str,
    region: str,
) -> None:
    """JSON format: msh/{region}/2/json/{channel}
    The decoder must extract the channel name using the same positional logic."""

    topic = f"msh/{region}/2/json/{channel}"
    decoder = MqttPacketDecoder(channel_keys={})
    result = decoder.extract_channel_from_topic(topic)

    assert result == channel, (
        f"Expected channel '{channel}' from topic '{topic}', got '{result}'"
    )


def test_topic_without_type_indicator_returns_unknown() -> None:
    """Topics without a type indicator (e, c, or json) should return 'unknown'."""

    decoder = MqttPacketDecoder(channel_keys={})

    # No type indicator at all
    assert decoder.extract_channel_from_topic("msh/US/2/x/LongFast") == "unknown"
    assert decoder.extract_channel_from_topic("some/random/topic") == "unknown"
    assert decoder.extract_channel_from_topic("") == "unknown"
    assert decoder.extract_channel_from_topic("msh/US/2") == "unknown"

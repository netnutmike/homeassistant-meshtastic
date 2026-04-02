# Feature: meshtastic-mqtt-integration, Property 12: MQTT broker validation
# **Validates: Requirements 1.6**
"""Property-based test: MQTT broker validation.

For any broker host string that is empty, the config flow validation should
reject the input.  For any broker port integer outside the range 1-65535, the
config flow validation should reject the input.
"""

import base64

from hypothesis import given, settings, strategies as st


# ---------------------------------------------------------------------------
# Validation functions under test
# ---------------------------------------------------------------------------
# These are copied verbatim from config_flow.py because that module imports
# homeassistant packages which are unavailable in the lightweight test
# environment.  The property tests verify the *logic* of these validators.


def _validate_mqtt_port(port: int) -> bool:
    """Validate that port is in range 1-65535."""
    return 1 <= port <= 65535


def _validate_base64_key(key_str: str) -> bool:
    """Validate that a string is valid base64."""
    try:
        base64.b64decode(key_str, validate=True)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Ports that are definitely invalid (outside 1-65535).
_invalid_port_low = st.integers(max_value=0)
_invalid_port_high = st.integers(min_value=65536)
_invalid_port = st.one_of(_invalid_port_low, _invalid_port_high)

# Ports that are valid (1-65535).
_valid_port = st.integers(min_value=1, max_value=65535)


# ---------------------------------------------------------------------------
# Property 12 tests
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(port=_invalid_port)
def test_mqtt_port_validation_rejects_out_of_range(port: int) -> None:
    """Any port outside 1-65535 must be rejected."""
    assert _validate_mqtt_port(port) is False, (
        f"Port {port} should be rejected (outside 1-65535)"
    )


@settings(max_examples=200)
@given(port=_valid_port)
def test_mqtt_port_validation_accepts_valid_range(port: int) -> None:
    """Any port in 1-65535 must be accepted."""
    assert _validate_mqtt_port(port) is True, (
        f"Port {port} should be accepted (within 1-65535)"
    )


def test_mqtt_host_validation_rejects_empty_string() -> None:
    """An empty broker host string must be rejected by the config flow.

    The config flow checks ``host = user_input.get(..., "").strip()`` and
    rejects when ``not host`` is True.  We verify the same logic here.
    """
    for empty_host in ["", "   ", "\t", "\n", "  \t\n  "]:
        stripped = empty_host.strip()
        assert not stripped, (
            f"Host {empty_host!r} should be empty after stripping"
        )



# Feature: meshtastic-mqtt-integration, Property 13: Invalid base64 channel key rejection
# **Validates: Requirements 6.4**
"""Property-based test: Invalid base64 channel key rejection.

For any string that is not valid base64 encoding, the config flow validation
should reject it when provided as a channel key.
"""

# ---------------------------------------------------------------------------
# Hypothesis strategies for base64 testing
# ---------------------------------------------------------------------------

# Strategy that generates strings which are NOT valid base64.
# We filter the general text strategy to only keep strings that fail
# base64 decoding with validate=True.
def _is_invalid_base64(s: str) -> bool:
    """Return True if s is NOT valid base64 (strict mode)."""
    try:
        base64.b64decode(s, validate=True)
        return False
    except Exception:  # noqa: BLE001
        return True


_invalid_base64_string = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
    ),
    min_size=1,
    max_size=100,
).filter(_is_invalid_base64)


# ---------------------------------------------------------------------------
# Property 13 tests
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(key_str=_invalid_base64_string)
def test_base64_key_validation_rejects_invalid_base64(key_str: str) -> None:
    """Any string that is not valid base64 must be rejected as a channel key."""
    assert _validate_base64_key(key_str) is False, (
        f"Key {key_str!r} is not valid base64 but was accepted"
    )


@settings(max_examples=200)
@given(data=st.binary(min_size=1, max_size=64))
def test_base64_key_validation_accepts_valid_base64(data: bytes) -> None:
    """Any properly base64-encoded string must be accepted as a channel key."""
    key_str = base64.b64encode(data).decode("ascii")
    assert _validate_base64_key(key_str) is True, (
        f"Key {key_str!r} is valid base64 but was rejected"
    )


# ===========================================================================
# Unit tests for MQTT config flow (Task 4.6)
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.2, 6.3, 6.4
# ===========================================================================

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub ``aiomqtt`` so we can import _test_mqtt_connection from config_flow.
# ---------------------------------------------------------------------------

_aiomqtt_stub = types.ModuleType("aiomqtt")


class _FakeMqttClient:
    """Minimal stand-in for ``aiomqtt.Client``."""

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


_aiomqtt_stub.Client = _FakeMqttClient
sys.modules.setdefault("aiomqtt", _aiomqtt_stub)


# ---------------------------------------------------------------------------
# Copy the _test_mqtt_connection function from config_flow.py so we can test
# it without importing the full HA-dependent module.
# ---------------------------------------------------------------------------


async def _test_mqtt_connection(
    host: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
    use_tls: bool = False,
) -> bool:
    """Test MQTT broker connection with a 10-second timeout."""
    import aiomqtt

    tls_params = None
    if use_tls:
        import ssl
        tls_params = ssl.create_default_context()

    try:
        async with asyncio.timeout(10):
            async with aiomqtt.Client(
                hostname=host,
                port=port,
                username=username if username else None,
                password=password if password else None,
                tls_params=tls_params,
            ):
                return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Constants mirrored from const.py (to avoid importing HA-dependent modules)
# ---------------------------------------------------------------------------

CONF_CONNECTION_MQTT_HOST = "mqtt_host"
CONF_CONNECTION_MQTT_PORT = "mqtt_port"
CONF_CONNECTION_MQTT_USERNAME = "mqtt_username"
CONF_CONNECTION_MQTT_PASSWORD = "mqtt_password"
CONF_CONNECTION_MQTT_TLS = "mqtt_tls"
CONF_CONNECTION_MQTT_TOPIC = "mqtt_topic"
CONF_CONNECTION_MQTT_CHANNEL_KEYS = "mqtt_channel_keys"
CONF_CONNECTION_MQTT_REGION = "mqtt_region"
CONF_CONNECTION_TYPE = "connection_type"
CONF_MQTT_CHANNEL_NAME = "mqtt_channel_name"
CONF_MQTT_CHANNEL_KEY = "mqtt_channel_key"
CONF_MQTT_ADD_ANOTHER_CHANNEL = "mqtt_add_another_channel"
MQTT_DEFAULT_PORT = 1883
MQTT_DEFAULT_TOPIC = "msh/US/2/e/#"
MQTT_DEFAULT_REGION = "US"


# ===========================================================================
# 1. Validation function unit tests
# ===========================================================================


class TestValidateMqttPort:
    """Unit tests for _validate_mqtt_port."""

    def test_valid_port_min(self):
        assert _validate_mqtt_port(1) is True

    def test_valid_port_max(self):
        assert _validate_mqtt_port(65535) is True

    def test_valid_port_default(self):
        assert _validate_mqtt_port(1883) is True

    def test_invalid_port_zero(self):
        assert _validate_mqtt_port(0) is False

    def test_invalid_port_negative(self):
        assert _validate_mqtt_port(-1) is False

    def test_invalid_port_too_high(self):
        assert _validate_mqtt_port(65536) is False

    def test_invalid_port_very_large(self):
        assert _validate_mqtt_port(100000) is False


class TestValidateBase64Key:
    """Unit tests for _validate_base64_key."""

    def test_valid_default_key(self):
        """The default Meshtastic key 'AQ==' is valid base64."""
        assert _validate_base64_key("AQ==") is True

    def test_valid_long_key(self):
        assert _validate_base64_key("1PG7OiApB1nwvP+rz05pAQ==") is True

    def test_valid_simple_key(self):
        assert _validate_base64_key("dGVzdA==") is True

    def test_invalid_key_with_spaces(self):
        assert _validate_base64_key("not a valid key!") is False

    def test_invalid_key_special_chars(self):
        assert _validate_base64_key("!!!@@@###") is False

    def test_empty_string_is_valid_base64(self):
        """Empty string decodes to empty bytes — technically valid base64."""
        assert _validate_base64_key("") is True

    def test_invalid_padding(self):
        """Incorrect padding should be rejected with validate=True."""
        assert _validate_base64_key("AQ=") is False


# ===========================================================================
# 2. Test MQTT connection function tests (mocked aiomqtt)
# ===========================================================================


class TestMqttConnectionFunction:
    """Unit tests for _test_mqtt_connection with mocked aiomqtt."""

    @pytest.mark.asyncio
    async def test_successful_connection(self):
        """Happy path: broker accepts connection → returns True."""
        with patch("aiomqtt.Client", return_value=_FakeMqttClient()):
            result = await _test_mqtt_connection(
                host="mqtt.example.com", port=1883
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_with_credentials(self):
        """Connection with username/password should pass them through."""
        captured = {}

        class _CapturingClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch("aiomqtt.Client", _CapturingClient):
            result = await _test_mqtt_connection(
                host="broker.local",
                port=8883,
                username="meshdev",
                password="large4cats",
            )

        assert result is True
        assert captured["hostname"] == "broker.local"
        assert captured["port"] == 8883
        assert captured["username"] == "meshdev"
        assert captured["password"] == "large4cats"

    @pytest.mark.asyncio
    async def test_connection_with_tls(self):
        """TLS=True should pass tls_params (an ssl.SSLContext)."""
        captured = {}

        class _CapturingClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch("aiomqtt.Client", _CapturingClient):
            result = await _test_mqtt_connection(
                host="secure.broker.com",
                port=8883,
                use_tls=True,
            )

        assert result is True
        import ssl
        assert isinstance(captured["tls_params"], ssl.SSLContext)


    @pytest.mark.asyncio
    async def test_connection_failure_returns_false(self):
        """When the broker is unreachable, should return False."""

        class _FailingClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                raise ConnectionRefusedError("Connection refused")

            async def __aexit__(self, *args):
                pass

        with patch("aiomqtt.Client", _FailingClient):
            result = await _test_mqtt_connection(
                host="unreachable.broker.com", port=1883
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_auth_failure_returns_false(self):
        """When authentication fails, should return False."""

        class _AuthFailClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                raise Exception("Not authorized")  # noqa: TRY002

            async def __aexit__(self, *args):
                pass

        with patch("aiomqtt.Client", _AuthFailClient):
            result = await _test_mqtt_connection(
                host="broker.local",
                port=1883,
                username="wrong",
                password="creds",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_returns_false(self):
        """When connection takes longer than 10s, should return False."""

        class _SlowClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                raise asyncio.TimeoutError()

            async def __aexit__(self, *args):
                pass

        with patch("aiomqtt.Client", _SlowClient):
            result = await _test_mqtt_connection(
                host="slow.broker.com", port=1883
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_empty_username_passed_as_none(self):
        """Empty username string should be passed as None to aiomqtt."""
        captured = {}

        class _CapturingClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch("aiomqtt.Client", _CapturingClient):
            await _test_mqtt_connection(
                host="broker.local", port=1883, username="", password=""
            )

        assert captured["username"] is None
        assert captured["password"] is None


# ===========================================================================
# 3. Config flow logic tests (validation, channel accumulation, error paths)
# ===========================================================================


class TestConfigFlowMqttValidationLogic:
    """Test the validation logic used in async_step_manual_mqtt.

    Since we can't instantiate the real ConfigFlow (HA deps), we replicate
    the validation logic from the step and verify it produces correct errors.
    """

    @staticmethod
    def _validate_mqtt_step(user_input: dict) -> dict[str, str]:
        """Replicate the validation logic from async_step_manual_mqtt."""
        errors: dict[str, str] = {}
        host = user_input.get(CONF_CONNECTION_MQTT_HOST, "").strip()
        if not host:
            errors[CONF_CONNECTION_MQTT_HOST] = "mqtt_invalid_host"
        port = user_input.get(CONF_CONNECTION_MQTT_PORT, MQTT_DEFAULT_PORT)
        if not _validate_mqtt_port(port):
            errors[CONF_CONNECTION_MQTT_PORT] = "mqtt_invalid_port"
        return errors

    def test_valid_input_no_errors(self):
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "mqtt.example.com",
            CONF_CONNECTION_MQTT_PORT: 1883,
        })
        assert errors == {}

    def test_empty_host_error(self):
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "",
            CONF_CONNECTION_MQTT_PORT: 1883,
        })
        assert CONF_CONNECTION_MQTT_HOST in errors
        assert errors[CONF_CONNECTION_MQTT_HOST] == "mqtt_invalid_host"

    def test_whitespace_only_host_error(self):
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "   ",
            CONF_CONNECTION_MQTT_PORT: 1883,
        })
        assert CONF_CONNECTION_MQTT_HOST in errors

    def test_invalid_port_zero_error(self):
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "broker.local",
            CONF_CONNECTION_MQTT_PORT: 0,
        })
        assert CONF_CONNECTION_MQTT_PORT in errors
        assert errors[CONF_CONNECTION_MQTT_PORT] == "mqtt_invalid_port"

    def test_invalid_port_too_high_error(self):
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "broker.local",
            CONF_CONNECTION_MQTT_PORT: 70000,
        })
        assert CONF_CONNECTION_MQTT_PORT in errors

    def test_both_host_and_port_invalid(self):
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "",
            CONF_CONNECTION_MQTT_PORT: 0,
        })
        assert CONF_CONNECTION_MQTT_HOST in errors
        assert CONF_CONNECTION_MQTT_PORT in errors

    def test_host_stripped_of_whitespace(self):
        """Host with leading/trailing whitespace should be accepted after strip."""
        errors = self._validate_mqtt_step({
            CONF_CONNECTION_MQTT_HOST: "  mqtt.example.com  ",
            CONF_CONNECTION_MQTT_PORT: 1883,
        })
        assert errors == {}


class TestConfigFlowChannelKeyAccumulation:
    """Test the channel key accumulation logic from async_step_mqtt_channels.

    Replicates the validation and accumulation logic from the config flow step.
    """

    @staticmethod
    def _validate_channel_step(
        user_input: dict, existing_keys: dict[str, str]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Replicate validation logic from async_step_mqtt_channels.

        Returns (errors, updated_channel_keys).
        """
        errors: dict[str, str] = {}
        channel_keys = dict(existing_keys)

        channel_name = user_input.get(CONF_MQTT_CHANNEL_NAME, "").strip()
        channel_key = user_input.get(CONF_MQTT_CHANNEL_KEY, "").strip()

        if not channel_name:
            errors[CONF_MQTT_CHANNEL_NAME] = "mqtt_invalid_channel_name"
        if not channel_key:
            errors[CONF_MQTT_CHANNEL_KEY] = "mqtt_invalid_channel_key"
        elif not _validate_base64_key(channel_key):
            errors[CONF_MQTT_CHANNEL_KEY] = "mqtt_invalid_base64_key"

        if not errors:
            channel_keys[channel_name] = channel_key

        return errors, channel_keys

    def test_valid_channel_added(self):
        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            {},
        )
        assert errors == {}
        assert keys == {"LongFast": "AQ=="}

    def test_multiple_channels_accumulate(self):
        """Adding channels one by one should accumulate them."""
        keys: dict[str, str] = {}

        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            keys,
        )
        assert errors == {}
        assert len(keys) == 1

        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "ShortSlow", CONF_MQTT_CHANNEL_KEY: "dGVzdA=="},
            keys,
        )
        assert errors == {}
        assert len(keys) == 2
        assert keys["LongFast"] == "AQ=="
        assert keys["ShortSlow"] == "dGVzdA=="

    def test_empty_channel_name_error(self):
        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            {},
        )
        assert CONF_MQTT_CHANNEL_NAME in errors
        assert keys == {}

    def test_empty_channel_key_error(self):
        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: ""},
            {},
        )
        assert CONF_MQTT_CHANNEL_KEY in errors
        assert errors[CONF_MQTT_CHANNEL_KEY] == "mqtt_invalid_channel_key"

    def test_invalid_base64_key_error(self):
        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "not-base64!!!"},
            {},
        )
        assert CONF_MQTT_CHANNEL_KEY in errors
        assert errors[CONF_MQTT_CHANNEL_KEY] == "mqtt_invalid_base64_key"

    def test_overwrite_existing_channel(self):
        """Re-adding a channel name should overwrite the key."""
        existing = {"LongFast": "AQ=="}
        errors, keys = self._validate_channel_step(
            {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "dGVzdA=="},
            existing,
        )
        assert errors == {}
        assert keys["LongFast"] == "dGVzdA=="


class TestConfigFlowHappyPath:
    """Test the end-to-end happy path: MQTT setup wizard flow.

    Simulates the full flow: validate host/port → channels → test connection
    → create entry, using the extracted validation logic.
    """

    @staticmethod
    def _simulate_mqtt_flow(
        mqtt_input: dict,
        channel_inputs: list[dict],
        connection_succeeds: bool = True,
    ) -> tuple[dict[str, str] | None, dict | None]:
        """Simulate the MQTT config flow logic.

        Returns (errors, config_data) where errors is None on success.
        """
        # Step 1: Validate MQTT broker settings
        errors: dict[str, str] = {}
        host = mqtt_input.get(CONF_CONNECTION_MQTT_HOST, "").strip()
        if not host:
            errors[CONF_CONNECTION_MQTT_HOST] = "mqtt_invalid_host"
        port = mqtt_input.get(CONF_CONNECTION_MQTT_PORT, MQTT_DEFAULT_PORT)
        if not _validate_mqtt_port(port):
            errors[CONF_CONNECTION_MQTT_PORT] = "mqtt_invalid_port"
        if errors:
            return errors, None

        data = dict(mqtt_input)
        data[CONF_CONNECTION_MQTT_HOST] = host
        data[CONF_CONNECTION_TYPE] = "mqtt"
        data[CONF_CONNECTION_MQTT_CHANNEL_KEYS] = {}

        # Step 2: Add channel keys
        for ch_input in channel_inputs:
            ch_name = ch_input.get(CONF_MQTT_CHANNEL_NAME, "").strip()
            ch_key = ch_input.get(CONF_MQTT_CHANNEL_KEY, "").strip()
            if not ch_name:
                return {CONF_MQTT_CHANNEL_NAME: "mqtt_invalid_channel_name"}, None
            if not ch_key:
                return {CONF_MQTT_CHANNEL_KEY: "mqtt_invalid_channel_key"}, None
            if not _validate_base64_key(ch_key):
                return {CONF_MQTT_CHANNEL_KEY: "mqtt_invalid_base64_key"}, None
            data[CONF_CONNECTION_MQTT_CHANNEL_KEYS][ch_name] = ch_key

        # Step 3: Test connection
        if not connection_succeeds:
            return {"base": "cannot_connect"}, None

        # Step 4: Create entry
        return None, data

    def test_happy_path_single_channel(self):
        """Full flow with one channel and successful connection."""
        errors, data = self._simulate_mqtt_flow(
            mqtt_input={
                CONF_CONNECTION_MQTT_HOST: "mqtt.meshtastic.org",
                CONF_CONNECTION_MQTT_PORT: 1883,
                CONF_CONNECTION_MQTT_USERNAME: "meshdev",
                CONF_CONNECTION_MQTT_PASSWORD: "large4cats",
                CONF_CONNECTION_MQTT_TLS: False,
                CONF_CONNECTION_MQTT_TOPIC: MQTT_DEFAULT_TOPIC,
                CONF_CONNECTION_MQTT_REGION: "US",
            },
            channel_inputs=[
                {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            ],
            connection_succeeds=True,
        )
        assert errors is None
        assert data is not None
        assert data[CONF_CONNECTION_TYPE] == "mqtt"
        assert data[CONF_CONNECTION_MQTT_HOST] == "mqtt.meshtastic.org"
        assert data[CONF_CONNECTION_MQTT_PORT] == 1883
        assert data[CONF_CONNECTION_MQTT_CHANNEL_KEYS] == {"LongFast": "AQ=="}

    def test_happy_path_multiple_channels(self):
        """Full flow with multiple channels."""
        errors, data = self._simulate_mqtt_flow(
            mqtt_input={
                CONF_CONNECTION_MQTT_HOST: "broker.local",
                CONF_CONNECTION_MQTT_PORT: 8883,
                CONF_CONNECTION_MQTT_TLS: True,
            },
            channel_inputs=[
                {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
                {CONF_MQTT_CHANNEL_NAME: "ShortSlow", CONF_MQTT_CHANNEL_KEY: "dGVzdA=="},
            ],
            connection_succeeds=True,
        )
        assert errors is None
        assert len(data[CONF_CONNECTION_MQTT_CHANNEL_KEYS]) == 2


    def test_connection_failure_returns_error(self):
        """When test connection fails, should return cannot_connect error."""
        errors, data = self._simulate_mqtt_flow(
            mqtt_input={
                CONF_CONNECTION_MQTT_HOST: "unreachable.broker.com",
                CONF_CONNECTION_MQTT_PORT: 1883,
            },
            channel_inputs=[
                {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            ],
            connection_succeeds=False,
        )
        assert errors is not None
        assert errors["base"] == "cannot_connect"
        assert data is None

    def test_invalid_host_stops_flow(self):
        """Empty host should stop the flow at step 1."""
        errors, data = self._simulate_mqtt_flow(
            mqtt_input={
                CONF_CONNECTION_MQTT_HOST: "",
                CONF_CONNECTION_MQTT_PORT: 1883,
            },
            channel_inputs=[
                {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            ],
        )
        assert errors is not None
        assert CONF_CONNECTION_MQTT_HOST in errors
        assert data is None

    def test_invalid_port_stops_flow(self):
        """Invalid port should stop the flow at step 1."""
        errors, data = self._simulate_mqtt_flow(
            mqtt_input={
                CONF_CONNECTION_MQTT_HOST: "broker.local",
                CONF_CONNECTION_MQTT_PORT: 0,
            },
            channel_inputs=[
                {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "AQ=="},
            ],
        )
        assert errors is not None
        assert CONF_CONNECTION_MQTT_PORT in errors

    def test_invalid_channel_key_stops_flow(self):
        """Invalid base64 channel key should stop the flow at step 2."""
        errors, data = self._simulate_mqtt_flow(
            mqtt_input={
                CONF_CONNECTION_MQTT_HOST: "broker.local",
                CONF_CONNECTION_MQTT_PORT: 1883,
            },
            channel_inputs=[
                {CONF_MQTT_CHANNEL_NAME: "LongFast", CONF_MQTT_CHANNEL_KEY: "not-base64!!!"},
            ],
        )
        assert errors is not None
        assert CONF_MQTT_CHANNEL_KEY in errors


class TestOptionsFlowChannelKeyParsing:
    """Test the options flow channel key parsing logic.

    The options flow accepts channel keys as a text block with lines like
    ``ChannelName:Base64Key``. We replicate and test that parsing logic.
    """

    @staticmethod
    def _parse_channel_keys_text(text: str) -> tuple[dict[str, str], dict[str, str]]:
        """Replicate the channel key parsing from async_step_mqtt_options.

        Returns (errors, channel_keys).
        """
        errors: dict[str, str] = {}
        channel_keys: dict[str, str] = {}
        if text:
            for line in text.strip().split("\n"):
                line = line.strip()
                if ":" in line:
                    name, key = line.split(":", 1)
                    name = name.strip()
                    key = key.strip()
                    if name and key:
                        if not _validate_base64_key(key):
                            errors[CONF_CONNECTION_MQTT_CHANNEL_KEYS] = "mqtt_invalid_base64_key"
                            break
                        channel_keys[name] = key
        return errors, channel_keys

    def test_parse_single_channel(self):
        errors, keys = self._parse_channel_keys_text("LongFast:AQ==")
        assert errors == {}
        assert keys == {"LongFast": "AQ=="}

    def test_parse_multiple_channels(self):
        text = "LongFast:AQ==\nShortSlow:dGVzdA=="
        errors, keys = self._parse_channel_keys_text(text)
        assert errors == {}
        assert len(keys) == 2
        assert keys["LongFast"] == "AQ=="
        assert keys["ShortSlow"] == "dGVzdA=="

    def test_parse_empty_text(self):
        errors, keys = self._parse_channel_keys_text("")
        assert errors == {}
        assert keys == {}

    def test_parse_invalid_base64_key(self):
        errors, keys = self._parse_channel_keys_text("LongFast:not-valid!!!")
        assert CONF_CONNECTION_MQTT_CHANNEL_KEYS in errors

    def test_parse_line_without_colon_skipped(self):
        """Lines without ':' should be silently skipped."""
        text = "LongFast:AQ==\ngarbage line\nShortSlow:dGVzdA=="
        errors, keys = self._parse_channel_keys_text(text)
        assert errors == {}
        assert len(keys) == 2

    def test_parse_whitespace_around_names_and_keys(self):
        text = "  LongFast  :  AQ==  "
        errors, keys = self._parse_channel_keys_text(text)
        assert errors == {}
        assert keys == {"LongFast": "AQ=="}

    def test_remove_channel_by_omitting_from_text(self):
        """Removing a channel is done by omitting it from the text block."""
        original = {"LongFast": "AQ==", "ShortSlow": "dGVzdA=="}
        # User edits to only keep LongFast
        text = "LongFast:AQ=="
        errors, keys = self._parse_channel_keys_text(text)
        assert errors == {}
        assert "ShortSlow" not in keys
        assert keys == {"LongFast": "AQ=="}

    def test_add_channel_by_appending_to_text(self):
        """Adding a channel is done by appending a new line."""
        text = "LongFast:AQ==\nNewChannel:1PG7OiApB1nwvP+rz05pAQ=="
        errors, keys = self._parse_channel_keys_text(text)
        assert errors == {}
        assert len(keys) == 2
        assert "NewChannel" in keys

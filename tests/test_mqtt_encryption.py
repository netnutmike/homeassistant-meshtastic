# Feature: meshtastic-mqtt-integration, Property 3: AES-CTR encryption/decryption round-trip
# **Validates: Requirements 2.4, 8.1, 8.7**
"""Property-based test: AES-CTR encryption/decryption round-trip.

For any plaintext byte sequence, packet ID (uint32), sender node ID (uint32),
and valid AES key (16 or 32 bytes), encrypting the plaintext with AES-CTR using
the constructed nonce and then decrypting with the same key and nonce should
produce the original plaintext.
"""

import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from hypothesis import given, settings, strategies as st

from aiomeshtastic.connection.decoder import MqttPacketDecoder

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_uint32 = st.integers(min_value=0, max_value=2**32 - 1)

# Valid AES keys: exactly 16 bytes (AES-128) or 32 bytes (AES-256).
_aes_key = st.one_of(
    st.binary(min_size=16, max_size=16),
    st.binary(min_size=32, max_size=32),
)

# Plaintext: arbitrary bytes up to Meshtastic DATA_PAYLOAD_LEN (233 bytes).
_plaintext = st.binary(min_size=1, max_size=233)

# Channel name used for key lookup.
_TEST_CHANNEL = "TestChannel"


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    plaintext=_plaintext,
    packet_id=_uint32,
    from_node_id=_uint32,
    key=_aes_key,
)
def test_aes_ctr_encryption_decryption_round_trip(
    plaintext: bytes,
    packet_id: int,
    from_node_id: int,
    key: bytes,
) -> None:
    """Encrypting plaintext with AES-CTR and then decrypting with the same
    key and nonce via MqttPacketDecoder.decrypt_payload() must produce the
    original plaintext."""

    # -- Set up a decoder with the generated key for our test channel --
    key_b64 = base64.b64encode(key).decode()
    decoder = MqttPacketDecoder(channel_keys={_TEST_CHANNEL: key_b64})

    # -- Build the nonce using the decoder's own method --
    nonce = decoder.build_nonce(packet_id, from_node_id)

    # -- Encrypt the plaintext using AES-CTR from the cryptography library --
    prepared_key = decoder.prepare_key(key)
    cipher = Cipher(algorithms.AES(prepared_key), modes.CTR(nonce))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()

    # -- Decrypt using the decoder --
    decrypted = decoder.decrypt_payload(
        ciphertext, _TEST_CHANNEL, packet_id, from_node_id
    )

    # -- Verify round-trip: decrypted output must match original plaintext --
    assert decrypted is not None, "decrypt_payload returned None"
    assert decrypted == plaintext, (
        f"Round-trip failed: expected {plaintext!r}, got {decrypted!r}"
    )


# Feature: meshtastic-mqtt-integration, Property 4: Key preparation produces valid AES key length
# **Validates: Requirements 8.3, 8.4, 8.5**
"""Property-based test: Key preparation produces valid AES key length.

For any raw key byte sequence of arbitrary length, the prepare_key function
should produce a key of exactly 16 or 32 bytes.  Specifically: keys ≤16 bytes
(after 0x01 expansion) produce 16-byte keys, keys of 17–32 bytes produce
32-byte keys, and keys >32 bytes produce 32-byte keys.
"""

# Strategy: arbitrary raw key bytes from 0 to 100 bytes.
_raw_key = st.binary(min_size=0, max_size=100)


@settings(max_examples=200)
@given(raw_key=_raw_key)
def test_prepare_key_produces_valid_aes_key_length(raw_key: bytes) -> None:
    """prepare_key must always return a 16- or 32-byte key, following the
    Meshtastic key-preparation rules."""

    decoder = MqttPacketDecoder(channel_keys={})
    prepared = decoder.prepare_key(raw_key)

    # 1. Result must be exactly 16 or 32 bytes (valid AES key sizes).
    assert len(prepared) in (16, 32), (
        f"Expected 16 or 32 bytes, got {len(prepared)} for input of {len(raw_key)} bytes"
    )

    # 2. Verify the specific length rules.
    if len(raw_key) == 1 and raw_key[0] == 0x01:
        # Special case: single byte 0x01 → default key → 16 bytes.
        assert len(prepared) == 16, (
            f"0x01 key should expand to 16-byte default key, got {len(prepared)}"
        )
    elif len(raw_key) <= 16:
        assert len(prepared) == 16, (
            f"Key of {len(raw_key)} bytes (≤16) should produce 16-byte key, got {len(prepared)}"
        )
    elif len(raw_key) <= 32:
        assert len(prepared) == 32, (
            f"Key of {len(raw_key)} bytes (17-32) should produce 32-byte key, got {len(prepared)}"
        )
    else:
        assert len(prepared) == 32, (
            f"Key of {len(raw_key)} bytes (>32) should produce 32-byte key, got {len(prepared)}"
        )


# Feature: meshtastic-mqtt-integration, Property 5: Nonce construction produces 16 bytes with correct layout
# **Validates: Requirements 8.1**
"""Property-based test: Nonce construction produces 16 bytes with correct layout.

For any packet ID (uint32) and sender node ID (uint32), the constructed nonce
should be exactly 16 bytes where the first 8 bytes equal
packet_id.to_bytes(8, "little") and the last 8 bytes equal
from_node_id.to_bytes(8, "little").
"""


@settings(max_examples=200)
@given(
    packet_id=_uint32,
    from_node_id=_uint32,
)
def test_nonce_construction_produces_16_bytes_with_correct_layout(
    packet_id: int,
    from_node_id: int,
) -> None:
    """build_nonce must return exactly 16 bytes with packet_id in the first 8
    bytes (little-endian) and from_node_id in the last 8 bytes (little-endian)."""

    decoder = MqttPacketDecoder(channel_keys={})
    nonce = decoder.build_nonce(packet_id, from_node_id)

    # 1. Result must be exactly 16 bytes.
    assert len(nonce) == 16, f"Expected 16 bytes, got {len(nonce)}"

    # 2. First 8 bytes must equal packet_id as little-endian.
    expected_first = packet_id.to_bytes(8, "little")
    assert nonce[:8] == expected_first, (
        f"First 8 bytes mismatch: expected {expected_first!r}, got {nonce[:8]!r}"
    )

    # 3. Last 8 bytes must equal from_node_id as little-endian.
    expected_last = from_node_id.to_bytes(8, "little")
    assert nonce[8:] == expected_last, (
        f"Last 8 bytes mismatch: expected {expected_last!r}, got {nonce[8:]!r}"
    )

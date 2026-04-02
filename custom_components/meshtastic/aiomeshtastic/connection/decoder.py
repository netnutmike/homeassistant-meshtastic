# SPDX-License-Identifier: MIT

"""MQTT packet decoder for Meshtastic ServiceEnvelope messages.

Handles ServiceEnvelope parsing, AES-CTR decryption, channel extraction
from MQTT topics, and JSON message handling.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..protobuf import mesh_pb2, mqtt_pb2, portnums_pb2  # noqa: TID252

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

# Default Meshtastic encryption key (base64: "1PG7OiApB1nwvP+rz05pAQ==")
_DEFAULT_KEY = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")

# Type indicators used in MQTT topic paths
_TYPE_INDICATORS = {"e", "c", "json"}


class MqttPacketDecoder:
    """Decodes Meshtastic MQTT messages into MeshPacket protobuf objects.

    Supports ServiceEnvelope parsing with fallback to direct MeshPacket,
    AES-CTR decryption of encrypted payloads, and JSON message handling.
    """

    def __init__(self, channel_keys: dict[str, str]) -> None:
        """Initialize the decoder with channel encryption keys.

        Args:
            channel_keys: Mapping of channel name to base64-encoded AES key.
        """
        self._channel_keys: dict[str, bytes] = {}
        for channel, key_b64 in channel_keys.items():
            try:
                raw = base64.b64decode(key_b64)
                self._channel_keys[channel] = self.prepare_key(raw)
            except Exception:
                LOGGER.warning("Invalid base64 key for channel %s, skipping", channel)

    def prepare_key(self, raw_key: bytes) -> bytes:
        """Prepare an AES key with padding/expansion rules.

        Rules:
            - 1 byte with value 0x01 → expand to default Meshtastic key
            - < 16 bytes → pad with 0x00 to 16 bytes
            - 16 bytes → use as-is (AES-128)
            - 17–31 bytes → pad with 0x00 to 32 bytes
            - 32 bytes → use as-is (AES-256)
            - > 32 bytes → truncate to 32 bytes

        Args:
            raw_key: The raw key bytes (decoded from base64).

        Returns:
            A 16-byte or 32-byte AES key.
        """
        if len(raw_key) == 1 and raw_key[0] == 0x01:
            return _DEFAULT_KEY

        length = len(raw_key)
        if length <= 16:
            return raw_key.ljust(16, b"\x00")
        if length <= 32:
            return raw_key.ljust(32, b"\x00")
        return raw_key[:32]

    def build_nonce(self, packet_id: int, from_node_id: int) -> bytes:
        """Build a 16-byte AES-CTR nonce from packet ID and sender node ID.

        The nonce is constructed as:
            packet_id (8 bytes, little-endian) + from_node_id (8 bytes, little-endian)

        Args:
            packet_id: The packet identifier.
            from_node_id: The sender's node identifier.

        Returns:
            A 16-byte nonce.
        """
        return packet_id.to_bytes(8, "little") + from_node_id.to_bytes(8, "little")

    def decrypt_payload(
        self,
        encrypted: bytes,
        channel: str,
        packet_id: int,
        from_node_id: int,
    ) -> bytes | None:
        """Decrypt an encrypted MeshPacket payload using AES-CTR.

        Args:
            encrypted: The encrypted payload bytes.
            channel: The channel name used to look up the decryption key.
            packet_id: The packet ID (used for nonce construction).
            from_node_id: The sender node ID (used for nonce construction).

        Returns:
            The decrypted payload bytes, or None if decryption fails.
        """
        key = self._channel_keys.get(channel)
        if key is None:
            LOGGER.debug("No key configured for channel '%s', skipping decryption", channel)
            return None

        try:
            nonce = self.build_nonce(packet_id, from_node_id)
            cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
            decryptor = cipher.decryptor()
            return decryptor.update(encrypted) + decryptor.finalize()
        except Exception:
            LOGGER.debug("Decryption failed for channel '%s'", channel, exc_info=True)
            return None

    def extract_channel_from_topic(self, topic: str) -> str:
        """Extract the channel name from an MQTT topic string.

        Locates the protocol version ``2`` followed by a type indicator
        (``e``, ``c``, or ``json``) and returns the next segment as the
        channel name.

        Supports standard format: msh/{region}/2/e/{channel}
        Extended format: msh/{region}/{area}/{network}/2/e/{channel}
        JSON format: msh/{region}/2/json/{channel}

        Args:
            topic: The MQTT topic string.

        Returns:
            The extracted channel name, or "unknown" if not found.
        """
        parts = topic.split("/")
        for i, part in enumerate(parts):
            if (
                part in _TYPE_INDICATORS
                and i >= 1
                and parts[i - 1] == "2"
                and i + 1 < len(parts)
            ):
                return parts[i + 1]
        return "unknown"

    def decode_to_mesh_packet(
        self, topic: str, payload: bytes
    ) -> mesh_pb2.MeshPacket | None:
        """Decode an MQTT message into a MeshPacket.

        Parsing strategy:
            1. Try parsing as ServiceEnvelope, extract MeshPacket
            2. Fall back to parsing directly as MeshPacket
            3. Handle JSON-format topics
            4. Decrypt encrypted payloads if a channel key is available

        Args:
            topic: The MQTT topic the message was received on.
            payload: The raw message payload bytes.

        Returns:
            A decoded MeshPacket, or None if parsing/decryption fails.
        """
        if not payload:
            return None

        channel = self.extract_channel_from_topic(topic)

        # Check if this is a JSON-format topic
        if "/json/" in topic:
            return self._handle_json_message(payload, channel)

        # Try ServiceEnvelope first
        mesh_packet = self._try_parse_service_envelope(payload)

        # Fall back to direct MeshPacket parsing
        if mesh_packet is None:
            mesh_packet = self._try_parse_mesh_packet(payload)

        if mesh_packet is None:
            LOGGER.debug("Failed to parse payload from topic '%s'", topic)
            return None

        # If the packet has an encrypted payload, attempt decryption
        if mesh_packet.HasField("encrypted") and mesh_packet.encrypted:
            return self._decrypt_mesh_packet(mesh_packet, channel)

        return mesh_packet

    def _try_parse_service_envelope(
        self, payload: bytes
    ) -> mesh_pb2.MeshPacket | None:
        """Try to parse payload as a ServiceEnvelope and extract MeshPacket."""
        try:
            envelope = mqtt_pb2.ServiceEnvelope()
            envelope.ParseFromString(payload)
            if envelope.HasField("packet"):
                return envelope.packet
        except Exception:
            LOGGER.debug("ServiceEnvelope parsing failed", exc_info=True)
        return None

    def _try_parse_mesh_packet(
        self, payload: bytes
    ) -> mesh_pb2.MeshPacket | None:
        """Try to parse payload directly as a MeshPacket."""
        try:
            packet = mesh_pb2.MeshPacket()
            packet.ParseFromString(payload)
            # Verify we got something meaningful by checking for a non-zero id or from
            if packet.id != 0 or getattr(packet, "from") != 0:
                return packet
        except Exception:
            LOGGER.debug("Direct MeshPacket parsing failed", exc_info=True)
        return None

    def _handle_json_message(
        self, payload: bytes, channel: str
    ) -> mesh_pb2.MeshPacket | None:
        """Handle a JSON-format MQTT message.

        Extracts type, from, to, and payload fields from the JSON and
        constructs a MeshPacket with a decoded Data payload.

        Args:
            payload: The raw JSON payload bytes.
            channel: The channel name extracted from the topic.

        Returns:
            A MeshPacket with decoded data, or None on failure.
        """
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            LOGGER.debug("Invalid JSON payload")
            return None

        if not isinstance(data, dict):
            LOGGER.debug("JSON payload is not an object")
            return None

        try:
            packet = mesh_pb2.MeshPacket()

            if "from" in data:
                packet.__setattr__("from", int(data["from"]))
            if "to" in data:
                packet.to = int(data["to"])
            if "id" in data:
                packet.id = int(data["id"])
            if "channel" in data:
                packet.channel = int(data["channel"])

            # Build decoded Data from the JSON payload field
            if "type" in data or "payload" in data:
                decoded = packet.decoded
                if "type" in data:
                    # Try to map the type string to a PortNum value
                    type_str = str(data["type"]).upper()
                    try:
                        decoded.portnum = portnums_pb2.PortNum.Value(type_str)
                    except ValueError:
                        # If it's a numeric value, use it directly
                        try:
                            decoded.portnum = int(data["type"])
                        except (ValueError, TypeError):
                            pass
                if "payload" in data:
                    payload_val = data["payload"]
                    if isinstance(payload_val, str):
                        decoded.payload = payload_val.encode("utf-8")
                    elif isinstance(payload_val, dict):
                        decoded.payload = json.dumps(payload_val).encode("utf-8")
                    elif isinstance(payload_val, bytes):
                        decoded.payload = payload_val

            return packet
        except Exception:
            LOGGER.debug("Failed to construct MeshPacket from JSON", exc_info=True)
            return None

    def _decrypt_mesh_packet(
        self, packet: mesh_pb2.MeshPacket, channel: str
    ) -> mesh_pb2.MeshPacket | None:
        """Attempt to decrypt an encrypted MeshPacket.

        Args:
            packet: The MeshPacket with encrypted payload.
            channel: The channel name for key lookup.

        Returns:
            The MeshPacket with decrypted decoded data, or None on failure.
        """
        from_node_id = getattr(packet, "from")
        decrypted = self.decrypt_payload(
            packet.encrypted, channel, packet.id, from_node_id
        )
        if decrypted is None:
            return None

        try:
            data = mesh_pb2.Data()
            data.ParseFromString(decrypted)
            packet.decoded.CopyFrom(data)
            # Clear the encrypted field since we've decoded it
            packet.ClearField("encrypted")
            return packet
        except Exception:
            LOGGER.debug("Failed to parse decrypted payload as Data protobuf", exc_info=True)
            return None

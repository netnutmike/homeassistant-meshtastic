# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

import contextlib

from .connection.tcp import TcpConnection
from .interface import MeshInterface

_interface = [MeshInterface, TcpConnection]

with contextlib.suppress(ImportError):
    from .connection.serial import SerialConnection

    _interface.append(SerialConnection)

with contextlib.suppress(ImportError):
    from .connection.bluetooth import BluetoothConnection

    _interface.append(BluetoothConnection)

with contextlib.suppress(ImportError):
    from .connection.mqtt import MqttConnection

    _interface.append(MqttConnection)


__all__ = list(_interface)

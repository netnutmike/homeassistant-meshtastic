# SPDX-FileCopyrightText: 2024-2025 Pascal Brogle @broglep
#
# SPDX-License-Identifier: MIT

from .version import VERSION

__all__ = ["VERSION", "locate_dir"]


def locate_dir() -> str:
    return __path__[0]

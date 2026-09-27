"""
py439 - Bit buffer for storing and manipulating packet bits.

Copyright (C) 2026 R4SCS (https://github.com/R4SCS/)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
"""
from typing import List, Optional


class BitBuffer:
    """Bit buffer for storing received bits with pulse/gap metadata."""

    def __init__(self):
        self.bits: List[int] = []
        self.gaps: List[int] = []
        self.pulses: List[int] = []

    def __len__(self):
        return len(self.bits)

    def __getitem__(self, idx):
        return self.bits[idx]

    def add_bit(self, bit: int, pulse: int = 0, gap: int = 0):
        """Append a single bit with optional pulse/gap timing metadata."""
        self.bits.append(bit & 1)
        self.pulses.append(pulse)
        self.gaps.append(gap)

    def add_bits(self, data: bytes):
        """Append bits from raw bytes (MSB first)."""
        for byte in data:
            for i in range(7, -1, -1):
                self.bits.append((byte >> i) & 1)
                self.pulses.append(0)
                self.gaps.append(0)

    def clear(self):
        """Clear all stored bits and timing data."""
        self.bits.clear()
        self.gaps.clear()
        self.pulses.clear()

    def extract_bytes(self, pos: int, count: int) -> bytes:
        """Extract 'count' bytes starting at bit position 'pos'."""
        result = bytearray()
        for i in range(count):
            byte_pos = pos + i * 8
            if byte_pos + 7 >= len(self.bits):
                break
            val = 0
            for j in range(8):
                val = (val << 1) | self.bits[byte_pos + j]
            result.append(val)
        return bytes(result)

    def extract_bits(self, pos: int, count: int) -> int:
        """Extract 'count' bits starting at bit position 'pos' as an integer."""
        val = 0
        for i in range(count):
            if pos + i >= len(self.bits):
                break
            val = (val << 1) | self.bits[pos + i]
        return val

    def to_hex(self) -> str:
        """Convert bits to hexadecimal string representation."""
        result = []
        for i in range(0, len(self.bits) - 7, 8):
            val = 0
            for j in range(8):
                val = (val << 1) | self.bits[i + j]
            result.append(f"{val:02X}")
        return "".join(result)

    def to_binary_string(self) -> str:
        """Convert bits to binary string representation."""
        return "".join(str(b) for b in self.bits)

    def reverse_bytes(self) -> "BitBuffer":
        """Return a new BitBuffer with bit order reversed within each byte."""
        new = BitBuffer()
        for i in range(0, len(self.bits), 8):
            chunk = self.bits[i:i + 8]
            pulses = self.pulses[i:i + 8]
            gaps = self.gaps[i:i + 8]
            for k in range(len(chunk) - 1, -1, -1):
                new.bits.append(chunk[k])
                new.pulses.append(pulses[k])
                new.gaps.append(gaps[k])
        return new

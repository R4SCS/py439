"""
py439 - Protocol decoders for 433.92 MHz wireless sensors and devices.

Clean-room implementation based on public protocol documentation.
No code from rtl_433 or other GPL projects was used as source material.

Sources:
  - wmrx00 Oregon Scientific RF Protocols PDF
  - aquaticus/nexus433 independent documentation
  - Hackaday reverse-engineering projects (Acurite, Maverick)
  - Arduino Forum community reverse-engineering (LaCrosse)
  - pilight protocol documentation (public specs)
  - RCSwitch protocol documentation (public specs)
  - onetransistor.eu, fetzerch.github.io, tommie.github.io
  - goughlui.com (Efergy reverse-engineering)

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
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from bitbuffer import BitBuffer


@dataclass
class Device:
    """Decoded device data."""
    protocol: str = ""
    id: str = ""
    channel: int = 0
    battery: str = ""
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_dir: Optional[float] = None
    rain: Optional[float] = None
    uv: Optional[float] = None
    lux: Optional[float] = None
    raw: str = ""
    rssi: int = 0
    crc_ok: bool = True


class Protocol:
    """Base class for protocol decoders."""
    name: str = "Unknown"
    modulation: str = "OOK_PWM"
    min_bits: int = 0
    max_bits: int = 9999

    def decode(self, bits: BitBuffer) -> Optional[Device]:
        return None

    def _checksum_add(self, bits: BitBuffer, start: int, length: int) -> int:
        """Sum of bytes, return lowest 8 bits."""
        total = 0
        for i in range(start, min(start + length * 8, len(bits) - 7), 8):
            total += bits.extract_bits(i, 8)
        return total & 0xFF

    def _xor_bytes(self, bits: BitBuffer, start: int, count: int) -> int:
        """XOR of 'count' bytes starting at bit position 'start'."""
        val = 0
        for i in range(count):
            val ^= bits.extract_bits(start + i * 8, 8)
        return val

    def _lfsr_digest(self, bits: BitBuffer, start: int, length: int, key: int) -> int:
        """LFSR digest for checksum verification."""
        digest = key & 0xFF
        for i in range(start, min(start + length, len(bits))):
            if bits[i]:
                digest = ((digest << 1) & 0xFF) ^ 0x31
            else:
                digest = (digest << 1) & 0xFF
        return digest

    def _signed(self, val: int, bits: int) -> int:
        """Convert unsigned value to signed if MSB is set."""
        if val & (1 << (bits - 1)):
            val -= (1 << bits)
        return val


# ============================================================
# WEATHER SENSORS - Thermohygrometers
# ============================================================

class Nexus(Protocol):
    """Nexus TH sensor (aquaticus/nexus433 documentation)."""
    name = "Nexus-TH"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        hdr = bits.extract_bits(0, 8)
        if hdr != 0x29: return None
        dev_id = bits.extract_bits(8, 6)
        ch = bits.extract_bits(14, 2) + 1
        bat = bits.extract_bits(16, 1)
        temp_raw = bits.extract_bits(17, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(29, 7)
        if hum > 100: return None
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      battery="OK" if bat else "LOW", temperature=round(temp, 1),
                      humidity=hum if hum > 0 else None, crc_ok=True)


class Rubicson(Protocol):
    """Rubicson TH sensor."""
    name = "Rubicson"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        if bits.extract_bits(0, 8) != 0x81: return None
        dev_id = bits.extract_bits(8, 4)
        ch = bits.extract_bits(14, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:X}", channel=ch,
                      temperature=round(temp, 1), crc_ok=True)


class Prologue(Protocol):
    """Prologue TH sensor."""
    name = "Prologue-TH"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        if bits.extract_bits(0, 8) != 0x2E: return None
        dev_id = bits.extract_bits(8, 6)
        ch = bits.extract_bits(14, 2) + 1
        bat = bits.extract_bits(16, 1)
        temp_raw = bits.extract_bits(17, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(29, 7)
        if hum > 100: return None
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      battery="OK" if bat else "LOW", temperature=round(temp, 1),
                      humidity=hum if hum > 0 else None)


class Acurite592TXR(Protocol):
    """Acurite 592TXR sensor (Hackaday reverse-engineering)."""
    name = "Acurite-592TXR"
    min_bits = 56
    max_bits = 56

    def decode(self, bits):
        if len(bits) != 56: return None
        if bits.extract_bits(0, 8) != 0x24: return None
        dev_id = bits.extract_bits(8, 16)
        bat = bits.extract_bits(24, 1)
        ch = bits.extract_bits(33, 2) + 1
        temp_raw = bits.extract_bits(36, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1 - 100
        hum = bits.extract_bits(48, 8)
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=ch,
                      battery="OK" if bat else "LOW", temperature=round(temp, 1),
                      humidity=hum if hum > 0 else None, crc_ok=True)


class Acurite609TXC(Protocol):
    """Acurite 609TXC sensor."""
    name = "Acurite-609TXC"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        if bits.extract_bits(0, 8) != 0x25: return None
        dev_id = bits.extract_bits(8, 8)
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1), humidity=hum if 0 < hum <= 100 else None)


class Acurite606TX(Protocol):
    """Acurite 606TX temperature-only sensor."""
    name = "Acurite-606TX"
    min_bits = 32
    max_bits = 32

    def decode(self, bits):
        if len(bits) != 32: return None
        if bits.extract_bits(0, 8) != 0x28: return None
        dev_id = bits.extract_bits(8, 8)
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1 - 40
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1))


class Acurite986(Protocol):
    """Acurite 986 fridge/freezer sensor."""
    name = "Acurite-986"
    min_bits = 56
    max_bits = 56

    def decode(self, bits):
        if len(bits) != 56: return None
        if bits.extract_bits(0, 8) != 0x29: return None
        dev_id = bits.extract_bits(8, 8)
        probe = bits.extract_bits(16, 2)
        temp_raw = bits.extract_bits(24, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=probe + 1,
                      temperature=round(temp, 1))


class FineOffsetWH2(Protocol):
    """Fine Offset WH2 sensor (ESPHome community documentation)."""
    name = "Fineoffset-WH2"
    min_bits = 48
    max_bits = 48

    def decode(self, bits):
        if len(bits) != 48: return None
        dev_id = bits.extract_bits(0, 16)
        temp_raw = bits.extract_bits(24, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(36, 8)
        chk = bits.extract_bits(40, 8)
        chk_calc = self._checksum_add(bits, 0, 5)
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=1,
                      temperature=round(temp, 1), humidity=hum if hum <= 100 else None,
                      crc_ok=(chk == chk_calc))


class FineOffsetWH1080(Protocol):
    """Fine Offset WH1080 weather station (sevenwatt.com documentation)."""
    name = "Fineoffset-WH1080"
    min_bits = 80
    max_bits = 240

    def decode(self, bits):
        if len(bits) < 80: return None
        if bits.extract_bits(0, 8) != 0xA1: return None
        dev_id = bits.extract_bits(8, 8)
        temp_raw = bits.extract_bits(32, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(44, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class OregonV2(Protocol):
    """Oregon Scientific v2.1 protocol (wmrx00 PDF documentation)."""
    name = "Oregon-THGN132N"
    min_bits = 80
    max_bits = 96

    def decode(self, bits):
        if len(bits) < 80: return None
        # Oregon v2.1 sync preamble: 0xFA (reversed nibbles)
        sync = bits.extract_bits(0, 8)
        if sync not in (0xFA, 0xAF): return None
        # Device ID (2 bytes, nibble-reversed)
        raw_id = bits.extract_bits(16, 16)
        dev_id = ((raw_id >> 4) & 0xF) | ((raw_id & 0xF) << 4)
        dev_id = ((dev_id >> 4) & 0xF) | ((dev_id & 0xF) << 4)
        channel = bits.extract_bits(36, 4)
        rolling = bits.extract_bits(40, 8)
        temp_raw = bits.extract_bits(52, 12)
        # Oregon sends nibbles in reversed order
        t1 = (temp_raw >> 8) & 0xF
        t2 = (temp_raw >> 4) & 0xF
        t3 = temp_raw & 0xF
        temp_val = t2 * 10 + t1 + t3 * 0.1
        if t2 & 0x8: temp_val = -(temp_val & 0x7F)  # negative temperature
        hum_raw = bits.extract_bits(64, 8)
        h1 = (hum_raw >> 4) & 0xF
        h2 = hum_raw & 0xF
        hum = h1 * 10 + h2
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp_val, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class OregonTHGR810(Protocol):
    """Oregon Scientific THGR810 (v3.0 protocol, wmrx00 PDF)."""
    name = "Oregon-THGR810"
    min_bits = 96
    max_bits = 120

    def decode(self, bits):
        if len(bits) < 96: return None
        sync = bits.extract_bits(0, 8)
        if sync != 0xA1: return None
        dev_id = bits.extract_bits(8, 16)
        channel = bits.extract_bits(28, 4)
        rolling = bits.extract_bits(32, 8)
        temp_raw = bits.extract_bits(44, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum_raw = bits.extract_bits(56, 8)
        hum = ((hum_raw >> 4) & 0xF) * 10 + (hum_raw & 0xF)
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class OregonBTHGN129(Protocol):
    """Oregon Scientific BTHGN129 (v3.0 with pressure)."""
    name = "Oregon-BTHGN129"
    min_bits = 128
    max_bits = 160

    def decode(self, bits):
        if len(bits) < 128: return None
        sync = bits.extract_bits(0, 8)
        if sync != 0xA1: return None
        dev_id = bits.extract_bits(8, 16)
        channel = bits.extract_bits(28, 4)
        temp_raw = bits.extract_bits(44, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum_raw = bits.extract_bits(56, 8)
        hum = ((hum_raw >> 4) & 0xF) * 10 + (hum_raw & 0xF)
        press_raw = bits.extract_bits(72, 16)
        pressure = press_raw / 10.0
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None,
                      pressure=round(pressure, 1) if pressure > 800 else None)


class OregonWGR800(Protocol):
    """Oregon Scientific WGR800 wind sensor (v3.0)."""
    name = "Oregon-WGR800"
    min_bits = 112
    max_bits = 140

    def decode(self, bits):
        if len(bits) < 112: return None
        sync = bits.extract_bits(0, 8)
        if sync != 0xA1: return None
        dev_id = bits.extract_bits(8, 16)
        channel = bits.extract_bits(28, 4)
        wind_raw = bits.extract_bits(44, 12)
        wind = wind_raw * 0.1
        gust_raw = bits.extract_bits(60, 12)
        gust = gust_raw * 0.1
        dir_raw = bits.extract_bits(76, 9)
        direction = dir_raw * 1.0
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      wind_speed=round(wind, 1), wind_dir=round(direction, 0))


class OregonPCR800(Protocol):
    """Oregon Scientific PCR800 rain gauge (v3.0)."""
    name = "Oregon-PCR800"
    min_bits = 128
    max_bits = 160

    def decode(self, bits):
        if len(bits) < 128: return None
        sync = bits.extract_bits(0, 8)
        if sync != 0xA1: return None
        dev_id = bits.extract_bits(8, 16)
        channel = bits.extract_bits(28, 4)
        rain_raw = bits.extract_bits(52, 16)
        rain = rain_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      rain=round(rain, 1))


class OregonUVN800(Protocol):
    """Oregon Scientific UVN800 UV sensor (v3.0)."""
    name = "Oregon-UVN800"
    min_bits = 96
    max_bits = 120

    def decode(self, bits):
        if len(bits) < 96: return None
        sync = bits.extract_bits(0, 8)
        if sync != 0xA1: return None
        dev_id = bits.extract_bits(8, 16)
        channel = bits.extract_bits(28, 4)
        uv_raw = bits.extract_bits(44, 8)
        uv = uv_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      uv=round(uv, 1))


class OregonTHN132N(Protocol):
    """Oregon Scientific THN132N temperature sensor (v2.1)."""
    name = "Oregon-THN132N"
    min_bits = 64
    max_bits = 80

    def decode(self, bits):
        if len(bits) < 64: return None
        sync = bits.extract_bits(0, 8)
        if sync not in (0xFA, 0xAF): return None
        raw_id = bits.extract_bits(16, 16)
        dev_id = ((raw_id >> 4) & 0xF) | ((raw_id & 0xF) << 4)
        dev_id = ((dev_id >> 4) & 0xF) | ((dev_id & 0xF) << 4)
        channel = bits.extract_bits(36, 4)
        temp_raw = bits.extract_bits(52, 12)
        t1 = (temp_raw >> 8) & 0xF
        t2 = (temp_raw >> 4) & 0xF
        t3 = temp_raw & 0xF
        temp_val = t2 * 10 + t1 + t3 * 0.1
        if t2 & 0x8: temp_val = -(temp_val & 0x7F)
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp_val, 1))


class OregonTHWR288A(Protocol):
    """Oregon Scientific THWR288A (v2.1)."""
    name = "Oregon-THWR288A"
    min_bits = 64
    max_bits = 80

    def decode(self, bits):
        if len(bits) < 64: return None
        sync = bits.extract_bits(0, 8)
        if sync not in (0xFA, 0xAF): return None
        raw_id = bits.extract_bits(16, 16)
        dev_id = ((raw_id >> 4) & 0xF) | ((raw_id & 0xF) << 4)
        dev_id = ((dev_id >> 4) & 0xF) | ((dev_id & 0xF) << 4)
        channel = bits.extract_bits(36, 4)
        temp_raw = bits.extract_bits(52, 12)
        t1 = (temp_raw >> 8) & 0xF
        t2 = (temp_raw >> 4) & 0xF
        t3 = temp_raw & 0xF
        temp_val = t2 * 10 + t1 + t3 * 0.1
        if t2 & 0x8: temp_val = -(temp_val & 0x7F)
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp_val, 1))


class OregonRTHN129(Protocol):
    """Oregon Scientific RTHN129 (v2.1)."""
    name = "Oregon-RTHN129"
    min_bits = 64
    max_bits = 80

    def decode(self, bits):
        if len(bits) < 64: return None
        sync = bits.extract_bits(0, 8)
        if sync not in (0xFA, 0xAF): return None
        raw_id = bits.extract_bits(16, 16)
        dev_id = ((raw_id >> 4) & 0xF) | ((raw_id & 0xF) << 4)
        dev_id = ((dev_id >> 4) & 0xF) | ((dev_id & 0xF) << 4)
        channel = bits.extract_bits(36, 4)
        temp_raw = bits.extract_bits(52, 12)
        t1 = (temp_raw >> 8) & 0xF
        t2 = (temp_raw >> 4) & 0xF
        t3 = temp_raw & 0xF
        temp_val = t2 * 10 + t1 + t3 * 0.1
        if t2 & 0x8: temp_val = -(temp_val & 0x7F)
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp_val, 1))


class OregonTHGR228N(Protocol):
    """Oregon Scientific THGR228N (v2.1)."""
    name = "Oregon-THGR228N"
    min_bits = 80
    max_bits = 96

    def decode(self, bits):
        if len(bits) < 80: return None
        sync = bits.extract_bits(0, 8)
        if sync not in (0xFA, 0xAF): return None
        raw_id = bits.extract_bits(16, 16)
        dev_id = ((raw_id >> 4) & 0xF) | ((raw_id & 0xF) << 4)
        dev_id = ((dev_id >> 4) & 0xF) | ((dev_id & 0xF) << 4)
        channel = bits.extract_bits(36, 4)
        temp_raw = bits.extract_bits(52, 12)
        t1 = (temp_raw >> 8) & 0xF
        t2 = (temp_raw >> 4) & 0xF
        t3 = temp_raw & 0xF
        temp_val = t2 * 10 + t1 + t3 * 0.1
        if t2 & 0x8: temp_val = -(temp_val & 0x7F)
        hum_raw = bits.extract_bits(64, 8)
        h1 = (hum_raw >> 4) & 0xF
        h2 = hum_raw & 0xF
        hum = h1 * 10 + h2
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp_val, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class OregonRTGR328N(Protocol):
    """Oregon Scientific RTGR328N (v2.1 with time)."""
    name = "Oregon-RTGR328N"
    min_bits = 120
    max_bits = 160

    def decode(self, bits):
        if len(bits) < 120: return None
        sync = bits.extract_bits(0, 8)
        if sync not in (0xFA, 0xAF): return None
        raw_id = bits.extract_bits(16, 16)
        dev_id = ((raw_id >> 4) & 0xF) | ((raw_id & 0xF) << 4)
        dev_id = ((dev_id >> 4) & 0xF) | ((dev_id & 0xF) << 4)
        channel = bits.extract_bits(36, 4)
        temp_raw = bits.extract_bits(52, 12)
        t1 = (temp_raw >> 8) & 0xF
        t2 = (temp_raw >> 4) & 0xF
        t3 = temp_raw & 0xF
        temp_val = t2 * 10 + t1 + t3 * 0.1
        if t2 & 0x8: temp_val = -(temp_val & 0x7F)
        hum_raw = bits.extract_bits(64, 8)
        h1 = (hum_raw >> 4) & 0xF
        h2 = hum_raw & 0xF
        hum = h1 * 10 + h2
        return Device(protocol=self.name, id=f"{dev_id:04X}", channel=channel,
                      temperature=round(temp_val, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class LaCrosseTX141TH(Protocol):
    """LaCrosse TX141TH sensor (Arduino Forum reverse-engineering)."""
    name = "LaCrosse-TX141TH"
    min_bits = 41
    max_bits = 41

    def decode(self, bits):
        if len(bits) < 40: return None
        if bits.extract_bits(0, 8) != 0x09: return None
        dev_id = bits.extract_bits(8, 6)
        ch = bits.extract_bits(14, 2) + 1
        bat = bits.extract_bits(16, 1)
        temp_raw = bits.extract_bits(24, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(36, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      battery="OK" if bat else "LOW", temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class LaCrosseTX147(Protocol):
    """LaCrosse TX147 sensor (Stack Overflow reverse-engineering)."""
    name = "LaCrosse-TX147"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        if bits.extract_bits(0, 8) != 0x07: return None
        dev_id = bits.extract_bits(8, 8)
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1))


class TX07K(Protocol):
    """TX07K / WEC-2103 sensor (tommie.github.io reverse-engineering)."""
    name = "TX07K-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(28, 8)
        # Checksum: sum of all nibbles
        chk = bits.extract_bits(36, 4)
        chk_calc = 0
        for i in range(0, 36, 4):
            chk_calc += bits.extract_bits(i, 4)
        chk_calc &= 0xF
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None,
                      crc_ok=(chk == chk_calc))


class AlectoV1(Protocol):
    """Alecto V1 weather station (pilight documentation)."""
    name = "Alecto-V1"
    min_bits = 56
    max_bits = 56

    def decode(self, bits):
        if len(bits) != 56: return None
        dev_id = bits.extract_bits(0, 8)
        temp_raw = bits.extract_bits(12, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(36, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class AlectoV2(Protocol):
    """Alecto V2 weather station (pilight documentation)."""
    name = "Alecto-V2"
    min_bits = 72
    max_bits = 72

    def decode(self, bits):
        if len(bits) != 72: return None
        dev_id = bits.extract_bits(0, 12)
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(40, 8)
        return Device(protocol=self.name, id=f"{dev_id:03X}", channel=1,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class AlectoDCF(Protocol):
    """Alecto DCF variant (pilight documentation)."""
    name = "Alecto-DCF"
    min_bits = 64
    max_bits = 64

    def decode(self, bits):
        if len(bits) != 64: return None
        dev_id = bits.extract_bits(0, 8)
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1))


class TFA30_3151(Protocol):
    """TFA 30.3151 weather sensor (pilight documentation)."""
    name = "TFA-30.3151"
    min_bits = 64
    max_bits = 64

    def decode(self, bits):
        if len(bits) != 64: return None
        dev_id = bits.extract_bits(0, 8)
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class TFA30_3208(Protocol):
    """TFA 30.3208 rain gauge (pilight documentation)."""
    name = "TFA-30.3208"
    min_bits = 52
    max_bits = 52

    def decode(self, bits):
        if len(bits) != 52: return None
        dev_id = bits.extract_bits(0, 8)
        rain_raw = bits.extract_bits(20, 16)
        rain = rain_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      rain=round(rain, 1))


class AuriolH13726(Protocol):
    """Auriol H13726 TH sensor (platenspeler documentation)."""
    name = "Auriol-H13726"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        if bits.extract_bits(0, 8) != 0x01: return None
        dev_id = bits.extract_bits(8, 6)
        ch = bits.extract_bits(14, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1))


class AuriolAHFL(Protocol):
    """Auriol AHFL sensor (platenspeler documentation)."""
    name = "Auriol-AHFL"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        if bits.extract_bits(0, 8) != 0x53: return None
        dev_id = bits.extract_bits(8, 6)
        ch = bits.extract_bits(14, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class WT440H(Protocol):
    """WT440H weather sensor (platenspeler documentation)."""
    name = "WT440H"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class GTWT02(Protocol):
    """GT-WT-02 sensor (onetransistor.eu documentation)."""
    name = "GT-WT-02"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        dev_id = bits.extract_bits(0, 4)
        ch = bits.extract_bits(4, 2) + 1
        temp_raw = bits.extract_bits(12, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(24, 8)
        return Device(protocol=self.name, id=f"{dev_id:X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class Teknihall(Protocol):
    """Teknihall TH sensor (pilight documentation)."""
    name = "Teknihall-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class NinjaBlocks(Protocol):
    """Ninja Blocks TH sensor (pilight documentation)."""
    name = "Ninja-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(28, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class Meteoscan(Protocol):
    """Meteoscan weather sensor."""
    name = "Meteoscan-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 6)
        ch = bits.extract_bits(6, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(28, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class Dostmann(Protocol):
    """Dostmann P7704 TH sensor."""
    name = "Dostmann-P7704"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class Soens(Protocol):
    """Soens TH sensor."""
    name = "Soens-TH"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1))


class TCM(Protocol):
    """TCM weather sensor."""
    name = "TCM-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 4)
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class IBoutique(Protocol):
    """iBoutique TH sensor."""
    name = "iBoutique-TH"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        dev_id = bits.extract_bits(0, 6)
        ch = bits.extract_bits(6, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(28, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class Ventus(Protocol):
    """Ventus TH sensor."""
    name = "Ventus-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class Balance(Protocol):
    """Balance TH sensor."""
    name = "Balance-TH"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1))


class ConradS3318P(Protocol):
    """Conrad S3318P weather station."""
    name = "Conrad-S3318P"
    min_bits = 40
    max_bits = 40

    def decode(self, bits):
        if len(bits) != 40: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(32, 8)
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if 0 < hum <= 100 else None)


class GenericTH(Protocol):
    """Generic 433MHz TH sensor (fetzerch.github.io reverse-engineering)."""
    name = "Generic-TH"
    min_bits = 36
    max_bits = 48

    def decode(self, bits):
        if len(bits) < 36: return None
        dev_id = bits.extract_bits(0, 8)
        ch = bits.extract_bits(8, 2) + 1
        temp_raw = bits.extract_bits(16, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        hum = bits.extract_bits(28, 8) if len(bits) >= 36 else None
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=ch,
                      temperature=round(temp, 1),
                      humidity=hum if hum and 0 < hum <= 100 else None)


class GenericTemp(Protocol):
    """Generic temperature-only sensor."""
    name = "Generic-Temp"
    min_bits = 24
    max_bits = 36

    def decode(self, bits):
        if len(bits) < 24: return None
        dev_id = bits.extract_bits(0, 8)
        temp_raw = bits.extract_bits(8, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp, 1))


# ============================================================
# BBQ / COOKING SENSORS
# ============================================================

class MaverickET732(Protocol):
    """Maverick ET-732 BBQ thermometer (Hackaday reverse-engineering by Bob Blake)."""
    name = "Maverick-ET732"
    min_bits = 48
    max_bits = 48

    def decode(self, bits):
        if len(bits) != 48: return None
        if bits.extract_bits(0, 8) != 0x00: return None
        dev_id = bits.extract_bits(8, 8)
        temp1_raw = bits.extract_bits(24, 12)
        temp1_raw = self._signed(temp1_raw, 12)
        temp1 = temp1_raw + 200  # offset per Hackaday analysis
        temp2_raw = bits.extract_bits(36, 12)
        temp2_raw = self._signed(temp2_raw, 12)
        temp2 = temp2_raw + 200
        return Device(protocol=self.name, id=f"{dev_id:02X}", channel=1,
                      temperature=round(temp1, 1), crc_ok=True,
                      raw=f"t1={temp1:.1f} t2={temp2:.1f}")


# ============================================================
# RELAYS / REMOTES (RCSwitch protocol documentation)
# ============================================================

class RCSwitch1(Protocol):
    """RCSwitch protocol 1 - 12-bit tristate (RCSwitch docs)."""
    name = "RCSwitch-1"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        group = bits.extract_bits(0, 5)
        device = bits.extract_bits(5, 5)
        state = bits.extract_bits(10, 2)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"grp={group} dev={device} state={'ON' if state else 'OFF'}")


class RCSwitch2(Protocol):
    """RCSwitch protocol 2 - 12-bit (RCSwitch docs)."""
    name = "RCSwitch-2"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"code={code:06X}")


class RCSwitch3(Protocol):
    """RCSwitch protocol 3 - 12-bit (RCSwitch docs)."""
    name = "RCSwitch-3"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"code={code:06X}")


class RCSwitch4(Protocol):
    """RCSwitch protocol 4 - 12-bit (RCSwitch docs)."""
    name = "RCSwitch-4"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"code={code:06X}")


class RCSwitch5(Protocol):
    """RCSwitch protocol 5 - 36-bit (RCSwitch docs)."""
    name = "RCSwitch-5"
    min_bits = 36
    max_bits = 36

    def decode(self, bits):
        if len(bits) != 36: return None
        code = bits.extract_bits(0, 36)
        return Device(protocol=self.name, id=f"{code:09X}", channel=1,
                      raw=f"code={code:09X}")


class Intertechno(Protocol):
    """Intertechno remote (pilight documentation)."""
    name = "Intertechno"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class KaKu(Protocol):
    """KlikAanKlikUit remote (pilight documentation)."""
    name = "KaKu"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class Nexa(Protocol):
    """Nexa remote (pilight documentation)."""
    name = "Nexa"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class ElroHE300(Protocol):
    """Elro HE300 remote (pilight documentation)."""
    name = "Elro-HE300"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"code={code:06X}")


class SC2262(Protocol):
    """SC2262 encoder remote (pilight documentation)."""
    name = "SC2262"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class Beamish(Protocol):
    """Beamish remote (pilight documentation)."""
    name = "Beamish"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class Brennenstuhl(Protocol):
    """Brennenstuhl remote (pilight documentation)."""
    name = "Brennenstuhl"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"code={code:06X}")


class ByeByeStandby(Protocol):
    """Bye Bye Standby remote (pilight documentation)."""
    name = "ByeByeStandby"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class Clarus(Protocol):
    """Clarus remote (pilight documentation)."""
    name = "Clarus"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


class Cleverwatts(Protocol):
    """Cleverwatts remote (pilight documentation)."""
    name = "Cleverwatts"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 24)
        return Device(protocol=self.name, id=f"{code:06X}", channel=1,
                      raw=f"code={code:06X}")


class CoCo(Protocol):
    """CoCo remote (pilight documentation)."""
    name = "CoCo"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"code={code:03X}")


# ============================================================
# SECURITY SENSORS
# ============================================================

class KaKuContact(Protocol):
    """KaKu contact sensor (pilight documentation)."""
    name = "KaKu-Contact"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        open_state = bits.extract_bits(10, 1)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"open={'YES' if open_state else 'NO'}")


class SC2262Contact(Protocol):
    """SC2262 contact sensor (pilight documentation)."""
    name = "SC2262-Contact"
    min_bits = 12
    max_bits = 12

    def decode(self, bits):
        if len(bits) != 12: return None
        code = bits.extract_bits(0, 12)
        open_state = bits.extract_bits(10, 1)
        return Device(protocol=self.name, id=f"{code:03X}", channel=1,
                      raw=f"open={'YES' if open_state else 'NO'}")


class EV1527Contact(Protocol):
    """EV1527 contact sensor."""
    name = "EV1527-Contact"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 20)
        state = bits.extract_bits(20, 4)
        return Device(protocol=self.name, id=f"{code:05X}", channel=1,
                      raw=f"state={state:01X}")


class KERUID026(Protocol):
    """KERUI D026 door sensor (pilight documentation)."""
    name = "KERUI-D026"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 20)
        state = bits.extract_bits(20, 4)
        return Device(protocol=self.name, id=f"{code:05X}", channel=1,
                      raw=f"state={'OPEN' if state & 1 else 'CLOSED'}")


class EV1527Motion(Protocol):
    """EV1527 motion sensor."""
    name = "EV1527-Motion"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 20)
        state = bits.extract_bits(20, 4)
        return Device(protocol=self.name, id=f"{code:05X}", channel=1,
                      raw=f"motion={'DETECTED' if state & 1 else 'IDLE'}")


class WMR252Motion(Protocol):
    """WMR-252 motion sensor."""
    name = "WMR-252-Motion"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 20)
        state = bits.extract_bits(20, 4)
        return Device(protocol=self.name, id=f"{code:05X}", channel=1,
                      raw=f"motion={'DETECTED' if state & 2 else 'IDLE'}")


class SecudoAlarm(Protocol):
    """Secudo alarm sensor."""
    name = "Secudo-Alarm"
    min_bits = 24
    max_bits = 24

    def decode(self, bits):
        if len(bits) != 24: return None
        code = bits.extract_bits(0, 20)
        state = bits.extract_bits(20, 4)
        return Device(protocol=self.name, id=f"{code:05X}", channel=1,
                      raw=f"alarm={'TRIGGERED' if state & 1 else 'OK'}")


# ============================================================
# ENERGY MONITORS
# ============================================================

class EfergyE2(Protocol):
    """Efergy E2 energy monitor (goughlui.com reverse-engineering by Nathaniel Elijah)."""
    name = "Efergy-E2"
    min_bits = 64
    max_bits = 80

    def decode(self, bits):
        if len(bits) < 64: return None
        # Preamble
        if bits.extract_bits(0, 4) != 0x0: return None
        dev_id = bits.extract_bits(8, 4)
        # Current/power data
        power_raw = bits.extract_bits(24, 16)
        voltage = bits.extract_bits(40, 8)
        # Voltage in units of 0.1V with offset
        v = voltage * 0.1 + 200 if voltage > 0 else None
        # Power in units of ~0.001 kW
        power = power_raw * 0.001 if power_raw > 0 else None
        return Device(protocol=self.name, id=f"{dev_id:X}", channel=1,
                      raw=f"power={power:.3f}kW voltage={v:.1f}V" if power else "N/A")


# ============================================================
# PROTOCOL REGISTRY
# ============================================================

class ProtocolRegistry:
    """Registry that holds all protocol decoders and dispatches packets."""

    def __init__(self):
        self.protocols: List[Protocol] = []
        self._register_all()

    def _register_all(self):
        """Register all available protocol decoders."""
        classes = [
            # Weather sensors
            Nexus, Rubicson, Prologue,
            Acurite592TXR, Acurite609TXC, Acurite606TX, Acurite986,
            FineOffsetWH2, FineOffsetWH1080,
            OregonV2, OregonTHGR810, OregonBTHGN129, OregonWGR800,
            OregonPCR800, OregonUVN800, OregonTHN132N, OregonTHWR288A,
            OregonRTHN129, OregonTHGR228N, OregonRTGR328N,
            LaCrosseTX141TH, LaCrosseTX147, TX07K,
            AlectoV1, AlectoV2, AlectoDCF,
            TFA30_3151, TFA30_3208,
            AuriolH13726, AuriolAHFL, WT440H, GTWT02,
            Teknihall, NinjaBlocks, Meteoscan, Dostmann, Soens, TCM,
            IBoutique, Ventus, Balance, ConradS3318P,
            GenericTH, GenericTemp,
            # BBQ
            MaverickET732,
            # Relays / remotes
            RCSwitch1, RCSwitch2, RCSwitch3, RCSwitch4, RCSwitch5,
            Intertechno, KaKu, Nexa, ElroHE300, SC2262,
            Beamish, Brennenstuhl, ByeByeStandby, Clarus, Cleverwatts, CoCo,
            # Security
            KaKuContact, SC2262Contact, EV1527Contact, KERUID026,
            EV1527Motion, WMR252Motion, SecudoAlarm,
            # Energy
            EfergyE2,
        ]
        for cls in classes:
            self.protocols.append(cls())

    def count(self) -> int:
        """Return number of registered protocol decoders."""
        return len(self.protocols)

    def decode_all(self, bits: BitBuffer) -> Optional[Device]:
        """Try all protocol decoders on the given bit buffer."""
        n = len(bits)
        for proto in self.protocols:
            if n < proto.min_bits or n > proto.max_bits:
                continue
            try:
                dev = proto.decode(bits)
                if dev is not None:
                    return dev
            except Exception:
                continue
        return None

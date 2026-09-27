# py439

**SDR decoder for 433.92 MHz wireless weather sensors, BBQ thermometers, smart plugs, and security devices.**

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)

Author: **R4SCS** — [https://github.com/R4SCS/](https://github.com/R4SCS/)

---

## Overview

py439 is a Python-based SDR decoder that listens to 433.92 MHz OOK/ASK signals via an RTL-SDR dongle and decodes packets from wireless sensors and devices. It includes a built-in web dashboard with real-time canvas charts, a device table, and CSV export.

**69 protocol decoders** covering weather sensors, BBQ thermometers, remote controls, contact/motion sensors, and energy monitors.

All decoders are **clean-room implementations** based on publicly available protocol documentation. No source code from rtl_433 or other GPL decoder projects was used.

## Quick Start

### Demo mode (no hardware)

```bash
python main.py --demo --web 8080 -v
```

Open `http://localhost:8080` in your browser — 5 simulated sensors will populate the dashboard.

### With RTL-SDR

```bash
# Terminal 1: start rtl_tcp
rtl_tcp -s 250000

# Terminal 2: start py439
python main.py --freq 433.92M --web 8080 -v
```

## Requirements

- **Python 3.10+**
- **RTL-SDR dongle** (RTL2832U-based)
- **rtl_tcp** — comes with `rtl-sdr` package

### Installing rtl-sdr

**Ubuntu/Debian:**
```bash
sudo apt install rtl-sdr
```

**macOS (Homebrew):**
```bash
brew install rtl-sdr
```

**Windows:** Download from [osmocom RTL-SDR](https://osmocom.org/projects/rtl-sdr)

## CLI Options

| Option | Default | Description |
|---|---|---|
| `--freq` | `433.92M` | Frequency (supports M/K suffixes) |
| `--rate` | `250000` | Sample rate in Hz |
| `--gain` | `auto` | Gain (auto or integer in dB) |
| `--web` | `0` (off) | Web dashboard port |
| `--host` | `127.0.0.1` | rtl_tcp host |
| `--port` | `1234` | rtl_tcp port |
| `-v` / `--verbose` | off | Print decoded messages to console |
| `--demo` | off | Simulated sensors (no hardware) |

## Web Dashboard

Open `http://localhost:8080` in your browser.

### Features

- **4 canvas charts** (no external libraries, pure HTML5 canvas):
  - **Temperature** — line chart with fill, per-device colors, 24h window
  - **Humidity** — line chart, 0–100% scale, per-device colors
  - **Protocol Distribution** — pie chart with percentages
  - **Message Rate** — bar chart, msg/min over last 60 samples
- **Statistics bar** — Devices, Messages, Msg/min, Protocols, CRC Errors
- **Device table** — Protocol, ID, Channel, Temperature, Humidity, Battery, CRC, Message count, Last seen, Age
- **Pause/Resume** — freeze dashboard updates
- **Export CSV** — download all devices as CSV
- **Connection indicator** — green/red dot
- **Uptime counter**
- **Color coding** — temperature (orange), humidity (blue), battery (green/red), CRC (green/red), age (green→yellow→red)

### JSON API

```bash
curl http://localhost:8080/api/data
```

Returns:
```json
{
  "devices": [...],
  "total_messages": 42,
  "crc_errors": 0,
  "msg_per_min": 7,
  "protocols": 3
}
```

### CSV Export

```bash
curl http://localhost:8080/api/csv -o devices.csv
```

## Architecture

```
RTL-SDR dongle
    |
    v
rtl_tcp (TCP server, port 1234)
    |  IQ stream (uint8 pairs, 250 ksps)
    v
py439 main.py
    |
    +-- Demodulator (demod.py)
    |       AM demodulation with AGC
    |       Output: amplitude envelope
    |
    +-- PulseDetector (pulse_detect.py)
    |       OOK pulse detection and classification
    |       Output: BitBuffer packets
    |
    +-- ProtocolRegistry (protocols/__init__.py)
    |       69 protocol decoders
    |       Each decoder tries to match the bit buffer
    |       Output: Device objects
    |
    +-- DashboardServer (web_dashboard.py)
            HTTP server on port 8080
            Serves HTML dashboard + JSON API + CSV export
```

### Files

| File | Description |
|---|---|
| `main.py` | Entry point, CLI, rtl_tcp client, main loop |
| `bitbuffer.py` | Bit buffer for storing and manipulating packet bits |
| `demod.py` | AM demodulator with adaptive AGC |
| `pulse_detect.py` | OOK pulse detector with timing classification |
| `protocols/__init__.py` | 69 clean-room protocol decoders |
| `web_dashboard.py` | Web dashboard with canvas charts |
| `LICENSE` | GPL-3.0 license + source attribution |

## Supported Protocols

### Weather Sensors (44)

| Protocol | Sensor Type | Source |
|---|---|---|
| Nexus-TH | Temperature + humidity | aquaticus/nexus433 |
| Rubicson | Temperature + humidity | Independent |
| Prologue-TH | Temperature + humidity | Independent |
| Acurite-592TXR | Temperature + humidity | Hackaday RE |
| Acurite-609TXC | Temperature + humidity | Hackaday RE |
| Acurite-606TX | Temperature only | Hackaday RE |
| Acurite-986 | Fridge/freezer temp | Hackaday RE |
| Fineoffset-WH2 | Temperature + humidity | ESPHome community |
| Fineoffset-WH1080 | Weather station | sevenwatt.com |
| Oregon-THGN132N | Temperature + humidity | wmrx00 PDF |
| Oregon-THGR810 | Temperature + humidity | wmrx00 PDF |
| Oregon-BTHGN129 | Temp + hum + pressure | wmrx00 PDF |
| Oregon-WGR800 | Wind speed/direction | wmrx00 PDF |
| Oregon-PCR800 | Rain gauge | wmrx00 PDF |
| Oregon-UVN800 | UV index | wmrx00 PDF |
| Oregon-THN132N | Temperature only | wmrx00 PDF |
| Oregon-THWR288A | Temperature only | wmrx00 PDF |
| Oregon-RTHN129 | Temperature only | wmrx00 PDF |
| Oregon-THGR228N | Temperature + humidity | wmrx00 PDF |
| Oregon-RTGR328N | Temp + hum + time | wmrx00 PDF |
| LaCrosse-TX141TH | Temperature + humidity | Arduino Forum |
| LaCrosse-TX147 | Temperature only | Stack Overflow |
| TX07K-TH | Temperature + humidity | tommie.github.io |
| Alecto-V1 | Temperature + humidity | pilight docs |
| Alecto-V2 | Temperature + humidity | pilight docs |
| Alecto-DCF | Temperature only | pilight docs |
| TFA-30.3151 | Temperature + humidity | pilight docs |
| TFA-30.3208 | Rain gauge | pilight docs |
| Auriol-H13726 | Temperature only | platenspeler |
| Auriol-AHFL | Temperature + humidity | platenspeler |
| WT440H | Temperature + humidity | platenspeler |
| GT-WT-02 | Temperature + humidity | onetransistor.eu |
| Teknihall-TH | Temperature + humidity | pilight docs |
| Ninja-TH | Temperature + humidity | pilight docs |
| Meteoscan-TH | Temperature + humidity | Independent |
| Dostmann-P7704 | Temperature + humidity | Independent |
| Soens-TH | Temperature only | Independent |
| TCM-TH | Temperature + humidity | Independent |
| iBoutique-TH | Temperature + humidity | Independent |
| Ventus-TH | Temperature + humidity | Independent |
| Balance-TH | Temperature only | Independent |
| Conrad-S3318P | Temperature + humidity | Independent |
| Generic-TH | Temperature + humidity | fetzerch.github.io |
| Generic-Temp | Temperature only | Independent |

### BBQ / Cooking (1)

| Protocol | Sensor Type | Source |
|---|---|---|
| Maverick-ET732 | Dual probe thermometer | Hackaday RE |

### Relays / Remotes (17)

| Protocol | Type | Source |
|---|---|---|
| RCSwitch-1 through RCSwitch-5 | Switch protocols | RCSwitch docs |
| Intertechno | Remote control | pilight docs |
| KaKu | Remote control | pilight docs |
| Nexa | Remote control | pilight docs |
| Elro-HE300 | Remote control | pilight docs |
| SC2262 | Remote control | pilight docs |
| Beamish | Remote control | pilight docs |
| Brennenstuhl | Remote control | pilight docs |
| ByeByeStandby | Remote control | pilight docs |
| Clarus | Remote control | pilight docs |
| Cleverwatts | Remote control | pilight docs |
| CoCo | Remote control | pilight docs |

### Security Sensors (7)

| Protocol | Type | Source |
|---|---|---|
| KaKu-Contact | Door/window contact | pilight docs |
| SC2262-Contact | Door/window contact | pilight docs |
| EV1527-Contact | Door/window contact | Independent |
| KERUI-D026 | Door sensor | pilight docs |
| EV1527-Motion | PIR motion sensor | Independent |
| WMR-252-Motion | PIR motion sensor | Independent |
| Secudo-Alarm | Alarm sensor | Independent |

### Energy Monitors (1)

| Protocol | Type | Source |
|---|---|---|
| Efergy-E2 | Electricity monitor | goughlui.com RE |

## Adding a New Protocol

### Step 1: Research the Protocol

Find public documentation for the protocol you want to add:
- Search for the device model + "433MHz protocol" or "reverse engineering"
- Check pilight docs, Hackaday, Arduino forums, and blogs
- Look for bit layout, timing, checksum algorithm, and data encoding

### Step 2: Create a Decoder Class

Add a new class in `protocols/__init__.py`:

```python
class MySensor(Protocol):
    """MySensor TH sensor (source documentation reference)."""
    name = "MySensor-TH"
    min_bits = 40
    max_bits = 40

    def decode(self, bits: BitBuffer) -> Optional[Device]:
        # 1. Check bit count
        if len(bits) != 40:
            return None

        # 2. Check sync/header bytes
        if bits.extract_bits(0, 8) != 0xAB:
            return None

        # 3. Extract fields
        dev_id = bits.extract_bits(8, 8)
        ch = bits.extract_bits(16, 2) + 1

        # 4. Extract and convert temperature (signed)
        temp_raw = bits.extract_bits(20, 12)
        temp_raw = self._signed(temp_raw, 12)
        temp = temp_raw * 0.1

        # 5. Extract humidity
        hum = bits.extract_bits(32, 8)

        # 6. Optional: verify checksum
        # chk = bits.extract_bits(36, 4)
        # chk_calc = ...

        # 7. Return Device
        return Device(
            protocol=self.name,
            id=f"{dev_id:02X}",
            channel=ch,
            temperature=round(temp, 1),
            humidity=hum if 0 < hum <= 100 else None,
            crc_ok=True,
        )
```

### Step 3: Register the Decoder

Add your class to the `_register_all` method in `ProtocolRegistry`:

```python
def _register_all(self):
    classes = [
        ...
        MySensor,  # Add here
    ]
```

### Step 4: Test

```bash
python main.py --demo --web 8080 -v
```

If you have the physical device, test with real RF:

```bash
rtl_tcp -s 250000
python main.py --freq 433.92M --web 8080 -v
```

### Common Patterns

| Pattern | Code |
|---|---|
| Signed temperature | `temp_raw = self._signed(temp_raw, 12)` |
| Sum checksum | `chk = self._checksum_add(bits, 0, 5)` |
| XOR checksum | `chk = self._xor_bytes(bits, 0, 4)` |
| Hex ID | `id=f"{dev_id:02X}"` |
| Nibble-reversed (Oregon) | Swap nibbles manually |

## Troubleshooting

### rtl_tcp won't connect

```bash
# Check if rtl_tcp is running
pgrep rtl_tcp

# Check if dongle is detected
lsusb | grep RTL

# Try different host/port
python main.py --host 127.0.0.1 --port 1234 --web 8080 -v
```

### Dashboard shows red indicator

The `/api/data` endpoint is returning an error. Check the console output of `main.py` for exceptions.

### No packets decoded

- Make sure the sensor is transmitting (check batteries)
- Try adjusting gain: `--gain 30`
- Try different sample rate: `--rate 1024000`
- Check frequency: most sensors are at 433.92 MHz, but some use 315 MHz or 868 MHz

### Dashboard URL not shown

The dashboard URL is printed before rtl_tcp connection:

```
Registered 69 protocol decoders
Dashboard: http://localhost:8080
Sample rate: 250000 Hz
Frequency: 433.920 MHz
Gain: auto
rtl_tcp ready: ...
Listening...
```

If you don't see it, make sure `--web` is specified.

## License

This project is licensed under **GPL-3.0**.

Copyright (C) 2026 [R4SCS](https://github.com/R4SCS/)

All protocol decoders are clean-room implementations based on publicly available protocol documentation. No source code from rtl_433 or other GPL-licensed decoder projects was used as reference material. See `LICENSE` for the full license text and source attribution.

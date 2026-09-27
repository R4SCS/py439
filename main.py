#!/usr/bin/env python3
"""
py439 - SDR decoder for 433.92 MHz weather sensors and wireless devices.

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
import argparse
import logging
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict

from demod import Demodulator
from protocols import ProtocolRegistry, Device
from web_dashboard import DashboardServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("py439")


@dataclass
class DeviceRecord:
    """Tracked device with latest sensor data and statistics."""
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
    last_seen: float = 0.0
    msg_count: int = 0


class Py439:
    """Main application: manages SDR connection, decoding, and web dashboard."""

    def __init__(self, freq=433920000, sample_rate=250000, gain="auto",
                 web_port=8080, verbose=False, demo=False, host="127.0.0.1", port=1234):
        self.freq = freq
        self.sample_rate = sample_rate
        self.gain = gain
        self.web_port = web_port
        self.verbose = verbose
        self.demo = demo
        self.host = host
        self.port = port

        self.devices: Dict[str, DeviceRecord] = {}
        self._lock = threading.Lock()
        self.total_messages = 0
        self.crc_errors = 0
        self.frequency = freq
        self.start_time = time.time()

        self.registry = ProtocolRegistry()
        logger.info("Registered %d protocol decoders", self.registry.count())

        self.demod = Demodulator(sample_rate=sample_rate)
        self.dashboard: Optional[DashboardServer] = None
        self._running = False
        self._sock: Optional[socket.socket] = None

    def _device_key(self, dev: Device) -> str:
        """Generate unique key for a device."""
        return f"{dev.protocol}:{dev.id}:ch{dev.channel}"

    def snapshot_devices(self):
        """Return a thread-safe copy of the device table for the dashboard."""
        with self._lock:
            return list(self.devices.items())

    def _update_device(self, dev: Device):
        """Add or update a device record (thread-safe)."""
        key = self._device_key(dev)
        with self._lock:
            if key not in self.devices:
                self.devices[key] = DeviceRecord(
                    protocol=dev.protocol, id=dev.id, channel=dev.channel,
                    battery=dev.battery, temperature=dev.temperature,
                    humidity=dev.humidity, pressure=dev.pressure,
                    wind_speed=dev.wind_speed, wind_dir=dev.wind_dir,
                    rain=dev.rain, uv=dev.uv, lux=dev.lux,
                    raw=dev.raw, rssi=dev.rssi, crc_ok=dev.crc_ok,
                    last_seen=time.time(), msg_count=1,
                )
                return
            rec = self.devices[key]
            rec.last_seen = time.time()
            rec.msg_count += 1
            if dev.temperature is not None: rec.temperature = dev.temperature
            if dev.humidity is not None: rec.humidity = dev.humidity
            if dev.pressure is not None: rec.pressure = dev.pressure
            if dev.wind_speed is not None: rec.wind_speed = dev.wind_speed
            if dev.wind_dir is not None: rec.wind_dir = dev.wind_dir
            if dev.rain is not None: rec.rain = dev.rain
            if dev.uv is not None: rec.uv = dev.uv
            if dev.lux is not None: rec.lux = dev.lux
            if dev.battery: rec.battery = dev.battery
            rec.raw = dev.raw
            rec.crc_ok = dev.crc_ok

    def _process_packets(self, packets):
        """Decode packets and update device records."""
        for bits in packets:
            dev = self.registry.decode_all(bits)
            if dev is not None:
                self.total_messages += 1
                if not dev.crc_ok:
                    self.crc_errors += 1
                self._update_device(dev)
                if self.verbose:
                    parts = [f"{dev.protocol} id={dev.id} ch={dev.channel}"]
                    if dev.temperature is not None:
                        parts.append(f"temp={dev.temperature:.1f}C")
                    if dev.humidity is not None:
                        parts.append(f"hum={dev.humidity:.0f}%")
                    if not dev.crc_ok:
                        parts.append("CRC=FAIL")
                    logger.info("  %s", " ".join(parts))

    def _connect_rtl_tcp(self) -> bool:
        """Connect to rtl_tcp and configure the dongle."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5)
            self._sock.connect((self.host, self.port))

            # Read the 12-byte dongle info header. recv() may return it in
            # several chunks, so keep reading until all 12 bytes have arrived.
            data = b""
            while len(data) < 12:
                chunk = self._sock.recv(12 - len(data))
                if not chunk:
                    logger.error("rtl_tcp closed the connection during handshake")
                    return False
                data += chunk
            if data[:4] != b"RTL0":
                logger.error("Not an rtl_tcp stream (bad magic %r)", data[:4])
                return False
            tuner_type, tuner_gain_count = struct.unpack(">II", data[4:12])
            logger.info("rtl_tcp ready: tuner_type=%d, gain_steps=%d", tuner_type, tuner_gain_count)
            # Switch back to blocking mode for the streaming IQ loop.
            self._sock.settimeout(None)

            # Set frequency
            self._send_command(1, struct.pack(">I", self.freq))
            # Set sample rate
            self._send_command(2, struct.pack(">I", self.sample_rate))
            # Set gain mode
            if self.gain == "auto":
                self._send_command(3, struct.pack(">I", 0))
            else:
                self._send_command(3, struct.pack(">I", 1))
                self._send_command(4, struct.pack(">I", int(self.gain) * 10))

            return True
        except Exception as e:
            logger.error("Cannot connect to rtl_tcp: %s", e)
            return False

    def _send_command(self, cmd, param):
        """Send a command to rtl_tcp (5-byte frame: cmd byte + uint32 param)."""
        if self._sock is None: return
        self._sock.sendall(bytes([cmd]) + param)

    def run(self):
        """Start the application: web dashboard + SDR or demo mode."""
        self._running = True

        # Start web dashboard before anything else
        if self.web_port:
            self.dashboard = DashboardServer(port=self.web_port, py439=self)
            self.dashboard.start()
            logger.info("Dashboard: http://localhost:%d", self.web_port)

        if self.demo:
            self._run_demo()
        else:
            self._run_sdr()

    def _run_sdr(self):
        """Main SDR receive loop."""
        logger.info("Sample rate: %d Hz", self.sample_rate)
        logger.info("Frequency: %.3f MHz", self.freq / 1e6)
        logger.info("Gain: %s", self.gain)

        if not self._connect_rtl_tcp():
            logger.error("Cannot start. Is rtl_tcp running?")
            return

        logger.info("Listening...")
        buf_size = self.sample_rate * 2 // 10  # ~100ms of IQ data
        try:
            while self._running:
                try:
                    data = self._sock.recv(buf_size)
                except socket.timeout:
                    continue
                except OSError as exc:
                    logger.error("Socket error: %s", exc)
                    break
                if not data:
                    break
                packets = self.demod.process_iq(data)
                if packets:
                    self._process_packets(packets)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            if self._sock:
                self._sock.close()
            if self.dashboard:
                self.dashboard.stop()
            logger.info("Stopped.")

    def _run_demo(self):
        """Demo mode: simulate weather sensors without hardware."""
        logger.info("Demo mode: simulating weather sensors")

        # Simulated sensors
        sensors = [
            {"protocol": "Nexus-TH", "id": "5A", "channel": 1,
             "temp": 22.3, "hum": 58, "bat": "OK"},
            {"protocol": "Nexus-TH", "id": "3B", "channel": 2,
             "temp": 18.7, "hum": 64, "bat": "OK"},
            {"protocol": "Acurite-609TXC", "id": "7C", "channel": 1,
             "temp": 24.1, "hum": 52, "bat": "OK"},
            {"protocol": "Fineoffset-WH2", "id": "A1B2", "channel": 1,
             "temp": -5.2, "hum": 71, "bat": "OK"},
            {"protocol": "Rubicson", "id": "F", "channel": 3,
             "temp": 15.3, "hum": None, "bat": "LOW"},
        ]

        try:
            while self._running:
                for s in sensors:
                    # Add small random variation
                    temp = s["temp"] + round((time.time() / 100) % 2 - 1, 1)
                    dev = Device(
                        protocol=s["protocol"], id=s["id"], channel=s["channel"],
                        battery=s["bat"], temperature=round(temp, 1),
                        humidity=s["hum"], crc_ok=True,
                    )
                    self.total_messages += 1
                    self._update_device(dev)
                    if self.verbose:
                        logger.info("  %s id=%s ch=%d temp=%.1fC hum=%s%%",
                                    dev.protocol, dev.id, dev.channel,
                                    temp, s["hum"] if s["hum"] else "-")
                time.sleep(3)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            if self.dashboard:
                self.dashboard.stop()
            logger.info("Stopped.")

    def stop(self):
        """Stop the application."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="py439 - 433.92 MHz SDR decoder")
    parser.add_argument("--freq", default="433.92M", help="Frequency (default: 433.92M)")
    parser.add_argument("--rate", type=int, default=250000, help="Sample rate (default: 250000)")
    parser.add_argument("--gain", default="auto", help="Gain (default: auto)")
    parser.add_argument("--web", type=int, default=0, help="Web dashboard port (default: off)")
    parser.add_argument("--host", default="127.0.0.1", help="rtl_tcp host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=1234, help="rtl_tcp port (default: 1234)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--demo", action="store_true", help="Demo mode (no hardware)")
    args = parser.parse_args()

    # Parse frequency string
    freq_str = args.freq.upper().replace("HZ", "")
    if freq_str.endswith("M"):
        freq = int(float(freq_str[:-1]) * 1e6)
    elif freq_str.endswith("K"):
        freq = int(float(freq_str[:-1]) * 1e3)
    else:
        freq = int(freq_str)

    rtl = Py439(
        freq=freq, sample_rate=args.rate, gain=args.gain,
        web_port=args.web, verbose=args.verbose, demo=args.demo,
        host=args.host, port=args.port,
    )

    try:
        rtl.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

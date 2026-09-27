"""
py439 - Pulse detector for OOK signals, extracts pulses from IQ stream.

Copyright (C) 2026 R4SCS (https://github.com/R4SCS/)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
import logging
from typing import List, Tuple, Optional
from bitbuffer import BitBuffer

logger = logging.getLogger("py439")


class PulseDetector:
    """OOK pulse detector that extracts bits from demodulated amplitude signal."""

    def __init__(self, sample_rate: int = 250000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.state = 0  # 0 = idle, 1 = in pulse
        self.pulse_len = 0
        self.gap_len = 0
        self.current_buffer: Optional[BitBuffer] = None
        self.last_pulse_us = 0
        self.last_gap_us = 0
        self._pending_packet: Optional[BitBuffer] = None
        self.packet_count = 0

        # Timing thresholds in microseconds (typical for 433.92 MHz OOK)
        self.short_pulse_min = 200
        self.short_pulse_max = 600
        self.long_pulse_min = 600
        self.long_pulse_max = 1500
        self.sync_pulse_min = 2500
        self.gap_min = 200
        self.long_gap_min = 4000  # inter-packet gap
        self.adaptive_threshold = None

    def set_threshold(self, threshold: float):
        """Update detection threshold from adaptive AGC."""
        if threshold is not None and threshold > 0:
            self.threshold = threshold

    def _classify_pulse(self, us: int) -> str:
        """Classify pulse duration as short, long, or sync."""
        if self.short_pulse_min <= us <= self.short_pulse_max:
            return "short"
        elif self.long_pulse_min <= us <= self.long_pulse_max:
            return "long"
        elif us >= self.sync_pulse_min:
            return "sync"
        return "invalid"

    def _classify_gap(self, us: int) -> str:
        """Classify gap duration as short, normal, or end-of-packet."""
        if us < self.gap_min:
            return "short"
        elif us >= self.long_gap_min:
            return "end"
        return "normal"

    def process_sample(self, amplitude: float):
        """Process a single amplitude sample."""
        above = amplitude > self.threshold

        if self.state == 0:  # idle / in gap
            if above:
                # Rising edge - pulse starts
                if self.gap_len > 0:
                    self.last_gap_us = int(self.gap_len * 1e6 / self.sample_rate)
                    gap_type = self._classify_gap(self.last_gap_us)
                    if gap_type == "end" and self.current_buffer and len(self.current_buffer) >= 8:
                        self._pending_packet = self.current_buffer
                        self.current_buffer = None
                self.gap_len = 0
                self.pulse_len = 1
                self.state = 1
            else:
                self.gap_len += 1
                # End-of-packet detected by timeout: emit the buffer as soon
                # as the gap exceeds long_gap_min, without waiting for the next
                # edge. Otherwise the last packet of a burst is never returned.
                gap_us = int(self.gap_len * 1e6 / self.sample_rate)
                if (gap_us >= self.long_gap_min and self._pending_packet is None
                        and self.current_buffer and len(self.current_buffer) >= 8):
                    self._pending_packet = self.current_buffer
                    self.current_buffer = None

        elif self.state == 1:  # in pulse
            if above:
                self.pulse_len += 1
            else:
                # Falling edge - pulse ends
                self.last_pulse_us = int(self.pulse_len * 1e6 / self.sample_rate)
                ptype = self._classify_pulse(self.last_pulse_us)
                self.pulse_len = 0
                self.gap_len = 1
                self.state = 0

                if ptype == "sync":
                    # Sync pulse starts a new packet — preserve previous one
                    if self.current_buffer and len(self.current_buffer) >= 8:
                        self._pending_packet = self.current_buffer
                    self.current_buffer = BitBuffer()
                elif ptype in ("short", "long"):
                    if self.current_buffer is None:
                        self.current_buffer = BitBuffer()
                    # PWM encoding: short = 0, long = 1
                    bit = 0 if ptype == "short" else 1
                    self.current_buffer.add_bit(bit, pulse=self.last_pulse_us, gap=self.last_gap_us)
                elif ptype == "invalid":
                    # Invalid pulse - flush current buffer if it has enough bits
                    if self.current_buffer and len(self.current_buffer) >= 8:
                        self._pending_packet = self.current_buffer
                    self.current_buffer = None

    def get_packet(self) -> Optional[BitBuffer]:
        """Return pending packet if available."""
        if self._pending_packet is not None:
            pkt = self._pending_packet
            self._pending_packet = None
            self.packet_count += 1
            return pkt
        return None

    def flush(self):
        """Emit the current buffer if the line has been idle long enough.

        Safe to call at any time: it never splits a packet that is still being
        received, because it only fires in the idle state after a long gap.
        """
        if self.state != 0:
            return
        gap_us = int(self.gap_len * 1e6 / self.sample_rate)
        if (gap_us >= self.long_gap_min and self._pending_packet is None
                and self.current_buffer and len(self.current_buffer) >= 8):
            self._pending_packet = self.current_buffer
            self.current_buffer = None

"""
py439 - OOK/ASK demodulator for IQ stream from RTL-SDR.

Copyright (C) 2026 R4SCS (https://github.com/R4SCS/)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
import math
import logging
from bitbuffer import BitBuffer
from pulse_detect import PulseDetector

logger = logging.getLogger("py439")


class Demodulator:
    """AM demodulator with AGC and pulse detector for OOK modulation."""

    def __init__(self, sample_rate: int = 250000):
        self.sample_rate = sample_rate
        self.pulse_detector = PulseDetector(sample_rate=sample_rate)
        self.ema_alpha = 0.01
        self.ema_noise = 0.0
        self.ema_signal = 0.0
        self.samples_processed = 0
        self.agc_threshold = None
        self._initialized = False

    def process_iq(self, data: bytes) -> list:
        """Process a block of IQ data (uint8 pairs). Returns list of BitBuffer packets."""
        packets = []
        n = len(data)
        if n < 2:
            return packets

        for i in range(0, n - 1, 2):
            I = data[i] - 128
            Q = data[i + 1] - 128
            amp = math.sqrt(I * I + Q * Q)

            if not self._initialized:
                self.ema_noise = amp
                self.ema_signal = amp
                self._initialized = True
                continue

            # AGC: refine the noise floor only during silence and track the
            # signal level with a fast attack and a slow decay. This keeps the
            # threshold below the signal so long pulses are not cut short.
            alpha_noise = 0.001
            beta_signal = 0.05

            threshold = self.ema_noise + 0.5 * (self.ema_signal - self.ema_noise)
            if amp < threshold:
                self.ema_noise += alpha_noise * (amp - self.ema_noise)
            elif amp > self.ema_signal:
                self.ema_signal = amp
            else:
                self.ema_signal -= beta_signal * (self.ema_signal - amp)

            # Recompute the threshold so the update takes effect immediately,
            # but never let it climb above the tracked signal level.
            threshold = self.ema_noise + 0.5 * (self.ema_signal - self.ema_noise)
            ceiling = self.ema_signal * 0.9
            if self.ema_signal > 0 and threshold > ceiling:
                threshold = ceiling

            self.pulse_detector.set_threshold(threshold / 128.0)
            self.pulse_detector.process_sample(amp / 128.0)

            pkt = self.pulse_detector.get_packet()
            if pkt is not None:
                packets.append(pkt)

            self.samples_processed += 1

        return packets

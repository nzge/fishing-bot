"""Arduino HX711 serial reader (matches project_w_t_controller.ipynb protocol).

The Arduino firmware prints lines like:  raw: 12345
"""
from __future__ import annotations

import re
import time
from collections import deque
from typing import Optional, Tuple

import serial

SENSOR_LINE_PATTERN = re.compile(r'raw:\s*(-?\d+)')


def parse_sensor_line(line: str) -> Optional[int]:
    match = SENSOR_LINE_PATTERN.search(line)
    if not match:
        return None
    return int(match.group(1))


class ArduinoLoadCellReader:
    """Non-blocking reader for HX711 counts over Arduino serial."""

    def __init__(
        self,
        port: str,
        baud: int = 9600,
        timeout_s: float = 0.05,
        filter_window: int = 2,
        tare_samples: int = 20,
    ):
        self.port = port
        self.baud = baud
        self.timeout_s = timeout_s
        self.filter_window = max(1, filter_window)
        self.tare_samples = max(1, tare_samples)
        self._ser: Optional[serial.Serial] = None
        self._buffer: deque[int] = deque(maxlen=self.filter_window)
        self.zero_offset: Optional[float] = None

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def open(self) -> None:
        self._ser = serial.Serial(
            self.port,
            self.baud,
            timeout=self.timeout_s,
        )
        # Allow the Arduino to reset after USB enumeration.
        time.sleep(2.0)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def _readline_raw(self) -> Optional[int]:
        if not self.is_open:
            return None
        line = self._ser.readline().decode('utf-8', errors='ignore').strip()
        if not line:
            return None
        return parse_sensor_line(line)

    def tare(self) -> float:
        """Average ``tare_samples`` readings with no line load."""
        samples = []
        deadline = time.time() + max(5.0, self.tare_samples * self.timeout_s * 4)
        while len(samples) < self.tare_samples and time.time() < deadline:
            raw = self._readline_raw()
            if raw is not None:
                samples.append(raw)
        if not samples:
            raise RuntimeError(
                f'No load-cell samples from {self.port} during tare — '
                'is the Arduino running and printing "raw: <count>" lines?',
            )
        self.zero_offset = float(sum(samples) / len(samples))
        return self.zero_offset

    def read_filtered_raw(self) -> Optional[float]:
        """Return the latest filtered raw ADC count, or None if no new sample."""
        raw = self._readline_raw()
        if raw is None:
            return None
        self._buffer.append(raw)
        return float(sum(self._buffer) / len(self._buffer))

#!/usr/bin/env python3
"""
Verify SMY02 FM bandwidth changes using tinySA scanraw data.

Workflow:
1. Configure SMY02 at fixed RF/level and apply FM deviations for 6.25/12.5/25 kHz profiles.
2. Read tinySA raw sweep data around carrier for each profile.
3. Compute a relative width metric from each sweep.
4. Report whether width increases monotonically with deviation.
"""

from __future__ import annotations

import logging
import pathlib
import statistics
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

import serial

# Allow running this script directly from project root without manual PYTHONPATH.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.smy02_controller import SMY02Controller


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


TINYSA_PORT = "/dev/ttyACM0"
TINYSA_BAUD = 115200

RF_HZ = 144_000_000
LEVEL_DBM = -20.0
SPAN_HZ = 200_000
POINTS = 451

BANDWIDTHS = [
    ("6.25 kHz", 3125),
    ("12.5 kHz", 6250),
    ("25 kHz", 12500),
]


@dataclass
class SweepResult:
    name: str
    deviation: int
    peak_idx: int
    peak_val: int
    width_bins: int
    width_hz: float


class TinySAClient:
    def __init__(self, port: str = TINYSA_PORT, baud: int = TINYSA_BAUD):
        self.ser = serial.Serial(port, baud, timeout=0.2)

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    def cmd_text(self, cmd: str, wait: float = 0.3) -> str:
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode())
        time.sleep(wait)
        out = b""
        end = time.time() + 1.0
        while time.time() < end:
            chunk = self.ser.read(4096)
            if chunk:
                out += chunk
            else:
                time.sleep(0.02)
        return out.decode(errors="ignore")

    def scanraw(self, start_hz: int, stop_hz: int, points: int) -> List[int]:
        cmd = f"scanraw {start_hz} {stop_hz} {points}"
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode())

        data = b""
        end = time.time() + 2.5
        while time.time() < end:
            chunk = self.ser.read(8192)
            if chunk:
                data += chunk
            else:
                time.sleep(0.02)

        return self._parse_scanraw_frame(data)

    @staticmethod
    def _parse_scanraw_frame(data: bytes) -> List[int]:
        # Frame format observed:
        #   b'scanraw ...\\r\\n{'
        #   repeated samples b'x' + <low-byte> + <high-byte>
        #   b'}ch> '
        start = data.find(b"{")
        end = data.rfind(b"}")
        if start < 0 or end < 0 or end <= start:
            raise RuntimeError("Could not find scanraw frame delimiters")

        payload = data[start + 1 : end]
        samples: List[int] = []
        i = 0
        while i + 2 < len(payload):
            if payload[i] == ord("x"):
                lo = payload[i + 1]
                hi = payload[i + 2]
                samples.append(lo | (hi << 8))
                i += 3
            else:
                i += 1

        if not samples:
            raise RuntimeError("No scanraw samples parsed")
        return samples


def width_metric(samples: List[int], bin_hz: float) -> Tuple[int, float, int, int]:
    peak_val = max(samples)
    peak_idx = samples.index(peak_val)
    noise_floor = statistics.median(samples)

    # Relative threshold robust against absolute scaling differences.
    threshold = int(noise_floor + 0.35 * (peak_val - noise_floor))

    left = peak_idx
    while left > 0 and samples[left] >= threshold:
        left -= 1

    right = peak_idx
    last = len(samples) - 1
    while right < last and samples[right] >= threshold:
        right += 1

    width_bins = max(0, right - left - 1)
    return width_bins, width_bins * bin_hz, peak_idx, peak_val


def main() -> int:
    ctrl = SMY02Controller()
    tiny = TinySAClient()

    try:
        if not ctrl.connect():
            logger.error("SMY02 connect failed")
            return 1

        # Setup tinySA sweep around the carrier.
        start_hz = RF_HZ - SPAN_HZ // 2
        stop_hz = RF_HZ + SPAN_HZ // 2
        logger.info("tinySA: %s", tiny.cmd_text(f"sweep {start_hz} {stop_hz} {POINTS}").strip())
        logger.info("tinySA: %s", tiny.cmd_text("rbw 1").strip())

        # Configure RF chain once.
        if not ctrl.set_frequency(RF_HZ):
            logger.error("Failed to set RF frequency")
            return 1
        if not ctrl.set_amplitude(LEVEL_DBM):
            logger.error("Failed to set RF level")
            return 1
        if not ctrl.enable_output():
            logger.warning("RF enable returned False; continuing measurement (device-specific behavior)")

        results: List[SweepResult] = []
        bin_hz = (stop_hz - start_hz) / max(1, POINTS - 1)

        for name, dev in BANDWIDTHS:
            logger.info("Applying %s (deviation=%s Hz)", name, dev)
            if not ctrl.set_modulation_fm(dev):
                logger.warning("SMY02 reported failure applying deviation %s", dev)

            # Let synthesizer and analyzer settle.
            time.sleep(0.8)
            samples = tiny.scanraw(start_hz, stop_hz, POINTS)
            wb, whz, pidx, pval = width_metric(samples, bin_hz)
            results.append(SweepResult(name, dev, pidx, pval, wb, whz))
            logger.info(
                "%s -> peak_idx=%d peak=%d width_bins=%d width_hz=%.1f",
                name, pidx, pval, wb, whz,
            )

        # Decision: widths should increase with larger deviation.
        widths = [r.width_hz for r in results]
        monotonic = widths[0] < widths[1] < widths[2]

        logger.info("---- Summary ----")
        for r in results:
            logger.info("%-8s dev=%5d Hz  width=%8.1f Hz", r.name, r.deviation, r.width_hz)
        logger.info("Monotonic width increase: %s", "YES" if monotonic else "NO")

        if not monotonic:
            logger.warning(
                "Bandwidth change not clearly visible in tinySA width metric. "
                "Try larger span/RBW tuning or verify on modulation demod screen."
            )
            return 2
        return 0
    finally:
        try:
            ctrl.disable_output()
            ctrl.disconnect()
        except Exception:
            pass
        tiny.close()


if __name__ == "__main__":
    raise SystemExit(main())

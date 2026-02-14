#!/usr/bin/env python3
"""
Test SMY02 frequency tracking from 108 MHz to 155 MHz using tinySA.

Setup:
- SMY02 level: -20 dBm
- FM bandwidth profile: 12.5 kHz (deviation 6250 Hz)
- Frequency sweep: 108..155 MHz, 1 MHz step

Validation:
- tinySA measures peak frequency around each requested carrier.
- Pass if detected peak is within tolerance.
"""

from __future__ import annotations

import argparse
import pathlib
import statistics
import sys
import time
from dataclasses import dataclass
from typing import List

import serial

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.smy02_controller import SMY02Controller


TINYSA_PORT = "/dev/ttyACM0"
TINYSA_BAUD = 115200

START_MHZ = 108
STOP_MHZ = 155
STEP_MHZ = 1

LEVEL_DBM = -20.0
DEVIATION_HZ = 6250  # 12.5 kHz profile

SPAN_HZ = 250_000
POINTS = 121
TOLERANCE_HZ = 25_000
SETTLE_S = 0.05
SCAN_TIMEOUT_S = 1.2


@dataclass
class Measurement:
    target_hz: int
    detected_hz: int
    error_hz: int
    ok: bool


class TinySA:
    def __init__(self, port: str = TINYSA_PORT, baud: int = TINYSA_BAUD, scan_timeout_s: float = SCAN_TIMEOUT_S):
        self.ser = serial.Serial(port, baud, timeout=0.2)
        self.scan_timeout_s = scan_timeout_s

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass

    def cmd(self, command: str, wait: float = 0.35) -> str:
        self.ser.reset_input_buffer()
        self.ser.write((command + "\r").encode())
        time.sleep(wait)
        data = b""
        end = time.time() + 1.0
        while time.time() < end:
            chunk = self.ser.read(4096)
            if chunk:
                data += chunk
            else:
                time.sleep(0.02)
        return data.decode(errors="ignore").strip()

    def scanraw(self, start_hz: int, stop_hz: int, points: int) -> List[int]:
        self.ser.reset_input_buffer()
        self.ser.write((f"scanraw {start_hz} {stop_hz} {points}\r").encode())
        data = b""
        end = time.time() + self.scan_timeout_s
        while time.time() < end:
            chunk = self.ser.read(8192)
            if chunk:
                data += chunk
                # Prompt seen -> frame complete.
                if b"}ch> " in data:
                    break
            else:
                time.sleep(0.02)
        return self._parse_scanraw(data)

    @staticmethod
    def _parse_scanraw(frame: bytes) -> List[int]:
        start = frame.find(b"{")
        end = frame.rfind(b"}")
        if start < 0 or end < 0 or end <= start:
            raise RuntimeError("scanraw frame delimiters not found")
        payload = frame[start + 1 : end]
        out: List[int] = []
        i = 0
        while i + 2 < len(payload):
            if payload[i] == ord("x"):
                out.append(payload[i + 1] | (payload[i + 2] << 8))
                i += 3
            else:
                i += 1
        if not out:
            raise RuntimeError("no scanraw samples parsed")
        return out


def detect_peak_frequency(start_hz: int, stop_hz: int, samples: List[int]) -> int:
    peak_idx = max(range(len(samples)), key=lambda i: samples[i])
    bin_hz = (stop_hz - start_hz) / max(1, len(samples) - 1)
    return int(start_hz + peak_idx * bin_hz)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-mhz", type=int, default=START_MHZ)
    ap.add_argument("--stop-mhz", type=int, default=STOP_MHZ)
    ap.add_argument("--step-mhz", type=int, default=STEP_MHZ)
    ap.add_argument("--level-dbm", type=float, default=LEVEL_DBM)
    ap.add_argument("--deviation-hz", type=int, default=DEVIATION_HZ)
    ap.add_argument("--span-hz", type=int, default=SPAN_HZ)
    ap.add_argument("--points", type=int, default=POINTS)
    ap.add_argument("--tolerance-hz", type=int, default=TOLERANCE_HZ)
    ap.add_argument("--settle-s", type=float, default=SETTLE_S)
    ap.add_argument("--scan-timeout-s", type=float, default=SCAN_TIMEOUT_S)
    ap.add_argument("--rbw", type=str, default="3")
    args = ap.parse_args()

    ctrl = SMY02Controller()
    sa = TinySA(scan_timeout_s=args.scan_timeout_s)
    measurements: List[Measurement] = []
    t_start = time.time()

    try:
        if not ctrl.connect():
            print("ERROR: SMY02 connection failed")
            return 1

        print(sa.cmd(f"rbw {args.rbw}"))
        print(sa.cmd("modulation off"))

        if not ctrl.set_amplitude(args.level_dbm):
            print("ERROR: Failed to set level")
            return 1
        if not ctrl.set_modulation_fm(args.deviation_hz):
            print("WARNING: Failed to set FM deviation; continuing")
        if not ctrl.enable_output():
            print("WARNING: RF enable reported failure; continuing")

        for mhz in range(args.start_mhz, args.stop_mhz + 1, args.step_mhz):
            target_hz = mhz * 1_000_000
            ok = ctrl.set_frequency(target_hz)
            if not ok:
                print(f"FAIL set_frequency {mhz} MHz")
                measurements.append(Measurement(target_hz, 0, 0, False))
                continue

            time.sleep(args.settle_s)
            start_hz = target_hz - args.span_hz // 2
            stop_hz = target_hz + args.span_hz // 2
            samples = sa.scanraw(start_hz, stop_hz, args.points)
            detected_hz = detect_peak_frequency(start_hz, stop_hz, samples)
            error_hz = detected_hz - target_hz
            pass_ok = abs(error_hz) <= args.tolerance_hz
            measurements.append(Measurement(target_hz, detected_hz, error_hz, pass_ok))

            status = "OK" if pass_ok else "FAIL"
            print(
                f"{status} target={mhz:3d}.000 MHz "
                f"detected={detected_hz/1e6:9.6f} MHz "
                f"error={error_hz:+7d} Hz"
            )

        total = len(measurements)
        passed = sum(1 for m in measurements if m.ok)
        failed = total - passed
        errors = [abs(m.error_hz) for m in measurements if m.detected_hz != 0]
        avg_err = int(statistics.mean(errors)) if errors else 0
        max_err = max(errors) if errors else 0
        elapsed = time.time() - t_start
        step_intervals = max(1, total - 1)
        sec_per_step = elapsed / step_intervals

        print("\nSUMMARY")
        print(f"Range: {args.start_mhz}..{args.stop_mhz} MHz, step {args.step_mhz} MHz")
        print(f"Pass: {passed}/{total}, Fail: {failed}")
        print(f"Average abs error: {avg_err} Hz")
        print(f"Max abs error: {max_err} Hz")
        print(f"Tolerance: +/-{args.tolerance_hz} Hz")
        print(f"Elapsed: {elapsed:.2f} s")
        print(f"Average step time: {sec_per_step:.3f} s")
        return 0 if failed == 0 else 2
    finally:
        try:
            ctrl.disable_output()
            ctrl.disconnect()
        except Exception:
            pass
        sa.close()


if __name__ == "__main__":
    raise SystemExit(main())

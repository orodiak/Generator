#!/usr/bin/env python3
"""
Benchmark SMY02 frequency switching speed.

Modes:
- write_only: send `RF <Hz>` only
- write_esr : send `RF <Hz>` then query `*ESR?`

This measures command/ack timing, not analyzer tracking.
"""

from __future__ import annotations

import argparse
import statistics
import time
from typing import List

import pyvisa


RESOURCE = "GPIB0::28::INSTR"


def summarize_ms(samples_s: List[float]) -> str:
    ms = [x * 1000.0 for x in samples_s]
    ms_sorted = sorted(ms)
    n = len(ms_sorted)
    p50 = ms_sorted[int(0.50 * (n - 1))]
    p95 = ms_sorted[int(0.95 * (n - 1))]
    return (
        f"n={n} min={ms_sorted[0]:.2f} ms avg={statistics.mean(ms_sorted):.2f} ms "
        f"p50={p50:.2f} ms p95={p95:.2f} ms max={ms_sorted[-1]:.2f} ms"
    )


def build_freqs(start_mhz: int, stop_mhz: int, step_mhz: int, cycles: int) -> List[int]:
    one = [mhz * 1_000_000 for mhz in range(start_mhz, stop_mhz + 1, step_mhz)]
    # Alternate direction to avoid long retrace jumps.
    seq = []
    for i in range(cycles):
        seq.extend(one if i % 2 == 0 else list(reversed(one)))
    return seq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-mhz", type=int, default=108)
    ap.add_argument("--stop-mhz", type=int, default=155)
    ap.add_argument("--step-mhz", type=int, default=1)
    ap.add_argument("--cycles", type=int, default=3)
    ap.add_argument("--inter-cmd-ms", type=float, default=0.0, help="Extra sleep between steps")
    args = ap.parse_args()

    rm = pyvisa.ResourceManager()
    devices = rm.list_resources()
    if RESOURCE not in devices:
        print(f"ERROR: {RESOURCE} not found. Devices: {devices}")
        return 1

    instr = rm.open_resource(RESOURCE)
    instr.timeout = 3000
    instr.read_termination = "\r\n"
    instr.write_termination = "\r\n"

    try:
        idn = instr.query("*IDN?").strip()
        print(f"Connected: {idn}")
        instr.write("*CLS")
        time.sleep(0.05)

        freqs = build_freqs(args.start_mhz, args.stop_mhz, args.step_mhz, args.cycles)
        print(
            f"Benchmark points: {len(freqs)} "
            f"({args.start_mhz}..{args.stop_mhz} MHz step {args.step_mhz}, cycles={args.cycles})"
        )

        # Warmup
        for hz in freqs[:5]:
            instr.write(f"RF {hz}")
            time.sleep(0.02)
        instr.write("*CLS")

        # Mode 1: write only
        t_write: List[float] = []
        for hz in freqs:
            t0 = time.perf_counter()
            instr.write(f"RF {hz}")
            t1 = time.perf_counter()
            t_write.append(t1 - t0)
            if args.inter_cmd_ms > 0:
                time.sleep(args.inter_cmd_ms / 1000.0)
        print("write_only :", summarize_ms(t_write))

        # Mode 2: write + ESR check
        instr.write("*CLS")
        t_esr: List[float] = []
        esr_errors = 0
        for hz in freqs:
            t0 = time.perf_counter()
            instr.write(f"RF {hz}")
            esr_resp = instr.query("*ESR?").strip()
            t1 = time.perf_counter()
            t_esr.append(t1 - t0)
            try:
                esr_val = int(esr_resp.split()[-1])
            except Exception:
                esr_val = -1
            if esr_val not in (0,):
                esr_errors += 1
            if args.inter_cmd_ms > 0:
                time.sleep(args.inter_cmd_ms / 1000.0)
        print("write_esr  :", summarize_ms(t_esr), f"errors={esr_errors}")
        return 0
    finally:
        try:
            instr.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

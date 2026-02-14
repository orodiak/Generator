#!/usr/bin/env python3
"""
Probe SMY02 FM bandwidth/deviation command support.

This script does not rely on GUI logic. It tries multiple command variants
for target FM deviations and reports:
  - command sent
  - *ESR? result
  - FM?/AF? readbacks (if available)

Use this to identify which command syntax your specific SMY02 firmware accepts.
"""

import logging
from time import sleep
from typing import Optional

import pyvisa


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


RESOURCE = "GPIB0::28::INSTR"
DEVIATIONS = [3125, 6250, 12500]
COMMAND_TEMPLATES = [
    "FM:DEV {dev}",
    "FM:DEV {dev_e}",
    "FM:DEVIATION {dev}",
    "FM:INT:DEV {dev}",
    "FM {dev}",
]


def safe_query(instr, query: str, timeout_ms: int = 1200) -> Optional[str]:
    old_timeout = instr.timeout
    try:
        instr.timeout = timeout_ms
        return instr.query(query).strip()
    except Exception:
        return None
    finally:
        instr.timeout = old_timeout


def main() -> int:
    rm = pyvisa.ResourceManager()
    devices = rm.list_resources()
    logger.info("Available devices: %s", devices)
    if RESOURCE not in devices:
        logger.error("Device %s not found", RESOURCE)
        return 1

    instr = rm.open_resource(RESOURCE)
    instr.timeout = 5000
    instr.read_termination = "\r\n"
    instr.write_termination = "\r\n"

    try:
        idn = safe_query(instr, "*IDN?") or "UNKNOWN"
        logger.info("Connected: %s", idn)

        # Baseline config for repeatable FM tests.
        for cmd in ("*CLS", "RF 144000000", "LEVEL -20", "FM:INT 1.000E+3", "AF 1000", "FM:ON"):
            instr.write(cmd)
            sleep(0.15)

        logger.info("Baseline FM?: %s", safe_query(instr, "FM?"))
        logger.info("Baseline AF?: %s", safe_query(instr, "AF?"))
        logger.info("-" * 72)

        for dev in DEVIATIONS:
            logger.info("TARGET DEVIATION: %s Hz", dev)
            dev_e = f"{float(dev):.3E}"

            for tpl in COMMAND_TEMPLATES:
                cmd = tpl.format(dev=dev, dev_e=dev_e)
                instr.write("*CLS")
                sleep(0.05)
                instr.write(cmd)
                sleep(0.18)

                esr = safe_query(instr, "*ESR?")
                fm = safe_query(instr, "FM?")
                af = safe_query(instr, "AF?")
                logger.info("  %-20s | ESR=%s | FM?=%s | AF?=%s", cmd, esr, fm, af)

            logger.info("-" * 72)

        logger.info("Probe complete.")
        logger.info("Pick commands where ESR=0 and FM?/AF? change as expected.")
        logger.info("Final note: verify actual RF deviation with spectrum analyzer if possible.")
        return 0
    finally:
        try:
            instr.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

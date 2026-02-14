#!/usr/bin/env python3
"""
Aggressive SMY02 shutdown - comprehensive FM/RF disable sequence.

Tries multiple disable methods to ensure FM and RF are completely off.
Use this if normal shutdown leaves signal present.
"""

import pyvisa
from time import sleep
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def aggressive_shutdown():
    """Aggressively disable all RF and modulation on SMY02."""
    
    rm = pyvisa.ResourceManager()
    devices = rm.list_resources()
    
    if "GPIB0::28::INSTR" not in devices:
        logger.error("Device GPIB0::28::INSTR not found")
        return False
    
    instr = rm.open_resource("GPIB0::28::INSTR")
    instr.timeout = 5000
    instr.read_termination = '\r\n'
    instr.write_termination = '\r\n'
    
    try:
        logger.info("=" * 70)
        logger.info("SMY02 AGGRESSIVE SHUTDOWN")
        logger.info("=" * 70)
        
        idn = instr.query("*IDN?")
        logger.info(f"Device: {idn}\n")
        
        # ============ STEP 1: DISABLE RF OUTPUT (Multiple Methods) ============
        logger.info("STEP 1: Disable RF Output")
        logger.info("-" * 70)
        
        disable_cmds = [
            "OUTP OFF",
            "OUTP:STAT OFF",
            "OUTPUT OFF",
            "SOUR:OUTP OFF",
            "RFOUT:STATE OFF",
        ]
        
        for cmd in disable_cmds:
            try:
                logger.info(f"  Sending: {cmd}")
                instr.write(cmd)
                sleep(0.2)
            except Exception as e:
                logger.debug(f"    (exception: {e})")
        
        logger.info("")
        
        # ============ STEP 2: DISABLE FM MODULATION (Multiple Methods) ============
        logger.info("STEP 2: Disable FM Modulation")
        logger.info("-" * 70)
        
        fm_disable_cmds = [
            "FM:OFF",
            "FM OFF",
            "FM:STAT OFF",
            "FM:STATE OFF",
            "MOD:TYPE OFF",
            "MOD OFF",
            "SOUR:MOD:TYPE OFF",
            "SOUR:MOD OFF",
        ]
        
        for cmd in fm_disable_cmds:
            try:
                logger.info(f"  Sending: {cmd}")
                instr.write(cmd)
                sleep(0.2)
            except Exception as e:
                logger.debug(f"    (exception: {e})")
        
        logger.info("")
        
        # ============ STEP 3: DISABLE LFO/TONE ============
        logger.info("STEP 3: Disable LFO/Tone Generation")
        logger.info("-" * 70)
        
        lfo_cmds = [
            "LFO:STAT OFF",
            "LFO OFF",
            "LFO:STATE OFF",
            "SOUR:LFO:STAT OFF",
            "SOUR:MOD:LFO:STAT OFF",
        ]
        
        for cmd in lfo_cmds:
            try:
                logger.info(f"  Sending: {cmd}")
                instr.write(cmd)
                sleep(0.2)
            except Exception as e:
                logger.debug(f"    (exception: {e})")
        
        logger.info("")
        
        # ============ STEP 4: SET SAFE DEFAULTS ============
        logger.info("STEP 4: Set Safe Defaults")
        logger.info("-" * 70)
        
        default_cmds = [
            ("RF 100000000", "Reset frequency to 100 MHz"),
            ("LEVEL -30", "Reset level to -30 dBm"),
        ]
        
        for cmd, desc in default_cmds:
            try:
                logger.info(f"  {desc}: {cmd}")
                instr.write(cmd)
                sleep(0.2)
            except Exception as e:
                logger.debug(f"    (exception: {e})")
        
        logger.info("")
        
        # ============ STEP 5: RESET AND CLEAR ============
        logger.info("STEP 5: Reset Device")
        logger.info("-" * 70)
        
        logger.info("  Sending: *RST (reset to factory defaults)")
        instr.write("*RST")
        sleep(0.5)
        
        logger.info("  Sending: *CLS (clear status)")
        instr.write("*CLS")
        sleep(0.2)
        
        logger.info("")
        
        # ============ VERIFICATION ============
        logger.info("=" * 70)
        logger.info("VERIFICATION - Final Device State:")
        logger.info("-" * 70)
        
        sleep(0.5)
        
        queries = [
            ("RF?", "RF Frequency"),
            ("LEVEL?", "Output Level"),
            ("FM?", "FM Status"),
            ("AF?", "Audio Frequency"),
            ("LFO:STAT?", "LFO Status (if exists)"),
            ("*ESR?", "Event Status Register"),
            ("ERR?", "Error Queue"),
        ]
        
        for query, desc in queries:
            try:
                resp = instr.query(query)
                logger.info(f"  {desc:25s} ({query:15s}): {resp.strip()}")
            except Exception as e:
                logger.warning(f"  {desc:25s} ({query:15s}): TIMEOUT/ERROR")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ AGGRESSIVE SHUTDOWN COMPLETE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("If signal is STILL present on TinySA:")
        logger.info("  1. Physically disconnect SMY02 output cable from antenna/receiver")
        logger.info("  2. Power cycle the SMY02 unit (turn off, wait 10s, turn on)")
        logger.info("  3. Run this script again")
        logger.info("")
        logger.info("If signal disappears, device is responding to disable commands.")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        instr.close()
        logger.info("Device disconnected")

if __name__ == "__main__":
    success = aggressive_shutdown()
    exit(0 if success else 1)

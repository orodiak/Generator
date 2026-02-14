#!/usr/bin/env python3
"""
Safe shutdown script for SMY02.

Explicitly disables RF output, FM modulation, and verifies shutdown state.
Run this to turn off the signal generator completely.
"""

import pyvisa
from time import sleep
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def shutdown_smy02():
    """Safely shut down SMY02 signal generator."""
    
    rm = pyvisa.ResourceManager()
    devices = rm.list_resources()
    
    if "GPIB0::28::INSTR" not in devices:
        logger.error("Device GPIB0::28::INSTR not found")
        return False
    
    # Open device
    instr = rm.open_resource("GPIB0::28::INSTR")
    instr.timeout = 5000
    instr.read_termination = '\r\n'
    instr.write_termination = '\r\n'
    
    try:
        logger.info("=" * 70)
        logger.info("SMY02 Shutdown Sequence")
        logger.info("=" * 70)
        
        # Device identity
        idn = instr.query("*IDN?")
        logger.info(f"Device: {idn}\n")
        
        # ============ SHUTDOWN SEQUENCE ============
        logger.info("SHUTDOWN STEPS:")
        logger.info("-" * 70)
        
        # 1. Disable RF output first
        logger.info("1. Disabling RF output (OUTP OFF)...")
        instr.write("OUTP OFF")
        sleep(0.3)
        logger.info("   ✓ OUTP OFF sent\n")
        
        # 2. Disable FM modulation
        logger.info("2. Disabling FM modulation (FM:OFF or FM OFF)...")
        instr.write("FM:OFF")
        sleep(0.2)
        logger.info("   ✓ FM:OFF sent\n")
        
        # 3. Try alternate FM off command
        logger.info("3. Trying alternate FM disable (FM OFF)...")
        instr.write("FM OFF")
        sleep(0.2)
        logger.info("   ✓ FM OFF sent\n")
        
        # 4. Disable output level (CRITICAL - this actually disables RF output per manual)
        logger.info("4. Disabling output level (LEVEL:OFF)...")
        instr.write("LEVEL:OFF")
        sleep(0.2)
        logger.info("   ✓ LEVEL:OFF sent\n")
        
        # 5. Reset device to defaults
        logger.info("5. Resetting device to factory defaults (*RST)...")
        instr.write("*RST")
        sleep(0.5)
        logger.info("   ✓ *RST sent\n")
        
        # 6. Clear status
        logger.info("6. Clearing status (*CLS)...")
        instr.write("*CLS")
        sleep(0.1)
        logger.info("   ✓ *CLS sent\n")
        
        # ============ VERIFY SHUTDOWN ============
        logger.info("=" * 70)
        logger.info("VERIFYING SHUTDOWN STATE:")
        logger.info("-" * 70)
        
        sleep(0.5)
        
        try:
            rf = instr.query("RF?")
            logger.info(f"RF Frequency:    {rf.strip()}")
        except Exception as e:
            logger.warning(f"RF? query failed: {e}")
        
        try:
            level = instr.query("LEVEL?")
            logger.info(f"Output Level:    {level.strip()}")
        except Exception as e:
            logger.warning(f"LEVEL? query failed: {e}")
        
        try:
            fm = instr.query("FM?")
            logger.info(f"FM Status:       {fm.strip()}")
        except Exception as e:
            logger.warning(f"FM? query failed: {e}")
        
        try:
            esr = instr.query("*ESR?")
            logger.info(f"Event Status:    {esr.strip()}")
        except Exception as e:
            logger.warning(f"*ESR? query failed: {e}")
        
        try:
            err = instr.query("ERR?")
            logger.info(f"Error Queue:     {err.strip()}")
        except Exception as e:
            logger.warning(f"ERR? query failed: {e}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ Shutdown Complete")
        logger.info("=" * 70)
        logger.info("RF output should now be OFF and device reset to defaults.")
        logger.info("If signal is still detected on TinySA, check physical connectors")
        logger.info("and verify the signal generator is not powered from a different source.")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        instr.close()
        logger.info("Device disconnected")

if __name__ == "__main__":
    success = shutdown_smy02()
    exit(0 if success else 1)

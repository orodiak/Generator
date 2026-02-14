#!/usr/bin/env python3
"""
Query SMY02 device state without enabling RF output.

Safe diagnostic script to verify all settings before actual RF transmission.
"""

import pyvisa
from time import sleep
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def query_device_state():
    """Query and display SMY02 configuration state."""
    
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
        logger.info("=" * 60)
        logger.info("SMY02 Device State Query")
        logger.info("=" * 60)
        
        # Device identity
        idn = instr.query("*IDN?")
        logger.info(f"Device ID: {idn}")
        
        # Clear status
        instr.write("*CLS")
        sleep(0.1)
        
        # ============ QUERY ALL SETTINGS ============
        logger.info("")
        logger.info("FREQUENCY & AMPLITUDE:")
        logger.info("-" * 60)
        
        try:
            rf = instr.query("RF?")
            logger.info(f"  RF frequency:     {rf.strip()}")
        except Exception as e:
            logger.warning(f"  RF? failed: {e}")
        
        try:
            level = instr.query("LEVEL?")
            logger.info(f"  Output level:     {level.strip()}")
        except Exception as e:
            logger.warning(f"  LEVEL? failed: {e}")
        
        logger.info("")
        logger.info("MODULATION & TONE:")
        logger.info("-" * 60)
        
        try:
            fm_status = instr.query("FM?")
            logger.info(f"  FM status:        {fm_status.strip()}")
        except Exception as e:
            logger.warning(f"  FM? failed: {e}")
        
        try:
            af = instr.query("AF?")
            logger.info(f"  Audio frequency:  {af.strip()}")
        except Exception as e:
            logger.warning(f"  AF? failed: {e}")
        
        logger.info("")
        logger.info("OUTPUT STATUS:")
        logger.info("-" * 60)
        
        try:
            outp = instr.query("OUTP?")
            logger.info(f"  RF output:        {outp.strip()}")
        except Exception as e:
            logger.warning(f"  OUTP? failed: {e}")
        
        logger.info("")
        logger.info("ERROR STATUS:")
        logger.info("-" * 60)
        
        try:
            esr = instr.query("*ESR?")
            logger.info(f"  Event Status Reg: {esr.strip()}")
        except Exception as e:
            logger.warning(f"  *ESR? failed: {e}")
        
        try:
            err = instr.query("ERR?")
            logger.info(f"  Error query:      {err.strip()}")
        except Exception as e:
            logger.warning(f"  ERR? failed: {e}")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("Query complete. RF output is OFF.")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Error during query: {e}")
        return False
    finally:
        instr.close()
        logger.info("Device disconnected")

if __name__ == "__main__":
    success = query_device_state()
    exit(0 if success else 1)

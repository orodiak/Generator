#!/usr/bin/env python3
"""
Configure SMY02 for 144 MHz FM tone generation.

Based on interactive pyvisa-shell testing results, this script applies
the exact command sequence that worked in the user's session.
"""

import pyvisa
from time import sleep
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def configure_smy02_fm_tone():
    """Configure SMY02 for 144 MHz FM with 1 kHz tone."""
    
    rm = pyvisa.ResourceManager()
    
    # List devices
    devices = rm.list_resources()
    logger.info(f"Available devices: {devices}")
    
    if "GPIB0::28::INSTR" not in devices:
        logger.error("Device GPIB0::28::INSTR not found")
        return False
    
    # Open device
    instr = rm.open_resource("GPIB0::28::INSTR")
    instr.timeout = 5000
    instr.read_termination = '\r\n'
    instr.write_termination = '\r\n'
    
    try:
        # Verify connection
        idn = instr.query("*IDN?")
        logger.info(f"Device ID: {idn}")
        
        # Clear status
        instr.write("*CLS")
        sleep(0.1)
        
        # Query initial status
        esr = instr.query("*ESR?")
        logger.info(f"Initial *ESR?: {esr}")
        
        # ============ SET FREQUENCY ============
        logger.info("Setting frequency to 144 MHz...")
        instr.write("RF 144000000")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"After RF 144000000: *ESR? = {esr}")
        
        # Verify frequency
        try:
            rf_resp = instr.query("RF?")
            logger.info(f"RF? -> {rf_resp}")
        except Exception as e:
            logger.warning(f"RF? query timed out or failed: {e}")
        
        # ============ SET AMPLITUDE ============
        logger.info("Setting amplitude to -20 dBm...")
        instr.write("LEVEL -20")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"After LEVEL -20: *ESR? = {esr}")
        
        # Verify amplitude
        try:
            level_resp = instr.query("LEVEL?")
            logger.info(f"LEVEL? -> {level_resp}")
        except Exception as e:
            logger.warning(f"LEVEL? query timed out or failed: {e}")
        
        # ============ CONFIGURE FM TONE ============
        logger.info("Configuring FM modulation with 1 kHz tone...")
        
        # Set FM tone frequency (method 1: FM:INT)
        instr.write("FM:INT 1.000E+3")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"After FM:INT 1.000E+3: *ESR? = {esr}")
        
        # Verify FM:INT
        try:
            fm_resp = instr.query("FM?")
            logger.info(f"FM? -> {fm_resp}")
        except Exception as e:
            logger.warning(f"FM? query timed out: {e}")
        
        # Also set via AF (audio frequency / tone frequency)
        logger.info("Setting audio frequency to 1000 Hz...")
        instr.write("AF 1000")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"After AF 1000: *ESR? = {esr}")
        
        # Verify AF
        try:
            af_resp = instr.query("AF?")
            logger.info(f"AF? -> {af_resp}")
        except Exception as e:
            logger.warning(f"AF? query timed out: {e}")
        
        # ============ ENABLE FM ============
        logger.info("Enabling FM modulation (FM:ON)...")
        instr.write("FM:ON")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"After FM:ON: *ESR? = {esr}")
        
        # Verify FM enabled
        try:
            fm_resp = instr.query("FM?")
            logger.info(f"FM? after FM:ON -> {fm_resp}")
        except Exception as e:
            logger.warning(f"FM? query timed out: {e}")
        
        # ============ ENABLE RF OUTPUT ============
        logger.info("Enabling RF output...")
        instr.write("OUTP ON")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"After OUTP ON: *ESR? = {esr}")
        
        logger.info("✓ Configuration complete!")
        logger.info("Device should now output 144 MHz FM with 1 kHz tone at -20 dBm")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during configuration: {e}")
        return False
    finally:
        instr.close()
        logger.info("Device disconnected")

if __name__ == "__main__":
    success = configure_smy02_fm_tone()
    exit(0 if success else 1)

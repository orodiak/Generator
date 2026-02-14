#!/usr/bin/env python3
"""
Configure and enable SMY02 144 MHz FM tone for TinySA testing.

This script:
1. Sets frequency to 144 MHz
2. Sets level to -20 dBm
3. Enables FM modulation with 1 kHz tone
4. Enables RF output
5. Stays connected and periodically checks status
"""

import pyvisa
from time import sleep
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def enable_and_monitor():
    """Configure SMY02 and monitor for TinySA testing."""
    
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
        logger.info("SMY02 Configuration for TinySA Testing")
        logger.info("=" * 70)
        
        # Device identity
        idn = instr.query("*IDN?")
        logger.info(f"Device: {idn}\n")
        
        # Clear status
        instr.write("*CLS")
        sleep(0.1)
        
        # ============ CONFIGURE ============
        logger.info("CONFIGURATION STEPS:")
        logger.info("-" * 70)
        
        # 1. Set frequency
        logger.info("1. Setting frequency to 144 MHz...")
        instr.write("RF 144000000")
        sleep(0.2)
        rf = instr.query("RF?")
        logger.info(f"   → {rf.strip()}\n")
        
        # 2. Set amplitude
        logger.info("2. Setting amplitude to -20 dBm...")
        instr.write("LEVEL -20")
        sleep(0.2)
        level = instr.query("LEVEL?")
        logger.info(f"   → {level.strip()}\n")
        
        # 3. Set FM tone frequency
        logger.info("3. Setting FM tone frequency to 1 kHz...")
        instr.write("FM:INT 1.000E+3")
        sleep(0.2)
        fm_int = instr.query("FM?")
        logger.info(f"   → {fm_int.strip()}\n")
        
        # 4. Set audio frequency
        logger.info("4. Setting audio frequency to 1000 Hz...")
        instr.write("AF 1000")
        sleep(0.2)
        af = instr.query("AF?")
        logger.info(f"   → {af.strip()}\n")
        
        # 5. Enable FM
        logger.info("5. Enabling FM modulation...")
        instr.write("FM:ON")
        sleep(0.2)
        fm_stat = instr.query("FM?")
        logger.info(f"   → {fm_stat.strip()}\n")
        
        # 6. Enable output
        logger.info("6. Enabling RF output...")
        instr.write("OUTP ON")
        sleep(0.2)
        esr = instr.query("*ESR?")
        logger.info(f"   → RF output enabled (*ESR: {esr.strip()})\n")
        
        logger.info("=" * 70)
        logger.info("✓ Configuration Complete!")
        logger.info("=" * 70)
        logger.info("RF is NOW TRANSMITTING: 144 MHz FM with 1 kHz modulation tone")
        logger.info("Power level: -20 dBm")
        logger.info("")
        logger.info("Ready for TinySA testing. Press Ctrl+C to stop and disable output.")
        logger.info("=" * 70)
        
        # ============ MONITOR ============
        try:
            monitor_count = 0
            while True:
                sleep(5)
                monitor_count += 1
                
                # Periodically check status
                try:
                    esr = instr.query("*ESR?")
                    fm_stat = instr.query("FM?")
                    rf = instr.query("RF?")
                    level = instr.query("LEVEL?")
                    
                    if monitor_count % 6 == 0:  # Log every 30 seconds
                        logger.info(f"Status check #{monitor_count // 6}min:")
                        logger.info(f"  RF: {rf.strip()}")
                        logger.info(f"  Level: {level.strip()}")
                        logger.info(f"  FM: {fm_stat.strip()}")
                        logger.info(f"  ESR: {esr.strip()}")
                except Exception as e:
                    logger.debug(f"Status check error: {e}")
        
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        
        # ============ DISABLE OUTPUT ============
        logger.info("Disabling RF output...")
        instr.write("OUTP OFF")
        sleep(0.2)
        logger.info("Disabling FM modulation...")
        instr.write("FM:OFF")
        sleep(0.2)
        logger.info("Disabling output level (LEVEL:OFF per manual)...")
        instr.write("LEVEL:OFF")
        sleep(0.2)
        logger.info("RF output disabled")
        
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
    success = enable_and_monitor()
    exit(0 if success else 1)

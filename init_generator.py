#!/usr/bin/env python3
"""
Initial setup script for SMY02 signal generator.

Establishes communication, verifies device connection, and configures
for 144 MHz FM tone generation.
"""

import sys
import os
from time import sleep

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from smy02_controller import SMY02Controller


def main():
    """Main initialization routine."""
    
    print("=" * 60)
    print("SMY02 Signal Generator - Initialization")
    print("=" * 60)
    
    # List available devices
    print("\nScanning for available GPIB/USB devices...")
    devices = SMY02Controller.list_available_devices()
    
    if not devices:
        print("ERROR: No devices found!")
        return False
    
    print(f"Found {len(devices)} device(s):")
    for i, device in enumerate(devices, 1):
        print(f"  {i}. {device}")
    
    # Connect to device at GPIB 28
    resource_name = "GPIB0::28::INSTR"
    print(f"\nConnecting to {resource_name}...")
    
    controller = SMY02Controller(resource_name=resource_name)
    
    if not controller.connect():
        print("ERROR: Failed to connect to device!")
        return False
    
    print("✓ Connection established")
    
    # Get current settings
    print("\nQuerying device settings...")
    try:
        freq = controller.get_frequency()
        amp = controller.get_amplitude()
        print(f"  Current frequency: {freq} Hz")
        print(f"  Current amplitude: {amp} dBm")
    except Exception as e:
        print(f"  Warning: Could not query settings: {e}")
    
    # Configure for 144 MHz FM
    print("\nConfiguring for 144 MHz FM tone generation...")
    print("  Setting frequency to 144 MHz...")
    if not controller.set_frequency(144e6):
        print("ERROR: Failed to set frequency!")
        controller.disconnect()
        return False
    # Check instrument error queue and ESR
    err = controller.get_system_error()
    esr = controller.get_esr()
    print(f"  SYST:ERR? -> {err}")
    print(f"  *ESR? -> {esr}")
    if err and not err.startswith("0"):
        print(f"DEVICE ERROR AFTER SET FREQUENCY: {err}")
        print("Aborting to avoid unsafe state. Please check instrument.")
        controller.disconnect()
        return False
    print("  ✓ Frequency set")
    
    # Set amplitude to -20 dBm for safety
    print("  Setting amplitude to -20 dBm...")
    if not controller.set_amplitude(-20):
        print("ERROR: Failed to set amplitude!")
        controller.disconnect()
        return False
    err = controller.get_system_error()
    esr = controller.get_esr()
    print(f"  SYST:ERR? -> {err}")
    print(f"  *ESR? -> {esr}")
    if err and not err.startswith("0"):
        print(f"DEVICE ERROR AFTER SET AMPLITUDE: {err}")
        print("Aborting to avoid unsafe state. Please check instrument.")
        controller.disconnect()
        return False
    print("  ✓ Amplitude set")
    
    # Configure FM modulation
    print("  Enabling FM modulation with 5 kHz deviation...")
    if not controller.set_modulation_fm(deviation=5000):
        print("ERROR: Failed to set FM modulation!")
        controller.disconnect()
        return False
    err = controller.get_system_error()
    esr = controller.get_esr()
    print(f"  SYST:ERR? -> {err}")
    print(f"  *ESR? -> {esr}")
    if err and not err.startswith("0"):
        print(f"DEVICE ERROR AFTER SET MODULATION: {err}")
        print("Aborting to avoid unsafe state. Please check instrument.")
        controller.disconnect()
        return False
    print("  ✓ FM modulation enabled")
    
    # Set LFO for tone generation (1 kHz tone)
    print("  Setting LFO for 1 kHz tone...")
    if not controller.set_lfo_frequency(1000):
        print("ERROR: Failed to set LFO frequency!")
        controller.disconnect()
        return False
    err = controller.get_system_error()
    esr = controller.get_esr()
    print(f"  SYST:ERR? -> {err}")
    print(f"  *ESR? -> {esr}")
    if err and not err.startswith("0"):
        print(f"DEVICE ERROR AFTER SET LFO FREQUENCY: {err}")
        print("Aborting to avoid unsafe state. Please check instrument.")
        controller.disconnect()
        return False
    print("  ✓ LFO frequency set")
    
    # Enable LFO
    print("  Enabling LFO...")
    if not controller.enable_lfo():
        print("ERROR: Failed to enable LFO!")
        controller.disconnect()
        return False
    err = controller.get_system_error()
    esr = controller.get_esr()
    print(f"  SYST:ERR? -> {err}")
    print(f"  *ESR? -> {esr}")
    if err and not err.startswith("0"):
        print(f"DEVICE ERROR AFTER ENABLE LFO: {err}")
        print("Aborting to avoid unsafe state. Please check instrument.")
        controller.disconnect()
        return False
    print("  ✓ LFO enabled")
    
    # Enable output
    print("  Enabling RF output...")
    if not controller.enable_output():
        print("ERROR: Failed to enable output!")
        controller.disconnect()
        return False
    err = controller.get_system_error()
    esr = controller.get_esr()
    print(f"  SYST:ERR? -> {err}")
    print(f"  *ESR? -> {esr}")
    if err and not err.startswith("0"):
        print(f"DEVICE ERROR AFTER ENABLE OUTPUT: {err}")
        print("Aborting to avoid unsafe state. Please check instrument.")
        controller.disconnect()
        return False
    print("  ✓ RF output enabled")
    
    print("\n" + "=" * 60)
    print("CONFIGURATION COMPLETE")
    print("=" * 60)
    print("\nGenerator is now transmitting:")
    print("  Frequency: 144 MHz")
    print("  Modulation: FM")
    print("  Tone: 1 kHz")
    print("  Deviation: 5 kHz")
    print("  Power: -20 dBm")
    print("\nPress Enter to disable output and disconnect...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    # Cleanup
    print("\nShutting down...")
    controller.disable_output()
    controller.disable_lfo()
    controller.reset()
    controller.disconnect()
    print("✓ Disconnected")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

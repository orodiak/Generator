# SMY02 Signal Generator Control - Workflow Guide

## Project Overview
Python-based control system for Rhode & Schwarz SMY02 signal generator connected via GPIB/USB (address 28).

## Quick Start Commands

### 1. Query Device State (Safe - RF OFF)
```bash
python query_device_state.py
```
Shows current frequency, level, FM status, tone frequency, and error state without enabling output.

### 2. Enable RF for Testing (Transmitting)
```bash
python enable_and_monitor.py
```
- Configures: 144 MHz, -20 dBm, FM with 1 kHz tone
- Enables RF output
- Monitors device status every 30 seconds
- Press Ctrl+C to stop and disable output

### 3. Shutdown / Disable Output
```bash
python shutdown_smy02.py
```
- Disables RF output (OUTP OFF)
- Disables FM modulation (FM:OFF)
- Resets device to factory defaults (*RST)
- Verifies clean shutdown state

### 4. Complete Configuration Without Auto-Enable
```bash
python config_fm_tone.py
```
- Sets frequency, level, FM tone
- Does NOT enable RF output
- Useful for pre-configuration checks

## Device Communication

**Connection:** GPIB0::28::INSTR (GPIB address 28 over USB)

**Vendor-Specific Commands (Preferred):**
- `RF <frequency_Hz>` — Set RF frequency (e.g., `RF 144000000` for 144 MHz)
- `LEVEL <dBm>` — Set output amplitude (e.g., `LEVEL -20`)
- `FM:INT <Hz>` — Set FM tone frequency (e.g., `FM:INT 1.000E+3` for 1 kHz)
- `AF <Hz>` — Alternate audio frequency setting (e.g., `AF 1000`)
- `FM:ON` / `FM:OFF` — Enable/disable FM modulation
- `OUTP ON` / `OUTP OFF` — Enable/disable RF output

**Query Commands:**
- `RF?` — Read current frequency
- `LEVEL?` — Read current output level
- `FM?` — Read FM modulation status
- `AF?` — Read audio frequency
- `*ESR?` — Read Event Status Register (numeric, non-blocking)
- `ERR?` — Read error queue

## Typical Testing Workflow

### Step 1: Check Device Status
```bash
python query_device_state.py
```
Expected output:
- RF frequency: 144.000000E+6 (or previous setting)
- LEVEL: -20.0 dBm (or previous setting)
- FM Status: FM:OFF (if not transmitting)
- ERRORS: 0 (no errors)

### Step 2: Enable Transmission for TinySA Measurement
```bash
python enable_and_monitor.py
```
- Device will start transmitting 144 MHz FM with 1 kHz modulation
- Logs status every 30 seconds
- Device stays connected and active

### Step 3: Perform Measurements
While `enable_and_monitor.py` is running:
- Use TinySA to measure the 144 MHz signal
- Verify FM modulation characteristic
- Check power level at -20 dBm

### Step 4: Stop Transmission
In terminal running `enable_and_monitor.py`:
- Press Ctrl+C to cleanly shutdown
- Script will automatically disable output
- Device will disconnect

### Step 5: Verify Shutdown
```bash
python shutdown_smy02.py
```
- Final verification that output is off
- Device reset to factory defaults
- Check no residual signals

## Configuration Examples

### Safe Configuration (No Output)
```bash
python config_fm_tone.py
```

### Custom Frequency (With Output)
Edit `enable_and_monitor.py`, change:
```python
instr.write("RF 144000000")  # Change frequency here (in Hz)
instr.write("LEVEL -20")      # Change level here (in dBm)
```

### Longer Monitoring Duration
Edit `enable_and_monitor.py`, change monitoring loop sleep:
```python
sleep(5)  # Check every 5 seconds (change to desired interval)
```

## Troubleshooting

### Signal Still Present After Shutdown
1. Run `python shutdown_smy02.py` again
2. Physically disconnect SMY02 output cable
3. Power cycle the SMY02 unit

### Device Not Found
```bash
python -m pyvisa.shell
# Then type: list
# Should show "GPIB0::28::INSTR" in the list
```

### Queries Timeout
- Normal behavior for some query commands (device firmware quirk)
- Scripts use non-blocking `*ESR?` for status checks
- Best-effort readback queries have exception handling

### RF Output Won't Disable
1. Try `python shutdown_smy02.py` which sends multiple disable commands
2. Check GPIB cable connection
3. Verify device is responding to commands (check `*IDN?` works)

## File Structure

```
Generator/
├── src/
│   └── smy02_controller.py       # Main controller class (library)
├── enable_and_monitor.py          # Enable RF & monitor (TRANSMITTING)
├── config_fm_tone.py              # Configure but don't enable (SAFE)
├── query_device_state.py          # Query only, no changes (READ-ONLY)
├── shutdown_smy02.py              # Disable RF output (SAFE SHUTDOWN)
├── init_generator.py              # Legacy init script
├── requirements.txt               # Python dependencies
├── setup.py                       # Package setup
└── README.md                      # Project documentation
```

## Safety Reminders

✓ **Safe for casual testing:**
- `query_device_state.py` — only reads, never changes anything
- `config_fm_tone.py` — sets parameters but RF stays OFF
- `shutdown_smy02.py` — always safe, only disables

⚠️ **Transmitting (RF Output ON):**
- `enable_and_monitor.py` — actively transmits, keep away from sensitive equipment
- Always check TinySA shows the expected signal before relying on transmitter
- Press Ctrl+C to stop transmission immediately

## Device Specifications

- **Model:** Rhode & Schwarz SMY02
- **Serial:** 825248/028
- **Firmware:** 2.02
- **Connection:** GPIB over USB (address 28)
- **Typical Config:** 144 MHz FM, -20 dBm, 1 kHz modulation tone

## Next Steps

1. Use `enable_and_monitor.py` for TinySA measurements
2. Customize frequency/level/tone as needed
3. Add external modulation input (audio source) to FM modulation port
4. Expand controller for additional features (sweep, list mode, etc.)

---

**Last Updated:** 2026-02-14
**Status:** ✓ Fully functional and tested

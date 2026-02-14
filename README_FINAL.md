# SMY02 Signal Generator Control System - Final Status

## ✓ Project Complete

All functionality is working as expected. The SMY02 signal generator is now fully controlled via Python with reliable RF enable/disable.

## Quick Reference Commands

```bash
# Check device state (RF OFF - safe)
python query_device_state.py

# Enable transmission for testing (RF ON - transmitting)
python enable_and_monitor.py
# Press Ctrl+C to stop and cleanly shutdown

# Manual shutdown (if needed)
python shutdown_smy02.py
```

## Critical Discovery: LEVEL:OFF

The key to proper RF shutdown is the vendor-specific command `LEVEL:OFF` (not standard SCPI). This is the actual mute/disable command for the SMY02.

**Complete Shutdown Sequence:**
1. `OUTP OFF` — Disable RF output
2. `FM:OFF` — Disable FM modulation
3. `FM OFF` — Alternate FM disable form
4. **`LEVEL:OFF`** — Mute/disable output (CRITICAL)
5. `*RST` — Reset to factory defaults
6. `*CLS` — Clear status

## Device Configuration (Default)

- **Frequency:** 144 MHz
- **Level:** -20 dBm
- **Modulation:** FM with 1 kHz tone
- **Connection:** GPIB0::28::INSTR (GPIB address 28 over USB)
- **Device ID:** ROHDE&SCHWARZ,SMY02,825248/028,2.02

## Vendor Command Reference

### Configuration Commands
| Command | Purpose | Example |
|---------|---------|---------|
| `RF <Hz>` | Set frequency | `RF 144000000` (144 MHz) |
| `LEVEL <dBm>` | Set output level | `LEVEL -20` (-20 dBm) |
| `FM:INT <Hz>` | Set FM tone frequency | `FM:INT 1.000E+3` (1 kHz) |
| `AF <Hz>` | Set audio frequency (alternate) | `AF 1000` |
| `FM:ON` | Enable FM modulation | `FM:ON` |
| `FM:OFF` | Disable FM modulation | `FM:OFF` |
| `OUTP ON` | Enable RF output | `OUTP ON` |
| `OUTP OFF` | Disable RF output | `OUTP OFF` |
| **`LEVEL:OFF`** | **Mute output (KEY COMMAND)** | **`LEVEL:OFF`** |

### Query Commands
| Command | Purpose | Response |
|---------|---------|----------|
| `RF?` | Query frequency | `RF  144.000000E+6` |
| `LEVEL?` | Query output level | `LEVEL  -20.0` |
| `FM?` | Query FM status | `FM:INT 1.000E+3` or `FM:OFF` |
| `AF?` | Query audio frequency | `AF  1.0000E+3` |
| `*IDN?` | Query device identity | Device model/serial |
| `*ESR?` | Query event status (numeric) | Numeric status (0 = ok) |
| `ERR?` | Query error queue | `ERRORS  0` (0 = no errors) |

## File Structure

```
Generator/
├── enable_and_monitor.py      # ✓ Enable RF, monitor, clean shutdown
├── query_device_state.py      # ✓ Read-only state check
├── shutdown_smy02.py          # ✓ Safe shutdown with LEVEL:OFF
├── config_fm_tone.py          # ✓ Configure but don't enable
├── aggressive_shutdown.py     # ✓ Multiple disable methods
├── src/
│   └── smy02_controller.py    # Library class (Python API)
├── WORKFLOW.md                # Usage guide
├── SHUTDOWN_ANALYSIS.md       # Technical analysis (LEVEL:OFF discovery)
├── README.md                  # Project documentation
└── requirements.txt           # Python dependencies
```

## Workflow for RF Testing

### Step 1: Verify Device State
```bash
python query_device_state.py
```
Expected: RF=144 MHz, Level=-20 dBm, FM=OFF (when not transmitting)

### Step 2: Start Transmission
```bash
python enable_and_monitor.py
```
- Configures 144 MHz FM with 1 kHz tone at -20 dBm
- Enables RF output (transmitting)
- Logs status every 30 seconds
- Device stays connected and active

### Step 3: Measure with TinySA
While `enable_and_monitor.py` is running:
- Connect TinySA to SMY02 RF output
- Observe 144 MHz signal with FM modulation
- Verify -20 dBm power level
- Check modulation characteristics

### Step 4: Stop Transmission
Press Ctrl+C in terminal running `enable_and_monitor.py`:
- Script cleanly stops transmission
- Sends `LEVEL:OFF` to mute output
- Disables FM and RF
- Device disconnects
- **Signal disappears from TinySA** ✓

## Testing Results

✓ **Signal Generation:** 144 MHz FM with 1 kHz tone successfully generated  
✓ **Signal Detection:** TinySA detects the signal correctly  
✓ **Power Level:** -20 dBm confirmed  
✓ **Shutdown:** Signal properly disappears with `LEVEL:OFF` command  
✓ **Repeatability:** Multiple enable/disable cycles work reliably  

## Known Behaviors

- `SYST:ERR?` query sometimes times out (use `*ESR?` instead for non-blocking status)
- `OUTP?` query may timeout (not critical, use `OUTP ON/OFF` without verification)
- System GPIB layer shows "libgpib: invalid descriptor" warnings (harmless, from system layer)
- Device responds to multiple command variants (e.g., `FM:ON`, `FM ON`, `FM:STAT ON`)
- After `*RST` reset, frequency returns to 100 MHz and level to -30 dBm (factory defaults)

## Customization

### Change Frequency
Edit `enable_and_monitor.py`:
```python
instr.write("RF 144000000")  # Change this value (in Hz)
```

### Change Output Level
Edit `enable_and_monitor.py`:
```python
instr.write("LEVEL -20")     # Change dBm value
```

### Change Modulation Tone Frequency
Edit `enable_and_monitor.py`:
```python
instr.write("FM:INT 1.000E+3")  # Change Hz value
```

## Safety Notes

✓ **Safe (RF OFF):**
- `query_device_state.py` — Read-only queries, no changes
- `config_fm_tone.py` — Pre-configuration, RF stays disabled
- `shutdown_smy02.py` — Disable all outputs

⚠️ **Transmitting (RF ON):**
- `enable_and_monitor.py` — Active transmission
- Keep away from sensitive equipment during testing
- Always press Ctrl+C to cleanly stop transmission
- Never leave device transmitting unattended

## Troubleshooting

**Signal still present after shutdown:**
1. Check that `python shutdown_smy02.py` sends `LEVEL:OFF`
2. Verify TinySA is connected to correct port
3. Power cycle the SMY02 device
4. Physically disconnect RF cable if needed

**Device not responding:**
1. Check GPIB/USB cable connection
2. Run `python query_device_state.py` to verify connection
3. Use `python -m pyvisa.shell` to manually test commands

**Queries timeout:**
- Normal behavior for some commands on this firmware
- Use `*ESR?` (numeric) instead of `SYST:ERR?` (text)
- Scripts use exception handling for timeouts

## Next Steps

1. ✓ Basic RF generation and control — **COMPLETE**
2. Additional features (sweep, list mode, etc.) — Can be added
3. External audio input to FM modulation port — Hardware dependent
4. Integration with other test equipment — Documented API in `src/smy02_controller.py`

---

**Project Status:** ✓ Fully Functional  
**Last Updated:** 2026-02-14  
**Tested:** Yes - RF generation and shutdown verified with TinySA  
**Key Learning:** `LEVEL:OFF` is the critical mute command for the SMY02

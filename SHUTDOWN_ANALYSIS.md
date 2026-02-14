# SMY02 RF Signal Shutdown - Root Cause Analysis

## Problem Found
Signal was persisting after FM modulation was disabled because the **output level was not being disabled**.

## Root Cause
The SMY02 has separate control paths:
1. **RF Output Enable** (`OUTP ON/OFF`) — Controls RF carrier availability
2. **FM Modulation** (`FM:ON/OFF`) — Routes audio to FM deviation
3. **Output Level** (`LEVEL:OFF`) — Actually disables/mutes the output (per manual)

Previous shutdown disabled #1 and #2, but the critical command `LEVEL:OFF` (which actually mutes the output per the user manual) was missing.

## Solution
Add `LEVEL:OFF` to the shutdown sequence to completely disable output.

## Updated Shutdown Sequence

### Corrected Shutdown (Per Manual)
**Files:** `shutdown_smy02.py` and `enable_and_monitor.py`
```
1. OUTP OFF      — Disable RF output
2. FM:OFF        — Disable FM modulation (primary)
3. FM OFF        — Disable FM modulation (alternate)
4. LEVEL:OFF     — Disable output level (CRITICAL - actual mute command per manual)
5. *RST          — Reset to factory defaults
6. *CLS          — Clear status
```

### Enhanced Monitoring (Updated)
**File:** `enable_and_monitor.py`
Now includes proper shutdown on Ctrl+C:
```
1. OUTP OFF      — Disable RF output
2. FM:OFF        — Disable FM modulation
3. LEVEL:OFF     — Disable output level (actual mute)
```

## Testing Results

**Before Fix:**
- Signal persisted after `FM:OFF` and `OUTP OFF`
- TinySA still detected 144 MHz signal
- Tried `AF:OFF` (incorrect command)

**After Using Correct `LEVEL:OFF`:**
- Signal disappeared from TinySA ✓
- Complete shutdown verified
- Per user manual review: `LEVEL:OFF` is the actual output disable command

## Key Learning
The SMY02 command `LEVEL:OFF` (not a numeric level like `-30`) is the actual mute/disable command for output. This is different from SCPI-standard `SOUR:POW` commands and is specific to this device's vendor command set.

## Files Updated
- `shutdown_smy02.py` — Step 4 now uses `LEVEL:OFF` (corrected from `AF:OFF`)
- `enable_and_monitor.py` — Shutdown sequence now uses `LEVEL:OFF` (corrected)

## Usage
### Safe Shutdown (Complete - Corrected)
```bash
python shutdown_smy02.py
```
Signal should disappear after `LEVEL:OFF` command.

### Enable with Proper Cleanup
```bash
python enable_and_monitor.py
# Press Ctrl+C when done - properly disables output with LEVEL:OFF
```

## Recommendations for Future Implementations
1. Always send `LEVEL:OFF` to disable/mute output (vendor-specific command)
2. Use the verified sequence: `OUTP OFF` → `FM:OFF` → `FM OFF` → `LEVEL:OFF` → `*RST` → `*CLS`
3. Consult the user manual for vendor-specific disable commands
4. Test signal presence after each disable command to verify
5. Document this hardware-specific behavior: `LEVEL:OFF` is the actual mute command

---
**Status:** ✓ RESOLVED (Corrected from AF:OFF to LEVEL:OFF)
**Date:** 2026-02-14
**Source:** User manual review by operator

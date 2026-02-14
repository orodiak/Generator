# SMY02 GUI Application - User Guide

## Overview
The SMY02 GUI provides an easy-to-use interface for controlling the signal generator with advanced features like presets and frequency hopping.

## Starting the GUI

```bash
python smy02_gui.py
```

A window will open with multiple control sections.

## Features

### 1. Device Connection
- **Connect** — Establish connection to SMY02 (must do this first)
- **Disconnect** — Close connection safely
- Status indicator shows connection state (Red=Disconnected, Green=Connected)

### 2. Frequency & Level Control
- **Frequency (MHz)** — Enter frequency in MHz (e.g., 144.0 for 144 MHz)
- **Level (dBm)** — Enter power output in dBm (e.g., -20 for -20 dBm)
- **Modulation** — Select FM, AM, or Off
- **Bandwidth** — Select FM bandwidth: 6.25 kHz, 12.5 kHz, or 25 kHz
- Click **Set** buttons to apply changes

### 3. Transmit Control
- **Enable RF** — Start RF transmission with current settings
- **Disable RF** — Stop RF transmission (button changes to "Disable RF" when ON)
- **Shutdown** — Complete device shutdown with proper cleanup
- RF status indicator shows ON/OFF state

### 4. Presets
Save and load frequency/level/bandwidth configurations:

**Save a Preset:**
1. Set desired Frequency, Level, and Bandwidth
2. Enter a name (e.g., "VHF Repeater", "ISM Band")
3. Click **Save Preset**
4. Preset is saved to `presets.json`

**Load a Preset:**
1. Select preset from dropdown menu
2. Settings automatically populate
3. Click "Set" buttons or "Enable RF" to apply

**Delete a Preset:**
1. Select preset from dropdown
2. Click **Delete**

### 5. Frequency Hop Playlist

Create a sequence of frequencies to hop between automatically.

**Add to Playlist:**
1. Set desired frequency, level, and bandwidth
2. Click **Add to Playlist**
3. Entry appears in the list below

**Remove from Playlist:**
1. Select entry in list
2. Click **Remove Selected**

**Start Frequency Hopping:**
1. Configure dwell time (time on each frequency in seconds)
2. Click **Start Hopping**
3. Generator will automatically cycle through all frequencies
4. Current frequency is highlighted in the list
5. Settings update automatically on each hop

**Stop Hopping:**
1. Click **Stop Hopping** to end the sequence
2. Generator stays on last frequency

## Workflow Examples

### Example 1: Simple Transmission
```
1. Click "Connect"
2. Enter frequency: 144.0 MHz
3. Enter level: -20 dBm
4. Select bandwidth: 12.5 kHz
5. Click "Enable RF" (device transmits)
6. Use TinySA to measure signal
7. Click "Disable RF" to stop (or close window for automatic shutdown)
```

### Example 2: Save and Use Presets
```
1. Connect to device
2. Set frequency to 144.0 MHz, level -20 dBm
3. Enter preset name: "VHF Main"
4. Click "Save Preset"
5. Change to 147.0 MHz, -15 dBm
6. Enter preset name: "VHF Secondary"
7. Click "Save Preset"
8. Later: Select "VHF Main" from dropdown to instantly load those settings
```

### Example 3: Frequency Hopping (Repeater Test)
```
1. Connect to device
2. Add to playlist: 144.0 MHz, -20 dBm
3. Add to playlist: 144.5 MHz, -20 dBm
4. Add to playlist: 145.0 MHz, -20 dBm
5. Set dwell time: 3 seconds (spend 3 sec on each frequency)
6. Click "Start Hopping"
7. Generator cycles: 144.0 → 144.5 → 145.0 → 144.0 → ...
8. Click "Stop Hopping" to end sequence
```

### Example 4: Bandwidth Selection for Different Modes
```
FM Analog Voice (12.5 kHz deviation):
- Bandwidth: 12.5 kHz
- Frequency: 144.0 MHz
- Level: -20 dBm

Digital Mode (6.25 kHz):
- Bandwidth: 6.25 kHz
- Frequency: 144.390 MHz
- Level: -20 dBm

Wideband (25 kHz):
- Bandwidth: 25 kHz
- Frequency: 146.0 MHz
- Level: -20 dBm
```

## Keyboard Shortcuts & Tips

- **Enter key** in frequency/level fields acts as "Set" button
- **Presets persist** across sessions (saved in `presets.json`)
- **Dwell time** can be as short as 0.5 seconds or as long as 60 seconds
- **Hopping preserves** last frequency when stopped

## Troubleshooting

### "Device not connected" error
- Click **Connect** button first
- Check GPIB/USB cable
- Verify device appears in device list

### Changes don't apply
- Make sure device is **Connected** (green status)
- Click the **Set** button next to the value
- Check that RF is not actively transmitting (or click "Enable RF" to reapply)

### Hopping doesn't start
- Ensure playlist has at least one entry
- Device must be **Connected**
- Click **Start Hopping** button

### Presets not saving
- Check file permissions in the Generator directory
- `presets.json` should be created automatically
- Ensure you click **Save Preset** (not just entering a name)

## Advanced Features

### Modifying Bandwidth Mapping
Edit `smy02_gui.py` to adjust FM deviation for different bandwidth standards:

```python
BANDWIDTHS = {
    '6.25 kHz': 3125,      # ±3.125 kHz
    '12.5 kHz': 6250,      # ±6.25 kHz
    '25 kHz': 12500,       # ±12.5 kHz
}
```

### Adding More Bandwidth Options
Add new entries to `BANDWIDTHS` dictionary in the `SMY02GUI` class initialization.

### Custom Hopping Patterns
Presets can be combined with hopping for complex sequences:
1. Save multiple presets (e.g., "Channel A", "Channel B", "Channel C")
2. Load each preset and add to playlist
3. Start hopping to cycle through saved configurations

## Safety Notes

⚠️ **Always Connect Before Operating**
- Device must be connected before any transmission
- Disconnecting cleans up and shuts down RF

⚠️ **Monitor Transmission**
- Keep TinySA or other equipment connected to verify signal
- Do not enable RF without proper termination/load
- Keep transmit time short during testing

✓ **Clean Shutdown**
- Closing the window automatically disables RF and disconnects
- Or manually click "Shutdown" before disconnecting

---

**GUI Version:** 1.0  
**Last Updated:** 2026-02-14  
**Compatible with:** SMY02 signal generator firmware 2.02

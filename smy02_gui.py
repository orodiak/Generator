#!/usr/bin/env python3
"""
SMY02 Signal Generator GUI Control Application

Features:
- Real-time frequency and level control
- Modulation bandwidth selection (6.25 kHz, 12.5 kHz, 25 kHz)
- Preset management and playlist creation
- Frequency hopping between presets
- Device state monitoring
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from time import sleep
import json
import csv
import os
import sys
import copy
from pathlib import Path
import logging

from src.smy02_controller import SMY02Controller

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SMY02GUI:
    """GUI for SMY02 Signal Generator Control."""
    
    # Bandwidth presets (deviation for FM modulation)
    BANDWIDTHS = {
        '6.25 kHz': 3125,      # ±3.125 kHz deviation for 6.25 kHz BW
        '12.5 kHz': 6250,      # ±6.25 kHz deviation for 12.5 kHz BW
        '25 kHz': 12500,       # ±12.5 kHz deviation for 25 kHz BW
    }
    
    def __init__(self, root):
        """Initialize the GUI."""
        self.root = root
        self.root.title("SMY02 Signal Generator Control")
        self.root.geometry("900x700")
        
        self.controller = None
        self.connected = False
        self.transmitting = False
        self.playlist_running = False
        self.playlist_thread = None
        
        # Data
        self.presets = {}
        self.current_preset = None
        self.playlist = []
        self.current_playlist_index = 0
        self.active_hop_playlist = None
        self.state_refresh_in_progress = False
        self.state_refresh_job = None
        self.auto_follow_hop_var = tk.BooleanVar(value=True)
        self.highlight_hop_in_list_var = tk.BooleanVar(value=False)
        self.sync_controls_with_hop_var = tk.BooleanVar(value=False)
        
        self._create_widgets()
        self._load_presets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _create_widgets(self):
        """Create GUI widgets."""
        
        # ============ CONNECTION FRAME ============
        conn_frame = ttk.LabelFrame(self.root, text="Device Connection", padding=10)
        conn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(conn_frame, text="Connect", command=self._connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(conn_frame, text="Disconnect", command=self._disconnect).pack(side=tk.LEFT, padx=5)
        ttk.Button(conn_frame, text="Refresh State", command=self._refresh_device_state).pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(conn_frame, text="Disconnected", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # Separate live state line
        state_frame = ttk.LabelFrame(self.root, text="Device State", padding=10)
        state_frame.pack(fill=tk.X, padx=10, pady=5)
        self.device_state_label = ttk.Label(
            state_frame,
            text="RF: N/A | LEVEL: N/A | FM: N/A | AF: N/A",
            foreground="gray",
        )
        self.device_state_label.pack(fill=tk.X)
        
        # ============ FREQUENCY & LEVEL FRAME ============
        freq_frame = ttk.LabelFrame(self.root, text="Frequency & Level Control", padding=10)
        freq_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Frequency
        ttk.Label(freq_frame, text="Frequency (MHz):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.freq_var = tk.DoubleVar(value=144.0)
        self.freq_entry = ttk.Entry(freq_frame, textvariable=self.freq_var, width=15)
        self.freq_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(freq_frame, text="Set", command=self._set_frequency).grid(row=0, column=2, padx=5)
        
        # Level
        ttk.Label(freq_frame, text="Level (dBm):").grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.level_var = tk.DoubleVar(value=-20.0)
        self.level_entry = ttk.Entry(freq_frame, textvariable=self.level_var, width=15)
        self.level_entry.grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(freq_frame, text="Set", command=self._set_level).grid(row=0, column=5, padx=5)
        
        # Modulation Type
        ttk.Label(freq_frame, text="Modulation:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.mod_var = tk.StringVar(value="FM")
        ttk.Combobox(freq_frame, textvariable=self.mod_var, 
                    values=["FM", "AM", "Off"], state="readonly", width=12).grid(row=1, column=1, padx=5)
        
        # Bandwidth selection for FM
        ttk.Label(freq_frame, text="Bandwidth (FM):").grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        self.bw_var = tk.StringVar(value="12.5 kHz")
        bw_combo = ttk.Combobox(freq_frame, textvariable=self.bw_var,
                               values=list(self.BANDWIDTHS.keys()), state="readonly", width=12)
        bw_combo.grid(row=1, column=4, padx=5)
        bw_combo.bind("<<ComboboxSelected>>", lambda e: self._set_bandwidth())
        
        # ============ TRANSMIT CONTROL FRAME ============
        tx_frame = ttk.LabelFrame(self.root, text="Transmit Control", padding=10)
        tx_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.tx_button = ttk.Button(tx_frame, text="Enable RF", command=self._toggle_transmit)
        self.tx_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(tx_frame, text="Shutdown", command=self._shutdown).pack(side=tk.LEFT, padx=5)
        
        self.tx_status = ttk.Label(tx_frame, text="RF: OFF", foreground="red", font=("Arial", 11, "bold"))
        self.tx_status.pack(side=tk.LEFT, padx=20)
        
        # ============ PRESETS FRAME ============
        preset_frame = ttk.LabelFrame(self.root, text="Presets", padding=10)
        preset_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(preset_frame, text="Preset Name:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.preset_name_var = tk.StringVar()
        ttk.Entry(preset_frame, textvariable=self.preset_name_var, width=20).grid(row=0, column=1, padx=5)
        
        ttk.Button(preset_frame, text="Save Preset", command=self._save_preset).grid(row=0, column=2, padx=5)
        
        ttk.Label(preset_frame, text="Load Preset:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.preset_list_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(preset_frame, textvariable=self.preset_list_var,
                                        state="readonly", width=20)
        self.preset_combo.grid(row=1, column=1, padx=5, pady=5)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self._load_preset())
        
        ttk.Button(preset_frame, text="Delete", command=self._delete_preset).grid(row=1, column=2, padx=5)
        
        # ============ PLAYLIST FRAME ============
        playlist_frame = ttk.LabelFrame(self.root, text="Frequency Hop Playlist", padding=10)
        playlist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Buttons for playlist control
        button_frame = ttk.Frame(playlist_frame)
        button_frame.pack(fill=tk.X, pady=5)

        top_row = ttk.Frame(button_frame)
        top_row.pack(fill=tk.X, pady=2)
        bottom_row = ttk.Frame(button_frame)
        bottom_row.pack(fill=tk.X, pady=2)

        ttk.Button(top_row, text="Start Hopping", command=self._start_hopping).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_row, text="Stop Hopping", command=self._stop_hopping).pack(side=tk.LEFT, padx=5)
        ttk.Label(top_row, text="Dwell Time (sec):").pack(side=tk.LEFT, padx=10)
        self.dwell_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(top_row, from_=0.5, to=60, textvariable=self.dwell_var, width=8).pack(side=tk.LEFT)
        ttk.Button(top_row, text="Add to Playlist", command=self._add_to_playlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_row, text="Remove Selected", command=self._remove_from_playlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_row, text="Clone Selected", command=self._clone_selected_playlist_entry).pack(side=tk.LEFT, padx=5)

        ttk.Button(bottom_row, text="Move Up", command=self._move_playlist_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_row, text="Move Down", command=self._move_playlist_down).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_row, text="Clear Playlist", command=self._clear_playlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_row, text="Import CSV", command=self._import_playlist_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_row, text="Export CSV", command=self._export_playlist_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_row, text="Save Playlist", command=self._save_playlist_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_row, text="Load Playlist", command=self._load_playlist_json).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(
            bottom_row,
            text="Auto-scroll to current hop",
            variable=self.auto_follow_hop_var,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(
            bottom_row,
            text="Highlight current in list",
            variable=self.highlight_hop_in_list_var,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            bottom_row,
            text="Sync controls with hop",
            variable=self.sync_controls_with_hop_var,
        ).pack(side=tk.LEFT, padx=4)

        # Sweep generator controls
        sweep_frame = ttk.LabelFrame(playlist_frame, text="Sweep Generator", padding=8)
        sweep_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sweep_frame, text="Start MHz:").grid(row=0, column=0, padx=4, pady=3, sticky=tk.W)
        self.sweep_start_var = tk.DoubleVar(value=108.0)
        ttk.Entry(sweep_frame, textvariable=self.sweep_start_var, width=9).grid(row=0, column=1, padx=4, pady=3)

        ttk.Label(sweep_frame, text="Stop MHz:").grid(row=0, column=2, padx=4, pady=3, sticky=tk.W)
        self.sweep_stop_var = tk.DoubleVar(value=155.0)
        ttk.Entry(sweep_frame, textvariable=self.sweep_stop_var, width=9).grid(row=0, column=3, padx=4, pady=3)

        ttk.Label(sweep_frame, text="Step MHz:").grid(row=0, column=4, padx=4, pady=3, sticky=tk.W)
        self.sweep_step_var = tk.DoubleVar(value=1.0)
        ttk.Entry(sweep_frame, textvariable=self.sweep_step_var, width=9).grid(row=0, column=5, padx=4, pady=3)

        ttk.Label(sweep_frame, text="Base Level dBm:").grid(row=1, column=0, padx=4, pady=3, sticky=tk.W)
        self.sweep_level_base_var = tk.DoubleVar(value=-20.0)
        ttk.Entry(sweep_frame, textvariable=self.sweep_level_base_var, width=9).grid(row=1, column=1, padx=4, pady=3)

        self.sweep_alt_enable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            sweep_frame,
            text="Alternate Level",
            variable=self.sweep_alt_enable_var
        ).grid(row=1, column=2, padx=4, pady=3, sticky=tk.W)

        ttk.Label(sweep_frame, text="Alt Level dBm:").grid(row=1, column=3, padx=4, pady=3, sticky=tk.W)
        self.sweep_level_alt_var = tk.DoubleVar(value=-30.0)
        ttk.Entry(sweep_frame, textvariable=self.sweep_level_alt_var, width=9).grid(row=1, column=4, padx=4, pady=3)

        ttk.Label(sweep_frame, text="Toggle every N steps:").grid(row=1, column=5, padx=4, pady=3, sticky=tk.W)
        self.sweep_level_toggle_every_var = tk.IntVar(value=1)
        ttk.Spinbox(
            sweep_frame,
            from_=1,
            to=1000,
            textvariable=self.sweep_level_toggle_every_var,
            width=7,
        ).grid(row=1, column=6, padx=4, pady=3)

        self.sweep_replace_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            sweep_frame,
            text="Replace current playlist",
            variable=self.sweep_replace_var
        ).grid(row=2, column=0, columnspan=3, padx=4, pady=3, sticky=tk.W)

        ttk.Button(
            sweep_frame,
            text="Generate Sweep Playlist",
            command=self._generate_sweep_playlist
        ).grid(row=2, column=3, columnspan=2, padx=4, pady=3, sticky=tk.W)
        
        # Playlist display
        list_frame = ttk.Frame(playlist_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.playlist_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            height=8,
            selectbackground="#FFD400",
            selectforeground="#000000",
            activestyle="none",
            font=("Arial", 11, "bold"),
        )
        self.playlist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.playlist_listbox.yview)
        
        # Hop status
        self.hop_status = ttk.Label(playlist_frame, text="Hopping: OFF", foreground="red")
        self.hop_status.pack(fill=tk.X, pady=5)
        self.current_hop_label = ttk.Label(
            playlist_frame,
            text="CURRENT HOP: -",
            foreground="#B00000",
            font=("Arial", 13, "bold"),
        )
        self.current_hop_label.pack(fill=tk.X, pady=2)
        
    def _connect(self):
        """Connect to SMY02 device."""
        try:
            self.controller = SMY02Controller()
            if self.controller.connect():
                self.connected = True
                model = self.controller.model or "Unknown"
                self.status_label.config(text=f"Connected ({model})", foreground="green")
                self._refresh_device_state()
                self._schedule_device_state_refresh()
                logger.info("Connected to SMY02")
            else:
                messagebox.showerror("Error", "Failed to connect to device")
                self.connected = False
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")
            self.connected = False
    
    def _disconnect(self):
        """Disconnect from device."""
        if self.controller:
            self._stop_hopping()
            if self.transmitting:
                self._shutdown()
            self.controller.disconnect()
            self.connected = False
            self.status_label.config(text="Disconnected", foreground="red")
            self.device_state_label.config(text="RF: N/A | LEVEL: N/A | FM: N/A | AF: N/A", foreground="gray")
            self._cancel_device_state_refresh()

    def _format_device_state(self, state):
        return f"RF: {state['rf']} | LEVEL: {state['level']} | FM: {state['fm']} | AF: {state['af']}"

    def _refresh_device_state(self):
        """Refresh live device state in background thread."""
        if not self.connected or not self.controller:
            return
        if self.state_refresh_in_progress:
            return

        self.state_refresh_in_progress = True
        thread = threading.Thread(target=self._refresh_device_state_worker, daemon=True)
        thread.start()

    def _refresh_device_state_worker(self):
        try:
            state = self.controller.get_device_state()
            self.root.after(0, lambda: self.device_state_label.config(
                text=self._format_device_state(state), foreground="black"
            ))
        except Exception as e:
            logger.debug(f"State refresh failed: {e}")
            self.root.after(0, lambda: self.device_state_label.config(
                text="RF: read error | LEVEL: read error | FM: read error | AF: read error",
                foreground="red",
            ))
        finally:
            self.root.after(0, self._state_refresh_done)

    def _state_refresh_done(self):
        self.state_refresh_in_progress = False

    def _schedule_device_state_refresh(self):
        self._cancel_device_state_refresh()
        if self.connected:
            self.state_refresh_job = self.root.after(3000, self._auto_device_state_refresh)

    def _auto_device_state_refresh(self):
        if not self.connected:
            return
        self._refresh_device_state()
        self._schedule_device_state_refresh()

    def _cancel_device_state_refresh(self):
        if self.state_refresh_job is not None:
            self.root.after_cancel(self.state_refresh_job)
            self.state_refresh_job = None
    
    def _set_frequency(self):
        """Set frequency."""
        if not self.connected:
            messagebox.showwarning("Warning", "Device not connected")
            return
        try:
            freq_mhz = self.freq_var.get()
            freq_hz = int(freq_mhz * 1e6)
            
            if self.controller.set_frequency(freq_hz):
                logger.info(f"Frequency set to {freq_mhz} MHz")
            else:
                messagebox.showerror("Error", "Failed to set frequency")
        except ValueError:
            messagebox.showerror("Error", "Invalid frequency value")
    
    def _set_level(self):
        """Set output level."""
        if not self.connected:
            messagebox.showwarning("Warning", "Device not connected")
            return
        try:
            level = self.level_var.get()
            
            if self.controller.set_amplitude(level):
                logger.info(f"Level set to {level} dBm")
            else:
                messagebox.showerror("Error", "Failed to set level")
        except ValueError:
            messagebox.showerror("Error", "Invalid level value")
    
    def _set_bandwidth(self):
        """Set FM bandwidth (via deviation)."""
        if not self.connected:
            return
        try:
            bw_name = self.bw_var.get()
            self._apply_bandwidth(bw_name)
        except Exception as e:
            logger.error(f"Failed to set bandwidth: {e}")

    def _apply_bandwidth(self, bw_name):
        """Apply bandwidth by setting FM deviation."""
        deviation = self.BANDWIDTHS[bw_name]
        if self.controller.set_modulation_fm(deviation):
            logger.info(f"Bandwidth set to {bw_name} (deviation: {deviation} Hz)")
            return True
        logger.warning(f"Failed to set bandwidth to {bw_name}")
        return False
    
    def _toggle_transmit(self):
        """Toggle RF transmission."""
        if not self.connected:
            messagebox.showwarning("Warning", "Device not connected")
            return
        
        if self.transmitting:
            # Disable transmission (quick operation, no threading needed)
            if self.controller.disable_output():
                self.transmitting = False
                self.tx_button.config(text="Enable RF")
                self.tx_status.config(text="RF: OFF", foreground="red")
                logger.info("RF transmission disabled")
            else:
                messagebox.showerror("Error", "Failed to disable RF output")
        else:
            # Enable transmission in background thread to prevent GUI freeze
            freq_mhz = self.freq_var.get()
            level = self.level_var.get()
            bw_name = self.bw_var.get()
            thread = threading.Thread(
                target=self._enable_transmit_worker,
                args=(freq_mhz, level, bw_name),
                daemon=True,
            )
            thread.start()
    
    def _enable_transmit_worker(self, freq_mhz, level, bw_name):
        """Background worker to enable transmission."""
        try:
            # Set parameters
            freq_hz = int(freq_mhz * 1e6)
            
            logger.info("Setting frequency...")
            if not self.controller.set_frequency(freq_hz):
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to set frequency"))
                return
            
            sleep(0.3)
            
            logger.info("Setting level...")
            if not self.controller.set_amplitude(level):
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to set level"))
                return
            
            sleep(0.3)
            
            logger.info("Setting bandwidth...")
            if not self._apply_bandwidth(bw_name):
                self.root.after(0, lambda: messagebox.showwarning("Warning", "Bandwidth command may not be supported by this SMY02 firmware"))
            sleep(0.3)
            
            logger.info("Enabling RF output...")
            if self.controller.enable_output():
                self.transmitting = True
                self.root.after(0, lambda: self.tx_button.config(text="Disable RF"))
                self.root.after(0, lambda: self.tx_status.config(text="RF: ON", foreground="green"))
                logger.info("RF transmission enabled")
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to enable RF output"))
        
        except Exception as e:
            logger.error(f"Enable transmit error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Transmission failed: {e}"))
    
    def _shutdown(self):
        """Shutdown device completely."""
        if not self.connected:
            return
        try:
            self.controller.disable_output()
            self.transmitting = False
            self.tx_button.config(text="Enable RF")
            self.tx_status.config(text="RF: OFF", foreground="red")
            logger.info("Device shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
    
    def _save_preset(self):
        """Save current settings as preset."""
        name = self.preset_name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Enter a preset name")
            return
        
        preset = {
            'frequency': self.freq_var.get(),
            'level': self.level_var.get(),
            'bandwidth': self.bw_var.get(),
            'modulation': self.mod_var.get(),
        }
        
        self.presets[name] = preset
        self._save_presets_to_file()
        self._update_preset_combo()
        self.preset_name_var.set("")
        messagebox.showinfo("Success", f"Preset '{name}' saved")
        logger.info(f"Preset saved: {name}")
    
    def _load_preset(self):
        """Load selected preset."""
        name = self.preset_list_var.get()
        if not name or name not in self.presets:
            return
        
        preset = self.presets[name]
        self.freq_var.set(preset['frequency'])
        self.level_var.set(preset['level'])
        self.bw_var.set(preset['bandwidth'])
        self.mod_var.set(preset['modulation'])
        
        self.current_preset = name
        logger.info(f"Preset loaded: {name}")
    
    def _delete_preset(self):
        """Delete selected preset."""
        name = self.preset_list_var.get()
        if not name or name not in self.presets:
            messagebox.showwarning("Warning", "Select a preset to delete")
            return
        
        if messagebox.askyesno("Confirm", f"Delete preset '{name}'?"):
            del self.presets[name]
            self._save_presets_to_file()
            self._update_preset_combo()
            self.preset_list_var.set("")
            messagebox.showinfo("Success", f"Preset '{name}' deleted")
            logger.info(f"Preset deleted: {name}")
    
    def _add_to_playlist(self):
        """Add current frequency to playlist."""
        freq = self.freq_var.get()
        level = self.level_var.get()
        name = self.preset_list_var.get() or f"{freq} MHz @ {level} dBm"
        
        entry = {
            'name': name,
            'frequency': freq,
            'level': level,
            'bandwidth': self.bw_var.get(),
        }
        
        self.playlist.append(entry)
        self._refresh_playlist_listbox(select_idx=len(self.playlist) - 1)
        logger.info(f"Added to playlist: {name}")
    
    def _remove_from_playlist(self):
        """Remove selected entry from playlist."""
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select an entry to remove")
            return
        
        idx = selection[0]
        self.playlist.pop(idx)
        next_idx = min(idx, len(self.playlist) - 1)
        self._refresh_playlist_listbox(select_idx=next_idx if self.playlist else None)
        logger.info(f"Removed from playlist at index {idx}")
    
    def _clear_playlist(self):
        """Clear entire playlist."""
        if messagebox.askyesno("Confirm", "Clear entire playlist?"):
            self.playlist.clear()
            self._refresh_playlist_listbox()
            logger.info("Playlist cleared")

    def _clone_selected_playlist_entry(self):
        """Clone selected playlist entry."""
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select an entry to clone")
            return

        idx = selection[0]
        source = self.playlist[idx]
        clone = dict(source)
        clone["name"] = f"{source['name']} (copy)"
        self.playlist.insert(idx + 1, clone)
        self._refresh_playlist_listbox(select_idx=idx + 1)
        logger.info(f"Cloned playlist entry at index {idx}")

    def _move_playlist_up(self):
        """Move selected playlist entry up."""
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select an entry to move")
            return

        idx = selection[0]
        if idx == 0:
            return

        self.playlist[idx - 1], self.playlist[idx] = self.playlist[idx], self.playlist[idx - 1]
        self._refresh_playlist_listbox(select_idx=idx - 1)
        logger.info(f"Moved playlist entry from {idx} to {idx - 1}")

    def _move_playlist_down(self):
        """Move selected playlist entry down."""
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select an entry to move")
            return

        idx = selection[0]
        if idx >= len(self.playlist) - 1:
            return

        self.playlist[idx + 1], self.playlist[idx] = self.playlist[idx], self.playlist[idx + 1]
        self._refresh_playlist_listbox(select_idx=idx + 1)
        logger.info(f"Moved playlist entry from {idx} to {idx + 1}")

    def _import_playlist_csv(self):
        """Import playlist entries from CSV file."""
        file_path = filedialog.askopenfilename(
            title="Import Playlist CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            imported = []
            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError("CSV header not found")

                for row in reader:
                    lower = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k is not None}
                    freq_raw = lower.get("frequency_mhz") or lower.get("frequency")
                    if not freq_raw:
                        continue

                    frequency = float(freq_raw)
                    level = float(lower.get("level_dbm") or lower.get("level") or -20.0)
                    bandwidth = lower.get("bandwidth") or "12.5 kHz"
                    if bandwidth not in self.BANDWIDTHS:
                        bandwidth = "12.5 kHz"
                    name = lower.get("name") or f"{frequency} MHz @ {level} dBm"

                    imported.append(
                        {
                            "name": name,
                            "frequency": frequency,
                            "level": level,
                            "bandwidth": bandwidth,
                        }
                    )

            if not imported:
                messagebox.showwarning("Warning", "No valid rows found in CSV")
                return

            if self.playlist and messagebox.askyesno("Import Mode", "Replace current playlist with imported CSV?"):
                self.playlist = imported
            else:
                self.playlist.extend(imported)

            self._refresh_playlist_listbox(select_idx=len(self.playlist) - 1)
            messagebox.showinfo("Success", f"Imported {len(imported)} playlist entries")
            logger.info(f"Imported {len(imported)} entries from {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import CSV: {e}")
            logger.error(f"CSV import failed: {e}")

    def _export_playlist_csv(self):
        """Export playlist entries to CSV file."""
        if not self.playlist:
            messagebox.showwarning("Warning", "Playlist is empty")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Playlist CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="playlist.csv",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "frequency_mhz", "level_dbm", "bandwidth"])
                for entry in self.playlist:
                    writer.writerow([entry["name"], entry["frequency"], entry["level"], entry["bandwidth"]])

            messagebox.showinfo("Success", f"Exported {len(self.playlist)} entries to CSV")
            logger.info(f"Exported {len(self.playlist)} entries to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {e}")
            logger.error(f"CSV export failed: {e}")

    def _save_playlist_json(self):
        """Save current playlist to JSON file."""
        if not self.playlist:
            messagebox.showwarning("Warning", "Playlist is empty")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Playlist",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="playlist.json",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w") as f:
                json.dump(self.playlist, f, indent=2)
            messagebox.showinfo("Success", f"Saved {len(self.playlist)} entries")
            logger.info(f"Saved playlist to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save playlist: {e}")
            logger.error(f"Save playlist failed: {e}")

    def _load_playlist_json(self):
        """Load playlist from JSON file and show frequencies in list."""
        file_path = filedialog.askopenfilename(
            title="Load Playlist",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("Invalid playlist format: root must be a list")

            loaded = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                freq = float(item.get("frequency"))
                level = float(item.get("level", -20.0))
                bw = str(item.get("bandwidth", "12.5 kHz"))
                if bw not in self.BANDWIDTHS:
                    bw = "12.5 kHz"
                name = str(item.get("name", f"{freq} MHz @ {level} dBm"))
                loaded.append(
                    {
                        "name": name,
                        "frequency": freq,
                        "level": level,
                        "bandwidth": bw,
                    }
                )

            if not loaded:
                messagebox.showwarning("Warning", "No valid playlist entries found")
                return

            self.playlist = loaded
            self._refresh_playlist_listbox(select_idx=0)
            messagebox.showinfo("Success", f"Loaded {len(loaded)} entries")
            logger.info(f"Loaded playlist from {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load playlist: {e}")
            logger.error(f"Load playlist failed: {e}")

    def _refresh_playlist_listbox(self, select_idx=None):
        """Render playlist listbox from internal data."""
        self.playlist_listbox.delete(0, tk.END)
        for entry in self.playlist:
            self.playlist_listbox.insert(tk.END, f"{entry['name']} ({entry['frequency']} MHz)")

        if select_idx is not None and 0 <= select_idx < len(self.playlist):
            self.playlist_listbox.selection_set(select_idx)
            self.playlist_listbox.see(select_idx)

    def _generate_sweep_playlist(self):
        """Generate playlist from start/stop/step controls with optional level alternation."""
        try:
            start = float(self.sweep_start_var.get())
            stop = float(self.sweep_stop_var.get())
            step = float(self.sweep_step_var.get())
            base_level = float(self.sweep_level_base_var.get())
            alt_enabled = bool(self.sweep_alt_enable_var.get())
            alt_level = float(self.sweep_level_alt_var.get())
            toggle_every = int(self.sweep_level_toggle_every_var.get())

            if step <= 0:
                messagebox.showerror("Error", "Step must be > 0")
                return
            if toggle_every < 1:
                messagebox.showerror("Error", "Toggle every N must be >= 1")
                return

            ascending = stop >= start
            current = start
            entries = []
            idx = 0
            eps = step / 10.0

            while (current <= stop + eps) if ascending else (current >= stop - eps):
                if alt_enabled:
                    block = (idx // toggle_every) % 2
                    level = alt_level if block == 1 else base_level
                else:
                    level = base_level

                freq = round(current, 6)
                entries.append(
                    {
                        "name": f"Sweep {freq} MHz @ {level} dBm",
                        "frequency": freq,
                        "level": level,
                        "bandwidth": self.bw_var.get(),
                    }
                )
                idx += 1
                current = current + step if ascending else current - step

            if not entries:
                messagebox.showwarning("Warning", "No sweep entries generated")
                return

            if self.sweep_replace_var.get():
                self.playlist = entries
            else:
                self.playlist.extend(entries)

            self._refresh_playlist_listbox(select_idx=0 if self.playlist else None)
            logger.info(
                "Generated %d sweep entries (%s -> %s MHz, step %s MHz, alt level=%s, every N=%d)",
                len(entries),
                start,
                stop,
                step,
                alt_enabled,
                toggle_every,
            )
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric value in sweep settings")
    
    def _start_hopping(self):
        """Start frequency hopping through playlist."""
        if not self.connected:
            messagebox.showwarning("Warning", "Device not connected")
            return
        
        if not self.playlist:
            messagebox.showwarning("Warning", "Playlist is empty")
            return
        
        if self.playlist_running:
            messagebox.showwarning("Warning", "Hopping already running")
            return
        
        # Freeze a snapshot for deterministic hopping sequence.
        self.active_hop_playlist = copy.deepcopy(self.playlist)
        self.playlist_running = True
        self.current_playlist_index = 0
        self.hop_status.config(text="Hopping: ON", foreground="green")
        dwell_seconds = self.dwell_var.get()
        
        # Start hopping in background thread
        self.playlist_thread = threading.Thread(target=self._hopping_worker, args=(dwell_seconds,), daemon=True)
        self.playlist_thread.start()
        logger.info("Frequency hopping started")
    
    def _stop_hopping(self):
        """Stop frequency hopping."""
        self.playlist_running = False
        self.hop_status.config(text="Hopping: OFF", foreground="red")
        self.current_hop_label.config(text="CURRENT HOP: -", foreground="#B00000")
        logger.info("Frequency hopping stopped")

    def _update_hop_marker(self, idx, entry):
        """Update list marker and label to the current hop entry."""
        if self.highlight_hop_in_list_var.get():
            self.playlist_listbox.selection_clear(0, tk.END)
            if 0 <= idx < len(self.playlist):
                self.playlist_listbox.selection_set(idx)
                self.playlist_listbox.activate(idx)
                if self.auto_follow_hop_var.get():
                    self.playlist_listbox.see(idx)
        self.current_hop_label.config(
            text=f"CURRENT HOP: {entry['name']} ({entry['frequency']} MHz)",
            foreground="#005A00",
        )
    
    def _hopping_worker(self, dwell_seconds):
        """Worker thread for frequency hopping."""
        if not self.connected:
            return
        
        try:
            hop_playlist = self.active_hop_playlist or []
            rf_enable_failed = False
            last_bw = None
            while self.playlist_running:
                if not hop_playlist:
                    break
                
                entry = hop_playlist[self.current_playlist_index]
                
                # Update GUI marker/label in one place to keep them in sync.
                idx = self.current_playlist_index
                self.root.after(0, lambda i=idx, e=entry: self._update_hop_marker(i, e))
                
                # Set frequency and level
                freq_hz = int(entry['frequency'] * 1e6)
                if not self.controller.set_frequency(freq_hz):
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to set hop frequency: {entry['frequency']} MHz"))
                    break

                if not self.controller.set_amplitude(entry['level']):
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to set hop level: {entry['level']} dBm"))
                    break

                if entry['bandwidth'] != last_bw:
                    self._apply_bandwidth(entry['bandwidth'])
                    last_bw = entry['bandwidth']

                if not self.transmitting and not rf_enable_failed:
                    if not self.controller.enable_output():
                        rf_enable_failed = True
                        logger.warning("RF enable command failed during hopping; continuing with parameter hopping.")
                        self.root.after(
                            0,
                            lambda: messagebox.showwarning(
                                "Warning",
                                "RF enable command failed (ESR error). Hopping will continue applying frequencies."
                            ),
                        )
                    else:
                        self.transmitting = True
                        self.root.after(0, lambda: self.tx_button.config(text="Disable RF"))
                        self.root.after(0, lambda: self.tx_status.config(text="RF: ON", foreground="green"))

                if self.sync_controls_with_hop_var.get():
                    self.root.after(0, lambda e=entry: self.freq_var.set(e['frequency']))
                    self.root.after(0, lambda e=entry: self.level_var.set(e['level']))
                    self.root.after(0, lambda e=entry: self.bw_var.set(e['bandwidth']))
                logger.info(f"Hop to: {entry['name']}")
                
                # Dwell time
                sleep(dwell_seconds)
                
                # Next frequency
                self.current_playlist_index = (self.current_playlist_index + 1) % len(hop_playlist)
        
        except Exception as e:
            logger.error(f"Hopping error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Hopping error: {e}"))
        
        finally:
            self.playlist_running = False
            self.active_hop_playlist = None
            self.root.after(0, lambda: self.hop_status.config(text="Hopping: OFF", foreground="red"))
            self.root.after(0, lambda: self.current_hop_label.config(text="CURRENT HOP: -", foreground="#B00000"))
    
    def _update_preset_combo(self):
        """Update preset combobox with current presets."""
        self.preset_combo['values'] = list(self.presets.keys())
    
    def _save_presets_to_file(self):
        """Save presets to JSON file."""
        try:
            presets_file = Path("presets.json")
            with open(presets_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save presets: {e}")
    
    def _load_presets(self):
        """Load presets from JSON file."""
        try:
            presets_file = Path("presets.json")
            if presets_file.exists():
                with open(presets_file, 'r') as f:
                    self.presets = json.load(f)
                self._update_preset_combo()
                logger.info(f"Loaded {len(self.presets)} presets")
        except Exception as e:
            logger.error(f"Failed to load presets: {e}")
    
    def _on_closing(self):
        """Clean shutdown on window close."""
        if self.playlist_running:
            self._stop_hopping()
        self._cancel_device_state_refresh()
        if self.connected:
            self._shutdown()
            self._disconnect()
        self.root.destroy()


if __name__ == "__main__":
    try:
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            raise RuntimeError(
                "No graphical display detected (DISPLAY is not set). "
                "Run from a desktop session, use SSH X forwarding, or use xvfb-run."
            )
        root = tk.Tk()
        gui = SMY02GUI(root)
        root.mainloop()
    except (tk.TclError, RuntimeError) as e:
        logger.error("GUI startup failed: %s", e)
        print(f"GUI startup failed: {e}", file=sys.stderr)
        sys.exit(1)

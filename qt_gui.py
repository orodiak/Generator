#!/usr/bin/env python3
"""
SMY02 Qt6 GUI (MVP)

Initial Qt6 variant of the existing tkinter GUI:
- Connect/disconnect and live device state
- Frequency/level/bandwidth control
- RF enable/disable
- Playlist add/remove/save/load
- Frequency hopping with current-hop indicator
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.smy02_controller import SMY02Controller


class SMY02QtGUI(QMainWindow):
    BANDWIDTHS = {
        "6.25 kHz": 3125,
        "12.5 kHz": 6250,
        "25 kHz": 12500,
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SMY02 Signal Generator Control (Qt6)")
        self.resize(1100, 760)

        self.controller: SMY02Controller | None = None
        self.connected = False
        self.transmitting = False
        self.playlist_running = False
        self.playlist: List[Dict[str, Any]] = []
        self.current_idx = 0
        self._hop_last_bw: str | None = None

        self._build_ui()
        self._load_presets()

        self.state_timer = QTimer(self)
        self.state_timer.setInterval(3000)
        self.state_timer.timeout.connect(self._refresh_state)

        self.hop_timer = QTimer(self)
        self.hop_timer.timeout.connect(self._hop_once)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)

        conn = QGroupBox("Device Connection")
        conn_l = QHBoxLayout(conn)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._connect)
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self._disconnect)
        self.btn_refresh = QPushButton("Refresh State")
        self.btn_refresh.clicked.connect(self._refresh_state)
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #b00000; font-weight: 700;")
        conn_l.addWidget(self.btn_connect)
        conn_l.addWidget(self.btn_disconnect)
        conn_l.addWidget(self.btn_refresh)
        conn_l.addWidget(self.status_label, 1)
        main.addWidget(conn)

        state = QGroupBox("Device State")
        state_l = QHBoxLayout(state)
        self.state_label = QLabel("RF: N/A | LEVEL: N/A | FM: N/A | AF: N/A")
        self.state_label.setStyleSheet(
            "background: #fff3bf; color: #5c3d00; font-weight: 800; "
            "padding: 6px; border: 1px solid #d9b100; border-radius: 6px;"
        )
        state_l.addWidget(self.state_label)
        main.addWidget(state)

        ctl = QGroupBox("Frequency / Level / Modulation")
        ctl_g = QGridLayout(ctl)
        self.freq_mhz = QDoubleSpinBox()
        self.freq_mhz.setRange(0.001, 3000.0)
        self.freq_mhz.setDecimals(6)
        self.freq_mhz.setValue(144.0)
        self.level_dbm = QDoubleSpinBox()
        self.level_dbm.setRange(-140.0, 30.0)
        self.level_dbm.setDecimals(2)
        self.level_dbm.setValue(-20.0)

        self.bw_checks: Dict[str, QCheckBox] = {}
        bw_row = QHBoxLayout()
        for i, name in enumerate(self.BANDWIDTHS):
            cb = QCheckBox(name)
            cb.toggled.connect(lambda checked, n=name: self._bw_checked(n, checked))
            self.bw_checks[name] = cb
            bw_row.addWidget(cb)
            if i == 1:
                cb.setChecked(True)

        self.btn_set_freq = QPushButton("Set Frequency")
        self.btn_set_freq.clicked.connect(self._set_frequency)
        self.btn_set_level = QPushButton("Set Level")
        self.btn_set_level.clicked.connect(self._set_level)
        self.btn_set_bw = QPushButton("Apply BW")
        self.btn_set_bw.clicked.connect(self._set_bandwidth)

        self.chk_auto_mod = QCheckBox("Auto modulation by range")
        self.chk_auto_mod.setChecked(False)
        self.am_from_mhz = QDoubleSpinBox()
        self.am_from_mhz.setRange(0.001, 3000.0)
        self.am_from_mhz.setDecimals(3)
        self.am_from_mhz.setValue(118.0)
        self.am_to_mhz = QDoubleSpinBox()
        self.am_to_mhz.setRange(0.001, 3000.0)
        self.am_to_mhz.setDecimals(3)
        self.am_to_mhz.setValue(137.0)
        self.mod_hint = QLabel("Auto-mod OFF (manual FM)")
        self.mod_hint.setStyleSheet("color: #444; font-weight: 700;")

        self.btn_tx = QPushButton("Enable RF")
        self.btn_tx.clicked.connect(self._toggle_tx)
        self.btn_shutdown = QPushButton("Shutdown")
        self.btn_shutdown.clicked.connect(self._shutdown)
        self.tx_status = QLabel("RF: OFF")
        self.tx_status.setStyleSheet("color: #b00000; font-weight: 700;")

        ctl_g.addWidget(QLabel("Frequency (MHz):"), 0, 0)
        ctl_g.addWidget(self.freq_mhz, 0, 1)
        ctl_g.addWidget(self.btn_set_freq, 0, 2)
        ctl_g.addWidget(QLabel("Level (dBm):"), 0, 3)
        ctl_g.addWidget(self.level_dbm, 0, 4)
        ctl_g.addWidget(self.btn_set_level, 0, 5)

        ctl_g.addWidget(QLabel("Bandwidth (FM):"), 1, 0)
        ctl_g.addLayout(bw_row, 1, 1, 1, 3)
        ctl_g.addWidget(self.btn_set_bw, 1, 4)
        ctl_g.addWidget(self.btn_tx, 1, 5)
        ctl_g.addWidget(self.btn_shutdown, 1, 6)
        ctl_g.addWidget(self.tx_status, 1, 7)
        ctl_g.addWidget(self.chk_auto_mod, 2, 0, 1, 2)
        ctl_g.addWidget(QLabel("AM from MHz:"), 2, 2)
        ctl_g.addWidget(self.am_from_mhz, 2, 3)
        ctl_g.addWidget(QLabel("AM to MHz:"), 2, 4)
        ctl_g.addWidget(self.am_to_mhz, 2, 5)
        ctl_g.addWidget(self.mod_hint, 2, 6, 1, 2)
        main.addWidget(ctl)

        pl = QGroupBox("Playlist / Hopping")
        pl_l = QVBoxLayout(pl)
        row1 = QHBoxLayout()
        self.btn_add = QPushButton("Add Current")
        self.btn_add.clicked.connect(self._add_current)
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_playlist)
        self.btn_save = QPushButton("Save Playlist")
        self.btn_save.clicked.connect(self._save_playlist)
        self.btn_load = QPushButton("Load Playlist")
        self.btn_load.clicked.connect(self._load_playlist)
        row1.addWidget(self.btn_add)
        row1.addWidget(self.btn_remove)
        row1.addWidget(self.btn_clear)
        row1.addWidget(self.btn_save)
        row1.addWidget(self.btn_load)
        row1.addStretch(1)
        pl_l.addLayout(row1)

        row2 = QHBoxLayout()
        self.dwell_s = QDoubleSpinBox()
        self.dwell_s.setRange(0.2, 60.0)
        self.dwell_s.setDecimals(2)
        self.dwell_s.setValue(2.0)
        self.btn_hop_start = QPushButton("Start Hopping")
        self.btn_hop_start.clicked.connect(self._start_hopping)
        self.btn_hop_stop = QPushButton("Stop Hopping")
        self.btn_hop_stop.clicked.connect(self._stop_hopping)
        self.chk_follow = QCheckBox("Auto-scroll")
        self.chk_follow.setChecked(True)
        row2.addWidget(QLabel("Dwell (s):"))
        row2.addWidget(self.dwell_s)
        row2.addWidget(self.btn_hop_start)
        row2.addWidget(self.btn_hop_stop)
        row2.addWidget(self.chk_follow)
        row2.addStretch(1)
        pl_l.addLayout(row2)

        sweep = QGroupBox("Sweep Generator")
        sweep_g = QGridLayout(sweep)
        self.sweep_start_mhz = QDoubleSpinBox()
        self.sweep_start_mhz.setRange(0.001, 3000.0)
        self.sweep_start_mhz.setDecimals(6)
        self.sweep_start_mhz.setValue(108.0)
        self.sweep_stop_mhz = QDoubleSpinBox()
        self.sweep_stop_mhz.setRange(0.001, 3000.0)
        self.sweep_stop_mhz.setDecimals(6)
        self.sweep_stop_mhz.setValue(155.0)
        self.sweep_step_mhz = QDoubleSpinBox()
        self.sweep_step_mhz.setRange(0.000001, 100.0)
        self.sweep_step_mhz.setDecimals(6)
        self.sweep_step_mhz.setValue(1.0)

        self.sweep_base_level = QDoubleSpinBox()
        self.sweep_base_level.setRange(-140.0, 30.0)
        self.sweep_base_level.setDecimals(2)
        self.sweep_base_level.setValue(-20.0)
        self.sweep_alt_level = QDoubleSpinBox()
        self.sweep_alt_level.setRange(-140.0, 30.0)
        self.sweep_alt_level.setDecimals(2)
        self.sweep_alt_level.setValue(-30.0)
        self.sweep_alt_enable = QCheckBox("Alternate Level")
        self.sweep_toggle_every = QSpinBox()
        self.sweep_toggle_every.setRange(1, 10000)
        self.sweep_toggle_every.setValue(1)
        self.sweep_bw_combo = QComboBox()
        self.sweep_bw_combo.addItems(list(self.BANDWIDTHS.keys()))
        self.sweep_bw_combo.setCurrentText("12.5 kHz")
        self.sweep_replace = QCheckBox("Replace current playlist")
        self.sweep_replace.setChecked(True)
        self.sweep_reverse = QCheckBox("Back and forth")
        self.btn_generate_sweep = QPushButton("Generate Sweep Playlist")
        self.btn_generate_sweep.clicked.connect(self._generate_sweep_playlist)

        sweep_g.addWidget(QLabel("Start MHz:"), 0, 0)
        sweep_g.addWidget(self.sweep_start_mhz, 0, 1)
        sweep_g.addWidget(QLabel("Stop MHz:"), 0, 2)
        sweep_g.addWidget(self.sweep_stop_mhz, 0, 3)
        sweep_g.addWidget(QLabel("Step MHz:"), 0, 4)
        sweep_g.addWidget(self.sweep_step_mhz, 0, 5)
        sweep_g.addWidget(QLabel("Base Level dBm:"), 1, 0)
        sweep_g.addWidget(self.sweep_base_level, 1, 1)
        sweep_g.addWidget(self.sweep_alt_enable, 1, 2)
        sweep_g.addWidget(QLabel("Alt Level dBm:"), 1, 3)
        sweep_g.addWidget(self.sweep_alt_level, 1, 4)
        sweep_g.addWidget(QLabel("Toggle every N:"), 1, 5)
        sweep_g.addWidget(self.sweep_toggle_every, 1, 6)
        sweep_g.addWidget(QLabel("Sweep BW:"), 2, 0)
        sweep_g.addWidget(self.sweep_bw_combo, 2, 1)
        sweep_g.addWidget(self.sweep_replace, 2, 2, 1, 2)
        sweep_g.addWidget(self.sweep_reverse, 2, 4, 1, 1)
        sweep_g.addWidget(self.btn_generate_sweep, 2, 5, 1, 2)
        pl_l.addWidget(sweep)

        self.playlist_widget = QListWidget()
        self.playlist_widget.setStyleSheet(
            "QListWidget { font-size: 14px; }"
            "QListWidget::item:selected { background: #ffd400; color: #000; font-weight: 700; }"
        )
        pl_l.addWidget(self.playlist_widget, 1)

        self.hop_status = QLabel("Hopping: OFF")
        self.hop_status.setStyleSheet("color: #b00000; font-weight: 700;")
        self.current_hop = QLabel("CURRENT HOP: -")
        self.current_hop.setStyleSheet("color: #b00000; font-size: 16px; font-weight: 800;")
        pl_l.addWidget(self.hop_status)
        pl_l.addWidget(self.current_hop)
        main.addWidget(pl, 1)

    @staticmethod
    def _idn_parts(idn: str) -> tuple[str, str, str]:
        parts = [p.strip() for p in (idn or "").split(",")]
        vendor = parts[0] if len(parts) > 0 else "Unknown"
        model = parts[1] if len(parts) > 1 else "Unknown"
        firmware = parts[3] if len(parts) > 3 else (parts[-1] if parts else "Unknown")
        return vendor, model, firmware

    def _load_presets(self) -> None:
        p = Path("presets.json")
        if p.exists():
            try:
                json.loads(p.read_text())
            except Exception:
                pass

    def _bw_checked(self, name: str, checked: bool) -> None:
        if not checked:
            return
        for other, cb in self.bw_checks.items():
            if other != name:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)

    def _selected_bw(self) -> str:
        for name, cb in self.bw_checks.items():
            if cb.isChecked():
                return name
        return "12.5 kHz"

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _err(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def _connect(self) -> None:
        self.controller = SMY02Controller()
        if self.controller.connect():
            self.connected = True
            vendor, model, fw = self._idn_parts(self.controller.idn)
            self.status_label.setText(f"Connected ({vendor} {model} FW {fw})")
            self.status_label.setStyleSheet("color: #006400; font-weight: 700;")
            self.state_timer.start()
            self._refresh_state()
            return
        self.connected = False
        self._err("Connection", "Failed to connect to SMY02")

    def _disconnect(self) -> None:
        if self.playlist_running:
            self._stop_hopping()
        if self.controller:
            if self.transmitting:
                self._shutdown()
            self.controller.disconnect()
        self.connected = False
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: #b00000; font-weight: 700;")
        self.state_timer.stop()
        self.state_label.setText("RF: N/A | LEVEL: N/A | FM: N/A | AF: N/A")
        self.state_label.setStyleSheet(
            "background: #f3f3f3; color: #666; font-weight: 700; "
            "padding: 6px; border: 1px solid #ccc; border-radius: 6px;"
        )

    def _refresh_state(self) -> None:
        if not self.connected or not self.controller:
            return
        st = self.controller.get_device_state()
        self.state_label.setText(f"RF: {st['rf']} | LEVEL: {st['level']} | FM: {st['fm']} | AF: {st['af']}")
        if "N/A" in (st["rf"], st["level"], st["fm"], st["af"]):
            self.state_label.setStyleSheet(
                "background: #fff3bf; color: #5c3d00; font-weight: 800; "
                "padding: 6px; border: 1px solid #d9b100; border-radius: 6px;"
            )
        else:
            self.state_label.setStyleSheet(
                "background: #d9f7e6; color: #0b5d2a; font-weight: 800; "
                "padding: 6px; border: 1px solid #57b77d; border-radius: 6px;"
            )

    def _set_frequency(self) -> None:
        if not self.connected or not self.controller:
            self._warn("Device", "Device not connected")
            return
        freq_mhz = self.freq_mhz.value()
        hz = int(self.freq_mhz.value() * 1e6)
        if not self.controller.set_frequency(hz):
            self._err("Frequency", "Failed to set frequency")
            return
        self._apply_modulation_for_frequency(freq_mhz)

    def _set_level(self) -> None:
        if not self.connected or not self.controller:
            self._warn("Device", "Device not connected")
            return
        if not self.controller.set_amplitude(self.level_dbm.value()):
            self._err("Level", "Failed to set level")

    def _set_bandwidth(self) -> bool:
        if not self.connected or not self.controller:
            return False
        bw = self.sweep_bw_combo.currentText().strip()
        if bw not in self.BANDWIDTHS:
            bw = "12.5 kHz"
        return self.controller.set_modulation_fm(self.BANDWIDTHS[bw])

    def _apply_modulation_for_frequency(self, freq_mhz: float) -> bool:
        if not self.connected or not self.controller:
            return False
        if not self.chk_auto_mod.isChecked():
            self.mod_hint.setText("Auto-mod OFF (manual FM)")
            return True

        am_start = min(self.am_from_mhz.value(), self.am_to_mhz.value())
        am_stop = max(self.am_from_mhz.value(), self.am_to_mhz.value())
        in_am = am_start <= freq_mhz <= am_stop
        if in_am:
            ok = self.controller.set_modulation_am()
            self.mod_hint.setText(f"Auto-mod: AM ({am_start:.3f}-{am_stop:.3f} MHz)")
            self.mod_hint.setStyleSheet("color: #8a4b00; font-weight: 800;")
            if not ok:
                self._err("Modulation", "Failed to switch AM mode")
            return ok

        bw = self._selected_bw()
        ok = self.controller.set_modulation_fm(self.BANDWIDTHS[bw])
        self.mod_hint.setText(f"Auto-mod: FM (outside {am_start:.3f}-{am_stop:.3f} MHz)")
        self.mod_hint.setStyleSheet("color: #005a00; font-weight: 800;")
        if not ok:
            self._err("Modulation", "Failed to switch FM mode")
        return ok

    def _toggle_tx(self) -> None:
        if not self.connected or not self.controller:
            self._warn("Device", "Device not connected")
            return
        if self.transmitting:
            if self.controller.disable_output():
                self.transmitting = False
                self.btn_tx.setText("Enable RF")
                self.tx_status.setText("RF: OFF")
                self.tx_status.setStyleSheet("color: #b00000; font-weight: 700;")
            else:
                self._err("RF", "Failed to disable RF")
            return

        self._set_frequency()
        self._set_level()
        if not self.chk_auto_mod.isChecked():
            self._set_bandwidth()
        if self.controller.enable_output():
            self.transmitting = True
            self.btn_tx.setText("Disable RF")
            self.tx_status.setText("RF: ON")
            self.tx_status.setStyleSheet("color: #006400; font-weight: 700;")
        else:
            self._err("RF", "Failed to enable RF")

    def _shutdown(self) -> None:
        if self.controller:
            self.controller.disable_output()
        self.transmitting = False
        self.btn_tx.setText("Enable RF")
        self.tx_status.setText("RF: OFF")
        self.tx_status.setStyleSheet("color: #b00000; font-weight: 700;")

    def _add_current(self) -> None:
        entry = {
            "name": f"{self.freq_mhz.value():.6f} MHz @ {self.level_dbm.value():.2f} dBm",
            "frequency": float(self.freq_mhz.value()),
            "level": float(self.level_dbm.value()),
            "bandwidth": self._selected_bw(),
        }
        self.playlist.append(entry)
        self._refresh_playlist()

    def _remove_selected(self) -> None:
        row = self.playlist_widget.currentRow()
        if row < 0:
            return
        if 0 <= row < len(self.playlist):
            self.playlist.pop(row)
            self._refresh_playlist()

    def _clear_playlist(self) -> None:
        self.playlist.clear()
        self._refresh_playlist()

    def _save_playlist(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Playlist", "playlist.json", "JSON files (*.json)")
        if not path:
            return
        Path(path).write_text(json.dumps(self.playlist, indent=2))

    def _load_playlist(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Playlist", "", "JSON files (*.json)")
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text())
            if isinstance(raw, list):
                self.playlist = []
                for it in raw:
                    if not isinstance(it, dict):
                        continue
                    self.playlist.append(
                        {
                            "name": str(it.get("name", "Entry")),
                            "frequency": float(it.get("frequency", 144.0)),
                            "level": float(it.get("level", -20.0)),
                            "bandwidth": str(it.get("bandwidth", "12.5 kHz")),
                        }
                    )
                self._refresh_playlist()
        except Exception as e:
            self._err("Playlist", f"Load failed: {e}")

    def _refresh_playlist(self) -> None:
        self.playlist_widget.clear()
        for e in self.playlist:
            item = QListWidgetItem(f"{e['name']} ({e['frequency']} MHz)")
            self.playlist_widget.addItem(item)

    def _generate_sweep_playlist(self) -> None:
        start = float(self.sweep_start_mhz.value())
        stop = float(self.sweep_stop_mhz.value())
        step = float(self.sweep_step_mhz.value())
        base_level = float(self.sweep_base_level.value())
        alt_enabled = self.sweep_alt_enable.isChecked()
        alt_level = float(self.sweep_alt_level.value())
        toggle_every = int(self.sweep_toggle_every.value())
        if step <= 0:
            self._err("Sweep", "Step must be > 0")
            return
        if toggle_every < 1:
            self._err("Sweep", "Toggle every N must be >= 1")
            return

        bw = self._selected_bw()
        ascending = stop >= start
        forward: List[Dict[str, Any]] = []
        idx = 0
        current = start
        eps = step / 10.0
        while (current <= stop + eps) if ascending else (current >= stop - eps):
            if alt_enabled:
                block = (idx // toggle_every) % 2
                level = alt_level if block == 1 else base_level
            else:
                level = base_level
            freq = round(current, 6)
            forward.append(
                {
                    "name": f"Sweep {freq} MHz @ {level:.2f} dBm",
                    "frequency": freq,
                    "level": level,
                    "bandwidth": bw,
                }
            )
            idx += 1
            current = current + step if ascending else current - step

        if not forward:
            self._warn("Sweep", "No entries generated")
            return

        entries = list(forward)
        # Ping-pong style: forward then backward without repeating end points.
        if self.sweep_reverse.isChecked() and len(forward) > 2:
            tail = list(reversed(forward[1:-1]))
            entries.extend(tail)

        if self.sweep_replace.isChecked():
            self.playlist = entries
        else:
            self.playlist.extend(entries)
        self._refresh_playlist()

    def _start_hopping(self) -> None:
        if not self.connected or not self.controller:
            self._warn("Device", "Device not connected")
            return
        if not self.playlist:
            self._warn("Playlist", "Playlist is empty")
            return
        if self.playlist_running:
            return
        self.playlist_running = True
        self.current_idx = 0
        self._hop_last_bw = None
        self.hop_status.setText("Hopping: ON")
        self.hop_status.setStyleSheet("color: #006400; font-weight: 700;")
        self.hop_timer.start(int(self.dwell_s.value() * 1000))
        self._hop_once()

    def _stop_hopping(self) -> None:
        self.playlist_running = False
        self.hop_timer.stop()
        self._hop_last_bw = None
        self.hop_status.setText("Hopping: OFF")
        self.hop_status.setStyleSheet("color: #b00000; font-weight: 700;")
        self.current_hop.setText("CURRENT HOP: -")
        self.current_hop.setStyleSheet("color: #b00000; font-size: 16px; font-weight: 800;")

    def _hop_once(self) -> None:
        if not self.playlist_running or not self.controller or not self.playlist:
            return
        e = self.playlist[self.current_idx]
        hz = int(float(e["frequency"]) * 1e6)
        lvl = float(e["level"])
        bw = str(e.get("bandwidth", "12.5 kHz"))
        if bw not in self.BANDWIDTHS:
            bw = "12.5 kHz"

        self.controller.set_frequency(hz)
        self.controller.set_amplitude(lvl)
        if self.chk_auto_mod.isChecked():
            self._apply_modulation_for_frequency(float(e["frequency"]))
            self._hop_last_bw = None
        else:
            if bw != self._hop_last_bw:
                self.controller.set_modulation_fm(self.BANDWIDTHS[bw])
                self._hop_last_bw = bw
        if not self.transmitting:
            if self.controller.enable_output():
                self.transmitting = True
                self.btn_tx.setText("Disable RF")
                self.tx_status.setText("RF: ON")
                self.tx_status.setStyleSheet("color: #006400; font-weight: 700;")

        self.current_hop.setText(f"CURRENT HOP: {e['name']} ({float(e['frequency']):.6f} MHz)")
        self.current_hop.setStyleSheet("color: #005a00; font-size: 16px; font-weight: 800;")
        if self.chk_follow.isChecked():
            self.playlist_widget.setCurrentRow(self.current_idx)
            self.playlist_widget.scrollToItem(self.playlist_widget.item(self.current_idx))

        self.current_idx = (self.current_idx + 1) % len(self.playlist)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._stop_hopping()
            self._shutdown()
            self._disconnect()
        finally:
            event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    win = SMY02QtGUI()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

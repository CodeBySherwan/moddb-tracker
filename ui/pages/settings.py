"""ui/pages/settings.py"""

from pathlib import Path

import json, shutil
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget
import pyqtgraph as pg
import tracker
from tracker import CONFIG_FILE, load_config, save_config
from ui.theme import BORDER, DISPLAY_NAMES, PANEL2, TEXT
from ui.widgets import panel, section_label

class SettingsPage(QWidget):
    saved = pyqtSignal()
    file_reload = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Configuration")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        hint = QLabel("Everything is edited in-app and saved to config.json.")
        hint.setObjectName("Hint")
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)

        # ---- profile
        layout.addWidget(section_label("Member profile"))
        box = panel(content)
        gl = QGridLayout(box)
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(10)
        gl.addWidget(QLabel("Profile URL:"), 0, 0)
        self.profile = QLineEdit()
        self.profile.setPlaceholderText("https://www.moddb.com/members/yourname")
        gl.addWidget(self.profile, 0, 1)
        self.auto_discover = QCheckBox("Auto-discover mods/addons/files from the profile")
        gl.addWidget(self.auto_discover, 1, 0, 1, 2)
        layout.addWidget(box)

        # ---- manual mods
        layout.addWidget(section_label("Manual mods (tracked in addition to auto-discovered)"))
        box2 = panel(content)
        ml = QVBoxLayout(box2)
        self.mods_list = QListWidget()
        ml.addWidget(self.mods_list)
        mrow = QHBoxLayout()
        self.mod_url_input = QLineEdit()
        self.mod_url_input.setPlaceholderText("https://www.moddb.com/mods/...")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_mod)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_mod)
        mrow.addWidget(self.mod_url_input, 1)
        mrow.addWidget(add_btn)
        mrow.addWidget(remove_btn)
        ml.addLayout(mrow)
        layout.addWidget(box2)

        # ---- polling
        layout.addWidget(section_label("Polling"))
        box3 = panel(content)
        pl = QGridLayout(box3)
        pl.setHorizontalSpacing(12)
        pl.addWidget(QLabel("Interval (minutes):"), 0, 0)
        self.interval = QSpinBox()
        self.interval.setRange(5, 1440)
        self.interval.setSuffix(" min")
        pl.addWidget(self.interval, 0, 1)
        self.charts_each_poll = QCheckBox("Regenerate charts after each poll")
        pl.addWidget(self.charts_each_poll, 1, 0, 1, 2)
        layout.addWidget(box3)

        # ---- notifications
        layout.addWidget(section_label("Notifications"))
        box4 = panel(content)
        nl = QVBoxLayout(box4)
        self.notify_downloads = QCheckBox("New downloads")
        self.notify_comments = QCheckBox("New comments")
        self.notify_replies = QCheckBox("Replies to me")
        nl.addWidget(self.notify_downloads)
        nl.addWidget(self.notify_comments)
        nl.addWidget(self.notify_replies)
        ng = QGridLayout()
        ng.addWidget(QLabel("Max toasts per poll:"), 0, 0)
        self.max_toasts = QSpinBox()
        self.max_toasts.setRange(1, 20)
        ng.addWidget(self.max_toasts, 0, 1)
        ng.addWidget(QLabel("Toast app id:"), 1, 0)
        self.app_id = QLineEdit()
        ng.addWidget(self.app_id, 1, 1)
        nl.addLayout(ng)
        layout.addWidget(box4)

        # ---- tray
        layout.addWidget(section_label("System tray"))
        box5 = panel(content)
        tl = QVBoxLayout(box5)
        self.minimize_to_tray = QCheckBox("Minimize to tray when you minimize the window")
        self.start_minimized = QCheckBox("Start hidden in the tray (background mode)")
        tl.addWidget(self.minimize_to_tray)
        tl.addWidget(self.start_minimized)
        th = QLabel("The app keeps polling and showing toasts while it sits in the tray.")
        th.setObjectName("Hint")
        tl.addWidget(th)
        layout.addWidget(box5)

        # ---- window
        layout.addWidget(section_label("Window"))
        box6 = panel(content)
        wl = QVBoxLayout(box6)
        self.fullscreen = QCheckBox("Start the app in full screen")
        self.poll_on_open = QCheckBox("Poll ModDB automatically every time the app opens")
        wl.addWidget(self.fullscreen)
        wl.addWidget(self.poll_on_open)
        layout.addWidget(box6)

        # ---- appearance
        layout.addWidget(section_label("Appearance"))
        box6b = panel(content)
        ap = QGridLayout(box6b)
        ap.setHorizontalSpacing(12)
        ap.addWidget(QLabel("Theme:"), 0, 0)
        self.theme_combo = QComboBox()
        for name, display in DISPLAY_NAMES.items():
            self.theme_combo.addItem(display, name)
        ap.addWidget(self.theme_combo, 0, 1)
        ah = QLabel("The theme applies immediately, no restart needed.")
        ah.setObjectName("Hint")
        ap.addWidget(ah, 1, 0, 1, 2)
        layout.addWidget(box6b)

        # ---- paths
        layout.addWidget(section_label("Paths"))
        box7 = panel(content)
        pg = QGridLayout(box7)
        pg.setHorizontalSpacing(12)
        pg.addWidget(QLabel("Database:"), 0, 0)
        self.path_db = QLineEdit()
        pg.addWidget(self.path_db, 0, 1)
        pg.addWidget(QLabel("Charts output:"), 1, 0)
        self.path_output = QLineEdit()
        pg.addWidget(self.path_output, 1, 1)
        pg.addWidget(QLabel("Logs:"), 2, 0)
        self.path_logs = QLineEdit()
        pg.addWidget(self.path_logs, 2, 1)
        layout.addWidget(box7)

        # ---- advanced JSON
        layout.addWidget(section_label("Advanced"))
        box8 = panel(content)
        al = QVBoxLayout(box8)
        self.json_toggle = QCheckBox("Edit config.json as raw JSON")
        self.json_toggle.toggled.connect(self._toggle_json)
        al.addWidget(self.json_toggle)
        self.json_editor = QPlainTextEdit()
        self.json_editor.setMaximumHeight(240)
        self._style_json_editor()
        al.addWidget(self.json_editor)
        self.json_editor.hide()
        aj = QHBoxLayout()
        self.apply_json_btn = QPushButton("Apply JSON to form")
        self.apply_json_btn.clicked.connect(self._apply_json)
        aj.addWidget(self.apply_json_btn)
        aj.addStretch(1)
        al.addLayout(aj)
        self.apply_json_btn.hide()
        layout.addWidget(box8)

        # ---- data / reset
        layout.addWidget(section_label("Data"))
        box9 = panel(content)
        dl = QVBoxLayout(box9)
        dh = QLabel(
            "Deletes the database, all generated charts and logs, then resets config.json. "
            "The app restarts as a fresh first run (you will be asked for your account again)."
        )
        dh.setObjectName("Hint")
        dh.setWordWrap(True)
        dl.addWidget(dh)
        self.reset_btn = QPushButton("Delete all data and reset the app")
        self.reset_btn.setStyleSheet(
            "QPushButton { background: #DC2626; color: #FFFFFF; border: none; border-radius: 6px;"
            "padding: 8px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #B91C1C; }"
        )
        self.reset_btn.clicked.connect(self.reset_requested.emit)
        dl.addWidget(self.reset_btn)
        layout.addWidget(box9)

        layout.addStretch(1)

        # ---- buttons
        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save configuration")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save)
        self.reload_btn = QPushButton("Reload from file")
        self.reload_btn.clicked.connect(self._reload_from_file)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.reload_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.reload()

    # ---- helpers --------------------------------------------------------
    def _add_mod(self) -> None:
        url = self.mod_url_input.text().strip()
        if not url:
            return
        existing = [self.mods_list.item(i).text() for i in range(self.mods_list.count())]
        if url not in existing:
            self.mods_list.addItem(url)
        self.mod_url_input.clear()

    def _remove_mod(self) -> None:
        for item in self.mods_list.selectedItems():
            self.mods_list.takeItem(self.mods_list.row(item))

    def _style_json_editor(self) -> None:
        self.json_editor.setStyleSheet(
            f"QPlainTextEdit {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};"
            "border-radius: 6px; font-family: Consolas, monospace; font-size: 12px; }"
        )

    def _toggle_json(self, checked: bool) -> None:
        self.json_editor.setVisible(checked)
        self.apply_json_btn.setVisible(checked)
        if checked:
            self.json_editor.setPlainText(json.dumps(self.current_config(), indent=2))

    def _apply_json(self) -> None:
        try:
            parsed = json.loads(self.json_editor.toPlainText())
            if not isinstance(parsed, dict):
                raise ValueError("Root value must be a JSON object")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid JSON", str(exc))
            return
        merged = _merge_defaults(parsed)
        self._config = merged
        self.reload()
        self.json_editor.setPlainText(json.dumps(merged, indent=2))
        QMessageBox.information(self, "Applied", "JSON applied to the form. Review and press Save.")

    def _reload_from_file(self) -> None:
        try:
            self._config = load_config(CONFIG_FILE)
            self.reload()
            self.file_reload.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reload failed", str(exc))

    # ---- data -----------------------------------------------------------
    def reload(self) -> None:
        self._style_json_editor()
        self.profile.setText(self._config.get("profile_url", ""))
        self.auto_discover.setChecked(bool(self._config.get("auto_discover", True)))
        self.mods_list.clear()
        for url in self._config.get("mods", []):
            if url:
                self.mods_list.addItem(url)
        self.interval.setValue(int(self._config["poll"].get("interval_minutes", 30)))
        self.charts_each_poll.setChecked(bool(self._config["poll"].get("charts_each_poll", True)))
        self.notify_downloads.setChecked(bool(self._config["poll"].get("notify_on_downloads", True)))
        self.notify_comments.setChecked(bool(self._config["poll"].get("notify_on_comments", True)))
        self.notify_replies.setChecked(bool(self._config["poll"].get("notify_on_replies", True)))
        self.max_toasts.setValue(int(self._config["notifications"].get("max_toasts", 5)))
        self.app_id.setText(self._config["notifications"].get("app_id", "ModDB Tracker"))
        self.minimize_to_tray.setChecked(bool(self._config.get("tray", {}).get("minimize_to_tray", True)))
        self.start_minimized.setChecked(bool(self._config.get("tray", {}).get("start_minimized", False)))
        self.fullscreen.setChecked(bool(self._config.get("ui", {}).get("fullscreen", True)))
        self.poll_on_open.setChecked(bool(self._config.get("ui", {}).get("poll_on_open", True)))
        idx = self.theme_combo.findData(str(self._config.get("ui", {}).get("theme", "dark")))
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.path_db.setText(self._config["paths"].get("db", "tracker.db"))
        self.path_output.setText(self._config["paths"].get("output", "output"))
        self.path_logs.setText(self._config["paths"].get("logs", "logs"))
        if self.json_editor.isVisible():
            self.json_editor.setPlainText(json.dumps(self.current_config(), indent=2))

    def current_config(self) -> Dict[str, Any]:
        cfg = json.loads(json.dumps(self._config))
        cfg["profile_url"] = self.profile.text().strip()
        cfg["auto_discover"] = self.auto_discover.isChecked()
        cfg["mods"] = [self.mods_list.item(i).text().strip() for i in range(self.mods_list.count()) if self.mods_list.item(i).text().strip()]
        cfg["poll"]["interval_minutes"] = self.interval.value()
        cfg["poll"]["charts_each_poll"] = self.charts_each_poll.isChecked()
        cfg["poll"]["notify_on_downloads"] = self.notify_downloads.isChecked()
        cfg["poll"]["notify_on_comments"] = self.notify_comments.isChecked()
        cfg["poll"]["notify_on_replies"] = self.notify_replies.isChecked()
        cfg["notifications"]["max_toasts"] = self.max_toasts.value()
        cfg["notifications"]["app_id"] = self.app_id.text().strip() or "ModDB Tracker"
        cfg["tray"]["minimize_to_tray"] = self.minimize_to_tray.isChecked()
        cfg["tray"]["start_minimized"] = self.start_minimized.isChecked()
        cfg["ui"]["fullscreen"] = self.fullscreen.isChecked()
        cfg["ui"]["poll_on_open"] = self.poll_on_open.isChecked()
        cfg["ui"]["theme"] = self.theme_combo.currentData() or "dark"
        cfg["paths"]["db"] = self.path_db.text().strip() or "tracker.db"
        cfg["paths"]["output"] = self.path_output.text().strip() or "output"
        cfg["paths"]["logs"] = self.path_logs.text().strip() or "logs"
        return cfg

    def _save(self) -> None:
        try:
            save_config(self.current_config(), CONFIG_FILE)
            QMessageBox.information(self, "Saved", "Configuration saved to config.json")
            self.saved.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))



def _merge_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge a parsed JSON object over the built-in default config."""
    base = json.loads(json.dumps(tracker.DEFAULT_CONFIG))

    def _merge(b: Dict[str, Any], o: Dict[str, Any]) -> None:
        for key, value in o.items():
            if isinstance(value, dict) and isinstance(b.get(key), dict):
                _merge(b[key], value)
            else:
                b[key] = value

    _merge(base, data)
    return base



def is_profile_configured(config: Dict[str, Any]) -> bool:
    """True when the member profile URL has been filled in by the user."""
    url = (config.get("profile_url") or "").strip()
    return bool(url) and "YOUR-USERNAME" not in url



def reset_app_data(config: Dict[str, Any]) -> List[str]:
    """Delete the database, charts and logs described by config. Returns removed paths."""
    removed: List[str] = []
    db = str(Path(config["paths"]["db"]))
    for suffix in ("", "-wal", "-shm"):
        p = Path(db + suffix)
        if p.exists():
            try:
                p.unlink()
                removed.append(str(p))
            except Exception:  # noqa: BLE001
                pass
    for directory in (Path(config["paths"]["output"]), Path(config["paths"]["logs"])):
        if directory.exists():
            for entry in sorted(directory.iterdir()):
                try:
                    if entry.is_file():
                        entry.unlink()
                    else:
                        shutil.rmtree(entry)
                    removed.append(str(entry))
                except Exception:  # noqa: BLE001
                    pass
    return removed


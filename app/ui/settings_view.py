"""Settings view: OneDrive sync folder, Ollama model, notification prefs,
Azure app client id.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig, load_config, save_config
from app.sync import SyncPathError, ensure_sync_folder, looks_like_onedrive_path


class SettingsView(QWidget):
    def __init__(self, on_config_changed: Optional[Callable[[AppConfig], None]] = None, parent=None):
        super().__init__(parent)
        self.on_config_changed = on_config_changed
        self.config = load_config()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Settings</h2>"))

        form = QFormLayout()

        # --- Sync folder ---
        sync_row = QWidget()
        sync_row_layout = QVBoxLayout(sync_row)
        sync_row_layout.setContentsMargins(0, 0, 0, 0)
        self.sync_folder_edit = QLineEdit(self.config.sync_folder)
        self.sync_folder_edit.setPlaceholderText(
            "e.g. C:\\Users\\you\\OneDrive\\TaskOrganizer  (leave blank to use local-only storage)"
        )
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_sync_folder)
        sync_row_layout.addWidget(self.sync_folder_edit)
        sync_row_layout.addWidget(browse_btn)
        form.addRow("OneDrive sync folder", sync_row)

        # --- Ollama ---
        self.ollama_host_edit = QLineEdit(self.config.ollama_host)
        form.addRow("Ollama host", self.ollama_host_edit)

        self.ollama_model_edit = QLineEdit(self.config.ollama_model)
        form.addRow("Ollama model", self.ollama_model_edit)

        # --- Azure ---
        self.azure_client_id_edit = QLineEdit(self.config.azure_client_id)
        self.azure_client_id_edit.setPlaceholderText(
            "Application (client) ID from your free Azure AD app registration"
        )
        form.addRow("Azure AD client ID", self.azure_client_id_edit)

        # --- Notifications ---
        self.notify_deadline_checkbox = QCheckBox("Instant/upcoming deadline alerts")
        self.notify_deadline_checkbox.setChecked(self.config.notify_deadline_alerts)
        form.addRow("", self.notify_deadline_checkbox)

        self.deadline_hours_spin = QSpinBox()
        self.deadline_hours_spin.setRange(1, 168)
        self.deadline_hours_spin.setValue(self.config.deadline_alert_hours)
        self.deadline_hours_spin.setSuffix(" hours before deadline")
        form.addRow("Alert lead time", self.deadline_hours_spin)

        self.notify_daily_checkbox = QCheckBox("Daily digest")
        self.notify_daily_checkbox.setChecked(self.config.notify_daily_digest)
        form.addRow("", self.notify_daily_checkbox)

        self.notify_weekly_checkbox = QCheckBox("Weekly digest")
        self.notify_weekly_checkbox.setChecked(self.config.notify_weekly_digest)
        form.addRow("", self.notify_weekly_checkbox)

        layout.addLayout(form)

        help_label = QLabel(
            "See README.md for step-by-step instructions on registering a free "
            "Azure AD app (for Outlook/Teams) and installing Ollama (for AI features)."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        save_btn = QPushButton("Save settings")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _browse_sync_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose OneDrive sync folder")
        if folder:
            self.sync_folder_edit.setText(folder)

    def _save(self) -> None:
        sync_folder = self.sync_folder_edit.text().strip()
        if sync_folder:
            try:
                ensure_sync_folder(sync_folder)
            except SyncPathError as exc:
                QMessageBox.critical(self, "Invalid sync folder", str(exc))
                return
            if not looks_like_onedrive_path(sync_folder):
                QMessageBox.information(
                    self,
                    "Not a OneDrive folder?",
                    "That path doesn't look like it's inside a OneDrive folder. "
                    "Mobile sync only works if OneDrive is actually syncing this "
                    "folder -- see README.md for details.",
                )

        self.config.sync_folder = sync_folder
        self.config.ollama_host = self.ollama_host_edit.text().strip() or self.config.ollama_host
        self.config.ollama_model = self.ollama_model_edit.text().strip() or self.config.ollama_model
        self.config.azure_client_id = self.azure_client_id_edit.text().strip()
        self.config.notify_deadline_alerts = self.notify_deadline_checkbox.isChecked()
        self.config.deadline_alert_hours = self.deadline_hours_spin.value()
        self.config.notify_daily_digest = self.notify_daily_checkbox.isChecked()
        self.config.notify_weekly_digest = self.notify_weekly_checkbox.isChecked()

        save_config(self.config)
        QMessageBox.information(self, "Saved", "Settings saved. Some changes take effect on next launch.")
        if self.on_config_changed:
            self.on_config_changed(self.config)

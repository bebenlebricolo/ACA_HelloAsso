"""
Main window for the HelloAsso Syncer GUI.

This module contains the main application window and worker thread for the sync operation.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Syncer.helloasso.settings import (
    DEFAULT_CONCURRENCY,
    DEFAULT_OUTPUT_DIR,
    REQUEST_DELAY,
    Settings,
)
from helloasso.models import AuthConfig
from helloasso.reporter import Reporter
from helloasso.syncer import sync_forms
from .dialogs import SettingsDialog


def load_stylesheet() -> str:
    """Load the application stylesheet from the external CSS file."""
    stylesheet_path = Path(__file__).parent / "styles" / "styles.css"
    try:
        with open(stylesheet_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback to minimal styling if styles.css is missing
        return """
        QMainWindow {
            background-color: #2a2d3a;
        }
        QWidget#CentralWidget {
            background-color: #2a2d3a;
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #4da6ff;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
        }
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 8px;
        }
        """


# =============================================================================
# Worker thread + Qt-aware reporter
# =============================================================================


class QtReporter(Reporter):
    """Reporter that forwards pipeline events to the worker's Qt signals."""

    def __init__(self, worker: "SyncWorker"):
        self._worker = worker

    def log(self, message: str) -> None:
        self._worker.log.emit(str(message))

    def form_started(self, slug: str, index: int, total: int) -> None:
        self._worker.form_started.emit(slug, index, total)

    def payment_progress(self, slug: str, completed: int, total: int) -> None:
        self._worker.progress.emit(slug, completed, total)

    def form_finished(self, slug: str, path: Path) -> None:
        self._worker.form_finished.emit(slug, str(path))

    def should_cancel(self) -> bool:
        return self._worker.is_cancelled()


class SyncWorker(QThread):
    """Runs ``asyncio.run(sync_forms(...))`` off the UI thread."""

    log = Signal(str)
    form_started = Signal(str, int, int)
    progress = Signal(str, int, int)
    form_finished = Signal(str, str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self,
                 forms: List[str],
                 output_dir: Path,
                 organization: str,
                 settings: Settings,
                 config: AuthConfig):
        super().__init__()
        self._forms = forms
        self._output_dir = output_dir
        self._organization = organization
        self._settings = settings
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        reporter = QtReporter(self)
        try:
            files = asyncio.run(sync_forms(
                self._forms,
                self._output_dir,
                self._organization,
                self._settings,
                self._config,
                reporter,
            ))
            self.finished_ok.emit(files or [])
        except Exception as e:  # surfaced to the UI
            self.failed.emit(str(e))


# =============================================================================
# Main window
# =============================================================================


class MainWindow(QMainWindow):
    settings_data: Settings
    auth_config: AuthConfig

    def __init__(self, settings: Optional[Settings] = None, auth_config: Optional[AuthConfig] = None):
        super().__init__()
        self.setWindowTitle("HelloAsso Syncer")
        self.resize(800, 600)
        self._worker: Optional[SyncWorker] = None

        # Initialize settings data with defaults
        if settings is not None:
            self.settings_data = settings
        else:
            self.settings_data = Settings()

        # Initialize authentication config with defaults
        if auth_config is not None:
            self.auth_config = auth_config
        else:
            self.auth_config = AuthConfig()

        # Load any existing saved settings
        self._load_saved_settings()

        # Apply modern style from external file
        self.setStyleSheet(load_stylesheet())

        # Create central widget with object name for styling
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        # Main layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with title and settings button
        header_layout = QHBoxLayout()

        self.title_label = QLabel("HelloAsso Syncer")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #4da6ff;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        # Settings button
        self.settings_button = QPushButton("⚙  Configuration")
        self.settings_button.setObjectName("SettingsButton")
        self.settings_button.setToolTip("Ouvrir la configuration")
        self.settings_button.clicked.connect(self._open_settings)
        header_layout.addWidget(self.settings_button)

        layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Prêt à synchroniser")
        layout.addWidget(self.progress_bar)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.run_button = QPushButton("Lancer la synchronisation")
        self.run_button.setObjectName("RunButton")
        self.run_button.clicked.connect(self._on_run)
        buttons_layout.addWidget(self.run_button)

        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._on_cancel)
        buttons_layout.addWidget(self.cancel_button)

        self.open_output_button = QPushButton("Ouvrir le dossier")
        self.open_output_button.clicked.connect(self._open_output_dir)
        buttons_layout.addWidget(self.open_output_button)

        buttons_layout.addStretch(1)
        layout.addLayout(buttons_layout)

        # Log view label
        log_label = QLabel("Journal de synchronisation :")
        log_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #b0b0b0;")
        layout.addWidget(log_label)

        # Log view
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, stretch=1)

    # --- Configuration dialog ------------------------------------------------

    def _open_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(self, self.settings_data, self.auth_config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings_data = dialog.settings_data
            self.auth_config = dialog.auth_config

            # Save settings to files
            self._save_settings()
            self._append_log("Configuration mise à jour")

    def _save_settings(self) -> None:
        """Save current settings to config files."""
        from helloasso.config_manager import save_config

        # Get save_to_user_config from settings or default to True
        save_to_user_config = self.settings_data.save_to_user_config

        # Save to local and optionally AppData
        save_config(
            self.auth_config,
            self.settings_data,
            local=True,
            appdata=save_to_user_config
        )

    # --- Helpers -------------------------------------------------------------

    def _open_output_dir(self) -> None:
        path = Path(self.settings_data.output_dir or str(DEFAULT_OUTPUT_DIR)).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _selected_forms(self) -> List[str]:
        forms = self.settings_data.selected_forms
        extra = self.settings_data.extra_forms or ''
        extra = extra.replace(",", " ").split()
        for slug in extra:
            if slug not in forms:
                forms.append(slug)
        return forms

    def _resolve_config(self) -> AuthConfig:
        client_id = self.auth_config.client_id or ''
        client_secret = self.auth_config.client_secret or ''
        if client_id and client_secret:
            return AuthConfig(client_id=client_id, client_secret=client_secret)

        self.settings_data.secrets_path
        self.auth_config.load_from_file(self.settings_data.secrets_path)
        return self.auth_config

    def _load_saved_settings(self) -> None:
        """Load saved settings from config files."""

        self.settings_data.load_from_file(self.settings_data.secrets_path)
        # if saved_config:
        #     # Merge with existing settings_data, with saved values taking precedence
        #     for key, value in saved_config.items():
        #         # Don't overwrite with empty strings for form selections
        #         if key == 'selected_forms' and isinstance(value, list):
        #             if value and self.settings_data.get('selected_forms'):
        #                 # Keep existing if already set
        #                 pass
        #             else:
        #                 self.settings_data[key] = value
        #         elif value is not None and value != '':
        #             self.settings_data[key] = value

    # --- Run / cancel ------------------------------------------------------

    def _on_run(self) -> None:
        forms = self._selected_forms()
        if not forms:
            QMessageBox.warning(self, "Aucune billetterie", "Sélectionnez au moins une billetterie dans les paramètres.")
            return

        try:
            config = self._resolve_config()
        except ValueError as e:
            QMessageBox.critical(self, "Configuration", str(e))
            return

        settings = Settings(
            request_delay=self.settings_data.request_delay or REQUEST_DELAY,
            concurrency=self.settings_data.concurrency or DEFAULT_CONCURRENCY,
            sequential=self.settings_data.sequential or False,
        )

        output_dir = Path(self.settings_data.output_dir or str(DEFAULT_OUTPUT_DIR)).expanduser()
        organization = self.settings_data.organization

        self.log_view.clear()
        self.progress_bar.setRange(0, 0)
        self._set_running(True)

        self._worker = SyncWorker(forms, output_dir, organization, settings, config)
        self._worker.log.connect(self._append_log)
        self._worker.form_started.connect(self._on_form_started)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self._append_log("Annulation demandée…")

    def _set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    # --- Signal slots (main thread) ---------------------------------------

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message.replace("\r", "").rstrip("\n"))

    def _on_form_started(self, slug: str, index: int, total: int) -> None:
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(f"{slug} ({index}/{total})")

    def _on_progress(self, slug: str, completed: int, total: int) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(completed)
        self.progress_bar.setFormat(f"{slug} — %v/%m")

    def _on_finished_ok(self, files: list) -> None:
        self._set_running(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_bar.setFormat("Terminé")
        summary = f"{len(files)} fichier(s) généré(s)."
        if files:
            summary += "\n\n" + "\n".join(files)
        QMessageBox.information(self, "Synchronisation terminée", summary)

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Échec")
        QMessageBox.critical(self, "Erreur", message)


def show_first_run_dialog() -> Optional[tuple]:
    """
    Show the first-run configuration dialog.

    Returns a tuple of (client_id, client_secret, save_to_appdata) or None if cancelled.
    """
    from .dialogs import FirstRunDialog

    # Need to create a QApplication instance first
    temp_app = QApplication.instance()
    if temp_app is None:
        temp_app = QApplication(sys.argv)

    dialog = FirstRunDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_credentials()
    return None


def check_or_create_config() -> dict:
    """
    Check if config exists, and if not, show first-run dialog.

    Returns the configuration dictionary.
    """

    # Check if config exists
    # if config_exists():
    #     # Load existing config
    #     config = loadauth_config()
    #     if config:
    #         return config

    # Config doesn't exist or is invalid - show first-run dialog
    # We need a QApplication instance for the dialog
    temp_app = QApplication.instance()
    if temp_app is None:
        temp_app = QApplication(sys.argv)

    result = show_first_run_dialog()

    if result is None:
        # User cancelled - return empty config
        return {}

    client_id, client_secret, save_to_appdata = result

    # Return the basic config
    return {
        'client_id': client_id,
        'client_secret': client_secret,
        'save_to_appdata': save_to_appdata,
    }


def main() -> None:
    app = QApplication(sys.argv)

    # Set application style for better modern appearance
    app.setStyle("Fusion")

    # Check for configuration or show first-run dialog
    # config = check_or_create_config()

    # if not config:
    #     # User cancelled first-run dialog
    #     sys.exit(0)

    settings = Settings()
    auth_config = AuthConfig()

    # Pass config to MainWindow
    window = MainWindow(auth_config=auth_config, settings=settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

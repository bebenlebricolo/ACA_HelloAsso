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



from ..models.Constants import *
from ..models.app.Config import Config
from ..models.app.Secrets import Secrets
from ..models.app.UserSettings import UserSettings
from ..helloasso.config_manager import save_config, get_executable_path, get_persistent_config_folder
from ..helloasso.reporter import Reporter
from ..helloasso.syncer import sync_forms
from .dialogs import SettingsDialog, FirstRunDialog


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

    forms:list[str]
    secrets: Secrets
    config: Config

    def __init__(self,
                 forms: List[str],
                 config: Config,
                 secrets: Secrets):
        super().__init__()
        self.forms = forms
        self.config = config
        self.secrets = secrets
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        reporter = QtReporter(self)
        try:
            files = asyncio.run(sync_forms(
                self.forms,
                self.config,
                self.secrets,
                reporter,
            ))
            self.finished_ok.emit(files or [])
        except Exception as e:  # surfaced to the UI
            self.failed.emit(str(e))


# =============================================================================
# Main window
# =============================================================================


class MainWindow(QMainWindow):
    config: Config
    secrets: Secrets
    user_settings: UserSettings

    def __init__(self, config: Optional[Config] = None, secrets: Optional[Secrets] = None, user_settings : Optional[UserSettings] = None):
        super().__init__()
        self.setWindowTitle("HelloAsso Syncer")
        self.resize(800, 600)
        self._worker: Optional[SyncWorker] = None

        # Initialize settings data with defaults
        if config is not None:
            self.config = config
        else:
            self.config = Config()

        # Initialize authentication config with defaults
        if secrets is not None:
            self.secrets = secrets
        else:
            # try to load secrets, if available
            self.secrets = Secrets()
            candidate_secrets_file = find_secrets_file()
            if candidate_secrets_file is not None :
                self.secrets.load_from_file(candidate_secrets_file)

        if user_settings is not None:
            self.user_settings = user_settings
        else :
            self.user_settings = UserSettings()

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
        dialog = SettingsDialog(self, self.config, self.secrets, self.user_settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:

            # Gather data from the sub dialog
            self.config = dialog.config
            self.secrets = dialog.secrets
            self.user_settings = dialog.user_settings

            # Save settings to files
            save_ok = self._save_settings()
            if not save_ok :
                QMessageBox.warning(
                    self,
                    "Impossible de sauvegarder les paramètres utilisateur",
                    "Veuillez vérifier vos données."
                )

            self._append_log("Configuration mise à jour")

    def _save_settings(self) -> bool:
        """Save current settings to config files."""

        # Save to local and optionally AppData
        return save_config(
            self.secrets,
            self.config,
            self.user_settings,
            local=True,
        )

    # --- Helpers -------------------------------------------------------------

    def _open_output_dir(self) -> None:
        path = Path(self.config.output_dir or str(DEFAULT_OUTPUT_DIR)).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _selected_forms(self) -> List[str]:
        forms = self.user_settings.selected_forms
        extra = self.user_settings.extra_forms or ''
        extra = extra.replace(",", " ").split()
        for slug in extra:
            if slug not in forms:
                forms.append(slug)
        return forms

    def _resolve_secrets(self) -> Secrets:
        client_id = self.secrets.client_id or ''
        client_secret = self.secrets.client_secret or ''
        if client_id and client_secret:
            return Secrets(client_id=client_id, client_secret=client_secret)

        self.config.secrets_path
        self.secrets.load_from_file(self.config.secrets_path)
        return self.secrets

    # --- Run / cancel ------------------------------------------------------

    def _on_run(self) -> None:
        forms = self._selected_forms()
        if not forms:
            QMessageBox.warning(self, "Aucune billetterie", "Sélectionnez au moins une billetterie dans les paramètres.")
            return

        # try:
        #     secrets = self._resolve_secrets()
        # except ValueError as e:
        #     QMessageBox.critical(self, "Configuration", str(e))
        #     return

        self.log_view.clear()
        self.progress_bar.setRange(0, 0)
        self._set_running(True)

        self._worker = SyncWorker(forms, self.config, self.secrets)
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

    # Need to create a QApplication instance first
    temp_app = QApplication.instance()
    if temp_app is None:
        temp_app = QApplication(sys.argv)

    dialog = FirstRunDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_data()
    return None


def find_config_file() -> Optional[Path]:
    persisted_config_dir = get_persistent_config_folder()

    user_config_path = None
    if persisted_config_dir != None :
        user_config_path = persisted_config_dir / CONFIG_FILENAME

    local_folder = get_executable_path()
    local_config = local_folder / CONFIG_FILENAME

    if not user_config_path or not user_config_path.exists():
        if not local_config.exists():
            return None
        return local_config

    # Favor local file, takes over the user one (weird use case, a decision had to be made)
    if user_config_path.exists() and user_config_path.exists():
        return local_config
    elif user_config_path.exists():
        return user_config_path
    return None

def find_user_settings_file() -> Optional[Path]:
    persisted_config_dir = get_persistent_config_folder()
    user_settings_file = None
    if persisted_config_dir != None:
        user_settings_file = persisted_config_dir / USER_SETTINGS_FILENAME

    if user_settings_file and user_settings_file.exists():
        return user_settings_file
    return None

def find_secrets_file() -> Optional[Path]:
    persisted_config_dir = get_persistent_config_folder()
    user_secrets_path = None
    if persisted_config_dir != None :
        user_secrets_path = persisted_config_dir / SECRETS_FILENAME

    # Nothing is stored in user profile / config folders
    local_folder = get_executable_path()
    local_secrets = local_folder / SECRETS_FILENAME
    if not user_secrets_path or not user_secrets_path.exists():
        if not local_secrets.exists():
            return None
        return local_secrets

    # Favor local file, takes over the user one (weird use case, a decision had to be made)
    if user_secrets_path.exists() and local_secrets.exists():
        return local_secrets
    elif user_secrets_path.exists():
        return user_secrets_path
    return None

def load_secrets(filepath: Path) -> Secrets:
    secrets = Secrets()
    secrets.load_from_file(filepath)

    return secrets

def retrieve_secrets() -> Optional[Secrets]:
    """
    Check if secrets exists, and if not, show first-run dialog.

    Returns the secrets object, or nothing.
    """

    # Check if secrets exists
    secrets_file = find_secrets_file()
    if secrets_file != None:
        # Load existing config
        secrets = load_secrets(secrets_file)
        if secrets:
            return secrets
    return None

def retrieve_config() -> Optional[Config]:

    # Check if config exists
    config_file = find_config_file()
    if config_file != None and config_file.exists():
        # Load existing config
        config = Config()
        config.load_from_file(config_file)
        return config
    return None

def retrieve_user_settings() -> Optional[UserSettings]:

    # Check if settings exists
    user_settings_file = find_user_settings_file()
    if user_settings_file != None and user_settings_file.exists():
        # Load existing settings
        settings = UserSettings()
        settings.load_from_file(user_settings_file)
        return settings
    return None

def main() -> None:
    app = QApplication(sys.argv)

    # Set application style for better modern appearance
    app.setStyle("Fusion")

    # Check for configuration or show first-run dialog
    secrets = retrieve_secrets()
    config = retrieve_config()
    user_settings = retrieve_user_settings()
    if secrets is None:
        # Config doesn't exist or is invalid - show first-run dialog
        # We need a QApplication instance for the dialog
        temp_app = QApplication.instance()
        if temp_app is None:
            temp_app = QApplication(sys.argv)
        result = show_first_run_dialog()

        # User cancelled and closed the window
        if result is None:
            sys.exit(0)

        client_id, client_secret, persist_on_save = result
        secrets = Secrets(client_id, client_secret)

    if config is None:
        config = Config()

    if user_settings is None:
        user_settings = UserSettings()

    # Save secrets to user profile / appdata / config folders
    if config.persist_on_save:
        # Save to local and optionally AppData
        saved_ok = save_config( secrets, config, user_settings, local=True )
        if not saved_ok:
            print("Oups ! Impossible de sauvegarder la configuration locale !")

    # Pass config to MainWindow
    window = MainWindow(secrets=secrets, config=config, user_settings=user_settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

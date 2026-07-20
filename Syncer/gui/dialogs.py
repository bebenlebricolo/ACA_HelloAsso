"""
Settings dialog for the HelloAsso Syncer GUI.

Contains the SettingsDialog class with all configuration options organized in tabs.
"""

from copy import copy
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from Syncer.helloasso.models.schemas import AuthConfig
from Syncer.helloasso.settings import (
    Settings,
)


class SettingsDialog(QDialog):
    """Dialog containing all configuration options."""

    settings_data: Settings
    auth_config: AuthConfig

    def __init__(self, parent: QWidget, settings_data: Settings, auth_config: AuthConfig):
        super().__init__(parent)
        self.setWindowTitle("Configuration - HelloAsso Syncer")
        self.resize(800, 600)
        self.setModal(True)

        # Duplicate the settings data to avoid modifying the original until the user clicks "OK"
        self.settings_data = copy(settings_data)

        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Create tab widget for better organization
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Tab 1: HelloAsso Credentials
        self._create_credentials_tab()

        # Tab 2: Forms
        self._create_forms_tab()

        # Tab 3: Parameters
        self._create_parameters_tab()

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _create_credentials_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Identifiants HelloAsso")
        form = QFormLayout(group)

        # Config file
        self.secrets_path_edit = QLineEdit()
        self.secrets_path_edit.setPlaceholderText("secrets.json (par défaut)")
        browse = QPushButton("Parcourir...")
        browse.clicked.connect(self._pick_config_file)
        row = QHBoxLayout()
        row.addWidget(self.secrets_path_edit, stretch=1)
        row.addWidget(browse)
        row_w = QWidget()
        row_w.setLayout(row)
        form.addRow("Fichier de config :", row_w)

        # Client ID and Secret
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText("Optionnel : surcharge le fichier")
        form.addRow("Client ID :", self.client_id_edit)

        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setPlaceholderText("Optionnel : surcharge le fichier")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Client secret :", self.client_secret_edit)

        layout.addWidget(group)
        self.tab_widget.addTab(tab, "Authentification")

    def _create_forms_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Billetteries")
        vbox = QVBoxLayout(group)

        # Forms list
        self.forms_list = QListWidget()

        for slug in self.settings_data.selected_forms:
            item = QListWidgetItem(slug)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.forms_list.addItem(item)

        for slug in self.settings_data.unselected_forms:
            item = QListWidgetItem(slug)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.forms_list.addItem(item)
        vbox.addWidget(self.forms_list)

        # Select all/none buttons
        select_all = QPushButton("Tout sélectionner")
        select_all.clicked.connect(lambda: self._set_all_forms(Qt.CheckState.Checked))
        select_none = QPushButton("Tout désélectionner")
        select_none.clicked.connect(lambda: self._set_all_forms(Qt.CheckState.Unchecked))
        btn_row = QHBoxLayout()
        btn_row.addWidget(select_all)
        btn_row.addWidget(select_none)
        btn_row.addStretch(1)
        vbox.addLayout(btn_row)

        # Extra forms
        self.extra_forms_edit = QLineEdit()
        self.extra_forms_edit.setPlaceholderText("Slugs supplémentaires, séparés par des espaces ou des virgules")
        vbox.addWidget(QLabel("Autres billetteries :"))
        vbox.addWidget(self.extra_forms_edit)

        layout.addWidget(group)
        self.tab_widget.addTab(tab, "Billetteries")

    def _create_parameters_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Paramètres")
        form = QFormLayout(group)

        # Concurrency
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 100)
        form.addRow("Requêtes simultanées :", self.concurrency_spin)

        # Delay
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 10.0)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setDecimals(2)
        form.addRow("Délai entre requêtes (s) :", self.delay_spin)

        # Sequential mode
        self.sequential_check = QCheckBox("Mode séquentiel (debug, une requête à la fois)")
        self.sequential_check.toggled.connect(self.concurrency_spin.setDisabled)
        form.addRow("", self.sequential_check)

        # Output directory
        self.output_edit = QLineEdit()
        browse = QPushButton("Parcourir...")
        browse.clicked.connect(self._pick_output_dir)
        row = QHBoxLayout()
        row.addWidget(self.output_edit, stretch=1)
        row.addWidget(browse)
        row_w = QWidget()
        row_w.setLayout(row)
        form.addRow("Dossier de sortie :", row_w)

        # Organization
        self.org_edit = QLineEdit()
        form.addRow("Organisation :", self.org_edit)

        # AppData persistence option
        self.save_appdata_check = QCheckBox(
            "Enregistrer aussi dans AppData (persistance entre installations)"
        )
        self.save_appdata_check.setChecked(True)
        form.addRow("", self.save_appdata_check)

        layout.addWidget(group)
        self.tab_widget.addTab(tab, "Paramètres")

    def _load_settings(self) -> None:
        """Load settings from the data dictionary."""
        settings = self.settings_data
        secrets = self.auth_config

        # Credentials
        self.secrets_path_edit.setText(settings.secrets_path.as_posix())
        self.client_id_edit.setText(secrets.client_id)
        self.client_secret_edit.setText(secrets.client_secret)

        # Forms
        selected_forms = settings.selected_forms
        for i in range(self.forms_list.count()):
            item = self.forms_list.item(i)
            slug = item.text()
            item.setCheckState(
                Qt.CheckState.Checked if slug in selected_forms
                else Qt.CheckState.Unchecked
            )
        self.extra_forms_edit.setText(settings.extra_forms or '')

        # Parameters
        self.concurrency_spin.setValue(settings.concurrency)
        self.delay_spin.setValue(settings.request_delay)
        self.sequential_check.setChecked(settings.sequential)
        self.output_edit.setText(str(settings.output_dir))
        self.org_edit.setText(settings.organization)
        self.save_appdata_check.setChecked(settings.save_to_user_config)

    def _save_settings(self) -> dict:
        """Save settings to the data dictionary."""
        data = {}

        # Credentials
        data['config_path'] = self.secrets_path_edit.text().strip()
        data['client_id'] = self.client_id_edit.text().strip()
        data['client_secret'] = self.client_secret_edit.text().strip()

        # Forms
        data['selected_forms'] = self._get_selected_forms()
        data['extra_forms'] = self.extra_forms_edit.text().strip()

        # Parameters
        data['concurrency'] = self.concurrency_spin.value()
        data['delay'] = self.delay_spin.value()
        data['sequential'] = self.sequential_check.isChecked()
        data['output_dir'] = self.output_edit.text().strip()
        data['organization'] = self.org_edit.text().strip()
        data['save_to_appdata'] = self.save_appdata_check.isChecked()

        return data

    def _set_all_forms(self, state: Qt.CheckState) -> None:
        for i in range(self.forms_list.count()):
            self.forms_list.item(i).setCheckState(state)

    def _get_selected_forms(self) -> List[str]:
        forms = [
            self.forms_list.item(i).text()
            for i in range(self.forms_list.count())
            if self.forms_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        return forms

    def _pick_config_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choisir secrets.json", "", "JSON (*.json)")
        if path:
            self.secrets_path_edit.setText(path)

    def _pick_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de sortie",
            self.output_edit.text()
        )
        if path:
            self.output_edit.setText(path)

    def accept(self) -> None:
        """Override accept to save settings."""
        self.settings_data.save_to_file(Path(self.secrets_path_edit.text().strip()))
        super().accept()


# =============================================================================
# First Run Dialog
# =============================================================================


class FirstRunDialog(QDialog):
    """Dialog shown on first launch to configure HelloAsso credentials."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Premier lancement - Configuration requise")
        self.setModal(True)
        self.resize(500, 300)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Icon and title
        title_label = QLabel("Bienvenue dans HelloAsso Syncer")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #4da6ff;")
        layout.addWidget(title_label)

        desc_label = QLabel(
            "Avant de commencer, veuillez fournir vos identifiants HelloAsso."
        )
        desc_label.setStyleSheet("color: #b0b0b0;")
        layout.addWidget(desc_label)
        layout.addSpacing(16)

        # Form group
        group = QGroupBox("Identifiants HelloAsso")
        form = QFormLayout(group)

        # Client ID
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText("Entrez votre Client ID")
        form.addRow("Client ID :", self.client_id_edit)

        # Client Secret
        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setPlaceholderText("Entrez votre Client Secret")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Client Secret :", self.client_secret_edit)

        layout.addWidget(group)
        layout.addSpacing(16)

        # Save to AppData option
        self.save_appdata_check = QCheckBox(
            "Enregistrer aussi dans le dossier AppData (recommandé pour la persistance)"
        )
        self.save_appdata_check.setChecked(True)
        self.save_appdata_check.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(self.save_appdata_check)
        layout.addSpacing(16)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Store result
        self.saved = False
        self.save_to_appdata = True

    def _save_and_close(self) -> None:
        """Save configuration and close the dialog."""
        client_id = self.client_id_edit.text().strip()
        client_secret = self.client_secret_edit.text().strip()

        if not client_id or not client_secret:
            QMessageBox.warning(
                self,
                "Configuration incomplète",
                "Veuillez entrer à la fois le Client ID et le Client Secret."
            )
            return

        # Save configuration
        config_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'save_to_appdata': self.save_appdata_check.isChecked(),
        }

        # Save to files
        from helloasso.config_manager import save_config
        save_to_appdata = self.save_appdata_check.isChecked()

        if save_config(config_data, local=True, appdata=save_to_appdata):
            self.saved = True
            self.save_to_appdata = save_to_appdata
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Erreur",
                "Impossible d'enregistrer la configuration. Vérifiez les permissions."
            )

    def get_credentials(self) -> tuple:
        """Return the entered credentials."""
        return (
            self.client_id_edit.text().strip(),
            self.client_secret_edit.text().strip(),
            self.save_appdata_check.isChecked()
        )

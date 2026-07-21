# =============================================================================
# Main Models
# =============================================================================

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

from ..Jsonable import Jsonable

CLIENT_ID_ENV_VAR = "HELLOASSO_CLIENT_ID"
CLIENT_SECRET_ENV_VAR = "HELLOASSO_CLIENT_SECRET"


@dataclass
class Secrets(Jsonable):
    """Authentication configuration for HelloAsso API"""
    client_id: str = ""
    client_secret: str = ""

    def check_valid(self) -> bool:
        """Check if the configuration is valid (non-empty)"""
        return bool(self.client_id and self.client_secret)

    def from_json(self, content: dict[str, Any]) -> None:
        """Load authentication configuration from a JSON dictionary"""
        self.client_id = content.get("clientId", "")
        self.client_secret = content.get("clientSecret", "")

    def to_json(self) -> dict:
        """Convert the configuration to a dictionary"""
        return {
            "clientId": self.client_id,
            "clientSecret": self.client_secret
        }

    def load_from_file(self, file_path: Optional[Path]) -> None:
        """Load authentication configuration from a JSON file"""

        # Blank path
        file_paths = []

        # Try environment variables first
        if file_path is None:
            client_id = os.getenv(CLIENT_ID_ENV_VAR)
            client_secret = os.getenv(CLIENT_SECRET_ENV_VAR)

            # Use environment variables if available
            if client_id and client_secret:
                self.client_id = client_id
                self.client_secret = client_secret

        # Otherwise, load from the file
        else:
            file_path = cast(Path, file_path)  # We're now sure file_path is not None
            if not file_path.exists():
                raise ValueError( f"Le fichier de configuration spécifié n'existe pas: {file_path}")

            # Load from disk
            if file_path.exists():
                file_paths.append(file_path)

                with open(file_path, 'r') as f:
                    data = json.load(f)
                    self.from_json(data)

        # Final validity check
        if not self.check_valid():
            raise ValueError(
                f"Configuration invalide dans pour la configuration des clés d'authentification: {file_paths}. "
                "Assurez-vous que 'clientId' et 'clientSecret' sont présents."
            )

    def save_to_file(self, file_path: Optional[Path]) -> None:
        """Save authentication configuration to a JSON file"""
        if file_path is None:
            raise ValueError("Le chemin du fichier de configuration ne peut pas être None.")

        data = self.to_json()
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
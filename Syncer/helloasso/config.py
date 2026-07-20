"""
Configuration for the HelloAsso Syncer: constants, tunable runtime settings
and secret loading (from JSON file or environment variables).
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import AuthConfig

# =============================================================================
# Constants
# =============================================================================

DEFAULT_CONFIG_PATH = Path(__file__).parent / "secrets.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_API_URL = "https://api.helloasso.com"

# Organization (adapt if needed)
ORGANIZATION_SLUG = "aviron-club-angouleme"

# Form type
FORM_CATEGORY = "Membership"

# Rate limiting (defaults, overridable via CLI)
REQUEST_DELAY = 0.1  # Delay between requests (seconds)
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
DEFAULT_CONCURRENCY = 5  # Maximum concurrent requests

USER_AGENT = "HelloAsso-Syncer/1.0"

# Forms of interest (can be overridden by command line arguments)
FORMS = [
    "licence-jeunes-saison-25-26",
    "licence-saison-25-26-loisirs",
    "adhesion-2026-2027-sport-sante-1",
    "licence-saison-aviron-sante-25-26",
]


# =============================================================================
# Runtime settings
# =============================================================================


@dataclass
class Settings:
    """Tunable runtime parameters (throttling / retries / concurrency)."""

    request_delay: float = REQUEST_DELAY
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY
    concurrency: int = DEFAULT_CONCURRENCY
    sequential: bool = False


def load_config(config_path: Optional[Path] = None) -> AuthConfig:
    """Load the configuration from a JSON file or environment variables"""

    # Try environment variables first
    client_id = os.getenv("HELLOASSO_CLIENT_ID")
    client_secret = os.getenv("HELLOASSO_CLIENT_SECRET")

    if client_id and client_secret:
        return AuthConfig(client_id=client_id, client_secret=client_secret)

    # Otherwise, load from the file
    config_paths = []
    if config_path:
        config_paths.append(config_path)
    if DEFAULT_CONFIG_PATH.exists():
        config_paths.append(DEFAULT_CONFIG_PATH)

    for path in config_paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return AuthConfig(
                    client_id=data.get("clientId") or data.get("client_id"),
                    client_secret=data.get(
                        "clientSecret") or data.get("client_secret")
                )
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            continue

    raise ValueError(
        "Impossible de trouver la configuration. "
        "Fournissez un fichier secrets.json ou définissez les variables d'environnement "
        "HELLOASSO_CLIENT_ID et HELLOASSO_CLIENT_SECRET."
    )

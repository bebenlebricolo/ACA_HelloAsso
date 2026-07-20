"""
Configuration for the HelloAsso Syncer: constants, tunable runtime settings
and secret loading (from JSON file or environment variables).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# =============================================================================
# Constants
# =============================================================================

DEFAULT_SECRETS_PATH = Path(__file__).parent / "secrets.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_API_URL = "https://api.helloasso.com"

# Form type
FORM_CATEGORY = "Membership"

# Rate limiting (defaults, overridable via CLI)
REQUEST_DELAY = 0.1  # Delay between requests (seconds)
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
DEFAULT_CONCURRENCY = 5  # Maximum concurrent requests

USER_AGENT = "HelloAsso-Syncer/1.0"

# =============================================================================
# Runtime settings
# =============================================================================

@dataclass
class Settings:
    """Tunable runtime parameters (throttling / retries / concurrency)."""

    secrets_path: Path = DEFAULT_SECRETS_PATH

    # All forms are stored in the settings, but only the selected ones are processed.
    selected_forms: list[str] = field(default_factory=list)
    unselected_forms: list[str] = field(default_factory=list)
    extra_forms: Optional[str] = None  # Comma-separated list of additional form slugs

    concurrency: int = DEFAULT_CONCURRENCY
    request_delay: float = REQUEST_DELAY
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY
    sequential: bool = False

    output_dir: Path = DEFAULT_OUTPUT_DIR
    organization: str = "to-be-defined"
    save_to_user_config: bool = True

    def load_from_file(self, path: Optional[Path] = None):
        """Load settings from a JSON file."""
        if path is None:
            path = self.secrets_path
        if not path.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")
        with open(path, "r") as f:
            data = json.load(f)
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def save_to_file(self, path: Optional[Path] = None):
        """Save settings to a JSON file."""
        if path is None:
            path = self.secrets_path
        data = {field.name: getattr(self, field.name) for field in self.__dataclass_fields__.values()}
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

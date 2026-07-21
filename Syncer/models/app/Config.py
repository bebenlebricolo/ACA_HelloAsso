# =============================================================================
# Runtime settings
# =============================================================================

from typing import Any, Optional
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..Jsonable import Jsonable
from ..Constants import *


@dataclass
class HelloAssoConfig(Jsonable):
    """Configuration for the HelloAsso client."""

    base_url: str = BASE_API_URL
    organization: str = "to-be-defined"

    def from_json(self, content: dict[str, Any]):
        """Load configuration from a dictionary."""
        for key, value in content.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_json(self) -> dict:
        """Convert the configuration to a dictionary."""
        return {
            "base_url": self.base_url,
            "organization": self.organization,
        }

@dataclass
class HttpClientConfig(Jsonable):
    """Configuration for the HTTP client used to interact with HelloAsso API."""
    user_agent: str = USER_AGENT
    request_delay: float = REQUEST_DELAY
    max_retries: int = MAX_RETRIES
    retry_delay: float = RETRY_DELAY
    concurrency: int = DEFAULT_CONCURRENCY

    def from_json(self, content: dict[str, Any]):
        """Load configuration from a dictionary."""
        for key, value in content.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_json(self) -> dict:
        """Convert the configuration to a dictionary."""
        return {
            "user_agent": self.user_agent,
            "request_delay": self.request_delay,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "concurrency": self.concurrency,
        }

@dataclass
class Config(Jsonable):
    """Tunable runtime parameters (throttling / retries / concurrency)."""

    secrets_path: Path = field(default=Path("secrets.json"))

    # All forms are stored in the settings, but only the selected ones are processed.
    forms: list[str] = field(default_factory=list)
    output_dir: Path = DEFAULT_OUTPUT_DIR

    hello_asso: HelloAssoConfig = field(default_factory=HelloAssoConfig)
    http_client: HttpClientConfig = field(default_factory=HttpClientConfig)
    persist_on_save: bool = True

    def from_json(self, content: dict[str, Any]):
        """Load configuration from a dictionary."""
        for key, value in content.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_json(self) -> dict:
        """Convert the configuration to a dictionary."""
        return {
            "secrets_path": self.secrets_path.as_posix(),
            "forms": self.forms,
            "output_dir": self.output_dir.as_posix(),
            "hello_asso": self.hello_asso.to_json(),
            "http_client": self.http_client.to_json()
        }

    def load_from_file(self, path: Optional[Path] = None):
        """Load config from a JSON file."""

        if not path or not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r") as f:
            data = json.load(f)

        self.from_json(data)

    def save_to_file(self, path: Optional[Path] = None):
        """Save settings to a JSON file."""
        if path is None:
            path = self.secrets_path
        data = self.to_json()
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
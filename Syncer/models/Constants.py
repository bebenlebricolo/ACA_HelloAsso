from pathlib import Path

# Configuration file names
SECRETS_FILENAME = "secrets.json"
CONFIG_FILENAME = "config.json"
USER_SETTINGS_FILENAME = "settings.json"

# local outputs
DEFAULT_SECRETS_PATH = "secrets.json"
DEFAULT_OUTPUT_DIR = "output"

BASE_OAUTH_URL = "https://api.helloasso.com/oauth2/token"
BASE_API_URL = "https://api.helloasso.com/v5"
FORM_CATEGORY = "Membership"

# Rate limiting (defaults, overridable via CLI)
REQUEST_DELAY = 0.1  # Delay between requests (seconds)
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
DEFAULT_CONCURRENCY = 5  # Maximum concurrent requests

USER_AGENT = "HelloAsso-Syncer/1.0"
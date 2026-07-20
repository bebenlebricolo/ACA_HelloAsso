# HelloAsso Syncer

A collection of Python scripts (3.10+) that synchronize the data collected by our rowing club through the [HelloAsso](https://www.helloasso.com/) platform into local CSV files (and, later, remote storage such as Google Drive).

The script is asynchronous (`asyncio` + `aiohttp`): after authentication (a sequential first step), the retrieval of each form's order details is parallelized, with a configurable concurrency limit.

## Requirements

- Python 3.10+
- The `aiohttp` library (installed automatically via `requirements.txt`)

## Installation

```bash
# Clone the repository or navigate into the Syncer folder
cd HelloAsso/Syncer

# Install dependencies
pip install -r requirements.txt
```

## Configuration

The tool needs a single piece of configuration: your HelloAsso API credentials. You can provide them in two ways.

### Option 1: secrets.json file

Create a `secrets.json` file in the `Syncer` folder with your HelloAsso credentials:

```json
{
    "clientId": "<id generated from the HelloAsso admin portal>",
    "clientSecret": "<secret generated from the HelloAsso admin portal>"
}
```

A template is provided: [secrets.template.json](secrets.template.json). On the first run, just copy it and fill in your values.

### Option 2: Environment variables

You can also use environment variables:

```bash
export HELLOASSO_CLIENT_ID="your_client_id"
export HELLOASSO_CLIENT_SECRET="your_client_secret"
```

> ⚠️ **Never commit your credentials to git!**
> `secrets.json` is already listed in `.gitignore`.

## Usage

### Using the unified entry point (recommended)

The `run.py` script provides a unified entry point for both GUI and CLI:

```bash
# Launch GUI (default)
python run.py

# Launch GUI explicitly
python run.py --gui

# Launch CLI with arguments
python run.py --cli --forms licence-saison-aviron-sante-25-26
```

### Direct CLI usage (legacy)

You can also use the CLI directly:

```bash
# Fetch payments for a specific form
python helloasso/syncer.py --forms licence-saison-aviron-sante-25-26

# Fetch payments for several forms
python helloasso/syncer.py --forms licence-saison-aviron-sante-25-26 licence-saison-competition-25-26

# Fetch all known "Membership" forms
python helloasso/syncer.py --forms all

# Use a custom configuration file
python helloasso/syncer.py --config /path/to/my_secrets.json --forms all

# Change the output folder
python helloasso/syncer.py --output /path/to/output_folder --forms licence-saison-aviron-sante-25-26

# Dry run (test mode)
python helloasso/syncer.py --forms licence-saison-aviron-sante-25-26 --dry-run
```

### Parallelization and throttling

The script parallelizes network requests (order-detail fetches, and processing of forms among themselves). The number of simultaneous requests is bounded globally by a semaphore.

```bash
# Limit to 10 simultaneous requests
python helloasso/syncer.py --forms all --concurrency 10

# Space requests out further (throttling) to avoid being flagged
python helloasso/syncer.py --forms all --concurrency 3 --request-delay 0.5
```

Available options:

- `--concurrency N`: maximum number of simultaneous HTTP requests (default: `5`).
- `--request-delay SECONDS`: minimum delay between requests, with a small random jitter (default: `0.1`).
- `--max-retries N`: number of attempts on network errors (default: `3`).
- `--retry-delay SECONDS`: base delay for the exponential backoff between retries (default: `2`). `429 Too Many Requests` responses additionally honor the `Retry-After` header.

### Sequential mode (debug)

To make debugging easier (deterministic order, one request at a time, no parallelism):

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26 --sequential
```

### Full help

```bash
python Syncer.py --help
```

## Graphical interface (PySide6)

A desktop UI wraps the exact same pipeline for non-technical users with a **modern dark theme** interface.

```bash
# For CLI only:
pip install -r requirements.txt

# For GUI (includes CLI dependencies + PySide6):
pip install -r requirements-gui.txt

# Launch the app
python gui.py
# OR on Windows, double-click run.bat
```

The window has been redesigned with a clean, modern interface:

- **⚙ Configuration button** in the header opens a settings dialog with 3 tabs:
  - **Authentification**: Config file, Client ID, Client Secret
  - **Billetteries**: Select forms with check boxes, plus extra slugs field
  - **Paramètres**: Concurrency, request delay, sequential mode, output folder, organization
- Clean main window with progress bar, action buttons, and log view
- **Customizable styling**: Edit `styles.css` to change colors, fonts, and spacing

Under the hood the async pipeline runs in a background thread and reports progress to the UI through Qt signals, so the window stays responsive.

## Output

The script generates one CSV file per form in the `output/` folder (by default), named:

```
{form_slug}_{timestamp}.csv
```

Each file contains one row per authorized payment, with the following columns:

- `payment_id`, `payment_date`, `payment_amount` — payment identifier, date and amount (in euros)
- `first_name`, `last_name`, `email` — payer information
- `form_slug` — the form the payment belongs to
- `payment_receipt_url` — link to the payment receipt
- one additional column per custom field found on the orders (deduplicated across rows), which is where the club-specific data lives (phone number, parents' email, emergency contact, etc.)

## How it works

The pipeline (`Syncer.py`) does the following:

1. **Authenticates** against the HelloAsso servers and retrieves an OAuth token from the provided API key and secret.
2. **Lists the payments** made by members on a set of online forms ("Membership" category).
3. **Fetches the detailed information** for each payment (order details, custom fields, etc.).
4. **Aggregates the data** (a software-side SQL-like JOIN) between payments and their details.
5. **Generates CSV files** with all the consolidated information (one file per form).

## Project structure

The code is organized into Python packages for better modularity:

```
Syncer/
├── helloasso/              # Core package
│   ├── __init__.py          # Exports main symbols
│   ├── client.py            # HelloAssoClient: HTTP session, endpoints, throttling
│   ├── config.py            # Constants, Settings dataclass, secret loading
│   ├── export.py            # CSV export functionality
│   ├── models/              # Data models (schemas.py)
│   │   └── __init__.py
│   ├── reporter.py          # Progress reporting interface
│   └── syncer.py            # Main sync logic and CLI entry point
│
├── gui/                    # GUI package
│   ├── __init__.py
│   ├── main.py              # MainWindow, SyncWorker, QtReporter
│   ├── dialogs.py           # SettingsDialog with tabs
│   └── styles/             # Qt stylesheets
│       └── styles.css
│
├── assets/                 # Static assets (icons, etc.)
├── run.py                   # Unified entry point (GUI/CLI)
├── run.bat                  # Windows launcher
├── requirements.txt         # Base dependencies
└── requirements-gui.txt     # GUI dependencies (includes PySide6)
```

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `helloasso.client` | HelloAssoClient: owns the shared HTTP session and concurrency limiter, exposes API endpoints with throttling and retries. |
| `helloasso.config` | Constants, the `Settings` dataclass (tunable runtime parameters) and secret loading. |
| `helloasso.export` | CSV export of the aggregated payments. |
| `helloasso.models` | Dataclasses describing the HelloAsso API responses and the aggregated output. |
| `helloasso.reporter` | Progress reporting interface (used by both CLI and GUI). |
| `helloasso.syncer` | Main sync logic, CLI argument parsing, and orchestration. |

## Customization

Domain defaults live in [config.py](config.py) (most are also overridable on the command line):

- `ORGANIZATION_SLUG`: the slug of your HelloAsso organization.
- `FORM_CATEGORY`: the form type to process (default: `"Membership"`).
- `FORMS`: the list of forms used by `--forms all`.
- `DEFAULT_CONCURRENCY`: default number of simultaneous requests (option `--concurrency`).
- `REQUEST_DELAY`: delay between API requests (option `--request-delay`, to avoid rate limiting).
- `MAX_RETRIES`: number of attempts on network errors (option `--max-retries`).
- `RETRY_DELAY`: base delay for the retry backoff (option `--retry-delay`).

Club-specific normalization rules (e.g. phone number and parents' email formatting) live in `post_process_custom_fields` in `Syncer.py`.

## Troubleshooting

### Authentication error

Check that:

- Your credentials are correct.
- `secrets.json` is in the right folder, or the environment variables are set.

### No data retrieved

Check that:

- The form slug is correct (kebab-case).
- The organization actually has payments for that form.
- You have API access rights.

### Rate limiting issues

Lower the concurrency and space the requests out:

```bash
python Syncer.py --forms all --concurrency 2 --request-delay 1.0
```

You can also switch to sequential mode (`--sequential`) to remove parallelism entirely. The script automatically honors the `Retry-After` header on `429` responses.

## Contributing

Contributions are welcome! Open an issue or submit a pull request.

## License

This project is under the MIT license (or to be defined as needed).

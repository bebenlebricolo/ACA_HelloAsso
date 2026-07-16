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

### Fetch payments for a specific form

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26
```

### Fetch payments for several forms

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26 licence-saison-competition-25-26
```

### Fetch all known "Membership" forms

```bash
python Syncer.py --forms all
```

### Use a custom configuration file

```bash
python Syncer.py --config /path/to/my_secrets.json --forms all
```

### Change the output folder

```bash
python Syncer.py --output /path/to/output_folder --forms licence-saison-aviron-sante-25-26
```

### Dry run (test mode)

```bash
python Syncer.py --forms licence-saison-aviron-sante-25-26 --dry-run
```

### Parallelization and throttling

The script parallelizes network requests (order-detail fetches, and processing of forms among themselves). The number of simultaneous requests is bounded globally by a semaphore.

```bash
# Limit to 10 simultaneous requests
python Syncer.py --forms all --concurrency 10

# Space requests out further (throttling) to avoid being flagged
python Syncer.py --forms all --concurrency 3 --request-delay 0.5
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

The code is split into small, focused modules:

| File | Responsibility |
|------|----------------|
| `Syncer.py` | Entry point: CLI, orchestration, parsing and aggregation logic. |
| `config.py` | Constants, the `Settings` dataclass (tunable runtime parameters) and secret loading. |
| `client.py` | `HelloAssoClient`: owns the shared HTTP session and concurrency limiter, and exposes the API endpoints (auth, payments, order details) with centralized throttling and retries. |
| `export.py` | CSV export of the aggregated payments. |
| `models/` | Dataclasses describing the HelloAsso API responses and the aggregated output. |

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

# Setup Guide

## Requirements

- Python 3.12
- SQLite (bundled with Python; no separate install needed)

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `app` package in editable mode plus every development
tool (`pytest`, `mypy`, `ruff`, `black`, `pre-commit`).

Optional: install pre-commit hooks so lint/format/type checks run on every
commit automatically:

```bash
pre-commit install
```

## Configure

Copy nothing -- `config/default.yaml` already ships with safe development
defaults (a local SQLite file under `./data/`, no collectors enabled). To
override any value for your environment, either edit a copy of that file
and point `sigint` at it with `--config`, or set an environment variable
prefixed `SIGINT_` (see [`CONFIGURATION.md`](CONFIGURATION.md)).

Secrets (API keys, credentials) are **never** read from a YAML file --
only from environment variables. The foundation does not yet define any
secret-backed setting, since no collector requiring one is implemented
yet.

## Initialize the database

```bash
sigint init
```

This runs every Alembic migration up to `head`, creating the `signals`,
`weather_events`, `leads`, `audit_logs`, and `configuration` tables in the
SQLite file configured by `database.url` (default:
`sqlite:///./data/signals.db`).

## Verify the install

```bash
sigint config validate
sigint config show
sigint correlate   # should report "0 rule match(es)" on a fresh database
```

Run the test suite to confirm everything works end to end:

```bash
scripts/check.sh
```

This runs `ruff check`, `black --check`, `mypy`, and `pytest` (with
coverage) in sequence -- the same gate a CI pipeline should run.

## Running the CLI

```bash
sigint --help
sigint collect --collector ehitisregister   # run one collector by name
sigint collect --all                        # run every collector in collectors.enabled, concurrently
sigint verify signals --limit 100
sigint verify lead <uuid>
sigint correlate
sigint generate
sigint score                                # inspect stored leads' scores
sigint stats                                # counts of signals/leads/weather events
sigint export --format json
sigint pipeline --export-format csv --output leads.csv   # the whole pipeline in one command
```

No collector is enabled by default (`collectors.enabled: []` in
`config/default.yaml`), so `collect`/`pipeline` report "no collectors
enabled" until you opt one in -- see [`docs/COLLECTORS.md`](COLLECTORS.md)
for what each one requires before it can run. The real-estate listing
collectors additionally need a Playwright browser install:

```bash
playwright install chromium
```

See [`docs/DEVELOPMENT.md`](DEVELOPMENT.md) for how to add a new
collector, verifier, rule, or CLI command, and
[`docs/TESTING.md`](TESTING.md) for the test suite layout.

# Estonia Signal Intelligence Platform

A platform that collects **publicly available signals** indicating that a
residential property in Estonia may need one of four services:

- Roofing
- Kitchen remodeling
- Bathroom remodeling
- Solar installation

The platform does **not** collect homeowners, does **not** identify
individuals, and generates a Lead only after **multiple verified public
signals** together support that conclusion.

```
Public Data -> Signals -> Signal Verification -> Signal Storage ->
Correlation -> Lead Generation -> Lead Verification -> Lead Scoring -> Export
```

Signals are collected. Leads are generated. These are different concepts,
kept in separate tables, separate domain models, and separate scoring
systems throughout the codebase.

## Status

Clean Architecture foundation, a production collector layer (Ehitisregister,
Ilmateenistus, and three real-estate listing sites -- each gated behind
explicit configuration, disabled by default), verification (structural
checks plus duplicate detection), independent Signal/Lead scoring, CSV/Excel
export, and a full-pipeline CLI. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the layering and design
decisions, and [`docs/COLLECTORS.md`](docs/COLLECTORS.md) for exactly what
each collector does and does not do.

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium   # only needed for the real-estate listing collectors
```

See [`docs/SETUP.md`](docs/SETUP.md) for full setup instructions.

## Configuration

Everything configurable lives in `config/default.yaml`, overridable per
deployment by `SIGINT_`-prefixed environment variables (never commit a
secret to the YAML file). See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
for the complete reference -- database, logging, retry, verification,
duplicate detection, concurrency, caching, collectors, scoring, and export
settings.

```bash
sigint config show                              # print the fully resolved configuration
sigint config validate --config config/default.yaml
```

## CLI usage

```bash
sigint init                              # apply database migrations
sigint collect --collector ehitisregister   # run one collector
sigint collect --all                        # run every enabled collector, concurrently
sigint verify signals --limit 100           # verify pending signals
sigint verify lead <uuid>                   # verify a single lead
sigint correlate                            # find rule matches (no persistence)
sigint generate                             # correlate + persist leads
sigint score                                # inspect stored leads' Intent/Confidence/Priority
sigint stats                                # counts of signals/leads/weather events
sigint export --format xlsx --output leads.xlsx
sigint pipeline --export-format csv --output leads.csv   # run the whole pipeline end to end
```

Every command supports `--help`, validates its inputs, exits non-zero on
failure, and uses structured (Loguru) logging throughout. `collect --all`
and `pipeline` show Rich progress bars for each stage; `collect --all`'s
concurrency is controlled by `concurrency.max_concurrent_collectors`.

## Project structure

See [`docs/FOLDER_OVERVIEW.md`](docs/FOLDER_OVERVIEW.md) for the full
layout. In short: `app/domain` (entities), `app/application` (use cases and
interfaces), `app/collectors` / `app/verification` / `app/correlation` /
`app/rule_engine` / `app/lead_generation` / `app/repositories` /
`app/database` / `app/config` / `app/logging` (infrastructure),
`app/cli` (presentation), `app/core` (dependency-free primitives + the DI
container).

## Development workflow

```bash
source .venv/bin/activate
scripts/check.sh   # ruff + black --check + mypy + pytest, must be clean before a commit
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for adding a new collector,
verifier, or rule, and [`docs/TESTING.md`](docs/TESTING.md) for the test
layout and how to run a subset.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) -- Clean Architecture layering, data flow, key design decisions
- [`docs/SETUP.md`](docs/SETUP.md) -- installing and running the project
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) -- lint/type-check/test workflow, adding a new collector or rule
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) -- every configuration surface (YAML, env vars, rule files)
- [`docs/COLLECTORS.md`](docs/COLLECTORS.md) -- what each collector reads, requires, and does not fabricate
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) -- running the platform as a long-lived service
- [`docs/TESTING.md`](docs/TESTING.md) -- test layout, fixtures/fakes, coverage
- [`docs/FOLDER_OVERVIEW.md`](docs/FOLDER_OVERVIEW.md) -- what lives where and why

## Troubleshooting

- **`ConfigurationError: Invalid configuration after merging ...`** -- a
  YAML value or environment override failed Pydantic validation; the error
  message names the offending field. Run `sigint config validate` to
  reproduce it in isolation.
- **A collector raises `CollectorError` immediately** -- most collectors
  validate their own required settings (e.g. `ilmateenistus.xml_url`,
  `kv_ee.search_paths`) before making any request, and refuse to guess a
  value. See [`docs/COLLECTORS.md`](docs/COLLECTORS.md) for what each one
  needs.
- **`sqlite3.OperationalError: database is locked`** under concurrent
  writes -- raise `database.busy_timeout_seconds`; SQLite is single-writer
  by design, and the busy timeout only changes how long a write waits
  before giving up, not whether contention can happen at all.
- **A CLI command hangs** -- collectors that reach a real network (with
  caching disabled) can be slow; check `logging.level: DEBUG` for
  request-level detail, and confirm `retry.timeout_seconds` is set to a
  sane budget for your environment.

## Non-negotiable rules

This project never fabricates data, homeowners, identities, addresses,
coordinates, property ownership, or API responses. When information
can't be verified from a real public source, the correct behavior is to
stop and explain the limitation -- not to guess. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#non-negotiable-rules) for
how this is enforced in the code itself (domain validation, verification
gates, and collectors that raise rather than guess a missing setting).

# Deployment Guide

The platform ships as a Python package with a single CLI entry point
(`sigint`) and a SQLite database by default. There is no bundled web
server, container image, or orchestration manifest -- this guide covers
running it as a scheduled or long-lived process on a single host, and
what to change to point it at a shared database instead of a local file.

## Runtime requirements

- Python 3.12.
- For the real-estate listing collectors (`kv_ee`, `kinnisvara24`,
  `city24`): a Playwright-managed Chromium install (`playwright install
  chromium`). Not needed if those collectors stay disabled.
- Writable disk for the SQLite file (`database.url`) and, if configured,
  the rotating log file (`logging.log_file`) and export output directory
  (`export.output_directory`).

## Installing for production

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install .          # no [dev] extra -- skips pytest/mypy/ruff/black/pre-commit
playwright install chromium   # only if a real-estate collector is enabled
```

## Configuration for a deployment

- Copy `config/default.yaml`, adjust it for the environment (which
  collectors are enabled, database URL, logging), and point `sigint` at
  it via `--config` on commands that accept it, or set
  `SIGINT_RULES__DIRECTORY`/other `SIGINT_*` variables to override
  individual fields without a separate file.
- **Never** put a secret in the YAML file. There is no secret-backed
  setting today (no collector requires one); if one is added later, it
  must be read exclusively from an environment variable (see
  [`CONFIGURATION.md`](CONFIGURATION.md#secrets)).
- Set `environment: production` and `logging.level: INFO` (or `WARNING`)
  -- `DEBUG` logs request URLs and internal timing detail not meant for a
  production log stream.
- Set `logging.json_logs: true` if log entries feed a log aggregator that
  expects structured JSON rather than the human-readable default format.

## Database

SQLite (the default) is single-writer: concurrent collectors and CLI
invocations against the same file serialize their writes, and
`database.busy_timeout_seconds` controls how long a write waits on
another connection's lock before raising `database is locked` (raise it
if a deployment runs many concurrent `sigint` invocations against one
file). For a shared/multi-host deployment, point `database.url` at a
PostgreSQL instance instead -- the repository layer is written against
SQLAlchemy Core/ORM with no SQLite-specific SQL, so this is a
configuration change, not a code change; `busy_timeout_seconds` and the
SQLite-only `connect_args` in `app.database.session.create_sqlalchemy_engine`
are simply not applied for a non-SQLite URL.

Apply migrations before the first run and after every upgrade:

```bash
sigint init   # runs every Alembic migration up to head
```

## Running collection on a schedule

There is no built-in scheduler. Run `sigint collect --all` (or
`sigint pipeline`) from cron, systemd timers, or an external scheduler.
Example systemd timer + service pair:

```ini
# /etc/systemd/system/sigint-pipeline.service
[Unit]
Description=Signal Intelligence Platform pipeline run

[Service]
Type=oneshot
User=sigint
WorkingDirectory=/opt/sigint
EnvironmentFile=/opt/sigint/sigint.env
ExecStart=/opt/sigint/.venv/bin/sigint pipeline
```

```ini
# /etc/systemd/system/sigint-pipeline.timer
[Unit]
Description=Run the Signal Intelligence Platform pipeline hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

`sigint.env` holds `SIGINT_*` overrides (never secrets committed to the
repo); `sigint pipeline`'s exit code is non-zero on a real failure, so a
failed run surfaces in `systemctl status`/`journalctl` the normal way.

## Concurrency and rate limiting in production

- `concurrency.max_concurrent_collectors` bounds how many collectors
  `collect --all`/`pipeline` run at once -- keep this low (2-3) against
  sites that rate-limit or that this platform should be polite to
  regardless (see each collector's `request_delay_seconds` in
  [`COLLECTORS.md`](COLLECTORS.md)).
- Response caching (`collectors.<name>.cache_enabled`) only helps *within*
  a single `collect()` call -- a fresh `HttpClient` (and therefore a fresh,
  empty cache) is constructed every time a collector runs, so it does
  **not** carry over between separate `sigint collect`/`pipeline`
  invocations, scheduled or manual. It is only worth enabling for a
  collector that issues the same request more than once per run (e.g. a
  paginated fetch); it does not replace `request_delay_seconds`, which
  still governs the pace of every request regardless of caching.

## Logs and exports on disk

- `logging.log_file` rotates per `logging.rotation`/`logging.retention` --
  point it at a path your log-shipping agent (if any) already watches, or
  leave it `null` to log to stderr only under a process supervisor that
  captures stdout/stderr (systemd's journal does this automatically).
- `export.output_directory` is only a default for `sigint export`'s
  `--output`; nothing writes there automatically unless a scheduled job
  passes `--output` explicitly.

## Health checks

There is no HTTP health endpoint (no web server ships). A reasonable
external check is `sigint config validate` (confirms configuration is
loadable) followed by `sigint stats` (confirms the database is reachable
and queryable) -- both exit `0` on success and are cheap enough to run on
a monitoring interval. `sigint health` goes one step further and reports
each collector's last run status, duration, item count, and consecutive-
failure streak (read from the audit log; triggers no collection itself)
-- a good addition to an operator dashboard or a scheduled alert on
`consecutive_failures` crossing a threshold.

## Removing data from a retired or misconfigured source

`sigint purge signals --source <name>` / `sigint purge weather-events
--source <name>` delete every Signal/WeatherEvent from that source,
optionally only those older than `--before`. Both default to a dry-run
preview; pass `--yes` to actually delete, and every real deletion is
audit logged (`DATA_PURGED`). This replaces manually running `DELETE`
against the SQLite database, which this project's operator docs
otherwise never recommend. See
[`COLLECTORS.md#operator-tooling`](COLLECTORS.md#operator-tooling).

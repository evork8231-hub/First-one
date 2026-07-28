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
loadable) followed by `sigint db check` (confirms the database is
reachable and, for SQLite, structurally intact via `PRAGMA
integrity_check`) and `sigint db migration-status` (confirms the schema is
at head, listing any pending migrations by revision id otherwise) -- all
three exit `0` on success and are cheap enough to run on a monitoring
interval. `sigint health` goes one step further and reports each
collector's last run status, duration, item count, and consecutive-failure
streak (read from the audit log; triggers no collection itself) -- a good
addition to an operator dashboard or a scheduled alert on
`consecutive_failures` crossing a threshold. `sigint collector-status`
reports each registered collector's verification lifecycle state
(`discovered`/`tested`/`verified`) and whether it is currently enabled and
actually running, independent of any recent collection activity.

## Removing data from a retired or misconfigured source

`sigint purge signals --source <name>` / `sigint purge weather-events
--source <name>` delete every Signal/WeatherEvent from that source,
optionally only those older than `--before`. Both default to a dry-run
preview; pass `--yes` to actually delete, and every real deletion is
audit logged (`DATA_PURGED`). Purging Signals refuses the whole
operation -- deleting nothing -- if any of them are still cited by an
existing Lead's `supporting_signal_ids`; resolve or reject those leads
first (`sigint verify lead <id>`) if the purge needs to proceed. This
replaces manually running `DELETE` against the SQLite database, which
this project's operator docs otherwise never recommend. See
[`COLLECTORS.md#operator-tooling`](COLLECTORS.md#operator-tooling).

## Backing up the SQLite database before migrations

This platform ships no automated backup command; back up the database
file at the OS level before running `sigint init` against an existing
database (every application of new Alembic migrations), and on whatever
schedule the deployment's data-retention policy requires otherwise.

The default `database.url` (`sqlite:///./data/signals.db`) is a plain
file at `data/signals.db` relative to the working directory `sigint` is
run from -- confirm the actual path for a given deployment with:

```bash
sigint config show
```

With no writer active (stop the timer/cron job first, or run this
between scheduled invocations -- SQLite's single-writer lock means a
copy taken mid-write can capture a partial transaction), take a
consistent snapshot using SQLite's own backup command, which safely
copies a live database file including its WAL/journal state:

```bash
sqlite3 data/signals.db ".backup data/signals.db.$(date +%Y%m%dT%H%M%S).bak"
```

If `sqlite3` is not installed on the host, a plain filesystem copy is an
acceptable fallback **only** while no process holds the database open:

```bash
cp data/signals.db "data/signals.db.$(date +%Y%m%dT%H%M%S).bak"
```

Keep the backup outside `data/` (or otherwise excluded from whatever
this deployment's disk-space and log-retention tooling manages) so it is
not itself picked up and deleted by mistake.

## Restoring from a backup

1. Stop every process that could open the database (`sigint` scheduled
   runs, any manual invocation in progress).
2. Move the current (broken/corrupted) database file aside rather than
   deleting it, in case it turns out to still be needed for diagnosis:

   ```bash
   mv data/signals.db data/signals.db.broken.$(date +%Y%m%dT%H%M%S)
   ```

3. Copy the chosen backup file into place:

   ```bash
   cp data/signals.db.<timestamp>.bak data/signals.db
   ```

4. Confirm the restored database is reachable and its migration state is
   current before resuming scheduled runs:

   ```bash
   sigint stats
   sigint init   # safe to re-run -- Alembic only applies migrations not yet recorded
   ```

## Rollback incident procedure

Use this when a specific collector run needs to be undone -- e.g. a
collector ingested malformed or duplicate data on its last run, or a
misconfigured source needs to be reversed before it corrupts downstream
Leads.

1. Identify the affected collector name (matches the `collector` field
   already written to its `COLLECTOR_RUN_COMPLETED` audit entries, e.g.
   `ehitisregister`, `ilmateenistus`).
2. Preview the rollback first (dry run is the default -- nothing is
   deleted without `--yes`):

   ```bash
   sigint rollback signals <collector>
   # or, for a weather collector:
   sigint rollback weather-events <collector>
   ```

   This reports the run's `execution_id` and how many records would be
   deleted.
3. Review the preview. If it looks correct, confirm the actual rollback:

   ```bash
   sigint rollback signals <collector> --yes
   ```

   The deletion and its `COLLECTOR_RUN_ROLLED_BACK` audit entry commit
   atomically -- either both happen or neither does, so the same run can
   never be rolled back twice and the audit trail always reflects what
   was actually deleted.
4. If the command instead reports that the rollback was blocked because
   a Signal is still cited by an existing Lead, resolve those Leads
   (`sigint verify lead <id>`, or otherwise reject/close them per the
   deployment's operator process) before retrying the rollback -- this
   is a fail-closed refusal, not a transient error.
5. If the command reports a database error (locked, unreachable, disk
   full), the rollback did not complete -- fix the underlying database
   issue and retry; the atomic write guarantees no partial rollback was
   left behind.
6. After a successful rollback, confirm the platform's state with:

   ```bash
   sigint stats
   sigint health
   ```

## Recommended staging validation steps

Before promoting a configuration or code change to production, run
against a staging environment pointed at its own database
(`database.url` distinct from production). See
[`STAGING_VALIDATION.md`](STAGING_VALIDATION.md) for the full checklist
(fresh install, migration verification, backup/restore drill, first
collector activation, lead review) with expected outcomes spelled out for
each step; the summary below is the same flow condensed:

1. Validate configuration loads and is internally consistent:

   ```bash
   sigint config validate
   ```

2. Apply migrations to a fresh or already-migrated staging database:

   ```bash
   sigint init
   ```

3. Run a real collection against staging (respects each collector's
   normal rate limiting and configuration):

   ```bash
   sigint collect --all
   # or, to exercise the full path through to Leads:
   sigint pipeline
   ```

4. Confirm collectors ran cleanly and inspect record counts:

   ```bash
   sigint health
   sigint stats
   ```

5. Spot-check verification and export on the data just collected:

   ```bash
   sigint verify signals
   sigint export --format csv
   ```

6. Exercise the destructive paths against staging data specifically
   (never run these against production without a fresh backup first --
   see above): a dry-run preview of both `sigint purge` and `sigint
   rollback` against a staging collector, confirming the reported counts
   match expectations before ever passing `--yes`.
7. Only once staging looks correct, repeat the relevant subset of these
   steps (starting with a backup, per above) against production.

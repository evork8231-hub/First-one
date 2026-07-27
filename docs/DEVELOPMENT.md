# Development Guide

## Workflow

```bash
source .venv/bin/activate
scripts/check.sh        # ruff + black --check + mypy + pytest, must be clean before a commit
```

Individually:

```bash
ruff check app tests alembic       # lint
ruff check --fix app tests alembic # lint, autofixing what's safe
black app tests alembic            # format
mypy app                           # strict type check (app/ only; tests are intentionally excluded, see pyproject.toml)
pytest                             # unit tests + coverage report
pytest -k test_name                # run a single test
```

`mypy` runs in `strict = True` mode. Every public function and class in
`app/` must be fully type-hinted -- this is enforced, not a suggestion.

## Adding a new signal type

1. Add the member to `app.domain.enums.SignalType`.
2. If it maps to a new `ServiceCategory`, add that too (rare -- the four
   categories are fixed by the mission).
3. Reference the new type from a `SignalCondition` in a rule YAML file
   under `config/rules/`. No other code changes are required for the
   rule engine to start matching on it.

## Adding a new collector

1. Create `app/collectors/<source_name>_collector.py` with a class
   extending `app.collectors.base.BaseCollector`.
2. Implement `async def collect(self) -> list[Signal]`, using
   `self._with_retry(...)` for any individual network call.
3. **Do not fabricate data.** Every `Signal` the collector returns must be
   built from data actually retrieved from the documented, real source.
   If the source doesn't support something you need, stop and document
   the limitation -- do not guess a response shape.
4. Register the collector in `app.core.container.Container` (add a
   provider) and add its name to `collectors.enabled` in
   `config/default.yaml` (or an environment override) to turn it on.
5. Add unit tests using a fake HTTP layer (e.g. `httpx.MockTransport` or a
   recorded fixture) -- never test against the live source in CI.
6. If the collector reads over HTTP via `app.collectors.http_client.HttpClient`,
   response caching is available for free -- add `cache_enabled` /
   `cache_ttl_seconds` fields to its config model (see `EhitisregisterConfig`)
   and leave `cache_enabled` defaulting to `false` unless the source's data
   changes slower than a typical run cadence.
7. See [`COLLECTORS.md`](COLLECTORS.md) for the narrative guide this list
   feeds into -- add a section there for the new collector, following the
   existing format (uses / required settings / known limitations / what
   it produces).
8. Before enabling any collector in production, run
   `sigint verify-collector <name>` (see
   [`COLLECTORS.md#operator-tooling`](COLLECTORS.md#operator-tooling)) --
   it executes the collector for real (without persisting anything) and
   prints a READY/NOT READY report. For a JSON-based collector, pair it
   with `sigint discover-fields`; for a browser-based listing collector,
   `sigint discover-selectors`; for an XML feed, `sigint inspect-xml`.
   These tools only suggest -- they never write configuration for you.

## Adding a new verifier

Implement `app.application.interfaces.verifier.SignalVerifier` or
`LeadVerifier`, register it with the DI container (`signal_verifiers` /
`lead_verifiers` providers use `providers.List`, so add another provider
to that list), and add tests. `VerificationService` requires every
registered verifier to return `VERIFIED` for an entity to pass -- any
`REJECTED` short-circuits the result.

## Adding a new rule

Add a YAML entry under `config/rules/` (see
[`CONFIGURATION.md`](CONFIGURATION.md#rule-files) for the schema). No
Python change is needed. `RuleLoader` caches the parsed rules after the
first successful `load_all()`/`get_active_rules()` call within a process
(see "Caching" below) -- restart the process (or call `RuleLoader.reload()`
directly) to pick up an edited file; the foundation does not implement
file-watching.

## Caching

Three call sites cache in-process, all opt-out or naturally self-limiting
-- see `docs/ARCHITECTURE.md#performance-and-reliability` for the full
rationale:

- `app.core.cache.TTLCache` is the shared primitive (`get`/`set`/`invalidate`,
  with hit/miss counters for logging). It is not thread-safe by design and
  must never be pointed at mutable business data (Signals, Leads).
- `app.collectors.http_client.HttpClient` caches GET responses when a
  collector's config sets `cache_enabled: true` (default `false`).
- `app.rule_engine.loader.RuleLoader` caches parsed rules by default
  (`cache_enabled=True`); pass `cache_enabled=False` or call `reload()` to
  bypass it.
- `app.config.loader.load_settings` caches the resolved `AppSettings` per
  `(config_path, current SIGINT_* environment)` -- pass `use_cache=False`
  to force a fresh read, or call `clear_settings_cache()` (used by
  `tests/conftest.py`'s autouse fixture to keep the test suite hermetic).

## Adding a new CLI command

1. Add `app/cli/commands/<name>_cmd.py`, resolving only DI-container
   services (`ctx.obj`) -- no business logic in the command itself, per
   `docs/ARCHITECTURE.md`'s presentation-layer rule.
2. Validate inputs explicitly and exit with code `2` for a usage error
   (bad flag combination, invalid value) versus `1` for a runtime failure
   (e.g. a `CollectorError`/`ExportError` raised deeper in the stack) --
   see `app/cli/commands/collect_cmd.py` / `export_cmd.py` for the pattern.
3. Wrap any operation with real latency in a `rich.progress.Progress` --
   a `SpinnerColumn` for a single indivisible call, a `BarColumn` when
   there's a genuine per-item count to advance through (see
   `verify_cmd.verify_signals` / `pipeline_cmd.pipeline`). Progress bars
   render to the same Rich `Console`, kept separate from Loguru's own
   stderr sink, so the two never interleave mid-line.
4. Register the command in `app/cli/main.py`.
5. Add tests in `tests/cli/test_cli.py` using `typer.testing.CliRunner`,
   covering at least: `--help` doesn't crash, a validation error exits
   `2`, and the happy path exits `0` against an empty/fresh SQLite database.

## Repository backends

Every repository has a SQLite implementation
(`app.repositories.sqlite.*`) and an in-memory implementation
(`app.repositories.in_memory.*`), both satisfying the same interface in
`app.application.interfaces.repositories`. Tests should default to the
in-memory implementation for speed and to the SQLite implementation only
when specifically testing persistence/query behavior (see
`tests/repositories/`).

## Database migrations

Schema changes go through Alembic, never `Base.metadata.create_all()` in
production code (that call only appears in test fixtures, see
`tests/conftest.py`).

```bash
alembic revision -m "add X column to signals"
# edit the generated file under alembic/versions/
alembic upgrade head
```

`alembic/env.py` resolves the database URL the same way the application
does (`app.config.loader.load_settings()`), so migrations always target
whatever `SIGINT_DATABASE__URL` (or `config/default.yaml`) currently
points at.

## Commit hygiene

- Keep commits scoped to one phase/concern.
- Run `scripts/check.sh` before every commit.
- Every new module needs tests (see `tests/` for the existing layout,
  mirroring `app/`).
- Every public function/class needs type hints and a docstring explaining
  *why*, not *what* (the code already says what).

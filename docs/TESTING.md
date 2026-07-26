# Testing Guide

## Running tests

```bash
pytest                      # full suite + coverage report (see pyproject.toml addopts)
pytest -k test_name          # a single test by (partial) name
pytest tests/verification    # a single directory
pytest -m unit                # only tests marked @pytest.mark.unit
pytest -m integration         # only tests marked @pytest.mark.integration (touch DB/filesystem)
```

`scripts/check.sh` runs `ruff check`, `black --check`, `mypy`, then
`pytest` in sequence -- the same gate expected before every commit.

## Ground rules

- **No live network, no live browser.** Every collector test uses
  `httpx.MockTransport` (HTTP collectors) or a fake `BrowserClient`
  (Playwright-based collectors) -- never a real request to
  `andmed.eesti.ee`, `ilmateenistus.ee`, `kv.ee`, etc.
- **Deterministic.** No test depends on wall-clock time, network latency,
  or external service state. Where a test needs to simulate elapsed time
  (retry backoff, cache TTL expiry), it injects a fake clock rather than
  sleeping for real (see `tests/core/test_cache.py::test_entry_expires_after_ttl`).
- **In-memory repositories by default.** Use
  `app.repositories.in_memory.*` for application/domain-level tests; use
  the SQLite repositories (`tests/repositories/test_sqlite_repositories.py`,
  `tests/database/test_session.py`) only when the SQL itself is what's
  under test (filters translating to `WHERE` clauses, `COUNT(*)`
  behavior, the SQLite `busy_timeout` connect arg).

## Layout

Mirrors `app/`:

| Directory | Covers |
|---|---|
| `tests/domain/` | Entity/value-object validation (Signal, Lead, Rule, Coordinates, Address, ...) |
| `tests/application/` | Services: SignalService, VerificationService, CorrelationService, LeadGenerationService, ExportService, WeatherEventService, and `test_pipeline.py` (a full in-memory Collect->Verify->Correlate->Generate->Verify->Export run) |
| `tests/collectors/` | Ehitisregister, Ilmateenistus, real-estate collectors, and shared utilities (JSON-LD, XML parsing, phrase matching, rate limiting, `HttpClient` incl. retry and caching) |
| `tests/verification/` | `StructuralSignalVerifier`, `StructuralLeadVerifier`, `DuplicateDetector`, `DuplicateSignalVerifier` |
| `tests/correlation/`, `tests/rule_engine/`, `tests/lead_generation/` | Clustering, rule matching/loading (incl. its cache), scoring |
| `tests/repositories/` | Both backends (in-memory + SQLite) against the same interface, including `count()`/`add_many` |
| `tests/database/` | Engine/session-factory construction (busy timeout, commit/rollback semantics) |
| `tests/config/` | YAML + environment merging, precedence, and the settings cache |
| `tests/core/` | Retry policy/backoff, exception hierarchy, the DI container, `TTLCache` |
| `tests/cli/` | Every `sigint` subcommand via `typer.testing.CliRunner` |
| `tests/fixtures/` | `factories.py` (valid entity builders, e.g. `make_signal`, `make_lead`) and `fakes.py` (test-double collectors/verifiers/generators satisfying the real interfaces) |

## Fixtures and fakes

- `tests/fixtures/factories.py` builds valid domain entities with sensible
  overridable defaults (`make_signal(county="Tartu")`, etc.) -- prefer
  these over constructing `Signal(...)`/`Lead(...)` by hand so tests don't
  duplicate every required field.
- `tests/fixtures/fakes.py` provides `FakeCollector`, `FakeWeatherCollector`,
  `FakeSignalVerifier`, `FakeLeadVerifier`, `FakeLeadGenerator` -- minimal
  implementations of the real interfaces, for tests that need a collector
  or verifier with a scripted, deterministic outcome rather than a mock.
- `tests/conftest.py` provides `sqlite_engine`/`sqlite_session_factory`
  (an in-memory SQLite database, one schema per test) and an autouse
  fixture that clears `app.config.loader`'s settings cache before and
  after every test, so no test can leak a cached `AppSettings` into
  another.

## Testing a new collector

Follow `tests/collectors/test_ehitisregister_collector.py` or
`test_real_estate_collectors.py` as a template:

1. Build an `httpx.MockTransport` (or fake `BrowserClient`) handler that
   returns fixture data shaped like the real source's actual response.
2. Assert the resulting `Signal`/`WeatherEvent` fields match the fixture
   exactly -- no field should differ from what was "returned."
3. Add a case for a malformed/incomplete response and assert the
   collector raises `CollectorError` rather than filling in a guess.
4. Add a case for a transient failure (500 response, transport error) and
   assert it retries (see `_fast_retry_policy()`-style helpers that use a
   near-zero backoff so the test stays fast) and eventually raises
   `CollectorUnavailableError` if retries are exhausted.

## Testing a new CLI command

See [`DEVELOPMENT.md#adding-a-new-cli-command`](DEVELOPMENT.md#adding-a-new-cli-command).
Use `runner.invoke(app, [...])` and assert on `result.exit_code` and
`result.output`; set `SIGINT_DATABASE__URL=sqlite:///:memory:` (or a
`tmp_path` file) via `monkeypatch.setenv` so tests never touch a real
database file, and `SIGINT_RULES__DIRECTORY` to an empty `tmp_path` so a
test never depends on the shipped `config/rules/*.yaml` files.

## Coverage

`pytest`'s default run (`addopts` in `pyproject.toml`) always reports
coverage (`--cov=app --cov-report=term-missing`); `app/cli/*` is excluded
from the coverage source list (see `[tool.coverage.run]`) since CLI
commands are exercised through `tests/cli/test_cli.py`'s
`CliRunner`-based black-box tests rather than line-coverage instrumentation
of Typer's own plumbing. There is no hard coverage gate enforced in CI
today; `scripts/check.sh` failing on `pytest` (not on a coverage
threshold) is what blocks a commit.

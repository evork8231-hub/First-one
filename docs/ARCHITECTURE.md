# Architecture

## Layering

Strict Clean Architecture. Dependencies point inward only:

```
Presentation (app/cli)
       v
Application (app/application)
       v
Domain (app/domain)
       ^
Infrastructure (app/database, app/repositories, app/collectors,
                 app/verification, app/correlation, app/rule_engine,
                 app/lead_generation, app/config, app/logging)
```

- **Domain** (`app/domain`) has zero dependencies on anything else in the
  project. It never imports SQLAlchemy, Playwright, BeautifulSoup, httpx,
  Typer, or any infrastructure package. It only depends on `app.core` and
  `app.utils`, which are themselves dependency-free (no imports from any
  other `app.*` package).
- **Application** (`app/application`) depends only on `app.domain` and on
  the abstract interfaces it declares itself
  (`app/application/interfaces/*`). It never imports a concrete
  infrastructure class.
- **Infrastructure** packages (`app/collectors`, `app/verification`,
  `app/correlation`, `app/rule_engine`, `app/lead_generation`,
  `app/repositories`, `app/database`, `app/config`, `app/logging`) provide
  concrete implementations of those interfaces. They depend on
  `app.domain` and `app.application.interfaces`, never the reverse.
- **`app/core/container.py`** is the composition root: the one module
  permitted to import from every layer, wiring interfaces to
  implementations with `dependency-injector`.
- **Presentation** (`app/cli`) depends only on the DI container and the
  application services it resolves. No business logic lives here.

This is enforced by convention and code review today; a future phase can
add `import-linter` or a ruff/flake8 architecture-boundary plugin to
enforce it automatically in CI.

## The pipeline

```
Public Data -> Signals -> Signal Verification -> Signal Storage ->
Correlation -> Lead Generation -> Lead Verification -> Lead Scoring -> Export
```

- **Signals** (`app.domain.signal.Signal`) are facts observed at a public
  source. A `Collector` (`app.application.interfaces.collector.CollectorInterface`)
  reads exactly one public source and returns Signals -- nothing else.
  Collectors never generate, verify, or score Leads. Five collectors ship
  (`app.collectors.ehitisregister_collector`, `ilmateenistus_collector`,
  and three real-estate listing collectors under `app.collectors.real_estate`)
  but none run unless explicitly named in `collectors.enabled` -- see
  [`docs/COLLECTORS.md`](COLLECTORS.md) for what each one does and does not
  fabricate.
- **Verification** (`app.application.interfaces.verifier`) advances a
  Signal or Lead from `UNVERIFIED` to `VERIFIED` or `REJECTED`.
  `StructuralSignalVerifier` checks country/county/municipality/postal
  code/coordinate-bounds consistency; `DuplicateSignalVerifier`
  (`app.verification.duplicate_detector`) additionally checks a signal
  against others in the same county/municipality -- by building
  identifier, phone number, coordinate proximity (haversine distance),
  then RapidFuzz fuzzy address matching -- producing a
  Duplicate/Possible-Duplicate/Unique result with every threshold
  configurable via `VerificationConfig.duplicate_detection`. A verifier
  that cross-references a real external registry beyond the collector's
  own source is still a future phase, since fabricating that behavior now
  would violate the "never invent API responses" rule.
- **Correlation** (`app.correlation.engine.CorrelationEngine`) consumes
  only `VERIFIED` signals and groups them into `SignalCluster`s by shared
  location identity: building registry code first, then street + house
  number, falling back to county + municipality. It never sees
  unverified signals and raises if handed one.
- **Rule Engine** (`app.rule_engine`) evaluates data-driven
  `app.domain.rule.Rule` definitions (loaded from
  `config/rules/*.yaml` by `RuleLoader`) against each `SignalCluster`,
  producing `RuleMatch` objects. Rules are never hardcoded in Python.
- **Lead Generation** (`app.lead_generation.generator.LeadGenerator`)
  turns `RuleMatch`es into `Lead` entities. **Weather signals are
  deliberately excluded from `Lead.supporting_signal_ids`** -- per the
  mission rule "weather never becomes a lead, weather only affects
  confidence," a matched weather signal only scales
  `estimated_confidence` / `intent_score` via a configurable boost
  factor; it never counts toward the required minimum of independent
  supporting evidence.
- **Scoring** (`app.lead_generation.scoring`) keeps two systems
  independent: `SignalConfidenceAggregator` combines Signals' own
  `confidence` values into a Lead's `estimated_confidence`;
  `LeadScorer`/`PriorityCalculator` combine matched Rules' `base_confidence`
  and `weight` into `intent_score` and `priority`. Neither derives from
  the other.
- **Export** (`app.application.services.export_service.ExportService`)
  serializes already-persisted, already-verified Leads to JSON, CSV, or
  Excel (`.xlsx`, via openpyxl -- styled/frozen header row, autofilter,
  auto-sized columns, native numeric/date cell types, all controlled by
  `ExcelExportConfig`). Every format is implemented fully (not a
  placeholder) because export only serializes existing data -- no
  external collection, no fabrication risk. Every format enforces
  `VerificationStatus.VERIFIED` unconditionally; raw Signals are never
  exported, only a lead's `Source` column (the distinct collector sources
  behind its supporting signals).

## Domain model summary

| Model | Purpose |
|---|---|
| `Signal` | A single verifiable public fact. Never a lead. |
| `WeatherEvent` | A severe weather occurrence, stored independently. Also bridged into a `SignalType.WEATHER_EVENT` Signal by `WeatherSignalBridgeService` (timestamped at collection time, not the forecast period, to satisfy `Signal`'s future-timestamp rejection) so a `weather_event` rule condition can be satisfied by real data -- weather still never independently produces a Lead; see `MIN_SUPPORTING_SIGNALS`/`LeadGenerator` below. |
| `Rule` / `SignalCondition` | A data-driven definition of which signal types (and how many, how recent, how confident) justify a Lead. |
| `Lead` | A generated opportunity, always citing >= 2 supporting Signal IDs and a human-readable `reasoning` string. |
| `AuditLogEntry` | An immutable record of a noteworthy pipeline event (collector run, verification decision, lead generated, etc.). |
| `ConfigurationEntry` | A runtime-adjustable key/value setting, persisted separately from the file-based `AppSettings`. |

Every entity is a frozen (`ConfigDict(frozen=True)`) Pydantic v2 model;
state transitions (e.g. verification) return a new instance via
`with_verification(...)` rather than mutating in place.

## Key design decisions

- **Repository pattern, two backends.** Every repository is declared as
  an `abc.ABC` in `app.application.interfaces.repositories` and has both
  a SQLite/SQLAlchemy implementation (`app.repositories.sqlite`) and an
  in-memory implementation (`app.repositories.in_memory`) used by tests.
  Swapping backends is a one-line DI container override.
- **SQLite datetime handling.** SQLAlchemy's `DateTime(timezone=True)`
  does not actually preserve `tzinfo` on SQLite (SQLite has no native
  timezone-aware column type). `app.database.column_types.to_storage_utc`
  /`assume_utc` normalize every timestamp to UTC before writing and
  reattach UTC on read, so the domain layer's "timestamps must be
  timezone-aware" invariant survives a round trip through SQLite and
  remains correct if the deployment later migrates to PostgreSQL (which
  *does* preserve the offset natively -- the same helpers are a no-op
  there).
- **Async only where I/O happens.** `CollectorInterface.collect()` and
  `SignalVerifier.verify()` / `LeadVerifier.verify()` are `async` because
  real implementations will call httpx/Playwright or an external
  registry. Everything downstream (correlation, rule evaluation, lead
  generation, repositories) is synchronous, since it only operates on
  already-fetched in-memory data or a local database -- adding `async`
  there would be complexity without benefit.
- **Retry is a zero-argument wrapper.** `app.core.retry.retry` /
  `retry_async` take a zero-argument callable rather than
  `(*args, **kwargs)` passthrough. Typing `*args: P.args` /
  `**kwargs: P.kwargs` together with additional keyword-only configuration
  parameters (`policy`, `retry_on`, `on_retry`) is not expressible with
  `ParamSpec` -- callers wrap the operation in a closure instead
  (`app.collectors.base.BaseCollector._with_retry` does exactly this).
- **Rules are configuration, not code.** `app.rule_engine.loader.RuleLoader`
  parses every `*.yaml` file in `config/rules/` into `Rule` models. Adding
  a new rule -- or a new signal-type combination for an existing lead
  type -- requires no Python change.
- **Every repository method literally named `list` was renamed to
  `list_all`.** A method named `list` inside a class that also type-hints
  `list[X]` elsewhere in that class shadows the builtin generic for mypy
  (a real, reproducible mypy quirk, not a style preference), breaking
  every later `list[X]` annotation in that class. Renaming avoids the
  landmine entirely rather than suppressing the error.

## Performance and reliability

- **Caching is opt-in and process-local, never applied to mutable business
  data.** `app.core.cache.TTLCache` backs three call sites: HTTP GET
  responses in `app.collectors.http_client.HttpClient` (off by default,
  per-collector `cache_enabled`/`cache_ttl_seconds`), `app.rule_engine.loader.RuleLoader`
  (rule files are static for a process's lifetime, cached after the first
  successful parse; `reload()` bypasses it), and `app.config.loader.load_settings`
  (cached per config path + the current `SIGINT_*` environment snapshot,
  so a changed environment variable always busts the cache). Signals and
  Leads are never cached -- every read goes through the repository.
- **Concurrent collectors, bounded and configurable.**
  `SignalService.ingest_from_collectors` runs multiple collectors under an
  `asyncio.Semaphore` sized by `concurrency.max_concurrent_collectors`; one
  collector's `CollectorError` is captured per-collector rather than
  aborting the whole batch, so `sigint collect --all` and `sigint pipeline`
  still ingest from every source that succeeded.
- **Batch inserts.** `SignalRepository.add_many` / `WeatherEventRepository.add_many`
  persist an entire collector run in one `session.add_all()` + one flush,
  instead of one round trip per record; `SignalService`/`WeatherEventService`
  use them while still emitting one audit-log entry per ingested record.
- **SQLite lock contention.** `database.busy_timeout_seconds` is passed as
  the SQLite connection's `timeout`, so a write that collides with another
  connection's lock waits and retries at the driver level instead of
  raising `database is locked` immediately -- relevant now that collectors
  and CLI commands can write concurrently.
- **Retry policy** (`app.core.retry.RetryPolicy`/`retry_async`) is
  unchanged from the foundation: configurable max retries, exponential
  backoff with jitter, an overall timeout budget, and an explicit
  `retry_on` exception filter so permanent failures (4xx HTTP responses)
  are never retried. `asyncio.CancelledError` always propagates
  immediately, never treated as retryable.

## Non-negotiable rules

Enforced in code, not just policy:

- `Signal.raw_payload` is a required field with no default -- a collector
  cannot construct a Signal without attaching the actual data it retrieved.
- `Lead.supporting_signal_ids` requires >= `MIN_SUPPORTING_SIGNALS` (2)
  distinct, non-duplicate IDs -- a Lead cannot be constructed from a
  single signal.
- `StructuralLeadVerifier` rejects a Lead if any cited signal is missing
  from storage or is not itself `VERIFIED` -- a Lead can never outlive or
  outrank the evidence it claims to be based on.
- `CorrelationEngine.correlate()` raises `CorrelationError` if handed an
  unverified signal.
- Coordinates are validated to real WGS84 ranges; addresses require
  non-empty county/municipality; nothing is defaulted to a plausible-looking
  placeholder.
- No collector, verifier, or scraper is implemented against an
  undocumented or guessed API/website structure. Where the foundation
  needed something a real implementation would provide (a live building
  registry, a real weather API), it stops at the interface boundary
  instead of faking a response.

## What's still explicitly out of scope

- **Resolved, previously flagged by production-readiness audit:** collected
  `WeatherEvent`s are now bridged into `SignalType.WEATHER_EVENT` Signals
  by `app.application.services.weather_signal_bridge_service.WeatherSignalBridgeService`,
  invoked from `sigint collect --all`/`pipeline` right after each enabled
  weather collector's ingestion. `config/rules/roofing.yaml`'s
  `roofing_storm_damage` rule (which requires a `weather_event`-typed
  signal alongside a building record and a roof mention) can now match
  real data. `service_category`/`confidence` for the bridged Signal come
  from the explicit, documented `weather_signal_bridge` config block
  (default `roofing`/`0.8`), not from inference on the event's content --
  see `docs/CONFIGURATION.md`.
- The Ehitisregister X-tee adapter
  (`app.collectors.ehitisregister_xtee_collector.EhitisregisterXTeeCollector`)
  remains intentionally disabled: X-tee is a real, documented access path
  but requires a registered member agreement, a security server, and
  certificates this platform cannot provision, and the operation-specific
  request/response schema was never verified against a real service.
  `sigint verify-collector ehitisregister_xtee` always reports `BLOCKED`.
  See `docs/COLLECTORS.md`.
- No verifier cross-references a real external registry beyond a
  collector's own declared source (that would require a second, separate
  data source per verifier -- a deliberate future phase, not fabricated now).
- No file-watching for rule files or configuration; both are read once per
  process and cached (see "Performance and reliability" above) -- restart
  the process to pick up an edited file.
- No authentication, multi-tenant, or web UI layer -- the CLI is the only
  presentation surface.

See `docs/COLLECTORS.md` for each collector's own, narrower limitations
(e.g. a schema that could not be confirmed against a live source).

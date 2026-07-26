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
  Collectors never generate, verify, or score Leads.
- **Verification** (`app.application.interfaces.verifier`) advances a
  Signal or Lead from `UNVERIFIED` to `VERIFIED` or `REJECTED`. The
  foundation ships structural verifiers only (internal consistency
  checks); a verifier that cross-references a real external registry is a
  future phase, since fabricating that behavior now would violate the
  "never invent API responses" rule.
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
  serializes already-persisted, already-verified Leads to JSON or CSV.
  This is implemented fully (not a placeholder) because it only
  serializes existing data -- no external collection, no fabrication risk.

## Domain model summary

| Model | Purpose |
|---|---|
| `Signal` | A single verifiable public fact. Never a lead. |
| `WeatherEvent` | A severe weather occurrence, stored independently; also surfaced as a `SignalType.WEATHER_EVENT` signal for correlation. |
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

## What's explicitly out of scope for this phase

Per the mission's STOP CONDITION:

- No production collector (no scraper, no real API client).
- No live verification against an external registry.
- No end-to-end pipeline run against real data.
- No example/fabricated leads.

See the top-level session report for the full "remaining limitations" list.

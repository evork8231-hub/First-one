# Folder Overview

```
app/
  core/                   Dependency-free primitives: exceptions, constants, retry policy, TTLCache, DI container.
  domain/                 Pydantic v2 entities and value objects. No infrastructure imports.
    enums.py              ServiceCategory, SignalType, WeatherEventType, VerificationStatus, LeadPriority, AuditEventType, Country.
    value_objects.py       Coordinates, Address, EstimatedLocation.
    signal.py, weather.py, lead.py, rule.py, audit.py, configuration.py
  application/
    interfaces/           Abstract repository/collector/verifier/correlation/rule_engine/lead_generation contracts.
    services/             Use-case orchestration: SignalService (incl. concurrent multi-collector ingestion),
                           VerificationService, CorrelationService, LeadGenerationService, ExportService,
                           WeatherEventService.
  collectors/             CollectorInterface scaffolding (BaseCollector, CollectorRegistry) plus five shipped,
                           config-gated collectors: ehitisregister_collector.py, ilmateenistus_collector.py,
                           real_estate/{kv_ee,kinnisvara24,city24}_collector.py. Shared: http_client.py (retry,
                           rate limiting, optional response caching), browser_client.py, jsonld.py, xml_utils.py,
                           phrase_matching.py, rate_limiting.py. See docs/COLLECTORS.md.
  verification/           StructuralSignalVerifier (structural/consistency checks incl. coordinate bounds),
                           StructuralLeadVerifier, DuplicateDetector + DuplicateSignalVerifier (duplicate
                           detection), geo.py (haversine distance).
  correlation/             CorrelationEngine -- groups verified Signals into SignalClusters.
  rule_engine/             RuleEngine (evaluation), matcher.py (per-condition matching), loader.py (YAML -> Rule,
                           with an in-process cache -- see docs/DEVELOPMENT.md#caching).
  lead_generation/         LeadGenerator, scoring.py (SignalConfidenceAggregator, LeadScorer, PriorityCalculator).
  database/
    models/                SQLAlchemy ORM models + from_domain()/to_domain() mappers, one file per entity.
    base.py, session.py, column_types.py
  repositories/
    sqlite/                Production repository implementations (SQLAlchemy + SQLite, Postgres-portable);
                           support count() and batch add_many() alongside the original CRUD methods.
    in_memory/              Lightweight implementations used by tests, satisfying the same interface.
  config/
    settings.py            Typed AppSettings (pydantic-settings) -- the schema.
    loader.py               Merges config/default.yaml with SIGINT_ environment overrides; caches the result
                           per (path, environment snapshot) -- see clear_settings_cache() for tests.
  logging/                 Loguru sink configuration.
  cli/
    main.py                 Typer app + DI container wiring.
    commands/                One module per subcommand: init, collect (single or --all, concurrent),
                           verify (signals/lead), correlate, generate, score, export, pipeline (full
                           end-to-end run), stats, config. Every command uses Rich progress bars and
                           structured logging; see docs/DEVELOPMENT.md#adding-a-new-cli-command.
  utils/                   ids.py (new_id), time.py (utc_now) -- the only place default IDs/clocks are generated.

config/
  default.yaml             Structured configuration defaults (see docs/CONFIGURATION.md).
  rules/*.yaml              Data-driven correlation rules.

alembic/                   Database migrations. alembic/env.py resolves its URL via app.config.loader.
alembic.ini

tests/                      Mirrors the app/ layout (adds tests/cli/, tests/core/, tests/database/).
                            tests/fixtures/ holds factories.py (valid entity builders) and fakes.py (in-repo
                            test doubles for collector/verifier/generator interfaces). See docs/TESTING.md.

scripts/
  check.sh                  Local quality gate: ruff + black --check + mypy + pytest.

docs/                       This file, ARCHITECTURE.md, SETUP.md, DEVELOPMENT.md, CONFIGURATION.md,
                           COLLECTORS.md, DEPLOYMENT.md, TESTING.md.
```

## Why no `presentation/`, `services/`, or `interfaces/` at the repo root?

The mission's example project layout listed `services/` and `interfaces/`
as siblings of `domain/`/`application/`. In this codebase:

- "Services" *is* `app/application/services/` -- use-case orchestration
  belongs in the application layer by Clean Architecture convention, and
  splitting it into a same-level sibling would only create an artificial
  second application layer.
- "Interfaces" *is* `app/application/interfaces/` for the same reason:
  interfaces the application layer depends on belong with the application
  layer, not floating at the root disconnected from what consumes them.
- "Presentation" is `app/cli/` -- the only presentation surface this
  foundation has. A `presentation/` wrapper around a single `cli/`
  package would add a directory level without adding meaning.

Every other folder from the mission's example structure
(`collectors/`, `verification/`, `correlation/`, `lead_generation/`,
`repositories/`, `database/`, `config/`, `logging/`, `cli/`, `core/`,
`utils/`) exists exactly as named.

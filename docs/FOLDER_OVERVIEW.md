# Folder Overview

```
app/
  core/                   Dependency-free primitives: exceptions, constants, retry policy, DI container.
  domain/                 Pydantic v2 entities and value objects. No infrastructure imports.
    enums.py              ServiceCategory, SignalType, WeatherEventType, VerificationStatus, LeadPriority, AuditEventType, Country.
    value_objects.py       Coordinates, Address, EstimatedLocation.
    signal.py, weather.py, lead.py, rule.py, audit.py, configuration.py
  application/
    interfaces/           Abstract repository/collector/verifier/correlation/rule_engine/lead_generation contracts.
    services/             Use-case orchestration: SignalService, VerificationService, CorrelationService,
                           LeadGenerationService, ExportService.
  collectors/             CollectorInterface scaffolding (BaseCollector, CollectorRegistry). No concrete
                           production collector ships in this phase.
  verification/           StructuralSignalVerifier, StructuralLeadVerifier -- structural/consistency checks only.
  correlation/             CorrelationEngine -- groups verified Signals into SignalClusters.
  rule_engine/             RuleEngine (evaluation), matcher.py (per-condition matching), loader.py (YAML -> Rule).
  lead_generation/         LeadGenerator, scoring.py (SignalConfidenceAggregator, LeadScorer, PriorityCalculator).
  database/
    models/                SQLAlchemy ORM models + from_domain()/to_domain() mappers, one file per entity.
    base.py, session.py, column_types.py
  repositories/
    sqlite/                Production repository implementations (SQLAlchemy + SQLite, Postgres-portable).
    in_memory/              Lightweight implementations used by tests.
  config/
    settings.py            Typed AppSettings (pydantic-settings) -- the schema.
    loader.py               Merges config/default.yaml with SIGINT_ environment overrides.
  logging/                 Loguru sink configuration.
  cli/
    main.py                 Typer app + DI container wiring.
    commands/                One module per subcommand (init, collect, verify, correlate, generate, export, config).
  utils/                   ids.py (new_id), time.py (utc_now) -- the only place default IDs/clocks are generated.

config/
  default.yaml             Structured configuration defaults (see docs/CONFIGURATION.md).
  rules/*.yaml              Data-driven correlation rules.

alembic/                   Database migrations. alembic/env.py resolves its URL via app.config.loader.
alembic.ini

tests/                      Mirrors the app/ layout. tests/fixtures/ holds factories.py (valid entity builders)
                            and fakes.py (in-repo test doubles for collector/verifier/generator interfaces).

scripts/
  check.sh                  Local quality gate: ruff + black --check + mypy + pytest.

docs/                       This file, ARCHITECTURE.md, SETUP.md, DEVELOPMENT.md, CONFIGURATION.md.
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

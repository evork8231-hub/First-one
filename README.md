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

## Status: architecture foundation

This repository currently contains the **foundation** of the platform:
domain models, interfaces, the correlation/rule/lead-generation engines,
persistence, configuration, logging, dependency injection, and the CLI
skeleton. **No production collector is implemented** -- the platform does
not yet scrape or call any live external source. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for what's built and what's
explicitly left for a future phase.

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

sigint init            # apply database migrations
sigint config show      # inspect resolved configuration
sigint config validate  # validate config/default.yaml
```

See [`docs/SETUP.md`](docs/SETUP.md) for full setup instructions and
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the development workflow
(linting, type checking, tests).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) -- Clean Architecture layering, data flow, key design decisions
- [`docs/SETUP.md`](docs/SETUP.md) -- installing and running the project
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) -- lint/type-check/test workflow, adding a new collector or rule
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) -- every configuration surface (YAML, env vars, rule files)
- [`docs/FOLDER_OVERVIEW.md`](docs/FOLDER_OVERVIEW.md) -- what lives where and why

## Non-negotiable rules

This project never fabricates data, homeowners, identities, addresses,
coordinates, property ownership, or API responses. When information
can't be verified from a real public source, the correct behavior is to
stop and explain the limitation -- not to guess. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#non-negotiable-rules) for
how this is enforced in the code itself (domain validation, verification
gates, and the deliberate absence of any collector that isn't backed by a
real, documented source).

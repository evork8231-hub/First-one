# Configuration Guide

Everything configurable lives outside application code. There are three
configuration surfaces:

1. **`config/default.yaml`** -- structured defaults (database, logging,
   retry, verification thresholds, enabled collectors, scoring weights,
   export settings). Loaded by `app.config.loader.load_settings()` into
   `app.config.settings.AppSettings`.
2. **Environment variables**, prefixed `SIGINT_` -- always take
   precedence over the YAML file. Nested fields use a double underscore:
   `SIGINT_DATABASE__URL`, `SIGINT_LOGGING__LEVEL`,
   `SIGINT_SCORING__WEATHER_CONFIDENCE_BOOST_FACTOR`. This is where
   secrets belong -- **never** put an API key or credential in
   `config/default.yaml`.
3. **`config/rules/*.yaml`** -- data-driven correlation rules, loaded by
   `app.rule_engine.loader.RuleLoader`. Independent of `AppSettings`.

There is also a fourth, database-backed surface --
`app.domain.configuration.ConfigurationEntry`, persisted in the
`configuration` table via `ConfigurationRepository` -- intended for
values an operator adjusts at runtime (e.g. temporarily disabling a rule)
without a redeploy. The foundation defines the repository and table; no
service yet reads from it to override `AppSettings` at runtime (a future
phase's job).

## `config/default.yaml` reference

| Key | Meaning | Default |
|---|---|---|
| `environment` | `development` / `staging` / `production` | `development` |
| `country_code` | ISO country this deployment targets | `EE` |
| `database.url` | SQLAlchemy connection URL | `sqlite:///./data/signals.db` |
| `database.echo` | Log every SQL statement | `false` |
| `database.busy_timeout_seconds` | SQLite only: how long a write waits on a lock before raising "database is locked" | `5.0` |
| `logging.level` | `TRACE`..`CRITICAL` | `INFO` |
| `logging.json_logs` | Structured JSON logs instead of text | `false` |
| `logging.log_file` | Path to a rotating log file, or `null` for stderr only | `logs/app.log` |
| `retry.max_retries` | Retries after the first attempt | `3` |
| `retry.initial_backoff_seconds` / `backoff_multiplier` / `max_backoff_seconds` / `jitter_seconds` | Exponential backoff shape | `0.5` / `2.0` / `30.0` / `0.1` |
| `retry.timeout_seconds` | Total wall-clock budget across all attempts | `60.0` |
| `verification.min_signal_confidence` | Floor enforced by `StructuralSignalVerifier` | `0.5` |
| `verification.min_lead_confidence` | Floor enforced by `StructuralLeadVerifier` | `0.5` |
| `verification.require_coordinates` | Reject a signal with no coordinates at all | `false` |
| `verification.postal_code_pattern` | Regex an Estonian postal code must match, if present | `^\d{5}$` |
| `verification.coordinate_bounds.*` | Estonia's lat/lon bounding box; coordinates outside it are rejected | `57.5..59.7 N, 21.5..28.2 E` |
| `verification.duplicate_detection.enabled` | Turn duplicate detection on/off | `true` |
| `verification.duplicate_detection.comparison_scope_limit` | Max same-county/municipality candidates compared | `200` |
| `verification.duplicate_detection.coordinate_duplicate_radius_meters` | Distance within which two signals are the same property | `25.0` |
| `verification.duplicate_detection.fuzzy_duplicate_threshold` / `fuzzy_possible_duplicate_threshold` | RapidFuzz similarity (0-100) for DUPLICATE / POSSIBLE_DUPLICATE | `95.0` / `80.0` |
| `verification.duplicate_detection.possible_duplicate_policy` | `flag` (keep verifiable) or `reject` a POSSIBLE_DUPLICATE | `flag` |
| `concurrency.max_concurrent_collectors` | Max collectors `collect --all`/`pipeline` run at once | `3` |
| `collectors.enabled` | List of registered collector names permitted to run | `[]` |
| `collectors.<name>.cache_enabled` / `cache_ttl_seconds` | Cache that collector's HTTP GET responses in-process | `false` / `300.0` |
| `rules.directory` | Where `RuleLoader` reads `*.yaml` files from | `config/rules` |
| `scoring.confidence_aggregation` | `mean` or `min`, how signal confidences combine into a lead's `estimated_confidence` | `mean` |
| `scoring.weather_confidence_boost_factor` | How much a matched weather signal scales confidence/intent (never counts as supporting evidence) | `0.2` |
| `scoring.priority_thresholds` | Minimum `intent_score` per `LeadPriority` | `critical: 0.85, high: 0.65, medium: 0.4, low: 0.0` |
| `export.default_format` | `json`, `csv`, or `xlsx` | `json` |
| `export.output_directory` | Default directory for `sigint export --output` | `exports` |
| `export.excel.*` | Header colors, frozen header, autofilter, column width bounds, date format for `.xlsx` export | see `config/default.yaml` |

## Rule files

Each file under `config/rules/` has a top-level `rules:` list. Each entry
maps directly onto `app.domain.rule.Rule`:

```yaml
rules:
  - id: roofing_storm_damage          # stable, unique slug
    name: "Roofing lead from storm damage"
    description: >
      Human-readable justification, copied into a generated Lead's
      reasoning field when this rule matches.
    lead_type: roofing                 # roofing | kitchen_remodeling | bathroom_remodeling | solar_installation
    base_confidence: 0.55              # [0.0, 1.0] contribution when this rule matches
    weight: 1.0                        # non-negative, used to combine multiple matched rules
    enabled: true                      # disable without deleting
    conditions:
      - signal_type: weather_event
        min_count: 1
        max_age_days: 60               # optional recency requirement
        min_confidence: 0.5            # optional per-condition confidence floor
      - signal_type: building_record
        min_count: 1
      - signal_type: roof_mention
        min_count: 1
    min_matching_conditions: 3         # optional; defaults to "all conditions" (logical AND)
```

`signal_type` must be one of the values in `app.domain.enums.SignalType`
(`building_record`, `real_estate_listing`, `construction_permit`,
`weather_event`, `energy_certificate`, `roof_mention`, `kitchen_mention`,
`bathroom_mention`, `renovation_mention`, `solar_opportunity`).

A `weather_event` condition can be part of a rule's conditions (it's
still *checked* for matching), but per platform policy a Signal of type
`weather_event` is always excluded from the resulting Lead's
`supporting_signal_ids` -- it only ever scales the score. See
`app.lead_generation.generator.LeadGenerator`.

The shipped files (`roofing.yaml`, `solar.yaml`, `kitchen.yaml`,
`bathroom.yaml`) are illustrative starter rules matching the mission's own
examples -- tune `base_confidence`, `weight`, and thresholds once real
signal data is available.

## Collectors

`collectors.enabled` (a list of collector names) is the master switch --
a collector fully configured below still will not run via `sigint collect`
or the DI-resolved registries unless its name is also listed here. Every
collector additionally validates its own required settings at `collect()`
time and raises `CollectorError` (never a guess) if they are missing. See
[`COLLECTORS.md`](COLLECTORS.md) for what each of the five shipped
collectors (`ehitisregister`, `ilmateenistus`, `kv_ee`, `kinnisvara24`,
`city24`) reads, requires before enabling, and does not fabricate.

## Secrets

No secret-backed setting exists yet (no collector requires one). When one
is added in a future phase, it must be declared as an environment-only
field on the relevant config model (never given a default that could be
committed) and read exclusively via `SIGINT_...` environment variables --
this is a hard requirement, not a style preference.

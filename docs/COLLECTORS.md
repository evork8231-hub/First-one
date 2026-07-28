# Collector Guide

Every collector implements either `app.application.interfaces.collector.CollectorInterface`
(returns `Signal`s) or `app.application.interfaces.weather_collector.WeatherCollectorInterface`
(returns `WeatherEvent`s), and extends the matching base class
(`app.collectors.base.BaseCollector` / `app.collectors.base_weather.BaseWeatherCollector`)
for identity, retry, and logging. None of them run unless their name is
listed in `collectors.enabled` (see [`CONFIGURATION.md`](CONFIGURATION.md)) --
a collector being fully configured below is necessary but not sufficient
for it to execute.

Every collector shares the same non-negotiable rule: **if the data it needs
isn't actually present in the response it retrieved, it raises
`CollectorError` (or leaves a field unset) rather than guessing.** This
guide documents, per collector, exactly what could and could not be
confirmed against a live source while building it.

## Ehitisregister (Estonian Building Registry) -- two access paths

Ehitisregister (EHR) has two real, government-documented access methods.
A dedicated production-readiness research pass (web search plus repeated
live-fetch attempts) established the following, distinguishing what was
independently corroborated from what remains unverified:

- **The public Open Data portal** (`andmed.eesti.ee`, "Eesti riigi
  andmete portaal") lists a dataset at
  `andmed.eesti.ee/datasets/ehitisregister` -- confirmed to exist via
  multiple independent web searches (a page titled "Ehitisregister" at
  exactly that URL), requiring no credentials. This is the platform's
  **preferred** access path: see `ehitisregister` below.
- **X-tee** (Estonia's secure inter-organizational data-exchange layer,
  part of the X-Road architecture) is also confirmed real and documented
  -- a RIHA (State Information System's registry) document titled
  "Ehitisregistris realiseeritavad x-tee teenused" describes query
  services implemented by the Building Register, including lookups by
  building code (`EHR_KOOD`), cadastral/address identifier (`ADS_OID`),
  and internal technical key (`EHIT_ID`). X-tee access requires the
  calling party to be a **registered X-tee member** operating a security
  server with member certificates -- an organizational agreement this
  platform cannot obtain on an operator's behalf. See
  `ehitisregister_xtee` below.

An unofficial, commercially-operated "Estonian Building Register API"
wrapper (hosted on a third-party API marketplace, funded by an unrelated
company) was also found during research. **It is deliberately not
used or referenced by any collector in this codebase** -- only the two
official paths above are implemented.

### `ehitisregister` (Open Data portal, `http_jsonld`) -- preferred, no credentials required

Reads Estonia's Building Registry via the state open-data portal's generic
Dataset API. `base_url` and `dataset_slug` combine into
`{base_url}/api/datasets/{dataset_slug}`, which the collector expects to
return a resource list; it fetches the first JSON-formatted resource and
maps fields via `field_map` (see below).

- **Uses:** `app.collectors.http_client.HttpClient` (retry, rate limiting,
  optional response caching -- see `cache_enabled`/`cache_ttl_seconds`).
- **Known limitation:** the dataset's existence is corroborated (see
  above), but its exact response schema was never fetched or confirmed --
  every attempt to load the live portal or its API docs was blocked at
  the network/gateway level in every environment this platform has been
  built in so far, not refused by the source itself. `field_map` lists,
  per canonical field, the candidate source JSON key names to try in
  order -- fully operator-adjustable in `config/default.yaml` without a
  code change, once the real schema is confirmed from a reachable
  environment.
- **Produces:** `SignalType.BUILDING_RECORD` signals with `default_confidence`.

### `ehitisregister_xtee` (X-tee adapter) -- disabled by design, requires credentials this platform cannot provide

`app.collectors.ehitisregister_xtee_collector.EhitisregisterXTeeCollector`
is registered like every other collector but **always raises
`CollectorError`**, regardless of configuration. It exists as a correctly
scoped scaffold, not a working integration:

- Its configuration surface
  (`app.config.settings.EhitisregisterXTeeConfig`) captures the generic,
  publicly standardized X-Road client/service identity model (member
  class/code, subsystem, security server, certificates) -- real fields
  with no defaults, since only an operator's own X-tee membership can
  supply them.
- `collect()` validates configuration completeness in three stages
  (disabled -> missing client identity -> missing target-service
  identifiers) and, even once every field above is filled in, still
  refuses to run: **the operation-specific X-tee request/response schema
  for Ehitisregister's own service was never verified** against a live or
  documented source. Only the generic X-Road message envelope is a
  stable public standard; the service-specific body is not, and
  fabricating it would violate this platform's rule against inventing
  undocumented API behavior.
- Enabling this adapter requires **both** listing `ehitisregister_xtee`
  in `collectors.enabled` **and** setting
  `collectors.ehitisregister_xtee.enabled: true` -- a deliberate
  double gate. Completing the integration requires an operator with a
  real X-tee agreement and Ehitisregister's confirmed WSDL/service
  catalog to extend `collect()` with the actual request mapping; this
  file marks exactly where that work begins.

## `ilmateenistus` (`rss_jsonld`)

Reads the Estonian Weather Service's public forecast XML feed and emits
`WeatherEvent`s -- never `Signal`s directly (see the known limitation
below).

- **Uses:** `HttpClient` for the XML fetch (built from the collector's own
  config fields, so `cache_enabled`/`cache_ttl_seconds` apply here too),
  `app.collectors.xml_utils.safe_parse_xml` for parsing.
- **Required before enabling:** `xml_url` has no default -- the exact feed
  URL could not be confirmed against a live source. The collector raises
  `CollectorError` until an operator sets it explicitly.
- **Known limitation:** `sigint collect --all`/`pipeline` do run this
  collector (once enabled) and persist its `WeatherEvent`s, but nothing
  today converts a `WeatherEvent` into a `SignalType.WEATHER_EVENT`
  `Signal`. Per the mission rule, weather should only ever adjust another
  signal's confidence, never independently create a lead -- but until
  this bridge is built, weather cannot influence correlation *at all*,
  so `config/rules/roofing.yaml`'s `roofing_storm_damage` rule can never
  match real data. See `docs/ARCHITECTURE.md#whats-still-explicitly-out-of-scope`.
- **`place_administrative_areas`** maps the feed's place names to a
  county/municipality; unmapped places are skipped, not guessed.
  `wind_severity_reference_ms` and `categorical_event_severity` are
  disclosed scoring policy this platform applies, not values the feed
  itself reports.

## `kv_ee`, `kinnisvara24`, `city24` (`playwright_jsonld`)

All three share `BrowserCollectorConfig` and the same strategy: a
headless-browser search page (Playwright) yields listing URLs via
`listing_link_selector` (a CSS selector), each listing's schema.org
JSON-LD is parsed, and an explicit Estonian renovation-indicator phrase in
the listing's own description text produces a Signal -- never inferred
from price, photos, or building age (see `app.collectors.phrase_matching`).

- **Uses:** `app.collectors.browser_client.BrowserClient` (Playwright,
  headless by default), `app.collectors.jsonld.extract_json_ld`.
- **Required before enabling:** `search_paths` (which URL path lists
  houses for sale) and `listing_link_selector` (which CSS selector
  identifies a listing link) are genuinely site-specific and have no
  default -- they could not be confirmed against the live sites while
  building these collectors.
- **No HTTP response caching** -- these collectors render pages through a
  real browser, not `HttpClient`, so the cache described above does not
  apply; each run performs fresh navigation, rate-limited by
  `request_delay_seconds`.
- **Produces:** `SignalType.REAL_ESTATE_LISTING` plus a phrase-matched
  mention type (`ROOF_MENTION`, `KITCHEN_MENTION`, `BATHROOM_MENTION`,
  `RENOVATION_MENTION`, or `SOLAR_OPPORTUNITY`) per matched listing, at
  `default_confidence` (lower than an authoritative registry, since it is
  text-mined).

## Adding a new collector

See [`DEVELOPMENT.md`](DEVELOPMENT.md#adding-a-new-collector) for the
step-by-step process (extend `BaseCollector`, register in the DI
container, add to `collectors.enabled`, write hermetic tests with
`httpx.MockTransport` or a fake `BrowserClient` -- never test against a
live site in CI).

## Running collectors

```bash
sigint collect --collector ehitisregister      # run exactly one, by name
sigint collect --all                           # run every enabled collector (signal + weather)
```

`--all` runs both signal collectors (concurrently, bounded by
`concurrency.max_concurrent_collectors`) and any enabled weather
collector, reporting per-collector success/failure without letting one
failing source abort the others (see
`app.application.services.signal_service.SignalService.ingest_from_collectors`
and `app.application.services.weather_event_service.WeatherEventService`).
`sigint pipeline` runs the same collection step as its first stage unless
`--skip-collect` is given.

## Collector lifecycle: DISCOVERED -> TESTED -> VERIFIED -> ENABLED

A collector registered in the DI container starts `DISCOVERED`. Running
`sigint verify-collector <name>` moves it to `TESTED` (attempted, but the
verdict was NOT READY) or `VERIFIED` (verdict was READY) --
`app.application.services.collector_lifecycle_service.CollectorLifecycleService`
records this via `ConfigurationRepository`, the same way schema-drift
fingerprints and weather-bridge dedup keys are stored. `ENABLED` is never
written by that service: it is a derived fact (listed in
`collectors.enabled` *and* currently `VERIFIED`), never something the
service grants on its own.

Both `sigint collect --all` and `sigint pipeline` read this state and
**refuse to actually run** a collector that is listed in
`collectors.enabled` but was never verified READY -- it is reported as a
skipped failure (`not verified for mass collection -- run
'sigint verify-collector <name>' ...`) instead of being executed, so
adding a name to `collectors.enabled` alone is never enough to make it
run. `sigint collect --collector <name>` (an operator naming one
collector to run right now, the same deliberate kind of action as
`verify-collector` itself) is **not** gated -- gating it too would make
it impossible to ever reach `VERIFIED` for the first time. A later failed
re-verification moves a `VERIFIED` collector back down to `TESTED`,
since only the most recent verification result is trusted.

```bash
sigint verify-collector ehitisregister   # -> VERIFIED if READY
sigint collect --all                     # now actually runs ehitisregister
```

## Schema drift detection

`sigint collect`/`sigint pipeline` fingerprint every signal-producing
collector's run by the set of raw-payload keys its Signals actually
carried (`Signal.raw_payload` -- the unmodified source record every
collector stores), and compare that set against the fingerprint from the
collector's previous run (`app.verification.schema_drift.SchemaDriftDetector`,
stored via `ConfigurationRepository` under
`schema_fingerprint.<collector_name>`). If the key set changed -- fields
added or removed -- a warning is printed and a `SCHEMA_DRIFT_DETECTED`
audit log entry is written, then the fingerprint updates to the new key
set so the same drift is not re-reported on every subsequent run.

This is diagnostic only: it never blocks a run, never changes what was
ingested, and never modifies configuration. A drift warning means "the
source's structure changed since last time -- check whether the
collector's `field_map`/selectors/parsing still make sense," not that
anything failed.

Deliberately **not** applied to the `ilmateenistus` weather collector:
`WeatherEvent.raw_payload` is a fixed-key dict `IlmateenistusCollector`
itself constructs from parsed fields (`place`, `phenomenon`, `text`,
`date`, `period`, `wind_gust_ms`), not the source feed's own structure --
its key set never changes regardless of what the real XML looks like, so
checking it would report false confidence rather than real drift. Use
`sigint inspect-xml` (below) to check the Ilmateenistus feed's actual
structure instead.

## Operator tooling

A set of read-only, advisory CLI commands reduce how much manual YAML
editing and direct SQL an operator needs to enable a collector safely.
Every one of them only reports findings or executes a collector's
existing, already-tested `collect()` -- none of them write configuration,
invent a selector/field/schema, or enable a collector on their own.

### `sigint discover-fields` -- field_map suggestions (Ehitisregister)

Samples a few real records from the Ehitisregister Open Data resource
(`EhitisregisterCollector.sample_raw_records`) and, for every JSON key the
currently configured `collectors.ehitisregister.field_map` does not
account for, suggests which canonical field it might belong to --
ranked by string similarity (RapidFuzz) against the field's name and its
already-configured candidate synonyms, with a confidence score. A key
with no plausible match is reported as unmapped, never guessed.
See `app.collectors.field_map_discovery`.

```bash
sigint discover-fields --sample-limit 5 --score-cutoff 60
```

### `sigint discover-selectors` -- listing-card/link candidates (KV.ee, Kinnisvara24, City24)

Analyzes a downloaded (or live-fetched) listing/search-results page and
reports repeated tag+class element groups that look like listing cards,
anchor groups that look like `listing_link_selector` candidates, and
address-related text samples (price-like text, postal codes, street
name + house number pairs matched together as one literal substring --
never a name and a number stitched together from separate parts of the
page -- and known Estonian city names found verbatim in the page) --
each with an occurrence count and a sample, for an operator to compare
against the real page. See `app.collectors.selector_discovery`.

```bash
sigint discover-selectors --html-file search_results.html
sigint discover-selectors --url https://www.kv.ee/... --collector kv_ee
```

### `sigint inspect-xml` -- element structure (Ilmateenistus)

Parses an XML feed (via the same DOCTYPE-rejecting `safe_parse_xml` every
collector uses) and reports every distinct element path, its occurrence
count, observed attribute names with a sample value, and sample text
content. With `--interactive`, walks through the element paths
`IlmateenistusCollector` currently hardcodes and asks the operator to
confirm each against what was actually found -- a diagnostic only; it
never rewrites the collector's parsing code.
See `app.collectors.xml_schema_inspector`.

```bash
sigint inspect-xml --xml-file forecast.xml
sigint inspect-xml --url https://www.ilmateenistus.ee/... --interactive
```

### `sigint verify-collector` -- enablement wizard

Runs a collector for real (`collector.collect()` never persists anything
itself -- only `SignalService`/`WeatherEventService` write to storage, so
this is a safe dry run), inspects what it actually produced, and prints a
final `READY`/`NOT READY` enablement report with a matching exit code (0
for READY). For `ehitisregister` this also runs the field-map coverage
check above; for the browser-based listing collectors and Ilmateenistus
it checks that the collector is configured before executing it.
`ehitisregister_xtee` always reports `BLOCKED` immediately, with no
discovery attempted -- see the X-tee section above for why.

```bash
sigint verify-collector ehitisregister
sigint verify-collector kv_ee
sigint verify-collector ehitisregister_xtee   # always BLOCKED by design
```

### `sigint health` -- collector run history

Reads the audit log for the last known status, duration, item count, and
consecutive-failure streak of every collector that has run at least once
(`app.application.services.collector_health_service.CollectorHealthService`).
Purely a summary of history `collect`/`pipeline` already recorded --
running it triggers no collection.

```bash
sigint health
```

### `sigint purge` -- safe deletion by source

Deletes Signals or WeatherEvents from a given `source`, optionally only
those older than `--before`, via
`app.application.services.data_management_service.DataManagementService`.
Always a dry-run preview by default; pass `--yes` to actually delete, and
every real deletion is audit logged (`DATA_PURGED`). Deliberately scoped
to Signals and WeatherEvents, not Leads -- a Lead can be generated from
signals across several sources, so it has no single `source` to purge by.

```bash
sigint purge signals --source "Ehitisregister (Estonian Building Registry)"        # preview
sigint purge signals --source "Ehitisregister (Estonian Building Registry)" --yes  # delete
sigint purge weather-events --source "Ilmateenistus (Estonian Environment Agency Weather Service)" --before 2026-01-01 --yes
```

### `sigint rollback` -- undo the last collector run

Undoes the most recent successful run of a single collector (identified
by its config name, e.g. `ehitisregister`, `ilmateenistus`), via
`app.application.services.rollback_service.RollbackService`. Unlike
`sigint purge`, it never has to guess which rows to delete: every
`COLLECTOR_RUN_COMPLETED` audit entry already records the exact
`execution_id` and the ids of every record that run inserted (written by
`SignalService`/`WeatherEventService`), so a rollback deletes precisely
those rows.

Always a dry-run preview by default; pass `--yes` to actually roll back.
A real rollback never edits or deletes the `COLLECTOR_RUN_COMPLETED`
entry it reverses -- it appends a new `COLLECTOR_RUN_ROLLED_BACK` entry,
so the audit history stays complete and the same run cannot be rolled
back twice (a second `--yes` call reports that there is no un-rolled-back
run left and exits non-zero).

**Atomic.** Deleting the records and writing the rollback's audit entry
happen inside a single database transaction
(`app.application.interfaces.rollback_unit_of_work.RollbackUnitOfWork`,
implemented by `SQLiteRollbackUnitOfWork`) -- a crash, disk-full, or lock
timeout between the two can never leave records deleted with no audit
trail of it; the whole operation either commits or is fully rolled back.

**Race-safe.** The same transaction re-checks, immediately before
committing and after it has already taken SQLite's write lock, whether
another process rolled back this exact run first. Two concurrent
`sigint rollback --yes` invocations on the same run can never both
succeed -- the loser gets a clear "already rolled back by another
process" error instead of writing a duplicate audit entry.

**Metadata is validated, never trusted.** A malformed `execution_id` or a
non-UUID entry in `inserted_signal_ids`/`inserted_event_ids` (corrupted
by a hand edit, a bug, or a future schema change) is caught and reported
as a clean error ("Rollback metadata ... is corrupted ... Rollback cannot
continue safely.") -- never an uncaught Python traceback, and nothing is
deleted.

**Refuses to orphan a Lead.** If a Signal a rollback would delete is
still cited by an existing Lead's `supporting_signal_ids`, the rollback
is blocked with a clear error rather than deleting the Signal (which
would leave the Lead pointing at a record that no longer exists) or
silently rewriting the Lead. Resolve or reject the Lead first, then
retry.

```bash
sigint rollback signals ehitisregister              # preview
sigint rollback signals ehitisregister --yes        # actually roll back
sigint rollback weather-events ilmateenistus --yes
```

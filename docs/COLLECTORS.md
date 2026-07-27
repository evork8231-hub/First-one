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

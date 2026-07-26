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

## `ehitisregister` (`http_jsonld`)

Reads Estonia's Building Registry via the state open-data portal's generic
Dataset API. `base_url` and `dataset_slug` combine into
`{base_url}/api/datasets/{dataset_slug}`, which the collector expects to
return a resource list; it fetches the first JSON-formatted resource and
maps fields via `field_map` (see below).

- **Uses:** `app.collectors.http_client.HttpClient` (retry, rate limiting,
  optional response caching -- see `cache_enabled`/`cache_ttl_seconds`).
- **Known limitation:** the exact response schema of the discovered
  resource could not be confirmed against a live source while building
  this collector. `field_map` lists, per canonical field, the candidate
  source JSON key names to try in order -- fully operator-adjustable in
  `config/default.yaml` without a code change, once the real schema is
  confirmed.
- **Produces:** `SignalType.BUILDING_RECORD` signals with `default_confidence`.

## `ilmateenistus` (`rss_jsonld`)

Reads the Estonian Weather Service's public forecast XML feed and emits
`WeatherEvent`s (never `Signal`s directly -- weather only ever influences
confidence during correlation, never independently creates a lead).

- **Uses:** `HttpClient` for the XML fetch (built from the collector's own
  config fields, so `cache_enabled`/`cache_ttl_seconds` apply here too),
  `app.collectors.xml_utils.safe_parse_xml` for parsing.
- **Required before enabling:** `xml_url` has no default -- the exact feed
  URL could not be confirmed against a live source. The collector raises
  `CollectorError` until an operator sets it explicitly.
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
sigint collect --all                           # run every enabled collector concurrently
```

`--all` bounds concurrency with `concurrency.max_concurrent_collectors`
and reports per-collector success/failure without letting one failing
source abort the others (see `app.application.services.signal_service.SignalService.ingest_from_collectors`).
`sigint pipeline` runs the same collection step as its first stage unless
`--skip-collect` is given.

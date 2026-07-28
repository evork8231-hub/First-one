# Staging Validation Checklist

A practical, run-it-yourself checklist for proving the platform works
safely in a staging environment before any real collector is enabled in
production. It assumes staging points at its own database
(`database.url` distinct from production) and complements
[`DEPLOYMENT.md`](DEPLOYMENT.md), which covers the same operations in more
narrative detail. Every command below is read-only or dry-run unless
explicitly noted.

Four operator commands exist specifically to make this checklist provable
without hand-querying the database:

- `sigint db check` -- confirms the database is reachable and, for SQLite,
  runs `PRAGMA integrity_check`. Exits non-zero on any problem.
- `sigint db migration-status` -- reports the database's current Alembic
  revision against the latest migration on disk, and lists exactly which
  migrations are pending if it is behind. Exits non-zero if not up to date.
- `sigint collector-status` -- lists every registered collector's
  verification lifecycle state (`discovered` / `tested` / `verified`) and
  whether it is currently listed in `collectors.enabled`, without needing
  to remember the result of the last `sigint verify-collector` run.
- `sigint inspect-lead <id>` -- prints one Lead's full detail plus every
  supporting Signal's source, confidence, and verification state, for the
  manual lead-review procedure in step 5 below. Never re-verifies or
  mutates anything.

## 1. Fresh installation procedure

Scenario: an empty database, first-ever startup.

```bash
sigint config validate
sigint init
sigint db check                # expect: reachable and healthy, exit 0
sigint db migration-status     # expect: up to date at head, exit 0
sigint pipeline --skip-collect # nothing to do yet -- confirms no error on an empty DB
sigint stats                   # expect: every count is zero
sigint export --format csv     # expect: header row only, no error
```

**Expected outcome**: every command exits `0`; `sigint db check` and
`sigint db migration-status` both report a healthy, up-to-date database;
`sigint stats` shows zero Signals/Leads/WeatherEvents.

## 2. Migration verification

Scenario: a database that already contains Signals/Leads from an earlier
schema version.

```bash
sigint db migration-status     # confirm it reports pending migrations, not an error
sigint stats                   # record counts before migrating
sigint init                    # applies every pending migration to head
sigint db migration-status     # expect: up to date, exit 0
sigint stats                   # compare against the counts recorded above
```

**Expected outcome**: `sigint stats` reports identical counts before and
after; `sigint db migration-status` moves from "pending" to "up to date";
no data loss. `sigint init` is safe to run again immediately afterward --
it is retry-safe by design (see `alembic/versions/0002_lead_identity_key.py`
and `tests/database/test_lead_identity_key_migration.py` for the
crash-recovery proof) and reports "up to date" with no changes on a
no-op rerun.

## 3. Backup/restore drill

Scenario: create a backup, restore it into a clean environment, confirm
identical behavior.

```bash
# stop every process that writes to the database first
sqlite3 data/signals.db ".backup data/signals.db.$(date +%Y%m%dT%H%M%S).bak"

# in a clean environment, pointed at a fresh copy of the backup file:
sigint db check                # expect: reachable and healthy
sigint db migration-status     # expect: up to date (or a known-pending state, if the
                                # backup predates a later migration -- see step 2)
sigint stats                   # compare against sigint stats run just before the backup
sigint init                    # must be a safe no-op if already at head
sigint pipeline                # confirm normal operation resumes
```

**Expected outcome**: `sigint stats` output is identical immediately before
the backup and immediately after the restore; `sigint init` against an
already-current restored database reports "up to date" with no changes.
Full restore procedure (stopping writers, moving the broken file aside,
etc.) is in [`DEPLOYMENT.md#restoring-from-a-backup`](DEPLOYMENT.md#restoring-from-a-backup).

## 4. Collector activation steps

**Enable exactly one collector at a time.** `ehitisregister` (the Open
Data portal path) is the recommended first candidate -- no credentials, no
browser automation, and it is the platform's documented preferred access
path (see [`COLLECTORS.md`](COLLECTORS.md#ehitisregister-estonian-building-registry----two-access-paths)).

```bash
sigint collector-status                     # confirm it starts at 'discovered'
sigint discover-fields                      # confirm field_map covers real observed keys
sigint verify-collector ehitisregister      # must report READY; read the sampled
                                             # records printed -- not just "no exception"
sigint collector-status                     # confirm it now shows 'verified'
```

Add the collector to `collectors.enabled` in the **staging** config only,
then:

```bash
sigint collect --collector ehitisregister   # run once explicitly (ungated)
sigint stats                                # inspect what was actually ingested
sigint verify signals                       # confirm a plausible verified/rejected split;
                                             # read rejection reasons for anything unexpected
sigint pipeline --skip-collect              # correlate -> generate -> verify-leads on
                                             # what was just collected
sigint collector-status                     # confirm 'listed' and 'actually runs' are both yes
```

**Expected outcome**: `sigint verify-collector` reports `READY`;
`collector-status` shows `verified` and, once added to
`collectors.enabled`, `yes`/`yes` for listed/actually-runs; the ingested
Signals and any resulting Leads read as plausible on manual inspection
(see step 5). Only after this passes should the collector be added to the
**production** `collectors.enabled` list.

## 5. Lead review procedure

For every Lead generated during collector activation or any staging run:

```bash
sigint score                    # list every Lead with its scores/priority
sigint inspect-lead <lead-id>   # full detail + every supporting signal, for the lead below
```

For each Lead, check against the quality checklist:

- **Correct service category** -- `lead_type` matches what the reasoning
  and supporting signals actually describe.
- **Correct location** -- county/municipality plausible for the cited
  signals.
- **Genuine homeowner intent** -- the intent score is supported by the
  evidence types actually cited, not a coincidental keyword match.
- **Enough supporting evidence** -- at least two non-weather signals
  (enforced structurally), and on manual read they substantively concern
  the same opportunity, not two unrelated facts sharing only a
  municipality.
- **No fabricated information** -- every claim in `reasoning` traces to a
  field on a cited Signal (`inspect-lead` prints each Signal's source and
  confidence so this is checkable without a separate database query).
- **Traceable source evidence** -- `inspect-lead`'s "supporting signals"
  table shows `N/N found`; any count below the Lead's total supporting-id
  count is flagged in red and must be investigated before treating the
  Lead as trustworthy.

Classify each reviewed Lead:

- **A -- sellable**: passes every check above with no reviewer doubt, and
  `sigint verify lead <id>` reports `verified`.
- **B -- manual review**: passes structural verification but a reviewer
  has a specific, articulable doubt on one checklist item.
- **C -- reject**: fails structural verification, or a reviewer finds
  fabricated/unsupported claims or a mismatched category.

Never export or hand off a Lead to a contractor-facing process without
having gone through this classification at least once for that collector.

# Staging Runbook

A literal, step-by-step execution script for staging validation -- every
step names the exact command, the exact output an operator should see,
what a deviation means, and whether that deviation blocks moving to the
next step. This is the executable counterpart to
[`STAGING_VALIDATION.md`](STAGING_VALIDATION.md) (which explains *why*
each check exists); this document is what an operator actually types.

**Scope.** This runbook proves one thing: *an operator, with no developer
involved, can deploy LeadFinder to staging, upgrade its database, back it
up and restore it, activate exactly one real collector, and manually
review the Leads it produces.* Nothing here requires reading source code.

**Conventions used below:**

- Every command is `sigint ...`, installed via `pip install .` per
  [`DEPLOYMENT.md`](DEPLOYMENT.md#installing-for-production). Run from
  wherever `database.url` and `config/default.yaml` are expected to
  resolve for this environment (see `sigint config show` if unsure).
- **Exit code** is the single most reliable pass/fail signal -- check it
  even when the printed text looks right. `echo $?` immediately after a
  command shows it.
- "**Blocks?**" means: if this step's actual result does not match
  "Expected output," stop and do not proceed to the next step until it is
  resolved. A step marked "No" means the deviation is worth investigating
  but staging validation can continue past it.
- Commands that mutate data are called out explicitly. Every other command
  is read-only or dry-run by default.

---

## 1. Fresh installation validation

Proves: an empty database can be initialized and the platform starts in a
known-good state.

### 1.1 Validate configuration

```bash
sigint config validate
```
- **Expected output:** `Configuration at config/default.yaml is valid.` (green), exit code `0`.
- **Failure means:** the YAML file is malformed, or environment overrides merge into an invalid `AppSettings` (e.g. a bad type, a missing required field). The error message names the specific field.
- **Blocks?** Yes -- nothing downstream can be trusted until configuration loads.

### 1.2 Apply migrations to an empty database

```bash
sigint init
```
- **Expected output:** `Applying migrations against sqlite:///<path> ...` followed by Alembic's own `Running upgrade  -> 0001, ...` / `Running upgrade 0001 -> 0002, ...` log lines, ending in `Database schema is up to date.` (green), exit code `0`.
- **Failure means:** a raw Python traceback here (not a clean red message) is a real bug, not an expected failure path -- stop and escalate to a developer rather than retrying blindly. A "database is locked" error means another process already has the file open.
- **Blocks?** Yes.

### 1.3 Confirm database health

```bash
sigint db check
```
- **Expected output:** `Database is reachable and healthy (6 table(s)).` (green), exit code `0`.
- **Failure means:** exit `1` with "Database is reachable but has never been migrated" means step 1.2 did not actually commit (re-run `sigint init`); "Database integrity check failed: ..." means file-level corruption -- treat the file as unusable and start over from a fresh path; "Database is not reachable" means a connection-level problem (permissions, wrong path, wrong URL).
- **Blocks?** Yes.

### 1.4 Confirm migration status

```bash
sigint db migration-status
```
- **Expected output:** `Database is up to date at revision '0002'.` (green), exit code `0`.
- **Failure means:** any non-zero exit here after step 1.2 reported success is a real inconsistency (e.g. `sigint init` silently failed) -- do not proceed on the assumption it will "sort itself out."
- **Blocks?** Yes.

### 1.5 Confirm the pipeline runs end-to-end with no data

```bash
sigint pipeline --skip-collect
```
- **Expected output:** ends with `Pipeline complete: 0 signal(s) verified, 0 rule match(es), 0 lead(s) generated, 0 lead(s) verified.`, exit code `0`.
- **Failure means:** any exception here on a genuinely empty database indicates a bug in the pipeline stages themselves (not a data problem, since there is no data) -- escalate to a developer.
- **Blocks?** Yes.

### 1.6 Confirm reporting commands work on an empty database

```bash
sigint stats
sigint export --format csv
```
- **Expected output:** `sigint stats` prints three tables (Signals, Leads, priority) all showing zero counts, plus `Weather events stored: 0`; `sigint export --format csv` prints only the CSV header row. Both exit `0`.
- **Failure means:** same as 1.5 -- a bug, not a data issue.
- **Blocks?** No, but do not proceed to section 4 (real collector activation) until this passes.

**Section 1 pass criterion:** every step above exits `0` and matches its expected output.

---

## 2. Existing database upgrade validation

Proves: a database carried over from an earlier schema version upgrades
without data loss. Use a **copy** of a real database from the previous
deployment (or staging's own database, if it predates the latest
migration) -- never the only copy of production data.

### 2.1 Confirm the copy is reachable and record its pre-upgrade state

```bash
sigint db check
sigint db migration-status
sigint stats
```
- **Expected output:** `db check` reports healthy; `db migration-status` reports either `up to date` (nothing to test -- get an older copy) **or** `Database is at revision '<rev>'; head is '0002'.` followed by `Pending migration(s): <rev-list>`, exit `1`; `stats` prints the Signal/Lead/WeatherEvent counts to compare against after the upgrade. **Write these counts down.**
- **Failure means:** `db check` failing here means the copy itself is bad (corrupted or wrong file) -- get a fresh copy before continuing. `db migration-status` exiting `1` with "Pending migration(s)" listed is the *expected* starting condition for this section, not a failure.
- **Blocks?** Yes if `db check` fails; No (expected) for `db migration-status` reporting pending migrations.

### 2.2 Apply the migrations

```bash
sigint init
```
- **Expected output:** same as step 1.2, but the Alembic log lines start from the database's actual current revision (e.g. `Running upgrade 0001 -> 0002, ...` only, if it was already at `0001`), ending in `Database schema is up to date.`, exit `0`.
- **Failure means:** a raw traceback is a real bug in the migration itself -- do not attempt manual SQL repair (the migration is designed to be retry-safe; simply re-running `sigint init` is always the correct recovery step, see `alembic/versions/0002_lead_identity_key.py`). If a second `sigint init` also fails with the same error, escalate.
- **Blocks?** Yes.

### 2.3 Confirm the upgrade completed and no data was lost

```bash
sigint db migration-status
sigint stats
```
- **Expected output:** `db migration-status` reports `Database is up to date at revision '0002'.`, exit `0`. `sigint stats` reports **exactly the same counts** recorded in step 2.1.
- **Failure means:** any count difference from step 2.1 is data loss -- stop immediately, do not run anything else against this database, and escalate with both `stats` outputs attached. `db migration-status` still reporting pending migrations means step 2.2 did not actually apply -- re-run `sigint init` once; if it still reports pending, escalate.
- **Blocks?** Yes.

### 2.4 Confirm the migration is idempotent

```bash
sigint init
```
- **Expected output:** `Database schema is up to date.` with no `Running upgrade` lines this time (nothing left to apply), exit `0`.
- **Failure means:** any error on a second, immediate `sigint init` against an already-current database is a real bug -- escalate.
- **Blocks?** No, but treat any failure here as seriously as 2.2/2.3.

**Section 2 pass criterion:** `sigint stats` output is byte-identical before and after; `sigint db migration-status` ends at "up to date."

---

## 3. Backup and restore drill

Proves: a backup taken today can be restored into a clean environment and
behaves identically. Full narrative version:
[`DEPLOYMENT.md#backing-up-the-sqlite-database-before-migrations`](DEPLOYMENT.md#backing-up-the-sqlite-database-before-migrations).

### 3.1 Record pre-backup state and take the backup

```bash
sigint stats                                                    # record output
# stop every process that writes to this database first, then:
sqlite3 data/signals.db ".backup data/signals.db.$(date +%Y%m%dT%H%M%S).bak"
```
- **Expected output:** `sqlite3 .backup` prints nothing on success and exits `0`; a new `.bak` file appears alongside `data/signals.db`.
- **Failure means:** a non-zero exit from `sqlite3` (e.g. "database is locked") means a writer was not actually stopped -- confirm no `sigint` process or scheduled job is running against this file, then retry.
- **Blocks?** Yes -- do not proceed with an unverified or partial backup file.

### 3.2 Restore into a clean environment

```bash
# in the clean environment, pointed at a copy of the .bak file renamed to
# the path SIGINT_DATABASE__URL / database.url resolves to:
cp data/signals.db.<timestamp>.bak data/signals.db
```
- **Expected output:** the copy command exits `0`; the file exists at the expected path.
- **Failure means:** a filesystem error (permissions, disk full) -- resolve at the OS level before continuing.
- **Blocks?** Yes.

### 3.3 Confirm the restored database is healthy and current

```bash
sigint db check
sigint db migration-status
sigint stats
```
- **Expected output:** `db check` reports healthy; `db migration-status` reports the same state the source database was in at backup time (`up to date`, most likely); `sigint stats` output is **identical** to the output recorded in step 3.1.
- **Failure means:** any count mismatch against step 3.1 means the backup or restore was not a clean, consistent snapshot -- do not trust this restore; investigate whether a writer was truly stopped during the `.backup` call. `db check` failing means the copied file is corrupted or truncated.
- **Blocks?** Yes.

### 3.4 Confirm `sigint init` is a safe no-op and normal operation resumes

```bash
sigint init
sigint pipeline --skip-collect
```
- **Expected output:** `sigint init` reports `Database schema is up to date.` with no changes; `sigint pipeline --skip-collect` completes normally (see step 1.5's expected output shape, with real counts this time if signals/leads exist).
- **Failure means:** same interpretation as sections 1 and 2 above -- a raw traceback or a stage exception is a real bug, not an expected restore outcome.
- **Blocks?** Yes.

**Section 3 pass criterion:** `sigint stats` output matches exactly before backup and after restore; every command in 3.3-3.4 exits `0`.

---

## 4. First collector activation procedure

Proves: exactly one real, credential-free collector (`ehitisregister`,
the Open Data portal path -- see
[`COLLECTORS.md`](COLLECTORS.md#ehitisregister-estonian-building-registry----two-access-paths))
can be safely enabled end-to-end. **Do not enable a second collector until
this entire section passes for the first one.**

### 4.1 Confirm the collector's starting state

```bash
sigint collector-status
```
- **Expected output:** a table listing every registered collector; the row for `ehitisregister` shows lifecycle state `discovered` and `no`/`no` in the last two columns.
- **Failure means:** if `ehitisregister` is missing from the table entirely, the DI container is misconfigured -- this is a developer-level issue, escalate rather than proceeding.
- **Blocks?** No -- this step is a baseline recording, not a pass/fail gate.

### 4.2 Check field-map coverage against the real source

```bash
sigint discover-fields
```
- **Expected output:** either `Every key observed in N sampled record(s) is already covered by field_map.` (green) or a table of unmapped keys with suggested canonical fields and confidence scores, plus a reminder that nothing was changed automatically.
- **Failure means:** `Could not sample records: ...` (red), exit `1`, means the Open Data portal is unreachable from this environment -- resolve network access before continuing; do not proceed to activation without ever having reached the real source. `The source returned no records; nothing to analyze.` means the source is reachable but currently empty -- retry later rather than treating this as a hard failure.
- **Blocks?** Yes if the source cannot be reached at all. No (proceed to 4.3, which will re-confirm) if only unmapped keys are reported -- review them, update `field_map` if warranted, and re-run.

### 4.3 Run the enablement wizard

```bash
sigint verify-collector ehitisregister
```
- **Expected output:** three numbered steps printed to console, sampled real records shown, ending in `Enablement report: READY` (green), exit code `0`.
- **Failure means:** `Enablement report: NOT READY` (red), exit `1`, with specific reasons listed (e.g. "Sampling failed", "collect() produced zero signals"). **Read the sampled records printed in Step 1/3 yourself** -- do not treat a bare `READY` as sufficient without a human glance at real data.
- **Blocks?** Yes -- do not proceed until this reports `READY`.

### 4.4 Confirm the lifecycle state moved to verified

```bash
sigint collector-status
```
- **Expected output:** the `ehitisregister` row now shows `verified`; the "listed" column is still `no` (not yet in `collectors.enabled`).
- **Failure means:** still showing `discovered`/`tested` means step 4.3 did not actually record success -- re-run 4.3.
- **Blocks?** Yes.

### 4.5 Enable the collector in the staging config only

Add `ehitisregister` to `collectors.enabled` in the **staging** `config/default.yaml` (or `SIGINT_COLLECTORS__ENABLED`), then:

```bash
sigint collector-status
```
- **Expected output:** the `ehitisregister` row now shows `verified` / `yes` / `yes`.
- **Failure means:** `yes`/`no` (listed but not running) means the lifecycle state regressed or was never actually `verified` -- re-run 4.3.
- **Blocks?** Yes.

### 4.6 Run the collector for real, once, explicitly (mutates data)

```bash
sigint collect --collector ehitisregister
```
- **Expected output:** `Ingested N signal(s) from 'ehitisregister'.` (green), `N >= 0`, exit `0`. A yellow schema-drift warning may also print -- this is diagnostic, not a failure.
- **Failure means:** exit `1` with `Collector 'ehitisregister' failed: <reason>` means the live source rejected or errored the request -- read the reason; a network/rate-limit issue is retryable, a schema-shape issue needs a developer.
- **Blocks?** Yes.

### 4.7 Inspect what was actually ingested

```bash
sigint stats
sigint verify signals
```
- **Expected output:** `sigint stats`' Signal counts increase by the `N` reported in 4.6. `sigint verify signals` prints `Verified N signal(s): X verified, Y rejected.`, exit `0`.
- **Failure means:** a rejection rate that looks implausibly high (e.g. everything rejected) means either the source's data doesn't match this platform's Estonia-only/structural assumptions, or `field_map` needs adjustment -- read the specific rejection reasons via the audit log before re-running.
- **Blocks?** No, but do not treat a mostly-rejected batch as a pass -- investigate before section 5.

### 4.8 Run correlation and generation on what was just collected

```bash
sigint pipeline --skip-collect
```
- **Expected output:** `Pipeline complete: N signal(s) verified, M rule match(es), K lead(s) generated, J lead(s) verified.` (`M`/`K`/`J` can legitimately be `0` if the data doesn't happen to satisfy any rule), exit `0`.
- **Failure means:** an exception here on real data (as opposed to the empty-database case in 1.5) can indicate a data-shape edge case the pipeline doesn't handle -- capture the traceback and escalate.
- **Blocks?** Yes.

**Section 4 pass criterion:** `sigint collector-status` shows `verified`/`yes`/`yes` for `ehitisregister`; at least one real collection ran without a `CollectorError`; the resulting Signals show a plausible verified/rejected split. Only after this passes should `ehitisregister` be added to the **production** `collectors.enabled` list.

---

## 5. Lead quality review procedure

Proves: any Lead the pipeline generated is fit to hand to a contractor, or
is correctly rejected/held for review. Run this against whatever Leads
section 4 (or any other staging run) produced.

### 5.1 List every Lead with its scores

```bash
sigint score
```
- **Expected output:** a table titled `N lead(s)` (or `No leads match the given filters.` if none exist yet -- if so, stop here, there is nothing to review), listing each Lead's ID, type, status, priority, intent score, confidence score, exit `0`.
- **Failure means:** n/a -- this command cannot meaningfully fail on valid input.
- **Blocks?** No.

### 5.2 Inspect each Lead's full detail and supporting evidence

For every Lead ID from step 5.1:

```bash
sigint inspect-lead <lead-id>
```
- **Expected output:** the Lead's type, location, verification status, priority, intent/confidence scores, and reasoning, followed by a "Supporting signals (N/N found)" table listing each signal's ID, type, source, verification status, confidence, and timestamp, exit `0`.
- **Failure means:** a count below `N/N` (e.g. `1/2 found`), highlighted red with "no longer exist in storage," means this Lead cites a Signal that is no longer in the database -- **do not treat this Lead as reviewable**; its evidence chain is broken. Exit `1` with "No lead found" means the ID from 5.1 doesn't exist (a race with a concurrent purge/rollback -- re-run 5.1).
- **Blocks?** Yes for the individual Lead with a broken evidence chain (exclude it from sections 5.3-5.4); No for the overall review procedure.

### 5.3 Apply the manual quality checklist

For each Lead's `inspect-lead` output, check by hand:

- **Correct service category** -- `lead_type` matches what the reasoning and cited signals actually describe.
- **Correct location** -- county/municipality plausible for the cited signals.
- **Genuine homeowner intent** -- the intent score is backed by real evidence types, not a coincidental match.
- **Enough supporting evidence** -- the signals substantively concern the same opportunity (already structurally enforced to be `>= 2` and all `verified`; this check is about *relevance*, not count).
- **No fabricated information** -- every claim in `reasoning` traces to a field visible in the supporting-signals table.
- **Traceable source evidence** -- the `N/N found` count from 5.2 is complete.

Classify each Lead:
- **A -- sellable:** passes every item above, no reviewer doubt.
- **B -- manual review:** passes structurally but has a specific, articulable doubt.
- **C -- reject:** fails structurally, or has fabricated/unsupported claims.

- **Failure means:** n/a -- this is human judgment, not a command. A pattern of many Leads landing in C is a signal to revisit rule configuration or the collector's data quality (return to section 4), not something to fix by relaxing this checklist.
- **Blocks?** A/B Leads may proceed; C Leads must not be exported or handed off.

### 5.4 Formally verify and export only the Leads that passed

```bash
sigint verify lead <lead-id>       # for each A/B lead
sigint export --format csv
```
- **Expected output:** `verify lead` prints `Lead <id> verification result: verified` (or `rejected`, if `StructuralLeadVerifier` disagrees -- trust the automated check over a manual A/B call if it rejects), exit `0`. `sigint export` prints the CSV payload (or writes it with `--output`), containing only `VERIFIED` Leads, exit `0`.
- **Failure means:** `verify lead` reporting `rejected` for a Lead you classified A/B means its supporting signals changed state since 5.2 (e.g. one was rolled back) -- re-run `inspect-lead` to see why before treating this as a tooling bug.
- **Blocks?** Yes for handing off a specific Lead if it does not come back `verified`.

**Section 5 pass criterion:** every exported Lead is `VERIFIED`, was manually classified A or B, and every `inspect-lead` check in 5.2 showed a complete evidence chain.

---

## Overall pass/fail

Staging validation as a whole passes only if **all five sections above
pass in order**. A failure in an earlier section (especially 1-3) means
later sections are being run against an unproven foundation and their
results cannot be trusted -- do not skip ahead to "just check if the
collector works" without first clearing sections 1-3.

If every section passes: the answer to "can an operator safely deploy,
run, validate, and review LeadFinder without developer intervention?" is
**yes**, for the collector(s) actually exercised in section 4. Repeat
section 4 (only) for each additional collector before it is added to
`collectors.enabled` in production.

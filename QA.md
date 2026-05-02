# QA Methodology

## Timing Patterns

- Parallel CI builds complete in ~50-70s (backend/bot/frontend), ML ~6min, precommit ~7min
- Total CI-to-live: ≈4min for non-ML changes

## Browser QA

- Login credentials are auto-filled on the login page — just click "Sign In"
- All 6 pages to check: Dashboard, Sleep, Statistics, Trainings, Data Status, Settings
- Page routes are `/dashboard`, `/dashboard/sleep`, `/dashboard/statistics`, `/dashboard/trainings`, `/dashboard/data-status`, `/dashboard/settings`
- 401 on `/api/auth/me` at login page is expected (session check before login)

## Backend Logs

- `[ERROR] Control server error: Permission denied: '/home/appuser'` is cosmetic gunicorn issue, ignore
- Scheduler runs on its own deployment — check `deployment/life-as-code-production-scheduler` separately
- Bot and ML pods may have no recent logs — silence is normal

## Database Migrations

- Alembic autogenerate detects spurious index changes (DESC vs ASC) — manually clean migration to only include intended changes
- Check constraints (like `valid_sync_source`) are NOT auto-updated by autogenerate when adding new enum values — must be added manually to migration
- Always verify migration downgrade restores dropped/replaced constraints

## Sync Backoff

- Failed syncs trigger exponential backoff (0/20m/3h/24h/72h)
- Reset backoff: `DELETE FROM sync_backoff WHERE source = '<source>'`
- Check backoff status: `GET /api/sync/backoff-status`
- "Sync already in progress" (advisory lock contention) should NOT trigger backoff — it's normal during pod restarts when scheduler and backend race for the same lock

## Eight Sleep Integration

- Auth response may not include userId — the `/users/me` endpoint must be used as fallback
- Empty user ID in URL (double slash like `/users//trends`) means the user ID extraction failed
- API response structure may nest user data under a `"user"` key
- Stored access tokens expire silently — `_ensure_authenticated()` must receive `token_expires_at` from DB, and all API calls must use `_request_with_reauth()` for automatic 401→re-authenticate→retry
- Unlike Whoop (OAuth refresh token), Eight Sleep uses email/password — re-authentication always possible without user intervention
- Eight Sleep data (HRV, HR, sleep duration, deep/REM/light, respiratory rate, score, bed/room temp) feeds into the fusion layer alongside Garmin and Whoop
- New data sources must be added to: `RawHealthData` fields, `load_raw_health_data` queries, `SOURCE_PRIORITY`, fusion functions, `FusedMetric`/`FusedHealthData`, frontend `METRIC_REGISTRY`, `TRENDS_METRIC_KEYS`, AND all `MultiProviderLineChart` consumers (HRVChart, HeartRateChart, SleepChart, etc. + DashboardOverview props)
- `MultiProviderLineChart` supports optional third source via `eightSleepLabel`/`eightSleepValue` — bar only renders when data exists (`hasEightSleep` check)
- Frontend `metric_baselines` and `raw_series` are `Record<string, ...>` — new keys auto-surface in Statistics page without schema changes

## Testing Infrastructure

- Integration tests need a real PostgreSQL — CI has its own test DB, local dev needs port-forward
- API tests (test_api.py) call `exit(1)` if DB connection fails — they cannot run without a database
- 18 analytics tests pass locally without DB; API tests require `TEST_DATABASE_URL` env var

## SonarCloud

- No OpenAPI spec available — skip Schemathesis for this project
- Main code smell hotspot: `frontend/src/lib/report-formatter.ts` — complex string formatting logic
- Quality gate typically passes (no bugs/vulnerabilities pattern)
- `python:S5713` on `pull_garmin_data.py` exception tuples is a false positive — garminconnect exceptions have no inheritance relationship; ignore
- `typescript:S7735` ("Unexpected negated condition"): fix `value !== null ? expr : default` → `value === null ? default : expr`; conjunctions (`!== null && condition`) are NOT flagged

## PWA Updates

- PWA auto-updates silently when new version detected — no user prompt
- During rollout, "Request failed:" may flash on login page — transient, resolves after backend pod is ready
- Playwright browser caches old SW — need manual "Update now" click on first visit after deploy, then auto-update works

## Recharts Charts

- `ResponsiveContainer` with `height="100%"` collapses to 0 when parent has no explicit height — always use `height={number}` for chart containers inside `ChartCard`
- Tooltip `formatter` prop: never use explicit `(value: number)` — Recharts types expect `number | undefined`

- Use inferred types: `formatter={(value, name) => ...}` like existing charts
- `formatDateTick` doesn't exist — use inline `(value: number) => format(new Date(value), "MMM d")`

## Accessibility

- Login page must use `<main>` landmark to satisfy axe `region` rule
- Crawler `button-name` violations can be intermittent (timing-dependent dynamic rendering) — run crawler twice if critical appears
- `nested-interactive`: Radix `Button asChild` + `<a>` triggers this — use styled `<a>` directly instead
- `heading-order`: `CardTitle` renders `<h2>` (was `<h3>`) — page heading is `<h1>`, then card titles `<h2>`, then subsection `<h3>`
- `color-contrast` on chart SVG text (Recharts) — library-generated, not actionable; focus on non-chart violations
- `/whoop/authorize` is an OAuth redirect to external domain — exclude from crawler via `crawler-exclude-urls`

## Authenticated Crawler

- QA test user `qa-autoqa@test.com` exists in prod for crawler login
- GH secrets `QA_USERNAME` and `QA_PASSWORD` configured for CI post-deploy-qa job
- Crawler uses form login: `CRAWL_USERNAME`, `CRAWL_PASSWORD`, `CRAWL_LOGIN_URL=/login`
- Without auth, crawler only visits login page (1 page); with auth, all 6 dashboard pages crawled

## Research Environment

- `research/` changes do NOT trigger Docker image rebuilds — backend/frontend/ML images stay at previous SHA
- SonarCloud analyzes `research/` Python files — `dict()` constructor calls (S7498), `np.where` vs `np.nonzero` (S6729) are common findings in notebook code
- S2115 (password in DB URL): avoid hardcoded connection strings with empty passwords in defaults — use env var with empty string fallback
- connectorx does NOT support parameterized queries (`execute_options` with params) — use validated identifiers + int cast instead
- Dependabot may fail on `research/pyproject.toml` if chronos-forecasting pins transformers to `<5` and Dependabot tries to bump to 5.x — this is expected, not actionable

## Color Contrast (a11y)

- shadcn/ui default `--muted-foreground` (46.9% lightness) on `bg-muted` (#f1f5f9) gives ~4.3:1 — below AA threshold
- Fix: reduce lightness to 42% for reliable ≥4.5:1 on both white and muted backgrounds
- CI axe may find issues local axe doesn't — headless Chrome color scheme differences
- `color-contrast` violations are global (75 nodes across all pages) when caused by CSS custom properties — fix the variable, not individual elements
- `opacity-60` on a parent silently kills child contrast — axe reports the *effective* mixed color, not the underlying values. If a badge inside an `opacity` wrapper fails contrast, raise opacity to 100% (or remove it) and pick a stronger token (e.g. `--brass-deep` instead of `--brass`) for small text on bone backgrounds.
- `bg-green-600 text-white` ≈ contrast 2.06 — Tailwind's `green-600` is too light for white text. Use a deeper token (`--moss` ≈ `108 20% 27%`) instead.

## SonarCloud Patterns

- `typescript:S5852` (regex backtracking): Sonar flags any `.+?\s*` or similar lazy quantifier even when input is short/safe. Fix by replacing regex parsing with manual char-class scan or `String.trimEnd()` — extract a shared util like `splitValueUnit` to avoid copy-paste.
- `typescript:S2245` (Math.random): pseudorandom is flagged everywhere. For DEV-only mock data generators (gated by `import.meta.env.DEV`), bulk-mark as SAFE via `POST /api/hotspots/change_status` with comment explaining gate.
- `typescript:S5725` (SRI on external CSS): Google Fonts URL is dynamic — SRI hash would invalidate on each font update. Mark as SAFE; ensure `crossorigin` is set.
- `typescript:S6767` (unused PropTypes): when removing visual props (e.g., avatar `shortName`/`colorClass` after editorial reskin), remove from BOTH the interface AND every JSX call site — Tailwind/CVA won't catch this, only tsc strict mode does.
- `typescript:S7748` (zero fraction): `14.0` → `14`, `19.0` → `19`. Mass-fix with `perl -i -pe 's/\b14\.0([^0-9])/14$1/g'`.
- `typescript:S7764` (prefer globalThis): `window.localStorage` → `globalThis.localStorage`, `typeof window` → `typeof globalThis.window`. Affects every browser-only guard.
- `typescript:S7755` (prefer .at()): `arr[arr.length - 1]` → `arr.at(-1)` (returns `T | undefined` — handle the undefined case explicitly).

## Demo Mode for Frontend QA

- DEV-only `?demo=1` query installs a fetch interceptor + sets fake auth — useful for visual verification of pages that need backend data when running frontend-only.
- Mock shapes MUST match real API exactly: `getDetailedWorkouts` returns `WorkoutExerciseDetail[]` not `{ workouts: [] }`. `longevity/interventions` returns array directly. Always `grep "request(\"/path"` in `lib/api.ts` for the return type signature before mocking.
- When extending demo-mode for new pages, mock `analytics_response` with explicit nested fields (not partial); pages access deep paths like `health_score.steps_status.use_today` that crash on undefined.

## Editorial Reskin Migration

- Swapping the design system (palette, typography, hairlines) is safe IF: (a) base color tokens get redefined in `index.css` with same names so all `text-foo`/`bg-foo` keep working, (b) shared atoms (Card, Button) update CVA classes but keep variant prop names so callsites don't break.
- Health metric color tokens (`--hrv`, `--sleep`, etc.) can be collapsed to a luxury palette (ink+brass+moss+rust) by overriding their HSL values; Recharts auto-picks up the new colors via `hsl(var(--xxx))` references.
- Window-exposed Zustand store via `import.meta.env.DEV` guard is safe and tree-shakes out of prod.
- When reverting a redesign, knip flags orphaned files in `src/components/<theme>/` AND the now-used files in knip.json ignore list — delete unused tsx in the same commit AND remove now-used files from `knip.json#ignore[]`.

## Pre-commit Recovery

- Pre-commit stashes unstaged changes to `~/.cache/pre-commit/patch<timestamp>-<pid>` before running hooks; if a commit attempt is interrupted by the user, the stash is restored — but if the stash gets stuck, manually `git apply ~/.cache/pre-commit/patch...` to recover working-tree changes.

## Bootstrap Pattern (Critical)

- `src/database.py:init_db()` MUST stamp `alembic_version` to head after `create_all()` for fresh databases — otherwise the next `alembic upgrade head` fails on migrations that ALTER tables created by `create_all()` (no initial schema migration exists in this project).
- Verified by `tests/test_db_bootstrap.py`: fresh DB → init_db → `alembic current` shows head → `alembic upgrade head` is no-op.

## Bot Persistence

- Telegram bot conversation history is persisted to `bot_messages` table (JSONB content blocks for Anthropic tool-use replay; soft-delete via `cleared_at` for /clear); chat_id is BigInteger (Telegram supergroup IDs exceed 32-bit signed).
- Hydration filters tool_use/tool_result blocks — replaying them through Anthropic API requires strict pairing, so only plain text user/assistant messages are restored to the in-memory window.
- Bot pre-sync calls `scheduler._sync_and_recompute` via `asyncio.to_thread()` — the bot pod's Dockerfile copies all `src/` (including `pull_*.py`) and base deps include `garminconnect`/`requests`, so the import works in the bot container.

## Type Checker Discrepancies

- Pyright + SQLAlchemy stubs flag `column == value` comparisons in asserts as "Invalid conditional operand of type ColumnElement[bool]" — false positive at runtime (ORM instances return Python primitives). Project CI uses mypy with sqlalchemy plugin, not pyright; suppress per-file via `# pyright: reportGeneralTypeIssues=false` in test files.
- ESLint `@typescript-eslint/no-unnecessary-condition` vs Sonar `typescript:S7741`: both fire on `globalThis.window === undefined` (TS sees Window as always defined). For Vite SPA (no SSR), remove the SSR-safety guard entirely instead of either typeof check or `=== undefined`.
- mypy `strict` flags `cast(int, msg.id)` as "Returning Any" because SQLAlchemy 2.0 ORM `id` access on flushed instances returns int but stubs declare `Mapped[int]`. Use a typed local `rowcount: int = ...` for `.update()` returns; for ORM `.id` access, just `return msg.id  # type: ignore[no-any-return]` is cleanest if mypy still complains.

## SonarCloud Patterns (additional)

- `python:S6437` (compromised password) fires on `password=<literal>` keyword args even for known-test passwords like "testpass" — wrap with `os.environ.get("POSTGRES_PASSWORD", "testpass")  # noqa: S105` to bypass.
- `python:S3776` cognitive complexity on type-dispatch functions (e.g. `flatten_text(content: str | list)`) — extract per-branch handlers (`_flatten_dict_block`, `_flatten_object_block`, `_flatten_block` dispatcher) so each is below 15.
- `python:S3776` on long parsers (e.g. `EightSleepSessionData.from_api_response`): extract one-shot side effects (`_log_payload_shape_once`) and multi-shape field probes (`_extract_fitness_score`) into separate classmethods. Each branch returning `score` early eliminates a nested `if` increment.
- `python:S1854` (dead store) on test fixtures with two consecutive `bad = SleepIndexInputs(...)` blocks — flatten to a single inline `compute_sleep_index(SleepIndexInputs(...))` call and capture the result. Do NOT keep the first one as "documentation".
- `typescript:S6819` (dialog role on div): for transient popovers without focus-trap/aria-modal, just remove `role="dialog"` — don't migrate to `<dialog>` element since that requires `showModal()` and changes default styling/behavior. The trigger button's `aria-expanded` carries enough semantics for a popover.

## Crawler EXCLUDE_URLS Bug (autoqa pre-0781377)

- Older `nikolay-e/autoqa` releases only checked `CRAWL_EXCLUDE_URLS` for response status codes (4xx/5xx filtering), NOT for navigation. So OAuth redirect paths like `/whoop/authorize` were still visited (and timed out at 30s) even when listed in `crawler-exclude-urls`. The fix gates both `crawlPage()` entry AND `extractLinks` enqueue with `isExcluded()`. When seeing `ERR /<oauth-path> | timeout` in the post-deploy-qa job, check the autoqa SHA pinned in `.github/workflows/ci.yml` and bump if needed.

## Sonar / Pyright Diagnostic Spam During QA

- After editing files in `src/`, the editor's Pyright LSP fires reportAttributeAccessIssue on every SQLAlchemy `Column[T]` assignment in the file — these are NOT actionable findings, project CI uses mypy with sqlalchemy plugin. Run `.venv/bin/mypy <file>` to confirm "Success: no issues found" before treating the file as broken. The pyright stream looks scary but is mostly noise.

## Range/Mode Switching — Timing Reproduction

- The `Today/6W/6M/2Y/5Y` reactivity check from earlier in this doc DOES require ~8s wait per range click, NOT 3.5s. With 3.5s, all of `6M/2Y/5Y` show identical KPIs because React Query's `keepPreviousData` keeps the stale data on screen while the cold-cache query is in flight. This is a TEST ARTEFACT, not a bug — verified by hitting `/api/analytics?mode=quarter|year|all` directly: each returns different `short_term_mean` values. Always wait long enough OR use `page.waitForResponse(r => r.url().includes('mode=<expected>'))`.

## Pre-commit Reformats Twice

- `pre-commit` (black/ruff/prettier) may reformat staged Python/TS files on FIRST commit — the commit succeeds but leaves a fresh dirty working tree. Re-stage and re-commit (no need to amend). This produces two adjacent commits where the second only contains formatter cleanups. Fine to leave both on `main`; squashing isn't worth the rebase risk.

## ArgoCD Image Updater — Per-Image Rollout

- Image Updater detects new tags PER IMAGE (backend, frontend, ml, bot are separate streams). After a single push to main, all four images build in parallel but Image Updater picks them up at slightly different times — expect ~2-5 min of mixed-version state where, e.g., `bot:main-afa12e8` is live but `backend:main-721cce1` lingers. The deployments are independent (no cross-image protocol versioning), so this is safe; just don't read CD as "stuck" when only some images updated.

## Playwright MCP — Stuck Browser Recovery

- "Browser is already in use for /Users/.../mcp-chrome-<hash>, use --isolated" means a previous MCP session left a Chromium owning `SingletonLock` in the cache profile dir. The symlink target is the holder PID. Verify with `lsof -p <pid> | grep -c <profile-dir>` (a real holder shows 100+ open handles in that dir). Kill with `kill <pid>` — safe because the MCP browser lives strictly under `~/Library/Caches/ms-playwright/mcp-chrome-*` and never touches `~/Library/Application Support/Google/Chrome`. After kill, the SingletonLock symlink disappears and `mcp__playwright__browser_navigate` works again on the next tool call.

## Dash / "—" Placeholder Audit (MANDATORY)

When user data should populate but doesn't, the UI shows `—` / `–` / `N/A`. The cause is almost always one of three:

1. **Schema drift**: frontend reads a key the backend never returns (or stopped returning). React's optional chaining swallows the missing key silently.
2. **Backend data dict skip**: `_compute_metric_baselines` (and similar dict-builders) iterate an input dict and `if not data: continue` — if a key wasn't put into the input dict at all, the baseline is missing entirely (different from "computed but null").
3. **Upstream sync produces NULLs**: provider API renamed the field, our parser still looks at the old path → DB column always NULL → frontend correctly shows `—`.

**Reproduction script (Playwright MCP):**

```js
async (page) => {
  // Walk all pages and report any cell whose text is exactly the dash glyph or N/A
  const pages = ['/dashboard', '/dashboard/sleep', '/dashboard/statistics', '/dashboard/trainings', '/dashboard/data-status', '/dashboard/settings', '/dashboard/health-log'];
  const out = {};
  for (const url of pages) {
    await page.goto(`https://life-as-code.com${url}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);
    out[url] = await page.evaluate(() => {
      const dashes = [];
      const all = Array.from(document.querySelectorAll('span, p, td, dd, h2, h3, h4, [class*="text-2xl"], [class*="text-3xl"]'));
      for (const el of all) {
        const t = (el.textContent || '').trim();
        if (t === '—' || t === '–' || t === 'N/A' || t === 'n/a') {
          const label = el.parentElement?.querySelector('p, span, h3, h4')?.textContent?.trim().slice(0, 50)
            || el.previousElementSibling?.textContent?.trim().slice(0, 50)
            || (el.parentElement?.textContent || '').trim().slice(0, 80);
          dashes.push({ value: t, label });
        }
      }
      return dashes.slice(0, 30);
    });
  }
  return JSON.stringify(out, null, 2);
}
```

**RCA procedure:**

1. List the labels reporting `—` (e.g. `Sleep Score`, `Sleep Fitness`, `Cardio`, `Zone 2 (7d)`).
2. Locate the frontend reads:

   ```bash
   grep -rn '<label-key-or-related>' frontend/src/
   ```

3. For each, hit the API directly from the authenticated session and inspect the actual response shape:

   ```js
   const r = await fetch('/api/analytics?mode=recent', { credentials: 'include' });
   const d = await r.json();
   d.metric_baselines?.sleep_score   // → undefined? null? present?
   d.longevity_insights?.longevity_score?.cardiorespiratory  // → null?
   ```

4. **Classify the cause:**
   - `undefined` (key missing from response) → backend dict-builder bug (e.g., not added to `_compute_metric_baselines`). **Code fix.**
   - `null` (key present, value null) → either (a) data really missing for the user, or (b) upstream sync extracts the wrong field. Run a DB query for the underlying column; if the column is always NULL, it's a sync parser bug.
   - Has value but UI shows `—` → frontend formatter has wrong null check (e.g., `value === undefined` instead of `value == null`).
5. **Test setting up:**
   - DB-column-always-NULL: investigate the provider sync extractor (`src/eight_sleep_schemas.py`, `src/pull_garmin_data.py`, etc.) — provider API field paths may have changed.
   - Backend dict-builder skip: add the missing key to the input dict alongside the corresponding raw data series.

**Known live drift cases (life-as-code, as of QA pass 2026-04-28):**

- `metric_baselines.sleep_score` was missing — backend `service.py` `_compute_metric_baselines` input dict didn't include `"sleep_score": raw.sleep_score_eight_sleep`. **Fixed.**
- `eight_sleep_sessions.sleep_fitness_score` column always NULL despite API providing it — `_to_session()` reads `day["health"]["sleepFitnessScore"]`, but Eight Sleep API may have moved the field. Worth re-validating against current upstream payload.
- `longevity_score.cardiorespiratory` and `training_zones.{zone2,zone5}_minutes_7d` are null when the user doesn't have recent cardio data. Genuine "no data" — not a code bug. Consider rendering an explicit "no recent data" message instead of `—` so it's distinguishable from schema drift.

## Range / Mode Switching — Data Reactivity Check (MANDATORY)

Pages with a Today/6W/6M/2Y/5Y/Custom (or recent/quarter/annual/lifetime) range selector MUST display different data when the user switches ranges. A bug where charts update but KPI/metric cards stay frozen is **invisible to the eye** unless verified — it usually means a hook is hardcoded to `"recent"` regardless of `selectedRange`.

**Reproduction script (Playwright MCP):**

```js
async (page) => {
  const ranges = ["Today", "6W", "6M", "2Y", "5Y"];
  const snapshots = {};
  for (const range of ranges) {
    const btnIdx = await page.evaluate((r) => {
      const all = Array.from(document.querySelectorAll('button'));
      return all.findIndex(b => b.textContent?.startsWith(r));
    }, range);
    await page.evaluate((i) => Array.from(document.querySelectorAll('button'))[i].click(), btnIdx);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2500);
    snapshots[range] = await page.evaluate(() => {
      const out = {};
      // Big metric numbers — top-of-page KPI cards
      document.querySelectorAll('.text-3xl, .text-2xl').forEach(el => {
        const card = el.closest('[class*="rounded"]') || el.parentElement?.parentElement;
        const title = card?.querySelector('p, span, h3, h4')?.textContent?.trim().slice(0, 40) || '';
        out[title || `v${Object.keys(out).length}`] = el.textContent?.trim().slice(0, 40);
      });
      // Chart axis (proves chart-side wiring is correct)
      out.__x = Array.from(document.querySelectorAll('.recharts-cartesian-axis-tick tspan')).slice(0, 6).map(e => e.textContent).join(' | ');
      return out;
    });
  }
  return JSON.stringify(snapshots, null, 2);
}
```

**Failure signature:** `Today`, `6W`, `6M`, `2Y`, `5Y` snapshots produce **identical KPI values** (e.g. `HRV: 35 ms` everywhere) while `__x` (chart X-axis dates) changes between ranges. → bug in the metric card data path, not the chart path.

**Common root cause:** `useAnalytics("recent")` hardcoded — should be `useAnalytics(modeMappedFromSelectedRange)`. ViewMode `"today"`/`"custom"` don't map cleanly to TrendMode; fall back to `"recent"` for those.

**Companion fix:** when range !== Today, the metric card's `value` should read `baseline.short_term_mean` (or `mean`), NOT `baseline.current_value` — `current_value` is the latest reading and identical on all ranges that include today.

**Test timing pitfall:** non-default modes (quarter/year/all) hit a cold backend cache and take longer than `recent`. A flat `waitForTimeout(3000)` after click can SHOW IDENTICAL VALUES across modes due to React Query's `placeholderData: keepPreviousData` masking the in-flight fetch — looks like a bug when it isn't, OR hides a real bug when it is. ALWAYS use `page.waitForResponse(r => r.url().includes('mode=<expected>'))` before sampling the DOM, not a flat sleep.

Add this Playwright check to any QA pass that touches `/dashboard`, `/dashboard/sleep`, or `/dashboard/statistics`.

## ML Insights — Contributing Factors Shape

- `analytics_response.ml_insights.ml_anomalies[].contributing_factors` is `Record<string, {value: number, z_score: number}>`, **not** `Record<string, number>`. Easy to misread as flat numbers — UI code that calls `value.toFixed(...)` will crash with `i.toFixed is not a function` and trip the React error boundary on the Statistics page.
- Sample: `{"avg_stress": {"value": 20, "z_score": -2.92}, "weight": {"value": 99.6, "z_score": 3.16}}`. When sorting by importance, sort by `Math.abs(factor.z_score)`. When rendering chips, format `factor.z_score`, NOT the wrapper object.
- The API endpoint `/api/ml/anomalies` and the inline `analytics_response.ml_insights.ml_anomalies` return the SAME shape — patch both consumers if you change the contract.

## pgbouncer + pg_advisory_lock — Lock Leak Pattern

- App uses `pg_try_advisory_lock(id)` inside a `with get_db_session_context() as lock_db:` block. SQLAlchemy returns the connection to the pool when the block exits, but pgbouncer (transaction-pooling mode) keeps the underlying physical connection open. **Session-level advisory locks survive across the pool boundary** — every subsequent sync attempt hits "Sync already in progress" because the lock is held by an idle connection.
- Symptom: `data_sync` table has NO rows with `status='in_progress'`, yet every sync attempt fails with "Sync already in progress for garmin/hevy". `pg_locks` shows `advisory ExclusiveLock granted=true` on an idle connection (state=idle, last query=ROLLBACK or COMMIT).
- Recovery: `kubectl exec -n shared-database shared-postgres-2 -- psql -U postgres lifeascode_production -c "SELECT pg_terminate_backend(pid) FROM pg_locks WHERE locktype='advisory';"` — kills the leaking connection, releases the lock. Restart of backend pod alone does NOT clear the lock (pgbouncer outlives the pod).
- Recovery also requires resetting `data_sync.status='error'` for any rows stuck at `in_progress` — sync_manager won't re-enter while one is `in_progress` even with the advisory lock free.
- Architectural fix would be either: (a) drop `pg_try_advisory_lock` and use a row-level lock in `data_sync` instead, or (b) configure pgbouncer for SESSION pooling for the app's connections (loses connection efficiency).

## Garmin Sleep API — Top-Level vs dailySleepDTO

- `garminconnect.get_sleep_data(date)` returns a structure where **most useful fields live at the TOP level**, not inside `dailySleepDTO`. dailySleepDTO contains stages (deep/light/rem/awake_minutes), totals, and sleep_score; everything else (body_battery_change, skin_temp_celsius, awake_count, sleep_quality_score, sleep_recovery_score, avgSpO2, lowestSpO2, averageRespiration) is at the response root.
- Original parser fed only `sleep_data["dailySleepDTO"]` to the schema — silently dropped 7 fields, leaving DB columns NULL forever.
- Fix: merge scalar top-level fields with dailySleepDTO before feeding the parser. Skip `dict`/`list` top-level subdocs (sleepLevels, sleepMovement, etc.) — those are time-series and not relevant to the daily summary.
- Audit signal: `respiratory_rate` populated 54/85 but `body_battery_change`/`skin_temp_celsius`/`awake_count`/`spo2_avg`/`spo2_min`/`sleep_quality_score`/`sleep_recovery_score` all 0/85 across all historical syncs. The fact that respiration worked at all came from one of its aliases happening to also exist in dailySleepDTO.
- Historical data does NOT backfill — the fix only populates new syncs. Run a 90-day re-sync (`POST /api/sync/garmin?days=90`) to backfill — `?full=true` is structurally fragile due to the long-held advisory lock (see pgbouncer pattern above).
- After top-level merge fix, body_battery_change went 0→86/237. After alias fix, awake_count went 0→2/237 (most days lack `awakeCount` in API response) and respiratory_rate 54→149/237.

## Garmin Sleep — Fields NOT Available

These DB columns CANNOT be filled from Garmin's `get_sleep_data` API alone:

- `skin_temp_celsius`: Garmin only returns `avgSkinTempDeviationC` (deviation from baseline, e.g., -0.5/+0.3), NOT absolute temperature. Mapping it to `skin_temp_celsius` is wrong (validator rejects 0-25 range anyway). Either add a new `skin_temp_deviation_c` column or accept this is Eight Sleep / wearable-specific.
- `sleep_quality_score`, `sleep_recovery_score`: Garmin's `sleepScores` is a dict of per-component qualifiers (`lightPercentage.value`, `deepPercentage.value`, `restlessness.value`, `overall.value`) — no single "quality" or "recovery" aggregate. These columns are populated by Eight Sleep / Whoop syncs, not Garmin.
- `spo2_avg`, `spo2_min`: NOT in `get_sleep_data` response. Requires separate `g.get_spo2_data(date)` API call. Currently un-wired in `pull_garmin_data.py`. To populate, add a new sync method that fetches SpO2 per day and updates the sleep row.

## treemapper --diff Caveats

- `treemapper . --diff <from>..<to>` doesn't always honour the diff filter and may dump the entire tree (~300k tokens). For code review of a specific commit range, prefer `git diff <from>..<to> --stat` then targeted `git diff <from>..<to> -- <file>` instead. Faster, cheaper, safer for context.

## SonarCloud Patterns (additional, batch from this pass)

- `typescript:S6959` (BUG: reduce without initial value): `arr.reduce((a, c) => ...)` flagged as MAJOR/BUG — every reduce needs an explicit initial value. For "find best of array" patterns, do `arr.reduce<T>((best, cur) => ..., arr[0])` after an empty-check guard. This is a `new_reliability_rating` quality-gate failure (single BUG flips A→C).
- `typescript:S4144` (identical functions): adding two `handleDelete = (id, name) => remove.mutate(...)` in same file across two unrelated tab components triggers this. Extract a top-level `makeDeleteHandler(remove)` factory — keeps both call sites clean and removes the dup.
- `typescript:S3776` cognitive complexity: extracting per-field pickers (`pickGarminPace`, `pickElevationGain`, etc.) is the cleanest reduction. Each picker handles its own null guard and returns `string | null`; the assembler just pushes non-null. Beats inlining all conditions in one function.
- `typescript:S3358` (nested ternary): inside JSX className/template literal interpolation: extract toneClass / arrowIcon / labelText helpers and call them inline. For "isPending ? 'Saving...' : initial ? 'Update' : 'Save'" extract a `submitLabel(isPending, initial)` helper.
- `typescript:S7735` (negated condition): `value !== null ? expr : default` → `value === null ? default : expr`. Conjunctions with `&&` are NOT flagged. The `??` operator is preferred where it works (for null-defaulting strings).
- `typescript:S4624` (nested template): `\`${qs ? \`?${qs}\` : ""}\`` flagged. Extract: `const path = qs ? \`/foo?${qs}\` : "/foo"; return request(path)`.
- `@typescript-eslint/no-base-to-string`: `String(value)` on `unknown` triggers it. Wrap with explicit type narrowing: `typeof v === "string" || typeof v === "number" || typeof v === "boolean" ? String(v) : JSON.stringify(v)` — extract to a util function, otherwise S3358 will flag the nested ternary.

## React Hooks — useState in useEffect

- `react-hooks/set-state-in-effect`: ESLint v9+ flags syncing prop→state via `useEffect(() => setX(prop), [prop])`. Replace with the "edits overlay" pattern: keep `state = { editValue: string | null, ... }` initialized to `null`, derive displayed value as `editValue ?? initialValueFromProp`, mutate via `setState((p) => ({ ...p, editValue: v }))`. Avoids the cascading-render warning AND eliminates a stale-state bug class.

## Pre-commit Reformat — Same File Twice

- When pre-commit reformats files during a commit, the commit succeeds (exit 0) but the formatted files appear as unstaged in `git status` immediately after. The `MM` flag in status output is the tell. Re-stage with explicit paths and re-commit — DO NOT amend. Pushing both commits is fine.

## Pyright vs mypy Discrepancy on api.py

- After editing `src/api.py`, the editor's Pyright LSP fires 10+ `reportAttributeAccessIssue` warnings on every SQLAlchemy `Column[T]` read/write (e.g., `creds.garmin_email = body.email`). Project CI uses mypy with the sqlalchemy plugin which understands these as ORM columns. Always verify with `.venv/bin/mypy src/api.py` before treating as a real failure — the pyright noise is consistent and not actionable.

## ArgoCD Image Updater — Force Refresh Pattern

- Image Updater can lag 1-3 min after CI build completes. To accelerate during QA: `kubectl annotate application life-as-code-production -n argocd argocd.argoproj.io/refresh=hard --overwrite`. Then poll `kubectl get deployment .../backend -o jsonpath='{.spec.template.spec.containers[0].image}'` until tag changes.
- Don't manually patch the deployment image — Image Updater will revert on next sync. Refresh is the only correct accelerator.

## SQLAlchemy `reset` Event + DISCARD ALL — Transaction Block Gotcha

When wiring a `@event.listens_for(engine, "reset")` handler that runs `DISCARD ALL` to clean session state for pgbouncer compatibility (releases advisory locks, prepared statements, temp tables, SET vars), you MUST `dbapi_connection.rollback()` BEFORE the cursor.execute. Without it, every request triggers `psycopg2.errors.ActiveSqlTransaction: DISCARD ALL cannot run inside a transaction block` → connection gets invalidated → pool thrash. Backend stays "Running" but every API call burns a connection. Symptom: hundreds of `connection_invalidated` warnings per minute, DISCARD never runs, leaked locks (which DISCARD was meant to release) still accumulate. Fix:

```python
@event.listens_for(engine, "reset")
def _reset(dbapi_conn, _record, _state):
    dbapi_conn.rollback()  # MUST come first
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("DISCARD ALL")
    finally:
        cursor.close()
```

## Sync Lock — Atomic UPSERT vs pg_advisory_lock

`pg_try_advisory_lock` + pgbouncer transaction-pooling = guaranteed leak (see ANALYSIS.md). The session-level lock survives the pool reset because `pool_reset_on_return='rollback'` (the SQLAlchemy default) only issues `ROLLBACK`, not `DISCARD ALL` or `pg_advisory_unlock_all`. Replacement pattern: atomic UPSERT against `data_sync` table with a WHERE clause that checks for stale (>30 min) `last_sync_timestamp`. Fully pgbouncer-friendly because no session state is held; the "lock" lives in the row itself. See `_try_claim_sync_slot` in `src/sync_manager.py` for reference.

## Alembic Migration Drop-Column Gotcha

When dropping columns the app no longer references (e.g. confirmed-dead `sleep_quality_score`, `sleep_recovery_score` on `sleep` table that were intended for Eight Sleep but actually live in `eight_sleep_sessions`):

1. Drop the column ref in `src/models.py` AND the Pydantic schema (`src/garmin_schemas.py` field + alias entries + any field_validator)
2. Drop the column ref in `frontend/src/types/api.ts` SleepData interface
3. Drop UI usage in any `*Page.tsx` that read it via `pickSleepLatestField(sleep, "sleep_quality_score")`
4. Vulture will flag now-unused icon imports — clean those (`Heart`, `Sparkles` were used only for these fields)
5. Pre-commit will fail until vulture passes — re-stage and recommit

Order matters: schema/model BEFORE migration (otherwise mypy chokes on stale field refs at commit time). The migration itself is the LAST thing to write, so it reflects the final shape.

## Tailwind Contrast Cheatsheet (1Password-Verified)

White text on Tailwind 600/700/800 colored bg:

| Class | Contrast | Verdict |
|-------|----------|---------|
| `bg-green-600 text-white` | ~2.02 | FAIL |
| `bg-green-700 text-white` | ~3.5  | FAIL for normal text |
| `bg-green-800 text-white` | ~5+   | OK (also OK with parent `opacity-60`?) — NO, parent opacity drops effective contrast below threshold; remove the wrapper opacity entirely |

Colored text on white:

| Class | Contrast | Verdict |
|-------|----------|---------|
| `text-red-500` (#ef4444) | ~3.76 | FAIL for text |
| `text-red-700` (#b91c1c) | ~5.9  | OK |
| `text-green-500` (#22c55e) | ~2.0 | FAIL |
| `text-green-600` (#16a34a) | ~3.21 | FAIL |
| `text-green-700` (#15803d) | ~4.55 | OK (borderline) |
| `text-yellow-600` (#ca8a04) | ~2.93 | FAIL |
| `text-yellow-700` (#a16207) | ~4.8 | OK |

**Rule:** for STATUS TEXT use 700+. For ICONS (h-4 w-4) the 3:1 non-text rule applies, so 500 is OK.

Wrapper `opacity-60` from version-info / footer kills child badge contrast — axe reports the *effective* mixed color. Remove the wrapper opacity; if you need a "subdued footer" effect, use `text-muted-foreground` for the surrounding plain text only, NOT a wrapper opacity that bleeds into colored badges inside.

`text-[10px] opacity-70` on a `bg-primary` button (default variant) → 3.23 contrast. Bump opacity-90 still fails (4.31). **Remove opacity entirely** — the 10px font-size carries the visual hierarchy on its own.

Project's `--destructive` HSL token: `0 84.2% 60.2%` ≈ red-500 — too light for AA. Use `0 72% 42%` ≈ red-700.

## Pre-commit ruff-format CI vs Local Drift

- Pre-commit hook on local commit only formats STAGED files. CI runs `pre-commit run --all-files` which also re-formats files outside the diff. After bumping `line-length` in `research/pyproject.toml` (or any ruff config change), run `uv run ruff format --check src research/src` from repo root before push — drift in untouched files (e.g. `research/src/export.py`) will fail CI's `pre-commit run --all-files` even though local file-by-file pre-commit on commit succeeded.

## Garmin Stress — rest_stress / activity_stress Always NULL

- Garmin `get_stress_data` API returns DURATIONS (seconds in low/medium/high/rest/activity stress ranges), not 0-100 LEVELS. The Pydantic mapping `restStressLevel` / `activityStressLevel` finds nothing because those fields don't exist in the response. Fields `rest_stress` and `activity_stress` columns in DB are 100% NULL across all historical syncs.
- Frontend fix: hide these stress sub-cards conditionally (`{latest.rest_stress !== null && (...)}`) — better than showing perpetual `—`. Avg Stress + Max Stress are the only Garmin-derivable values.
- Real fix would require either remapping to durations (e.g. `restStressDuration` in seconds → minutes percentage) or accepting that these columns will only populate from Whoop/Apple Watch.

## SonarCloud — Path Traversal S2083 (BLOCKER)

- `Path(args.output)` from CLI argparse triggers `pythonsecurity:S2083` BLOCKER and breaks the `new_security_rating` quality gate (single BLOCKER → rating E).
- For dev tools where output path defaults to a fixed location (e.g. `Path(__file__).parent.parent / "RESULTS.md"`), simplest fix is to remove the `--output` CLI override entirely. Don't try to validate the path — Sonar's taint tracking won't accept resolve()/is_relative_to() guards inline.

## SonarCloud Cognitive Complexity in Research/Stats Code

- Statistical methods (Box-Jenkins prewhitening, ICC(2,1), Kruskal-Wallis with multi-metric loops, ANOVA factor decomposition) often score S3776=20-50 because they have multiple if-branches and per-factor accumulation. These are inherent algorithmic complexity, not refactor opportunities.
- Pragma: extract per-branch helpers ONLY if it preserves the math semantics. Otherwise leave as-is — Sonar S3776 in research code is acceptable noise that does NOT block the quality gate (it affects `maintainability_rating`, not `reliability` or `security`).
- S3776 in dummy-matrix builders (month/weekday/epoch): extract `_month_dummies`, `_weekday_dummies`, `_epoch_dummies` helper functions with signature `(arr, n) -> ndarray`. Each has one loop with one if → well below 15.
- S3776 in Kruskal-Wallis multi-metric loops: extract `_kruskal_stats(groups)` (handles 0/1/2+ group branching) and `_kruskal_row_for_metric(raw, m_canon)` so `run_kruskal_wallis` is just list-comprehension + two `_apply_fdr` calls.
- S3776 in quadrant chi2: extract `_classify_quad(r, h) -> str`, `_chi2_test_result(table, counts_b, counts_other, tert_labels, n_per_tert)` (handles chi2 / fisher-exact / skip branches), and `_strain_cross_tab(df, strain_col, win, snapshot)` — reduces `run_quadrant_chi2` from complexity 53 to ~10.
- S1871 (identical branches): when two `if`/`elif` branches both do `record[key] = None`, merge them: `if (isinstance(value, float) and not math.isfinite(value)) or value is pd.NaT:`.
- S3358 (nested ternary): extract the inner ternary to a named variable BEFORE the return — `resolved_start = start if start is not None else (min(...) if ... else None)` — adding parentheses does NOT satisfy Sonar.

## Mobile Navigation — Hidden Pages Pattern

- When adding new top-level pages, check BOTH the desktop sidebar AND the mobile bottom nav (`MobileBottomNav.tsx`). The bottom nav only renders `PRIMARY_ITEMS` (5 fixed slots). Pages exported only in `SECONDARY_ITEMS` become completely unreachable on mobile.
- Fix pattern: add a Settings icon link in the header (`md:hidden`, always visible) + add a "Data Status" row inside the Settings page (`md:hidden`, acts as mobile-only nav entry). Avoids 6-item bottom nav overflow.
- After any new page is added, manually verify all routes are reachable from a 375px-wide viewport before merging.

## Timezone-Aware DateTime — NaT Serialization Bug

- Adding `DateTime(timezone=True)` columns to SQLAlchemy models causes a 500 on any API endpoint that passes those rows through `_serialize_generic_df` + `sanitize_for_json` unless both handle NaT.
- `_serialize_generic_df` must expand its `select_dtypes` to include `"datetimetz"` and use `.apply(lambda x: x.isoformat() if pd.notna(x) else None)` for those columns (`.astype(str)` on a `NaT` produces the string `"NaT"`, not `None`).
- `sanitize_for_json` must check `value is pd.NaT` (in addition to `math.isfinite` for floats) and set `record[key] = None`.
- Symptom: `ValueError: NaTType does not support timetuple` in the serialization layer, 500 on `/api/data/range`.
- Trigger: any migration adding `sleep_start_time` / `sleep_end_time` or similar `timestamp with time zone` columns to a table that goes through the generic serializer.

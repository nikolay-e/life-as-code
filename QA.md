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

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

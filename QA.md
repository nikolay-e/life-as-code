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
- SonarCloud analysis runs on latest pushed commit; verify issues against current HEAD (not deployed image tag) — stale issues disappear after push
- `typescript:S7735` ("Unexpected negated condition"): fix `value !== null ? expr : default` → `value === null ? default : expr`; conjunctions (`!== null && condition`) are NOT flagged
- `typescript:S3358` ("nested ternary"): extract inner ternary to a named variable before the outer ternary
- `typescript:S3776` ("cognitive complexity"): extract inner loop bodies to named helper functions

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

## Research Environment

- `research/` changes do NOT trigger Docker image rebuilds — backend/frontend/ML images stay at previous SHA
- SonarCloud analyzes `research/` Python files — `dict()` constructor calls (S7498), `np.where` vs `np.nonzero` (S6729) are common findings in notebook code
- S2115 (password in DB URL): avoid hardcoded connection strings with empty passwords in defaults — use env var with empty string fallback
- connectorx does NOT support parameterized queries (`execute_options` with params) — use validated identifiers + int cast instead
- Dependabot may fail on `research/pyproject.toml` if chronos-forecasting pins transformers to `<5` and Dependabot tries to bump to 5.x — this is expected, not actionable

## K8s Events

- Migration pod warnings (FailedToRetrieveImagePullSecret, secret not found) are transient — check exitCode, not events
- Migration pod with exitCode 0 and status Completed = success despite warning events

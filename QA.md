# QA Methodology

## Timing Patterns

- Parallel CI builds complete in ~50-70s (backend/bot/frontend), ML ~6min, precommit ~7min
- ArgoCD Image Updater picks up new images within 2-3min after CI build completes
- Pod rollout takes ~30s after Image Updater updates the deployment
- Total CI-to-live: builds ~1min + Image Updater ~2min + rollout ~30s ≈ 4min for non-ML changes

## Browser QA

- PWA aggressively caches — always click "Update now" toast before testing new version
- Verify version in footer (`vmain-<sha>`) matches target commit before testing
- Playwright session cookies don't persist across `browser_navigate` — login immediately before the page you need to test
- Login credentials stored in 1Password: `op item get "Admin Life As Code" --fields password --reveal`
- 401 on `/api/auth/me` during login page load is expected (session check), not an error

## Backend Logs

- Filter by `--since=5m` to avoid noise from pod init
- `[ERROR] Control server error: Permission denied: '/home/appuser'` is cosmetic gunicorn issue, ignore
- Scheduler runs on its own deployment — check `deployment/life-as-code-production-scheduler` separately

## Database Migrations

- Alembic autogenerate detects spurious index changes (DESC vs ASC) — manually clean migration to only include intended changes
- Check constraints (like `valid_sync_source`) are NOT auto-updated by autogenerate when adding new enum values — must be added manually to migration

## Sync Backoff

- Failed syncs trigger exponential backoff (0/20m/3h/24h/72h)
- Reset backoff: `DELETE FROM sync_backoff WHERE source = '<source>'`
- Check backoff status: `GET /api/sync/backoff-status`

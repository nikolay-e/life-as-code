# life-as-code

> Extends [../CLAUDE.md](../CLAUDE.md)

## Ultimate Goal

**Build software that helps people live to 150 years.**

Every feature, metric, and insight in this platform serves one mission: give people the data and tools to understand their biology deeply enough to extend healthy human lifespan to 150 years. Longevity is not a side effect — it is the purpose.

Privacy-first, multi-user health analytics platform aggregating Garmin, Hevy, and Whoop data.

## Tech Stack

- **Backend**: Python, Flask, Dash (Plotly)
- **Frontend**: TypeScript, React, Vite
- **Database**: PostgreSQL (shared K8s cluster)
- **Infrastructure**: Kubernetes (K3s), Helm, ArgoCD
- **Security**: Fernet encryption, bcrypt, Flask-Login

## Deployment

Production runs in Kubernetes via GitOps (ArgoCD). No local Docker development.

- **Namespace**: `life-as-code-production`
- **Pods**: backend, frontend, scheduler, ml, bot
- **DB**: `shared-database` namespace, `shared-postgres-rw` service
- **Secrets**: `life-as-code-production-secrets` (K8s secret)
- **PVC**: `life-as-code-production-garminconnect` (Garmin OAuth token cache)

### Common Commands

```bash
# View logs
kubectl logs -n life-as-code-production deployment/life-as-code-production-backend --tail=100
kubectl logs -n life-as-code-production deployment/life-as-code-production-scheduler --tail=100

# Database access
kubectl port-forward -n shared-database svc/shared-postgres-rw 5433:5432
psql -h localhost -p 5433 -U lifeascode_production -d lifeascode_production

# Run migrations
DATABASE_URL="postgresql+psycopg2://..." .venv/bin/python -m alembic upgrade head

# Restart a component
kubectl rollout restart deployment/life-as-code-production-scheduler -n life-as-code-production

# Check ArgoCD sync status
kubectl get application life-as-code-production -n argocd -o jsonpath='{.status.sync.status}'
```

## Data Sources

- **Garmin Connect**: Sleep, HRV, heart rate, weight, body composition, stress, training status
- **Hevy**: Workout sets, exercises, weights, RPE
- **Whoop**: Recovery, strain, sleep performance, workouts

## Architecture

```text
src/
├── app.py          # Flask entry point
├── models/         # SQLAlchemy models
├── routes/         # Flask routes
├── services/       # Data sync, analytics
└── utils/          # Helpers
```

### Single-Admin Model

- **Default admin** created automatically from environment variables on first startup
- **Credentials managed** through environment variables (no GUI editing for security)
- **Encrypted storage** of service credentials (Fernet per-user encryption)
- **Bootstrap script** creates admin user idempotently on each startup

### Key Tables

Users → UserCredentials (encrypted API keys) → health data tables (Sleep, HRV, Weight, HeartRate, Stress, Energy, Steps, WorkoutSet)

## Environment Variables

### Required

```bash
# Database
POSTGRES_USER=life_as_code_user
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=life_as_code
DATABASE_URL=postgresql+psycopg2://life_as_code_user:<password>@db:5432/life_as_code

# Application Security
SECRET_KEY=<secrets.token_hex(32)>
FERNET_KEY=<Fernet.generate_key().decode()>

# Default Admin User
ADMIN_USERNAME=admin@example.com
ADMIN_PASSWORD=<strong-password-min-16-chars>
```

### Optional (Service Credentials)

```bash
# Garmin Connect
GARMIN_EMAIL=your-garmin-email@example.com
GARMIN_PASSWORD=your-garmin-password

# Heavy
HEVY_API_KEY=your-hevy-api-key

# Whoop OAuth
WHOOP_CLIENT_ID=<client-id>
WHOOP_CLIENT_SECRET=<client-secret>
```

## Sync Flow

1. **Credentials configured** through Kubernetes secrets
2. **Bootstrap script** creates default admin user and populates credentials on startup
3. **Login** with admin credentials to access dashboard
4. **Click "Sync" buttons** in Settings to import data from Garmin/Hevy
5. **Dashboard updates** with new health metrics
6. **AI Daily Briefings** generated from aggregated data

### Credentials Management

**For Security:**

- Credentials are **NOT editable** through the web UI
- Settings page shows **read-only status** of configured services
- To update credentials: **modify Kubernetes secrets** in production, then restart the relevant pod

**Bootstrap Process:**

```text
Environment Variables → Bootstrap Script → Admin User + Encrypted Credentials → Database
                                                                              ↓
                                                            Sync Services (Garmin, Hevy, Whoop)
```

## Statistics & Trends Requirements

### Trend Modes

All statistics MUST recalculate based on selected mode:

| Mode | Short-Term | Baseline | Trend Window | Description |
|------|-----------|----------|--------------|-------------|
| Short | 7 days | 84 days (12w) | 7 days | Daily fluctuations |
| Mid | 28 days | 252 days (9mo) | 14 days | Weekly trends |
| Long | 90 days | 730 days (2yr) | 30 days | Long-term patterns |

### Today's Data Handling

**Critical Rule:** Today's incomplete data must be handled differently across views:

| Page | Today Included | Reason |
|------|----------------|--------|
| Health Dashboard (Today selected) | **YES** | User explicitly requests current snapshot |
| Health Dashboard (other ranges) | **NO** | Exclude incomplete day from statistics |
| Trends Page | **NO** | Always exclude today for accurate baselines |

**Implementation:**

- `useHealthData(days, excludeToday)` - backend query excludes today when `excludeToday=true`
- `getSeries(def, data, now, forceToday)` - skips `shouldUseTodayMetric` filtering when `forceToday=true`
- `shouldUseTodayMetric()` - checks day completeness for accumulating metrics (steps, calories, strain, stress)

### Metric Functions Requirements

All metric calculation functions MUST accept mode parameters:

```typescript
calculateRecoveryMetrics(data, shortTermWindow, longTermWindow, trendWindow)
calculateActivityMetrics(data, shortTermWindow, longTermWindow, trendWindow)
calculateWeightMetrics(data, shortTermWindow, longTermWindow, trendWindow)
calculateSleepMetrics(data, shortTermWindow, longTermWindow)
```

**Three-window model:**

- `shortTermWindow` - for current period averages (7, 28, 90 days)
- `longTermWindow` - for baseline statistics (84, 252, 730 days)
- `trendWindow` - for period-over-period change calculations (7, 14, 30 days)

**Never hardcode** time windows (7, 30, 90 days) in calculation functions.

**Sleep target capped at 90 days** - even in Long mode (730d baseline), sleep target calculation uses max 90 days to avoid overly stable targets.

### Z-Score Display

| Mode | Z-Score Type | Comparison |
|------|-------------|------------|
| Short | Raw z-score | Today vs 12-week baseline |
| Mid | Shifted z-score | 4-week avg vs 9-month baseline |
| Long | Shifted z-score | 90-day avg vs 2-year baseline |

### Data Fusion Quality Controls

**Critical Rule:** Z-scores from fusion layer (30-day window) must NOT override mode-specific z-scores. HealthScore always calculates z-scores via `calculateBaselineMetrics` using the correct mode window (84/252/730 days).

**Strain Scale Normalization:**

- Whoop strain: 0-21 scale
- Garmin ATL: 0-500+ scale (acute training load)
- Before blending, Garmin ATL values are normalized to Whoop scale using percentile mapping
- Minimum 14 days of data required for normalization; otherwise fallback to single source

**Blending Stop-Gates:**

- Minimum 7 days of valid data from each source required for blending
- If overlap insufficient, system uses single best source with reduced confidence
- Confidence score reflects data quality (0-1 scale)

**Fused Data Consistency:**

- All analytics functions (sleepMetrics, activityMetrics, recoveryMetrics) receive fused data
- Never mix raw single-source data with fused multi-source data in same calculation

**Day Key Unification:**

- All date handling uses `toLocalDayKey()` for consistent YYYY-MM-DD format
- Never use inline date parsing like `new Date(dateStr + "T00:00:00")`
- Use `toLocalDayDate()` to convert day keys to Date objects

## Testing

Integration tests only - test against real PostgreSQL database. No unit tests or mocking.

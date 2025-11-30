# life-as-code

> Extends [../CLAUDE.md](../CLAUDE.md)

Privacy-first, multi-user health analytics platform aggregating Garmin, Heavy, and Apple HealthKit data.

## Tech Stack

- **Backend**: Python, Flask, Dash (Plotly)
- **Database**: PostgreSQL
- **Container**: Docker Compose
- **Security**: Fernet encryption, bcrypt, Flask-Login

## Commands

```bash
# Setup
cp .env.example .env
# Generate keys:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_hex(32))"

# Run
docker-compose up --build -d

# User management
docker-compose exec web python manage_users.py

# Database access
docker-compose exec db psql -U user -d health_analytics

# Logs
docker-compose logs -f web
```

## Data Sources

- **Garmin Connect**: Sleep, HRV, heart rate, weight, body composition, stress
- **Heavy**: Workout sets, exercises, weights, RPE
- **Apple HealthKit**: Energy, steps, HRV (via CSV/XML import)

## Architecture

```text
src/
├── app.py          # Flask entry point
├── models/         # SQLAlchemy models
├── routes/         # Flask routes
├── services/       # Data sync, analytics
└── utils/          # Helpers
```

### Multi-User Model

- Admin-only user creation (no public registration)
- Encrypted credentials per user (Fernet)
- Data isolation between users

### Key Tables

Users → UserCredentials (encrypted API keys) → health data tables (Sleep, HRV, Weight, HeartRate, Stress, Energy, Steps, WorkoutSet)

## Environment Variables

```bash
POSTGRES_PASSWORD=<strong-password>
SECRET_KEY=<secrets.token_hex(32)>
FERNET_KEY=<Fernet.generate_key()>
DATABASE_URL=postgresql://user:pass@db:5432/health_analytics
```

## Sync Flow

1. User enters Garmin/Heavy credentials in Settings
2. Click "Sync" buttons to import data
3. Dashboard updates with new metrics
4. AI Daily Briefings generated from aggregated data

## Testing

Integration tests only - test against real PostgreSQL database via Docker Compose. No unit tests or mocking.

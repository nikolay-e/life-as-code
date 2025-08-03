# Life-as-Code: Personal Health Analytics Portal

A comprehensive, private, multi-user health analytics platform that aggregates and analyzes your health, fitness, and performance data from multiple sources including Garmin Connect, Hevy, and Apple HealthKit. Transform your health data into actionable insights with advanced analytics, AI-powered daily briefings, and beautiful visualizations.

## 🎯 What Life-as-Code Does

**🔗 Data Integration**
- **Garmin Connect**: Sleep, HRV, heart rate, weight, body composition, stress, and activity data
- **Hevy**: Workout sets, exercises, weights, RPE, and training progression
- **Apple HealthKit**: Energy expenditure, steps, HRV, and comprehensive health metrics
- **Manual Import**: Support for CSV/XML data from wearables and health apps

**📊 Advanced Analytics**
- **Personal Dashboard**: Interactive charts and trends for all health metrics
- **AI Daily Briefings**: LLM-generated insights and recommendations based on your data
- **Correlation Analysis**: Discover relationships between sleep, training, recovery, and performance
- **Health Scoring**: Personalized thresholds and status indicators for key metrics

**🔒 Privacy-First Architecture**
- **Self-Hosted**: Complete control over your sensitive health data
- **Multi-User**: Secure isolation between users with encrypted credential storage
- **No Cloud Dependencies**: Your data never leaves your infrastructure

## 🚀 Quick Start with Docker

This application is designed to run with Docker and Docker Compose.

### 1. Initial Setup
Copy the example environment file. This file contains the necessary configuration variables.
```bash
cp .env.example .env
```

Now, open the `.env` file and **set your own secure values** for:
- `POSTGRES_PASSWORD` - A strong password for your database
- `SECRET_KEY` - A long random string for Flask session security
- `FERNET_KEY` - Used for encrypting user credentials

Generate the security keys:
```bash
# Generate FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Run the Application

Start all services (web portal and database) in the background.

```bash
docker-compose up --build -d
```

### 3. Create Your First User

With the services running, execute the user management script inside the web container to create your admin account.

```bash
docker-compose exec web python manage_users.py
```

Follow the interactive prompts to create a user.

### 4. Log In and Configure

- Navigate to **`http://localhost:8080`** in your browser.
- Log in with the credentials you just created.
- Go to the **Settings** tab.
- Enter your Garmin email/password and your Hevy API key, then click "Save Credentials".

### 5. Sync Your Data

On the Settings page, click the "Sync Garmin Data" and "Sync Hevy Workouts" buttons to import your data into the database. Your dashboard and analysis tabs will now be populated.

---

## 🧑‍💻 User Management

The `manage_users.py` script is your command-line tool for administering the portal.

- **Run the tool:** `docker-compose exec web python manage_users.py`
- **Features:** You can create, list, update, and delete user accounts.

## 📊 Features

### Multi-User & Secure
- **Private Portal**: No public registration - only admins can create accounts
- **Data Isolation**: Each user's data is completely separate and secure
- **Encrypted Storage**: API credentials are encrypted in the database
- **Session Security**: Secure login with Flask-Login and bcrypt password hashing

### Health Data Integration
- **Garmin Connect**: Sleep, HRV, heart rate, weight, and body composition data
- **Hevy**: Workout sets, exercises, weights, and RPE tracking
- **Automatic Sync**: Real-time data synchronization from both platforms

### Analytics & Insights
- **Personal Dashboard**: Interactive charts showing your health trends
- **Daily Briefings**: AI-generated daily recommendations based on your data
- **Correlation Analysis**: Discover relationships between sleep, training, and recovery
- **Data Status**: Track sync history and data completeness

## 🗂️ Project Structure

```
life-as-code/
├── app.py              # Multi-user web portal (Flask + Dash)
├── models.py           # Database models with user relationships
├── database.py         # PostgreSQL connection and utilities
├── security.py         # Password hashing and credential encryption
├── manage_users.py     # User management CLI tool
├── pull_garmin_data.py # Garmin Connect data sync
├── pull_hevy_data.py   # Hevy workout data sync
├── generate_daily_briefing.py # Daily health analysis
├── analyze_correlations.py   # Health metric correlations
├── docker-compose.yml  # Container orchestration
├── Dockerfile         # Application container definition
├── requirements.txt   # Python dependencies
└── .env.example      # Environment variables template
```

## 🔧 Development

For development work:

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run database migrations (if needed)
docker-compose up db -d
python -c "from database import init_db; init_db()"

# Run the app locally (requires local PostgreSQL)
python app.py
```

## 🐳 Production Deployment

The `docker-compose.yml` includes an optional nginx reverse proxy for production:

```bash
# Start with nginx reverse proxy
docker-compose --profile production up -d

# Configure SSL certificates in ./ssl/ directory
# Update nginx.conf with your domain settings
```

## 🔒 Security Notes

- Change all default passwords in `.env`
- Use strong, unique SECRET_KEY and FERNET_KEY values
- Only create user accounts for trusted individuals
- Consider running behind a VPN for additional privacy
- Regularly backup your PostgreSQL data volume

## 📝 License

This project is for personal use. Please respect the terms of service for Garmin Connect and Hevy when using their APIs.

---

# Database Schema

Life-as-Code uses a PostgreSQL database with the following tables:

## User
**Table:** `users`

**Description:** User accounts for multi-user support.

**Columns:**
- `id`: INTEGER (required) 🔑
- `username`: VARCHAR(80) (required) 📇 ⭐
- `password_hash`: VARCHAR(200) (required)
- `encryption_key_sealed`: TEXT
- `created_at`: DATETIME

**Relationships:**
- `credentials` → UserCredentials
- `settings` → UserSettings
- `sleep_data` → Sleep
- `weight_data` → Weight
- `heart_rate_data` → HeartRate
- `stress_data` → Stress
- `hrv_data` → HRV
- `energy_data` → Energy
- `steps` → Steps
- `workout_sets` → WorkoutSet
- `data_syncs` → DataSync

## UserCredentials
**Table:** `user_credentials`

**Description:** Encrypted user credentials for external APIs.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 ⭐
- `garmin_email`: VARCHAR(200)
- `encrypted_garmin_password`: VARCHAR(500)
- `encrypted_hevy_api_key`: VARCHAR(500)
- `created_at`: DATETIME
- `updated_at`: DATETIME

**Relationships:**
- `user` → User

## UserSettings
**Table:** `user_settings`

**Description:** User-specific settings and thresholds for personalized analysis.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 ⭐
- `hrv_good_threshold`: INTEGER
- `hrv_moderate_threshold`: INTEGER
- `deep_sleep_good_threshold`: INTEGER
- `deep_sleep_moderate_threshold`: INTEGER
- `total_sleep_good_threshold`: FLOAT
- `total_sleep_moderate_threshold`: FLOAT
- `training_high_volume_threshold`: INTEGER
- `created_at`: DATETIME
- `updated_at`: DATETIME

**Relationships:**
- `user` → User

## Sleep
**Table:** `sleep`

**Description:** Sleep data from Garmin Connect.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `deep_minutes`: FLOAT
- `light_minutes`: FLOAT
- `rem_minutes`: FLOAT
- `awake_minutes`: FLOAT
- `total_sleep_minutes`: FLOAT
- `sleep_score`: INTEGER
- `created_at`: DATETIME

**Relationships:**
- `user` → User

**Constraints:**
- UniqueConstraint: `_user_sleep_date_uc`

## HRV
**Table:** `hrv`

**Description:** Heart Rate Variability data from Garmin Connect and Apple Watch.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `hrv_avg`: FLOAT
- `hrv_status`: VARCHAR(50)
- `created_at`: DATETIME

**Relationships:**
- `user` → User

**Constraints:**
- UniqueConstraint: `_user_hrv_date_uc`

## Weight
**Table:** `weight`

**Description:** Weight and body composition data from Garmin Connect.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `weight_kg`: FLOAT
- `bmi`: FLOAT
- `body_fat_pct`: FLOAT
- `muscle_mass_kg`: FLOAT
- `bone_mass_kg`: FLOAT
- `water_pct`: FLOAT
- `created_at`: DATETIME

**Relationships:**
- `user` → User

## HeartRate
**Table:** `heart_rate`

**Description:** Heart rate data from Garmin Connect.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `resting_hr`: INTEGER
- `max_hr`: INTEGER
- `avg_hr`: INTEGER
- `created_at`: DATETIME

**Relationships:**
- `user` → User

**Constraints:**
- UniqueConstraint: `_user_heart_rate_date_uc`

## Stress
**Table:** `stress`

**Description:** Daily stress data from Garmin.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `avg_stress`: FLOAT
- `max_stress`: FLOAT
- `stress_level`: VARCHAR(20)
- `rest_stress`: FLOAT
- `activity_stress`: FLOAT
- `created_at`: DATETIME

**Relationships:**
- `user` → User

**Constraints:**
- UniqueConstraint: `unique_user_stress_date`

## Energy
**Table:** `energy`

**Description:** Daily energy expenditure data from Apple Watch and Garmin.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `active_energy`: FLOAT
- `basal_energy`: FLOAT
- `created_at`: DATETIME

**Relationships:**
- `user` → User

**Constraints:**
- UniqueConstraint: `_user_date_energy_uc`

## Steps
**Table:** `steps`

**Description:** Daily steps and distance data from Garmin Connect.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `total_steps`: INTEGER
- `total_distance`: FLOAT
- `step_goal`: INTEGER
- `created_at`: DATETIME

**Relationships:**
- `user` → User

**Constraints:**
- UniqueConstraint: `_user_date_steps_uc`

## WorkoutSet
**Table:** `workout_sets`

**Description:** Individual workout sets from Hevy.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `date`: DATE (required) 📇
- `exercise`: VARCHAR(200) (required)
- `weight_kg`: FLOAT
- `reps`: INTEGER
- `rpe`: FLOAT
- `set_type`: VARCHAR(50)
- `duration_seconds`: INTEGER
- `distance_meters`: FLOAT
- `created_at`: DATETIME

**Relationships:**
- `user` → User

## DataSync
**Table:** `data_sync`

**Description:** Track when data was last synced from external sources.

**Columns:**
- `id`: INTEGER (required) 🔑
- `user_id`: INTEGER (required) 🔗 📇
- `source`: VARCHAR(50) (required)
- `data_type`: VARCHAR(50) (required)
- `last_sync_date`: DATE
- `last_sync_timestamp`: DATETIME
- `records_synced`: INTEGER
- `status`: VARCHAR(20)
- `error_message`: TEXT

**Relationships:**
- `user` → User

---

**Built with**: Python, Flask, Dash, PostgreSQL, Docker
**Supported APIs**: Garmin Connect, Hevy
**Architecture**: Multi-user, containerized, security-first

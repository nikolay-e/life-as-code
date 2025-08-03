# Life-as-Code: Personal Health Analytics Portal

A private, multi-user, data-driven portal to track and analyze your health, fitness, and performance metrics from services like Garmin and Hevy.

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

- Navigate to **`http://localhost:8050`** in your browser.
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

**Built with**: Python, Flask, Dash, PostgreSQL, Docker
**Supported APIs**: Garmin Connect, Hevy
**Architecture**: Multi-user, containerized, security-first

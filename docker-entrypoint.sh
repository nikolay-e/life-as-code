#!/bin/bash
set -e

echo "🏥 Starting Life-as-Code Unified Web Portal"
echo "============================================"
echo

echo "🔗 Checking database connection..."
python -c "
from src.database import check_db_connection, init_db
if check_db_connection():
    print('✅ Database connection successful')
    init_db()
    print('✅ Database tables ready')
else:
    print('❌ Database connection failed!')
    exit(1)
"

echo "🔐 Bootstrapping default admin user..."
python src/bootstrap_admin.py

echo
echo "🚀 Starting unified web portal on http://0.0.0.0:8080"
echo "💡 Access the dashboard in your browser at http://localhost:8080"
echo "🔄 Use the sync buttons in the app to update your health data"
echo

# Start the web application with gunicorn (production WSGI server)
# Memory optimization:
#   --workers 2: Reduced from 4 to halve memory footprint (~250MB saved)
#   --threads 4: Maintain 8 concurrent requests capacity
#   --max-requests 1000: Restart workers after 1000 requests to prevent memory leaks
#   --max-requests-jitter 100: Randomize restart to avoid simultaneous worker restarts
#   --preload: Load app once before fork, share memory via copy-on-write
exec gunicorn \
  --bind 0.0.0.0:8080 \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --preload \
  --access-logfile - \
  --error-logfile - \
  "src.app:server"

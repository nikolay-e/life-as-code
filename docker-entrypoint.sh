#!/bin/bash
set -e

echo "🏥 Starting Life-as-Code Unified Web Portal"
echo "============================================"
echo

echo "🔗 Checking database connection..."
python -c "
from database import check_db_connection, init_db
if check_db_connection():
    print('✅ Database connection successful')
    init_db()
    print('✅ Database initialization complete')
else:
    print('❌ Database connection failed!')
    exit(1)
"

echo "📊 Getting data status..."
python -c "
from database import get_table_counts
try:
    counts = get_table_counts()
    for table, count in counts.items():
        if table != 'data_sync':
            print(f'  📈 {table}: {count} records')
except:
    print('  📊 Data status check failed')
"

echo
echo "🚀 Starting unified web portal on http://0.0.0.0:443"
echo "💡 Access the dashboard in your browser at http://localhost:443"
echo "🔄 Use the sync buttons in the app to update your health data"
echo

# Start the web application
exec python app.py

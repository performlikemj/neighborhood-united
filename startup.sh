#!/bin/bash

# Container startup script for Django with Azure Blob Storage static files
set -e

echo "🚀 Starting Django container with Azure Blob Storage static files..."

# Check if we're in production (not DEBUG mode)
if [ "$DEBUG" = "False" ] || [ "$DEBUG" = "false" ]; then
    echo "📁 Production mode detected - collecting static files to Azure Blob Storage..."
    
    # Run database migrations first
    echo "🔄 Running database migrations..."
    python manage.py migrate --noinput
    
    # Collect static files to Azure Blob Storage with optimizations
    echo "📤 Collecting static files to Azure Blob Storage..."
    # Use --clear to remove old files and reduce conflicts
    # Use --verbosity=1 to reduce output and speed up process
    # Use timeout to prevent hanging
    timeout 300 python manage.py collectstatic --noinput --clear --verbosity=1 || {
        echo "⚠️ Static file collection timed out or failed, but continuing with startup..."
        echo "🔧 You may need to run collectstatic manually or check Azure Blob Storage configuration"
    }
    
    echo "✅ Static files collection completed (or skipped)!"
else
    echo "🛠️ Development mode detected - skipping static file collection"
    # Still run migrations in development
    python manage.py migrate --noinput
fi

# Start the Django application
echo "🌐 Starting Django application..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 hood_united.wsgi:application 
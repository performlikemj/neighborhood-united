#!/bin/bash

# Simplified container startup script for Django (skips static file collection)
set -e

echo "🚀 Starting Django container (simplified mode)..."

# Check if we're in production (not DEBUG mode)
if [ "$DEBUG" = "False" ] || [ "$DEBUG" = "false" ]; then
    echo "📁 Production mode detected"
    
    # Run database migrations first
    echo "🔄 Running database migrations..."
    python manage.py migrate --noinput
    
    echo "⚡ Skipping static file collection (assuming already done)"
else
    echo "🛠️ Development mode detected"
    # Still run migrations in development
    python manage.py migrate --noinput
fi

# Start the Django application (ASGI) so WebSockets work in local/dev containers
echo "🌐 Starting Django application (ASGI)..."
exec gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2 --timeout 120 hood_united.asgi:application 

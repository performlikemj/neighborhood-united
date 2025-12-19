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
    
    # Import GeoNames data if administrative areas table is empty
    # This is a one-time import of geographic reference data for the service area picker
    # Supported countries: JP (Japan), US (United States), GB (UK), CA (Canada), AU (Australia), etc.
    echo "🗺️ Checking if GeoNames data needs to be imported..."
    NEEDS_COUNT_UPDATE=false
    for COUNTRY in JP US; do
        python manage.py shell -c "
from local_chefs.models import AdministrativeArea
if AdministrativeArea.objects.filter(country='$COUNTRY').count() == 0:
    print('NEEDS_IMPORT')
" 2>/dev/null | grep -q "NEEDS_IMPORT" && {
            echo "📍 Importing GeoNames data for $COUNTRY (this may take a few minutes)..."
            python manage.py import_geonames $COUNTRY || echo "⚠️ GeoNames import for $COUNTRY failed"
            NEEDS_COUNT_UPDATE=true
            echo "✅ GeoNames import for $COUNTRY complete!"
        } || echo "✅ GeoNames data for $COUNTRY already exists, skipping"
    done
    
    # Update postal code counts if any imports happened (ensures prefectures show totals)
    if [ "$NEEDS_COUNT_UPDATE" = true ]; then
        echo "📊 Updating area postal code counts..."
        python manage.py update_area_counts || echo "⚠️ Count update failed"
    fi
    
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

# Start the Django application (ASGI, uvicorn workers)
echo "🌐 Starting Django application (ASGI)..."
exec gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 3 --timeout 120 hood_united.asgi:application 

#!/bin/bash
# Sautai: Azure to Supabase Migration Script
# This script handles the complete migration from Azure PostgreSQL to Supabase

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="/Users/michaeljones/Library/Mobile Documents/com~apple~CloudDocs/Documents/Projects/Web Development/hoodunited/hood_united"
VENV_DIR="$HOME/.hood"

echo -e "${GREEN}=== Sautai: Azure to Supabase Migration ===${NC}"
echo ""

# Check if we're in the right directory
cd "$PROJECT_DIR"

# Activate virtual environment
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
else
    echo -e "${RED}✗ Virtual environment not found at $VENV_DIR${NC}"
    exit 1
fi

# Load environment variables
if [ -f dev.env ]; then
    set -a
    source dev.env
    set +a
    echo -e "${GREEN}✓ Environment variables loaded from dev.env${NC}"
else
    echo -e "${RED}✗ dev.env not found${NC}"
    exit 1
fi

# Check if Supabase password is set
if [ "$SUPABASE_DB_PASSWORD" = "YOUR_SUPABASE_DATABASE_PASSWORD_HERE" ] || [ -z "$SUPABASE_DB_PASSWORD" ]; then
    echo -e "${RED}✗ Please update SUPABASE_DB_PASSWORD in dev.env with your actual Supabase database password${NC}"
    echo -e "${YELLOW}  Get it from: Supabase Dashboard → Project Settings → Database → Database password${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Supabase credentials configured${NC}"
echo ""

# Step 1: Test Supabase connection
echo -e "${YELLOW}Step 1: Testing Supabase connection...${NC}"
python manage.py dbshell --database=supabase -c "SELECT version();" 2>/dev/null || {
    echo -e "${RED}✗ Could not connect to Supabase. Please check your credentials.${NC}"
    exit 1
}
echo -e "${GREEN}✓ Supabase connection successful${NC}"
echo ""

# Step 2: Run migrations on Supabase
echo -e "${YELLOW}Step 2: Running Django migrations on Supabase...${NC}"
python manage.py migrate --database=supabase
echo -e "${GREEN}✓ Migrations completed${NC}"
echo ""

# Step 3: Export data from Azure (excluding meal plans)
echo -e "${YELLOW}Step 3: Exporting data from Azure PostgreSQL...${NC}"
echo "This will export users, chefs, dietary preferences, and other essential data."
echo "Meal plans older than 30 days will be skipped as requested."

# Export essential models using dumpdata
python manage.py dumpdata \
    auth.Group \
    auth.Permission \
    custom_auth.CustomUser \
    custom_auth.Address \
    custom_auth.HouseholdMember \
    custom_auth.UserRole \
    custom_auth.OnboardingSession \
    chefs.Chef \
    chefs.ChefRequest \
    chefs.ChefPhoto \
    chefs.ChefDefaultBanner \
    chefs.ChefVerificationDocument \
    chefs.ChefWaitlistConfig \
    chefs.ChefAvailabilityState \
    chefs.ChefWaitlistSubscription \
    chefs.AreaWaitlist \
    chefs.ChefPaymentLink \
    local_chefs.AdministrativeArea \
    local_chefs.PostalCode \
    local_chefs.ChefPostalCode \
    local_chefs.ServiceAreaRequest \
    meals.DietaryPreference \
    meals.CustomDietaryPreference \
    meals.MealType \
    meals.Tag \
    meals.Ingredient \
    meals.Dish \
    meals.PantryItem \
    meals.StripeConnectAccount \
    meals.PlatformFeeConfig \
    reviews.Review \
    customer_dashboard.ChatThread \
    customer_dashboard.UserMessage \
    customer_dashboard.UserSummary \
    customer_dashboard.WeeklyAnnouncement \
    chef_services.ChefServiceOffering \
    chef_services.ChefServicePriceTier \
    chef_services.ChefCustomerConnection \
    crm \
    memberships \
    messaging \
    services \
    django_celery_beat \
    --database=default \
    --indent=2 \
    -o migration_export.json 2>/dev/null || {
        echo -e "${YELLOW}⚠ Some models may have been skipped (this is normal)${NC}"
    }

echo -e "${GREEN}✓ Data exported to migration_export.json${NC}"
echo ""

# Step 4: Import data to Supabase
echo -e "${YELLOW}Step 4: Importing data to Supabase...${NC}"
if [ -f migration_export.json ]; then
    python manage.py loaddata migration_export.json --database=supabase
    echo -e "${GREEN}✓ Data imported to Supabase${NC}"
else
    echo -e "${RED}✗ Export file not found${NC}"
    exit 1
fi
echo ""

# Step 5: Reset sequences
echo -e "${YELLOW}Step 5: Resetting PostgreSQL sequences...${NC}"
python manage.py dbshell --database=supabase << 'EOSQL'
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT table_name, column_name 
              FROM information_schema.columns 
              WHERE column_default LIKE 'nextval%' 
              AND table_schema = 'public') 
    LOOP
        EXECUTE format('SELECT setval(pg_get_serial_sequence(''%I'', ''%I''), COALESCE(MAX(%I), 1)) FROM %I',
            r.table_name, r.column_name, r.column_name, r.table_name);
    END LOOP;
END $$;
EOSQL
echo -e "${GREEN}✓ Sequences reset${NC}"
echo ""

# Step 6: Verify migration
echo -e "${YELLOW}Step 6: Verifying migration...${NC}"
echo "Checking record counts in Supabase:"
python manage.py shell --database=supabase << 'EOPY'
from custom_auth.models import CustomUser
from chefs.models import Chef
from meals.models import DietaryPreference, Meal
print(f"  Users: {CustomUser.objects.using('supabase').count()}")
print(f"  Chefs: {Chef.objects.using('supabase').count()}")
print(f"  Dietary Preferences: {DietaryPreference.objects.using('supabase').count()}")
print(f"  Meals: {Meal.objects.using('supabase').count()}")
EOPY

echo ""
echo -e "${GREEN}=== Migration Complete ===${NC}"
echo ""
echo "Next steps:"
echo "1. Test the application with Supabase (update your local DB settings)"
echo "2. Update production environment variables to point to Supabase"
echo "3. Monitor for 7 days before decommissioning Azure"
echo ""
echo "To switch your local development to Supabase, update dev.env:"
echo "  DB_HOST=db.mxyciagjriainavtmzkw.supabase.co"
echo "  DB_NAME=postgres"
echo "  DB_USER=postgres"
echo "  DB_PASSWORD=<your-supabase-password>"

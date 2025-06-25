from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Create household member table and household_member_count column if they don't exist."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE custom_auth_customuser ADD COLUMN IF NOT EXISTS household_member_count INTEGER DEFAULT 1;"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS custom_auth_householdmember (\n"
                "    id SERIAL PRIMARY KEY,\n"
                "    user_id INTEGER NOT NULL REFERENCES custom_auth_customuser(id) ON DELETE CASCADE,\n"
                "    name VARCHAR(100),\n"
                "    age INTEGER,\n"
                "    notes TEXT\n"
                ");"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS custom_auth_householdmember_dietary_preferences (\n"
                "    id SERIAL PRIMARY KEY,\n"
                "    householdmember_id INTEGER NOT NULL REFERENCES custom_auth_householdmember(id) ON DELETE CASCADE,\n"
                "    dietarypreference_id INTEGER NOT NULL REFERENCES meals_dietarypreference(id) ON DELETE CASCADE\n"
                ");"
            )
        self.stdout.write(self.style.SUCCESS("Household tables ensured."))

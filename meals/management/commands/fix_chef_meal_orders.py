# meals/management/commands/fix_chef_meal_orders.py
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import ProgrammingError


class Command(BaseCommand):
    help = 'Directly fix database issues with ChefMealOrder schema and migrations'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # First, examine what columns actually exist in the table
            self.stdout.write("Listing all columns in meals_chefmealorder table...")
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='meals_chefmealorder' ORDER BY column_name;
            """)
            existing_columns = [col[0] for col in cursor.fetchall()]
            self.stdout.write(f"Existing columns: {', '.join(existing_columns)}")
            
            # Check for payment_intent_id
            has_payment_intent_id = 'payment_intent_id' in existing_columns
            has_stripe_payment_intent_id = 'stripe_payment_intent_id' in existing_columns
            
            if has_payment_intent_id and not has_stripe_payment_intent_id:
                self.stdout.write("Found payment_intent_id but not stripe_payment_intent_id. Renaming column...")
                cursor.execute("""
                    ALTER TABLE meals_chefmealorder 
                    RENAME COLUMN payment_intent_id TO stripe_payment_intent_id;
                """)
                self.stdout.write(self.style.SUCCESS("Renamed payment_intent_id to stripe_payment_intent_id"))
            elif not has_payment_intent_id and not has_stripe_payment_intent_id:
                self.stdout.write("Neither payment_intent_id nor stripe_payment_intent_id exists. Adding stripe_payment_intent_id column...")
                cursor.execute("""
                    ALTER TABLE meals_chefmealorder 
                    ADD COLUMN stripe_payment_intent_id varchar(255) NULL;
                """)
                self.stdout.write(self.style.SUCCESS("Added stripe_payment_intent_id column"))

            # Check for unit_price column
            has_unit_price = 'unit_price' in existing_columns
            if not has_unit_price:
                self.stdout.write("Adding unit_price column...")
                cursor.execute("""
                    ALTER TABLE meals_chefmealorder 
                    ADD COLUMN unit_price numeric(6,2) NULL;
                """)
                self.stdout.write(self.style.SUCCESS("Added unit_price column"))
            
            # Add any other missing columns from the ChefMealOrder model
            required_columns = {
                'stripe_refund_id': 'VARCHAR(255)',
                'price_adjustment_processed': 'BOOLEAN DEFAULT FALSE'
            }
            
            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    self.stdout.write(f"Adding missing column {col_name}...")
                    cursor.execute(f"""
                        ALTER TABLE meals_chefmealorder 
                        ADD COLUMN {col_name} {col_type};
                    """)
                    self.stdout.write(self.style.SUCCESS(f"Added {col_name} column"))
            
            # Fix unique constraints (careful here)
            self.stdout.write("Fixing unique constraints...")
            try:
                cursor.execute("""
                    SELECT conname FROM pg_constraint 
                    WHERE conrelid = 'meals_chefmealorder'::regclass AND contype = 'u';
                """)
                constraints = cursor.fetchall()
                
                for constraint in constraints:
                    constraint_name = constraint[0]
                    self.stdout.write(f"Found constraint {constraint_name}")
                
                # Only drop constraints if we need to and if there's no partial index that matches our needs
                if not any('uniq_active_order_per_event' in c[0] for c in constraints):
                    self.stdout.write("Attempting to add constraint uniq_active_order_per_event...")
                    try:
                        # PostgreSQL supports partial indexes
                        cursor.execute("""
                            ALTER TABLE meals_chefmealorder 
                            ADD CONSTRAINT uniq_active_order_per_event 
                            UNIQUE (customer_id, meal_event_id) 
                            WHERE (status IN ('placed', 'confirmed'));
                        """)
                        self.stdout.write(self.style.SUCCESS("Added conditional unique constraint"))
                    except ProgrammingError:
                        # Fallback to basic constraint if partial index not supported
                        self.stdout.write(self.style.WARNING("Could not add partial constraint, using basic constraint instead"))
                        cursor.execute("""
                            ALTER TABLE meals_chefmealorder 
                            ADD CONSTRAINT uniq_active_order_per_event 
                            UNIQUE (customer_id, meal_event_id);
                        """)
                        self.stdout.write(self.style.SUCCESS("Added basic constraint"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error handling constraints: {e}"))
            
            # Mark migrations as applied in Django's migration table
            self.stdout.write("Updating Django migrations record...")
            try:
                # Check if the django_migrations table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'django_migrations'
                    );
                """)
                if cursor.fetchone()[0]:
                    for migration_name in [
                        '0062_add_chef_meal_order_unique_constraint', 
                        '0063_manually_add_unit_price',
                        '0064_fix_chefmealorder_constraints', 
                        '0065_ensure_chefmealorder_fields',
                        '0066_merge_20250510_1322'
                    ]:
                        cursor.execute(f"""
                            SELECT COUNT(*) FROM django_migrations 
                            WHERE app='meals' AND name='{migration_name}';
                        """)
                        if cursor.fetchone()[0] == 0:
                            cursor.execute(f"""
                                INSERT INTO django_migrations (app, name, applied) 
                                VALUES ('meals', '{migration_name}', NOW());
                            """)
                            self.stdout.write(self.style.SUCCESS(f"Added migration record for {migration_name}"))
                else:
                    self.stdout.write(self.style.WARNING("django_migrations table does not exist"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error updating migration records: {e}"))
            
            self.stdout.write(self.style.SUCCESS("\nDatabase fix operations completed"))
            self.stdout.write(self.style.SUCCESS("You should now be able to run migrations and use the application normally"))
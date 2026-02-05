import os
import pytest
from unittest.mock import patch, MagicMock
import django
from django.conf import settings

# Configure Django settings before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')
django.setup()


def _get_orphaned_tables():
    """
    Find tables that exist in the database but not in Django models.
    These can cause TransactionTestCase failures due to FK constraints.
    """
    from django.db import connection
    from django.apps import apps

    # Get all tables Django knows about (without triggering queries)
    django_tables = set()
    for model in apps.get_models():
        # Just get the table name from meta, don't access any data
        django_tables.add(model._meta.db_table)
        # Include M2M tables
        for field in model._meta.local_many_to_many:
            m2m_table = field.m2m_db_table()
            if m2m_table:
                django_tables.add(m2m_table)

    # Add Django's internal tables
    django_tables.update([
        'django_migrations',
        'django_content_type',
        'django_session',
        'django_admin_log',
        'auth_permission',
        'auth_group',
        'auth_group_permissions',
    ])

    # Get all tables in the database (raw SQL, no ORM)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)
        db_tables = {row[0] for row in cursor.fetchall()}

    # Find orphans (in DB but not in Django)
    orphaned = db_tables - django_tables
    return orphaned


def _drop_orphaned_tables(orphaned_tables):
    """Drop orphaned tables with CASCADE to clean up test database."""
    from django.db import connection

    with connection.cursor() as cursor:
        for table in orphaned_tables:
            try:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
            except Exception as e:
                print(f"Warning: Could not drop orphaned table {table}: {e}")


@pytest.fixture(scope="session")
def check_orphaned_tables(django_db_setup, django_db_blocker):
    """
    Check for orphaned database tables (runs by default).

    Environment variable ORPHAN_TABLE_ACTION controls behavior:
    - 'warn': Warn about orphans, continue (default)
    - 'fail': Fail if orphans found (recommended for CI)
    - 'fix': Auto-drop orphaned tables
    - 'skip': Disable this check entirely
    """
    action = os.environ.get('ORPHAN_TABLE_ACTION', 'warn').lower()
    if action == 'skip':
        return

    try:
        with django_db_blocker.unblock():
            orphaned = _get_orphaned_tables()
    except Exception as e:
        print(f"\n⚠️  Orphan table check failed: {e}\n")
        return

    if not orphaned:
        return  # Silent when no orphans

    if action == 'fix':
        print(f"\n⚠️  Found {len(orphaned)} orphaned tables, auto-removing: {orphaned}")
        with django_db_blocker.unblock():
            _drop_orphaned_tables(orphaned)
        print("✓ Orphaned tables removed.\n")
    elif action == 'fail':
        pytest.exit(
            f"\n❌ Found orphaned tables in test database: {orphaned}\n"
            f"These tables exist in the DB but not in Django models.\n"
            f"Fix options:\n"
            f"  1. Run: pytest --create-db  (recreate fresh database)\n"
            f"  2. Run: ORPHAN_TABLE_ACTION=fix pytest  (auto-drop orphans)\n"
            f"  3. Create a migration to properly remove these tables\n",
            returncode=1
        )
    else:  # 'check' or any other value = warn
        print(
            f"\n⚠️  Warning: Found orphaned tables in test database: {orphaned}\n"
            f"   This may cause TransactionTestCase failures.\n"
            f"   Run 'pytest --create-db' to fix, or set ORPHAN_TABLE_ACTION=fix\n"
        )


# Auto-run orphan check by default (set ORPHAN_TABLE_ACTION=skip to disable)
def pytest_configure(config):
    if os.environ.get('ORPHAN_TABLE_ACTION', '').lower() != 'skip':
        config.addinivalue_line(
            "usefixtures", "check_orphaned_tables"
        )

# Create a mock OpenAI client for tests
@pytest.fixture(autouse=True)
def mock_openai_client():
    """
    Mock the OpenAI client to prevent API calls during testing.
    This is applied automatically to all tests.
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"dietary_preferences": ["Vegetarian", "Gluten-Free"]}'
                )
            )
        ]
    )
    
    with patch('openai.OpenAI', return_value=mock_client):
        yield mock_client 
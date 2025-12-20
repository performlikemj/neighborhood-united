# Generated migration to refactor AreaWaitlist to use FK to PostalCode
# This is a multi-step migration:
# 1. Add location FK (nullable)
# 2. Migrate data from postal_code/country to location FK
# 3. Remove old fields and make location non-nullable

import django.db.models.deletion
from django.db import migrations, models


def migrate_area_waitlist_to_fk(apps, schema_editor):
    """
    Migrate existing AreaWaitlist entries to use the new location FK.
    Creates PostalCode records if they don't exist.
    """
    AreaWaitlist = apps.get_model('chefs', 'AreaWaitlist')
    PostalCode = apps.get_model('local_chefs', 'PostalCode')
    
    for entry in AreaWaitlist.objects.all():
        if entry.postal_code and entry.country:
            # Get or create the PostalCode record
            postal_code_obj, _ = PostalCode.objects.get_or_create(
                code=entry.postal_code,
                country=entry.country,
                defaults={'display_code': entry.postal_code}
            )
            entry.location = postal_code_obj
            entry.save(update_fields=['location'])


def reverse_migrate_area_waitlist(apps, schema_editor):
    """
    Reverse migration: populate postal_code and country from location FK.
    """
    AreaWaitlist = apps.get_model('chefs', 'AreaWaitlist')
    
    for entry in AreaWaitlist.objects.select_related('location').all():
        if entry.location:
            entry.postal_code = entry.location.code
            entry.country = entry.location.country
            entry.save(update_fields=['postal_code', 'country'])


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0020_add_area_waitlist'),
        ('local_chefs', '0005_postalcode_coordinates'),
    ]

    operations = [
        # Step 1: Add the new location FK field (nullable at first)
        migrations.AddField(
            model_name='areawaitlist',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text='The postal code location the user is waiting for',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='area_waitlist_entries',
                to='local_chefs.postalcode',
            ),
        ),
        
        # Step 2: Run data migration
        migrations.RunPython(
            migrate_area_waitlist_to_fk,
            reverse_migrate_area_waitlist,
        ),
        
        # Step 3: Remove old indexes that reference old fields
        migrations.RemoveIndex(
            model_name='areawaitlist',
            name='chefs_areaw_postal__b34b93_idx',
        ),
        
        # Step 4: Remove old unique_together constraint
        migrations.AlterUniqueTogether(
            name='areawaitlist',
            unique_together=set(),
        ),
        
        # Step 5: Remove old fields
        migrations.RemoveField(
            model_name='areawaitlist',
            name='postal_code',
        ),
        migrations.RemoveField(
            model_name='areawaitlist',
            name='country',
        ),
        
        # Step 6: Make location non-nullable
        migrations.AlterField(
            model_name='areawaitlist',
            name='location',
            field=models.ForeignKey(
                help_text='The postal code location the user is waiting for',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='area_waitlist_entries',
                to='local_chefs.postalcode',
            ),
        ),
        
        # Step 7: Add new unique_together and indexes
        migrations.AlterUniqueTogether(
            name='areawaitlist',
            unique_together={('user', 'location')},
        ),
        migrations.AddIndex(
            model_name='areawaitlist',
            index=models.Index(fields=['location', 'notified'], name='chefs_areaw_locatio_8f2a1c_idx'),
        ),
    ]









from django.db import migrations, models

def convert_allergies(apps, schema_editor):
    CustomUser = apps.get_model('custom_auth', 'CustomUser')
    for user in CustomUser.objects.all():
        user.allergies = [] if user.allergies == 'None' else [user.allergies]
        user.save()

class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0014_alter_customuser_email'),
    ]

    operations = [
        migrations.RunPython(convert_allergies),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0015_rename_chefs_chefw_chef_id_a8d8e1_idx_chefs_chefw_chef_id_8dc66e_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='chef',
            name='is_on_break',
            field=models.BooleanField(default=False, help_text='Temporarily not accepting orders'),
        ),
    ]


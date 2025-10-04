# Generated manually for Chef Gallery feature
# Date: 2025-10-03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chefs', '0016_chef_is_on_break'),
        ('meals', '0001_initial'),  # Ensure meals app exists for FK relationships
    ]

    operations = [
        # Add new fields
        migrations.AddField(
            model_name='chefphoto',
            name='thumbnail',
            field=models.ImageField(blank=True, null=True, upload_to='chefs/photos/thumbnails/'),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='dish',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='photos', to='meals.dish'),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='meal',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='photos', to='meals.meal'),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='tags',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='category',
            field=models.CharField(blank=True, choices=[('appetizer', 'Appetizer'), ('main', 'Main Course'), ('dessert', 'Dessert'), ('beverage', 'Beverage'), ('side', 'Side Dish'), ('other', 'Other')], max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='width',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='height',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='file_size',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='is_public',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='chefphoto',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Modify existing title field to increase max_length
        migrations.AlterField(
            model_name='chefphoto',
            name='title',
            field=models.CharField(blank=True, max_length=255),
        ),
        # Add indexes for performance
        migrations.AddIndex(
            model_name='chefphoto',
            index=models.Index(fields=['chef', '-created_at'], name='chefs_photo_chef_created_idx'),
        ),
        migrations.AddIndex(
            model_name='chefphoto',
            index=models.Index(fields=['chef', 'category'], name='chefs_photo_chef_category_idx'),
        ),
        migrations.AddIndex(
            model_name='chefphoto',
            index=models.Index(fields=['chef', 'is_public'], name='chefs_photo_chef_public_idx'),
        ),
    ]


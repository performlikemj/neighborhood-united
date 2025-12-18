# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chefs', '0027_auto_rename_indexes'),
        ('meals', '0075_add_meal_plan_generation_job'),
    ]

    operations = [
        migrations.CreateModel(
            name='MealPlanReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('receipt_image', models.ImageField(help_text='Photo/scan of the receipt', upload_to='receipts/%Y/%m/')),
                ('receipt_thumbnail', models.ImageField(blank=True, help_text='Auto-generated thumbnail', null=True, upload_to='receipts/thumbnails/%Y/%m/')),
                ('amount', models.DecimalField(decimal_places=2, help_text='Total amount on the receipt', max_digits=10)),
                ('currency', models.CharField(default='USD', max_length=3)),
                ('tax_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Tax portion of the total', max_digits=10, null=True)),
                ('category', models.CharField(choices=[('ingredients', 'Ingredients'), ('supplies', 'Cooking Supplies'), ('equipment', 'Equipment'), ('packaging', 'Packaging'), ('delivery', 'Delivery/Transport'), ('other', 'Other')], default='ingredients', max_length=20)),
                ('merchant_name', models.CharField(blank=True, help_text='Store/vendor name', max_length=200)),
                ('purchase_date', models.DateField(help_text='Date of purchase')),
                ('description', models.TextField(blank=True, help_text='Description of items purchased')),
                ('items', models.JSONField(blank=True, help_text='Optional itemized list: [{name, quantity, unit_price, total}]', null=True)),
                ('status', models.CharField(choices=[('uploaded', 'Uploaded'), ('reviewed', 'Reviewed'), ('reimbursed', 'Reimbursed'), ('rejected', 'Rejected')], default='uploaded', max_length=20)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewer_notes', models.TextField(blank=True, help_text='Admin/reviewer notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chef', models.ForeignKey(help_text='The chef who uploaded this receipt', on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='chefs.chef')),
                ('chef_meal_plan', models.ForeignKey(blank=True, help_text='Chef-created meal plan this receipt is for', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts', to='meals.chefmealplan')),
                ('customer', models.ForeignKey(blank=True, help_text='Customer this expense is associated with (for billing)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chef_receipts', to=settings.AUTH_USER_MODEL)),
                ('meal_plan', models.ForeignKey(blank=True, help_text='User-generated meal plan this receipt is for', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts', to='meals.mealplan')),
                ('prep_plan', models.ForeignKey(blank=True, help_text='Prep plan this receipt is associated with', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipts', to='chefs.chefprepplan')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_receipts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-purchase_date', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='mealplanreceipt',
            index=models.Index(fields=['chef', '-purchase_date'], name='meals_mealp_chef_id_d1c81c_idx'),
        ),
        migrations.AddIndex(
            model_name='mealplanreceipt',
            index=models.Index(fields=['chef', 'status'], name='meals_mealp_chef_id_8f2b3a_idx'),
        ),
        migrations.AddIndex(
            model_name='mealplanreceipt',
            index=models.Index(fields=['chef', 'customer', '-purchase_date'], name='meals_mealp_chef_id_5e7a2d_idx'),
        ),
        migrations.AddIndex(
            model_name='mealplanreceipt',
            index=models.Index(fields=['chef', 'category'], name='meals_mealp_chef_id_c8f1a9_idx'),
        ),
    ]








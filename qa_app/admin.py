from django.contrib import admin
from .models import FoodQA

class FoodQAAdmin(admin.ModelAdmin):
    list_display = ('question', 'response')

admin.site.register(FoodQA, FoodQAAdmin)
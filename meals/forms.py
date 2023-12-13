from django import forms
from .models import Dish, Ingredient, Meal

class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ['name', 'ingredients', 'featured']


class IngredientForm(forms.ModelForm):
    spoonacular_choice = forms.ChoiceField(choices=[])

    class Meta:
        model = Ingredient
        fields = ['name', 'spoonacular_choice']
        exclude = ('chef',)


class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ['name', 'start_date', 'dishes', 'price', 'party_size', 'description']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }

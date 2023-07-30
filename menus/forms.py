from django import forms
from .models import Dish, Ingredient, Menu

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


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ['name', 'start_date', 'end_date', 'dishes', 'price', 'party_size', 'description']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

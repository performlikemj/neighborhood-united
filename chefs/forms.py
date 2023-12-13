from django import forms
from .models import Chef
from meals.models import Meal, Dish

class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ['start_date', 'dishes', 'price']
        widgets = {
            'start_date': forms.DateInput(format=('%Y-%m-%d'), attrs={'class':'form-control', 'placeholder':'Select a start date', 'type':'date'}),
            'dishes': forms.CheckboxSelectMultiple,
            'price': forms.NumberInput(attrs={'class':'form-control', 'placeholder':'Enter a price'}),
        }

        
class ChefProfileForm(forms.ModelForm):
    class Meta:
        model = Chef
        fields = ['experience', 'bio', 'profile_pic', 'serving_postalcodes']
        widgets = {
            'experience': forms.Textarea(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control'}),
            'profile_pic': forms.FileInput(attrs={'class': 'form-control'}),
            'serving_postalcodes': forms.CheckboxSelectMultiple(),
        }



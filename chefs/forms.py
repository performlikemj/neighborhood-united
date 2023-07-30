from django import forms
from .models import Chef
from menus.models import Menu, Dish

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ['start_date', 'end_date', 'dishes', 'price']
        widgets = {
            'start_date': forms.DateInput(format=('%Y-%m-%d'), attrs={'class':'form-control', 'placeholder':'Select a start date', 'type':'date'}),
            'end_date': forms.DateInput(format=('%Y-%m-%d'), attrs={'class':'form-control', 'placeholder':'Select an end date', 'type':'date'}),
            'dishes': forms.CheckboxSelectMultiple,
            'price': forms.NumberInput(attrs={'class':'form-control', 'placeholder':'Enter a price'}),
        }


        
class ChefProfileForm(forms.ModelForm):
    class Meta:
        model = Chef
        fields = ['experience', 'bio', 'profile_pic']


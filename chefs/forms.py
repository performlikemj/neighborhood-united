# chefs/forms.py
from django import forms
from .models import Chef, ChefPhoto
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


class ChefPhotoForm(forms.ModelForm):
    # Allow tags as comma-separated string for easier form input
    tags_input = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., vegan, gluten-free, seasonal'
        }),
        help_text='Comma-separated tags'
    )
    
    class Meta:
        model = ChefPhoto
        fields = [
            'image', 'title', 'caption', 'description', 
            'category', 'dish', 'meal', 'is_featured', 'is_public'
        ]
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'caption': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'dish': forms.Select(attrs={'class': 'form-control'}),
            'meal': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        chef = kwargs.pop('chef', None)
        super().__init__(*args, **kwargs)
        
        # Filter dish and meal choices to only show this chef's items
        if chef:
            self.fields['dish'].queryset = Dish.objects.filter(chef=chef)
            self.fields['meal'].queryset = Meal.objects.filter(chef=chef)
        
        # Pre-populate tags_input if editing existing photo
        if self.instance and self.instance.pk and self.instance.tags:
            self.fields['tags_input'].initial = ', '.join(self.instance.tags)
    
    def clean_tags_input(self):
        """Convert comma-separated string to list."""
        tags_str = self.cleaned_data.get('tags_input', '')
        if tags_str:
            # Split by comma, strip whitespace, filter empty strings
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            return tags
        return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Save tags from tags_input field
        instance.tags = self.cleaned_data.get('tags_input', [])
        if commit:
            instance.save()
        return instance


from django import forms
from .models import GoalTracking, FoodPreferences

class GoalForm(forms.ModelForm):
    class Meta:
        model = GoalTracking
        fields = ['goal_name', 'goal_description']


class FoodPreferencesForm(forms.ModelForm):
    class Meta:
        model = FoodPreferences
        fields = ['dietary_preference']
        widgets = {
            'dietary_preference': forms.RadioSelect()
        }

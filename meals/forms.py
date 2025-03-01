from django import forms
from .models import Dish, Ingredient, Meal, ChefMealEvent, ChefMealOrder, ChefMealReview
from django.utils import timezone
from custom_auth.models import CustomUser
import datetime

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
        fields = ['name', 'start_date', 'dishes', 'price', 'description']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ChefMealEventForm(forms.ModelForm):
    """Form for creating and editing chef meal events."""
    
    class Meta:
        model = ChefMealEvent
        fields = [
            'meal', 'event_date', 'event_time', 'order_cutoff_time',
            'max_orders', 'min_orders', 'base_price', 'min_price',
            'status', 'description', 'special_instructions'
        ]
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'event_time': forms.TimeInput(attrs={'type': 'time'}),
            'order_cutoff_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'special_instructions': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        self.chef = kwargs.pop('chef', None)
        super().__init__(*args, **kwargs)
        
        # If chef is provided, filter meals by this chef
        if self.chef:
            self.fields['meal'].queryset = Meal.objects.filter(chef=self.chef)
    
    def clean(self):
        cleaned_data = super().clean()
        event_date = cleaned_data.get('event_date')
        event_time = cleaned_data.get('event_time')
        order_cutoff_time = cleaned_data.get('order_cutoff_time')
        base_price = cleaned_data.get('base_price')
        min_price = cleaned_data.get('min_price')
        
        # Check that event date is in the future
        now = timezone.now()
        if event_date and event_date < now.date():
            self.add_error('event_date', 'Event date must be in the future.')
        
        # Check that the cutoff time is before the event
        if event_date and event_time and order_cutoff_time:
            event_datetime = datetime.datetime.combine(
                event_date, 
                event_time,
                tzinfo=timezone.get_current_timezone()
            )
            if order_cutoff_time >= event_datetime:
                self.add_error('order_cutoff_time', 'Order cutoff time must be before the event time.')
        
        # Check that the minimum price is less than the base price
        if base_price and min_price and min_price > base_price:
            self.add_error('min_price', 'Minimum price must be less than or equal to the base price.')
        
        return cleaned_data

class ChefMealOrderForm(forms.ModelForm):
    """Form for placing an order for a chef meal event."""
    
    class Meta:
        model = ChefMealOrder
        fields = ['quantity', 'special_requests']
        widgets = {
            'special_requests': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.meal_event = kwargs.pop('meal_event', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        
        if not self.meal_event:
            raise forms.ValidationError("No meal event specified.")
        
        if not self.meal_event.is_available_for_orders():
            raise forms.ValidationError("This meal event is not available for orders.")
        
        # Check that there's enough capacity for this order
        available_slots = self.meal_event.max_orders - self.meal_event.orders_count
        if quantity and quantity > available_slots:
            self.add_error('quantity', f'Only {available_slots} orders available.')
        
        return cleaned_data

class ChefMealReviewForm(forms.ModelForm):
    """Form for reviewing a chef meal order."""
    
    class Meta:
        model = ChefMealReview
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your experience with this meal...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.chef_meal_order = kwargs.pop('chef_meal_order', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not self.chef_meal_order:
            raise forms.ValidationError("No order specified.")
        
        if not self.customer:
            raise forms.ValidationError("No customer specified.")
        
        # Check if the customer owns this order
        if self.chef_meal_order.customer != self.customer:
            raise forms.ValidationError("You can only review your own orders.")
        
        # Check if the order is completed
        if self.chef_meal_order.status != 'completed':
            raise forms.ValidationError("You can only review completed orders.")
        
        # Check if this order has already been reviewed
        if hasattr(self.chef_meal_order, 'review'):
            raise forms.ValidationError("You have already reviewed this order.")
        
        return cleaned_data

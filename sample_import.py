import os
import django
from random import randint, choice
from datetime import datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hood_united.settings")
django.setup()

from django.contrib.auth import get_user_model
from chefs.models import Chef
from meals.models import Dish, Ingredient, Meal
from local_chefs.models import PostalCode, ChefPostalCode
from events.models import Event

User = get_user_model()

# Helper function to create users
def create_user(username, email, password='password123'):
    return User.objects.create_user(username=username, email=email, password=password)

# Create Customers
customers = [create_user(f'customer{i}', f'customer{i}@example.com') for i in range(1, 6)]

# Create Chefs
chef_winsome_user = create_user('Winsome', 'winsome@example.com')
chef_winsome = Chef.objects.create(user=chef_winsome_user)

chef_jamaris_user = create_user('Jamaris', 'jamaris@example.com')
chef_jamaris = Chef.objects.create(user=chef_jamaris_user)


# First, get or create the PostalCode instances
postal_code_winsome, _ = PostalCode.objects.get_or_create(code='11236')
postal_code_jamaris, _ = PostalCode.objects.get_or_create(code='11224')

# Assign postal codes to chefs
ChefPostalCode.objects.create(chef=chef_winsome, postal_code=postal_code_winsome)
ChefPostalCode.objects.create(chef=chef_jamaris, postal_code=postal_code_jamaris)


# Helper function to create dishes
def create_dish(chef, name, ingredients_list):
    dish = Dish.objects.create(chef=chef, name=name)
    for ingredient_name in ingredients_list:
        ingredient, _ = Ingredient.objects.get_or_create(chef=chef, name=ingredient_name)
        dish.ingredients.add(ingredient)
    dish.save()
    return dish

# Create Jamaican dishes for chef Winsome
jamaican_dishes = [
    ('Jerk Chicken', ['Chicken', 'Jerk seasoning', 'Scotch bonnet pepper']),
    ('Curry Goat', ['Goat', 'Curry powder', 'Potatoes']),
    ('Ackee and Saltfish', ['Ackee', 'Salted cod', 'Tomatoes']),
    ('Rice and Peas', ['Rice', 'Kidney beans', 'Coconut milk'])
]
for name, ingredients in jamaican_dishes:
    create_dish(chef_winsome, name, ingredients)

# Create Puerto Rican dishes for chef Jamaris
puerto_rican_dishes = [
    ('Mofongo', ['Plantains', 'Garlic', 'Pork']),
    ('Arroz con Gandules', ['Rice', 'Pigeon peas', 'Pork']),
    ('Pernil', ['Pork shoulder', 'Garlic', 'Oregano']),
    ('Tostones', ['Plantains', 'Salt', 'Garlic'])
]
for name, ingredients in puerto_rican_dishes:
    create_dish(chef_jamaris, name, ingredients)

# Create Events
event_categories = ['WS', 'SE', 'ME', 'CO', 'WE', 'FE', 'EX', 'FU', 'CO']
for i in range(4):
    event_date = datetime.now() + timedelta(days=randint(1, 30))
    Event.objects.create(
        title=f'Event {i + 1}',
        description='Description for event {i + 1}',
        date=event_date,
        location=f'Location {i + 1}',
        category=choice(event_categories),
        organizer=choice(customers)
    )

print("Sample data created successfully!")

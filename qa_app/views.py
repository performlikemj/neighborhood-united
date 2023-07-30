import openai
from openai.error import OpenAIError
import os
import json
from django.shortcuts import render, redirect
from .models import FoodQA
from menus.models import Dish, MealType, Menu
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.core.paginator import Paginator
from chefs.models import Chef
from datetime import date, timedelta
from django.db.models import Q


def get_meal_plan(query):
    # Determine the current date and the end of the week
    current_date = date.today()
    end_of_week = current_date + timedelta(days=(6 - current_date.weekday()))  # Sunday is considered the end of the week

    # Get all the meal types from the database
    meal_types = MealType.objects.all()

    # Determine if the query contains any meal type
    meal_type_names = [meal_type for meal_type in meal_types if meal_type in query.lower()]

    if meal_type_names:
        # Get the meal type objects from the database
        try:
            meal_types = MealType.objects.filter(name__in=meal_type_names)
        except MealType.DoesNotExist:
            return json.dumps({"message": f"No meal types found with the names {meal_type_names}."})

        # Get menus where the end_date is in the future and the start_date is within the current week
        menus = Menu.objects.filter(end_date__gte=current_date, start_date__lte=end_of_week)

        # Filter menus by query
        menus = menus.filter(Q(chef__user__username__icontains=query) | Q(name__icontains=query))

        result = []
        for menu in menus:
            # Get dishes from the menu that match any of the meal types
            dishes = menu.dishes.filter(meal_types__in=meal_types)

            # If there are any matching dishes
            if dishes.exists():
                menu_details = {
                    "name": menu.name,
                    "chef": menu.chef.user.username,
                    "start_date": menu.start_date,
                    "end_date": menu.end_date,
                    "dishes": [dish.name for dish in dishes]
                }
                result.append(menu_details)
    else:
        # Get menus where the end_date is in the future and the start_date is within the current week
        menus = Menu.objects.filter(end_date__gte=current_date, start_date__lte=end_of_week)

        # Filter menus by query
        menus = menus.filter(Q(chef__user__username__icontains=query) | Q(name__icontains=query))

        result = []
        for menu in menus:
            menu_details = {
                "name": menu.name,
                "chef": menu.chef.user.username,
                "start_date": menu.start_date,
                "end_date": menu.end_date,
                "dishes": [dish.name for dish in menu.dishes.all()]
            }
            result.append(menu_details)

    if not result:
        return json.dumps({"message": "No meal plans found matching your query."})

    return json.dumps(result)


def search_chefs(query):
    # Normalize the query by removing common titles and trimming whitespace
    normalized_query = query.lower().replace('chef', '').strip()

    chefs = Chef.objects.filter(user__username__icontains=normalized_query)

    result = []
    for chef in chefs:
        featured_dishes = [{"name": dish.name} for dish in chef.featured_dishes.all()]
        chef_info = {
            "name": chef.user.username,
            "experience": chef.experience,
            "bio": chef.bio,
            "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
            "featured_dishes": featured_dishes
        }
        result.append(chef_info)
    if not result:
        return json.dumps({"message": "No chefs found matching your query."})
    return json.dumps(result)


def search_dishes(query):
    # Assume this function takes a query and returns a JSON with the requested information about chefs, dishes, and ingredients
    dishes = Dish.objects.filter(name__icontains=query)  # Example of searching dishes by name
    result = []
    for dish in dishes:
        chefs = [chef.user.username for chef in [dish.chef]]
        result.append({"name": dish.name, "chefs": chefs, "ingredients": [ingredient.name for ingredient in dish.ingredients.all()]})
    if not result:
        return json.dumps({"message": "No dishes found matching your query."})
    return json.dumps(result)

@ratelimit(key='ip', rate='10/m')
def home(request):
    if request.method == 'POST':
        question = strip_tags(request.POST.get('question', ''))

        # Set up OpenAI
        openai.api_key = settings.OPENAI_KEY

        # Define available functions for GPT to call
        functions = [
            {
                "name": "search_dishes",
                "description": "Search dishes in the database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query to search for dishes",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_chefs",
                "description": "Search chefs in the database and get their info",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The query to search for chefs"},
                    },
                    "required": ["query"],
                },
            }
        ] 


        # Initialize function_response
        function_response = None

        try:
            # Initial call to the OpenAI API
            initial_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0613",
                messages=[
                    {"role": "system", "content": settings.OPENAI_PROMPT},
                    {"role": "user", "content": question}
                ],
                functions=functions,
                function_call="auto",
            )

            response_message = initial_response['choices'][0]['message']

            # Check if GPT wanted to call a function
            if response_message.get('function_call'):
                # Get the name of the function to call and the arguments
                function_name = response_message['function_call']['name']
                function_args = json.loads(response_message['function_call']['arguments'])

                # Map of available functions
                available_functions = {
                    'search_dishes': search_dishes,
                    'search_chefs': search_chefs,
                    'get_meal_plan': get_meal_plan,
                }

                # Call the appropriate function
                function_response = available_functions[function_name](**function_args)

                # Handle the response
                if 'message' in json.loads(function_response):
                    # Save the message to the database instead of the usual function response
                    FoodQA.objects.create(question=question, response=json.loads(function_response)['message'])
                    print(f'If Function response: {json.loads(function_response)["message"]}')
                else:
                    FoodQA.objects.create(question=question, response=function_response)
                    print(f'Else Function response: {function_response}')
            else:
                # If no function was called, save the initial response
                FoodQA.objects.create(question=question, response=response_message['content'])
                print(f'Outer Else response: {response_message["content"]}')

            if function_response:
                # If a function was called, check if there's a 'message' key in the response
                function_response_json = json.loads(function_response)
                if 'message' in function_response_json:
                    # If there's a 'message' key, use its value
                    response_data = {
                        "question": question,
                        "response": function_response_json['message']
                    }
                else:
                    # If there's no 'message' key, use the entire function response
                    response_data = {
                        "question": question,
                        "response": function_response
                    }
            else:
                # If no function was called, use the initial response from GPT
                response_data = {
                    "question": question,
                    "response": response_message['content']
                }

            return JsonResponse(response_data)
        except OpenAIError as e:
            # handle the OpenAI error
            print(e)
            return render(request, 'error.html', {'message': str(e)})

    # Fetch all the previously asked questions and responses
    qas_list = FoodQA.objects.all().order_by('-id')  # Ordered by latest
    paginator = Paginator(qas_list, 10)  # Show 10 questions per page

    page_number = request.GET.get('page')
    qas = paginator.get_page(page_number)

    return render(request, 'home.html', {'qas': qas})
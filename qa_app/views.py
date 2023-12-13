import openai
from openai import OpenAIError
import os
import json
from django.shortcuts import render, redirect
from .models import FoodQA
from meals.models import Dish, MealType, Meal
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.core.paginator import Paginator
from chefs.models import Chef
from custom_auth.models import Address
from datetime import date, timedelta
from django.db.models import Q
from reviews.models import Review
from django.contrib.contenttypes.models import ContentType
from random import sample
from collections import defaultdict
from datetime import datetime
from shared.utils import auth_get_meal_plan, auth_search_chefs, auth_search_dishes, guest_get_meal_plan, guest_search_chefs, guest_search_dishes, generate_review_summary, sanitize_query
from openai import OpenAI
from random import sample
from meals.models import Meal

@ratelimit(key='ip', rate='10/m')
def home(request):
    if request.method == 'POST':
        question = strip_tags(request.POST.get('question', ''))


        # Define available functions for GPT to call
        if request.user.is_authenticated:
            functions = [
                {
                    "name": "auth_search_dishes",
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
                    "name": "auth_search_chefs",
                    "description": "Search chefs in the database and get their info",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "The query to search for chefs"},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "auth_get_meal_plan",
                    "description": "Get a meal plan for the current week",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "The query to search for meal plans"},
                        },
                        "required": ["query"],
                    },
                },
                # {
                #     "name": "auth_search_ingredients",
                #     "description": "Search ingredients used in dishes in the database and get their info.",
                #     "parameters": {
                #         "type": "object",
                #         "properties": {
                #             "query": {
                #                 "type": "string", 
                #                 "description": "The query to search for ingredients"},
                #         },
                #         "required": ["query"],
                #     },
                # },
            ]
        else:
            functions = [
                {
                    "name": "guest_search_dishes",
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
                    "name": "guest_search_chefs",
                    "description": "Search chefs in the database and get their info",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "The query to search for chefs"},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "guest_get_meal_plan",
                    "description": "Get a meal plan for the current week",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "The query to search for meal plans"},
                        },
                        "required": ["query"],
                    },
                },
                # {
                #     "name": "guest_search_ingredients",
                #     "description": "Search ingredients used in dishes in the database and get their info.",
                #     "parameters": {
                #         "type": "object",
                #         "properties": {
                #             "query": {
                #                 "type": "string", 
                #                 "description": "The query to search for ingredients"},
                #         },
                #         "required": ["query"],
                #     },
                # }
            ] 


        try:
            client = OpenAI(api_key=settings.OPENAI_KEY)

            # Using JSON mode for structured outputs
            initial_response = client.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": settings.OPENAI_PROMPT + " Please respond in JSON format."},
                    {"role": "user", "content": question}
                ],
                functions=functions,
                function_call="auto",
            )
            # Check if the response is valid and has choices
            if initial_response and initial_response.choices:
                choice = initial_response.choices[0]

                # Check if the finish_reason is 'function_call'
                if choice.finish_reason == 'function_call' and choice.message.function_call:
                    function_call = choice.message.function_call
                    function_name = function_call.name
                    function_args = json.loads(function_call.arguments)

                    # Initialize function_response_json
                    function_response_json = None            
                    # Initialize function_response
                    function_response = None

                    # Map of available functions
                    if request.user.is_authenticated:
                        available_functions = {
                            'auth_search_dishes': auth_search_dishes,
                            'auth_search_chefs': auth_search_chefs,
                            'auth_get_meal_plan': auth_get_meal_plan,
                            # 'auth_search_ingredients': auth_search_ingredients,
                        }
                    else:
                        available_functions = {
                            'guest_search_dishes': guest_search_dishes,
                            'guest_search_chefs': guest_search_chefs,
                            'guest_get_meal_plan': guest_get_meal_plan,
                            # 'guest_search_ingredients': guest_search_ingredients,
                        }
                    # Call the appropriate function
                    if request.user.is_authenticated:
                        function_response = available_functions[function_name](request=request, **function_args)
                    else:
                        if function_name in ['auth_get_meal_plan', 'guest_get_meal_plan']:
                            function_response = available_functions[function_name](query=function_args.get('query', ''), query_type=function_args.get('query_type', ''))
                        else:
                            function_response = available_functions[function_name](query=function_args.get('query', ''))
                    # Try to load the function response as JSON                
                    try:
                        function_response_json = json.dumps(function_response)
                    except json.decoder.JSONDecodeError:
                        error_message = "function_response is not a valid JSON string."
                        function_response_json = {
                            "message": error_message
                        }
                        function_response = json.dumps({"message": error_message})                    
                    # Handle the response
                    if 'message' in function_response_json:
                        FoodQA.objects.create(question=question, response=function_response.get('message', function_response))
                        print(f'If Function response: {function_response.get("message", function_response)}')
                    else:
                        FoodQA.objects.create(question=question, response=function_response)
            else:
                # If no function was called, save the initial response
                # When saving the question or setting it up for the context
                safe_question = sanitize_query(question)
                FoodQA.objects.create(question=safe_question, response=response_content)


            # Prepare final response
            # Prepare the data for the template
            latest_qa = FoodQA.objects.last()
            safe_question = sanitize_query(question)
            # Fetch all meals with images from the database
            meals_with_images = Meal.objects.filter(image__isnull=False)

            # Determine the number of meals to display (up to 9)
            num_meals_to_display = min(meals_with_images.count(), 9)

            # Fetch a sample of random meals
            random_meals = sample(list(meals_with_images), num_meals_to_display) if meals_with_images.exists() else []

            context = {
                'current_date': datetime.now().strftime('%Y-%m-%d'),
                'question': safe_question,
                'response': function_response.get('message', function_response) if function_response_json else response_message['content'],
                'latest_qa': latest_qa,  # This is used to display the latest question and response in the template
                'random_meals': random_meals,
            }

            print(f'Context: {context}')
            # Render the template
            return render(request, 'home.html', context)

        except OpenAIError as e:
            # handle the OpenAI error
            print(e)
            return render(request, 'error.html', {'message': str(e)})

    # Fetch all the previously asked questions and responses
    qas_list = FoodQA.objects.all().order_by('-id')  # Ordered by latest
    paginator = Paginator(qas_list, 10)  # Show 10 questions per page

    page_number = request.GET.get('page')
    qas = paginator.get_page(page_number)
    # Fetch all meals with images from the database
    meals_with_images = Meal.objects.filter(image__isnull=False)

    # Determine the number of meals to display (up to 9)
    num_meals_to_display = min(meals_with_images.count(), 9)

    # Fetch a sample of random meals
    random_meals = sample(list(meals_with_images), num_meals_to_display) if meals_with_images.exists() else []

    context = {
        'current_date': datetime.now().strftime('%Y-%m-%d'),
        'qas': qas,
        'random_meals': random_meals,
    }
    return render(request, 'home.html', context)
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


# TODO: Create a completion that categorizes a meal based on what i have in the meal model

@api_view(['POST'])
def compltions_gpt(request):
    print("Chatting with Guest GPT")
    completions_id_file = "completions_id.txt"
    # Set up OpenAI
    client = OpenAI(api_key=settings.OPENAI_KEY)   
    question = "Which function should I call next?" 
    # Check if the assistant ID is already stored in a file
  
    # Processing the POST request
    try:
        print("Processing POST request")
        try:
            print(f"Request data: {request.data}")
            data = request.data
            print(f"Data: {data}")
        except json.JSONDecodeError:
            return Response({'error': 'Failed to parse JSON'}, status=400)

        question = data.get('question')
        print(f"Question: {question}")
        thread_id = data.get('thread_id')
        print(f"Thread ID: {thread_id}")

        if not question:
            return Response({'error': 'No question provided'}, status=400)
        
        # Check if thread_id is safe
        if thread_id and not re.match("^thread_[a-zA-Z0-9]*$", thread_id):
            return Response({'error': 'Invalid thread_id'}, status=400)

        # Handle existing or new thread
        if not thread_id:
            openai_thread = client.beta.threads.create()
            thread_id = openai_thread.id
            print(f"New thread ID: {thread_id}")
    
        try:
            print("Creating a message")
            # Add a Message to a Thread
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=question
            )
            print("Message created")
        except Exception as e:
            logger.error(f'Failed to create message: {str(e)}')
            return Response({'error': f'Failed to create message: {str(e)}'}, status=500)    
                

    
        # Variable to store tool call results
        formatted_outputs = []
            
        try:
            # Run the Assistant
            print('Running the assistant')
            print(f"Guest assistant ID: {guest_assistant_id}")
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=guest_assistant_id,
                # Optionally, you can add specific instructions here
            )
        except Exception as e:
            logger.error(f'Failed to create run: {str(e)}')
            return Response({'error': f'Failed to create run: {str(e)}'}, status=500)
        while True:
            try:
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )

                if run.status == 'completed':
                    logger.info('Run completed')
                    break
                elif run.status == 'failed':
                    logger.error('Run failed')
                    break
                elif run.status in ['expired', 'cancelled']:
                    logger.warning(f'Run {run.status}')
                    break
                elif run.status in ['queued', 'in_progress']:
                    time.sleep(0.5)
                    continue
                elif run.status == "requires_action":
                    tool_outputs = []
                    print("Run requires action")
                    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                        # Execute the function call and get the result
                        print(f"New Tool call: {tool_call}")
                        tool_call_result = guest_ai_call(tool_call, request)
                        print(f"Tool call result: {tool_call_result}")
                        # Prepare the update data
                        update_data = {
                            'function_name': tool_call_result['function'],  # Example, adjust based on your data structure
                            'result': tool_call_result
                        }
                        # Extracting the tool_call_id and the output
                        tool_call_id = tool_call_result['tool_call_id']
                        print(f"Tool call ID: {tool_call_id}")
                        output = tool_call_result['output']
                        print(f"Output: {output}")
                        # Assuming 'output' needs to be serialized as a JSON string
                        # If it's already a string or another format is required, adjust this line accordingly
                        output_json = json.dumps(output)
                        print(f"Output JSON: {output_json}")
                        # Prepare the output in the required format
                        formatted_output = {
                            "tool_call_id": tool_call_id,
                            "output": output_json
                        }
                        print(f"Formatted tool output: {formatted_output}")
                        tool_outputs.append(formatted_output)

                        formatted_outputs.append(formatted_output)
                    print(f"Ready to submit tool outputs: {tool_outputs}")
                    # Submitting the formatted outputs
                    client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs,
                    )
                    continue
            except Exception as e:
                logger.critical(f'Critical error occurred: {e}', exc_info=True)
        # Check the status of the Run and retrieve responses
        try:
            # Retrieve messages and log them
            print("Retrieving messages")
            messages = client.beta.threads.messages.list(thread_id)
        except Exception as e:
            logger.error(f'Failed to list messages: {str(e)}')
            return Response({'error': f'Failed to list messages: {str(e)}'}, status=500)


        with open("messages.json", "w") as f:
            messages_json = messages.model_dump()
            json.dump(messages_json, f, indent=4)
            

        try:
            # Retrieve the run steps
            print("Retrieving run steps")
            run_steps = client.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run.id)
        except Exception as e:
            return Response({'error': f'Failed to list run steps: {str(e)}'}, status=500)

        # Save the run steps to a file
        with open("run_steps.json", "w") as f:
            run_steps_json = run_steps.model_dump()
            json.dump(run.model_dump(), f, indent=4)
        


        response_data = {
            'last_assistant_message': next((msg.content[0].text.value for msg in (messages.data) if msg.role == 'assistant'), None),                
            'run_status': run.status,
            'new_thread_id': thread_id
        }

        print(thread_id)
        print(f'New thread ID: {thread_id}')

        print(f'message: {response_data["last_assistant_message"]}')
        
        # Wrap response_data in a Response object
        return Response(response_data)

    except Exception as e:
        # Return error message wrapped in Response
        logger.error(f'Error: {str(e)}')
        return Response({'error': str(e)}, status=500)



@ratelimit(key='ip', rate='10/m')
def home(request):
    if request.method == 'POST':
        question = strip_tags(request.POST.get('question', ''))


        # Define available functions for GPT to call
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
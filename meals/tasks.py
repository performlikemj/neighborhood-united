# might have to move this to the root or the shared folder
import json
from celery import shared_task
from meals.models import Meal, Dish, Ingredient
from chefs.models import Chef  # Adjust the import path based on your project structure
from openai import OpenAI
from django.conf import settings
from custom_auth.models import CustomUser
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake, UserSummary, UserMessage, ChatThread
from django.utils import timezone
from datetime import timedelta
from shared.utils import (get_user_info, post_review, update_review, delete_review, replace_meal_in_plan, 
                          remove_meal_from_plan, list_upcoming_meals, get_date, create_meal_plan, 
                          add_meal_to_plan, auth_get_meal_plan, auth_search_chefs, auth_search_dishes, 
                          approve_meal_plan, auth_search_ingredients, auth_search_meals_excluding_ingredient, 
                          search_meal_ingredients, suggest_alternative_meals,guest_search_ingredients ,
                          guest_get_meal_plan, guest_search_chefs, guest_search_dishes, 
                          generate_review_summary, access_past_orders, get_goal, 
                          update_goal, adjust_week_shift, get_unupdated_health_metrics, 
                          update_health_metrics, check_allergy_alert, provide_nutrition_advice, 
                          recommend_follow_up, find_nearby_supermarkets,
                          search_healthy_meal_options, provide_healthy_meal_suggestions, 
                          understand_dietary_choices, is_question_relevant, create_meal)
from local_chefs.views import chef_service_areas, service_area_chefs
from rest_framework.response import Response
import re
import time
import logging
from openai import OpenAIError

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding if response.data else None

functions = {
    "auth_search_dishes": auth_search_dishes,
    "auth_search_chefs": auth_search_chefs,
    "auth_get_meal_plan": auth_get_meal_plan,
    "chef_service_areas": chef_service_areas,
    "service_area_chefs": service_area_chefs,
    "approve_meal_plan": approve_meal_plan,
    "auth_search_ingredients": auth_search_ingredients,
    "search_meal_ingredients": search_meal_ingredients,
    "auth_search_meals_excluding_ingredient": auth_search_meals_excluding_ingredient,
    "suggest_alternative_meals": suggest_alternative_meals,
    "add_meal_to_plan": add_meal_to_plan,
    "create_meal_plan": create_meal_plan,
    "get_date": get_date,
    "list_upcoming_meals": list_upcoming_meals,
    "remove_meal_from_plan": remove_meal_from_plan,
    "replace_meal_in_plan": replace_meal_in_plan,
    "post_review": post_review,
    "update_review": update_review,
    "delete_review": delete_review,
    "generate_review_summary": generate_review_summary,
    "access_past_orders": access_past_orders,
    "get_user_info": get_user_info,
    "get_goal": get_goal,
    "update_goal": update_goal,
    "adjust_week_shift": adjust_week_shift,
    "get_unupdated_health_metrics": get_unupdated_health_metrics,
    "update_health_metrics": update_health_metrics,
    "check_allergy_alert": check_allergy_alert,
    "provide_nutrition_advice": provide_nutrition_advice,
    "find_nearby_supermarkets": find_nearby_supermarkets,
    "search_healthy_meal_options": search_healthy_meal_options,
    "provide_healthy_meal_suggestions": provide_healthy_meal_suggestions,
    "understand_dietary_choices": understand_dietary_choices,
    "create_meal": create_meal,
}

def ai_call(tool_call, request):
    function = tool_call.function
    name = function.name
    arguments = json.loads(function.arguments)
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    return_value = functions[name](**arguments)
    tool_outputs = {
        "tool_call_id": tool_call.id,
        "output": return_value,
        "function": name,
    }
    return tool_outputs

@shared_task
def update_chef_embeddings():    
    for chef in Chef.objects.filter(chef_embedding__isnull=True):
        chef_str = str(chef)  # Generate the string representation for the chef
        chef.chef_embedding = get_embedding(chef_str)  # Generate and assign the new embedding
        chef.save()  # Save the updated chef

@shared_task
def update_embeddings():

    for meal in Meal.objects.filter(meal_embedding__isnull=True):
        meal.meal_embedding = get_embedding(str(meal))
        meal.save()

    for dish in Dish.objects.filter(dish_embedding__isnull=True):
        dish.dish_embedding = get_embedding(str(dish))
        dish.save()

    for ingredient in Ingredient.objects.filter(ingredient_embedding__isnull=True):
        ingredient.ingredient_embedding = get_embedding(str(ingredient))
        ingredient.save()


@shared_task
def generate_user_summary(user_id):
    user = CustomUser.objects.get(id=user_id)

    # Calculate the date one month ago
    one_month_ago = timezone.now() - timedelta(days=30)

    # Query the models for records related to the user and within the past month, except for goals
    goal_tracking = GoalTracking.objects.filter(user=user)
    user_health_metrics = UserHealthMetrics.objects.filter(user=user, date_recorded__gte=one_month_ago)
    calorie_intake = CalorieIntake.objects.filter(user=user, date_recorded__gte=one_month_ago)

    # Format the queried data
    formatted_data = {
        "Goal Tracking": [f"Goal: {goal.goal_name}, Description: {goal.goal_description}" for goal in goal_tracking] if goal_tracking else ["No goals found."],
        "User Health Metrics": [
            f"Date: {metric.date_recorded}, Weight: {metric.weight} kg ({metric.weight * 2.20462} lbs), BMI: {metric.bmi}, Mood: {metric.mood}, Energy Level: {metric.energy_level}" 
            for metric in user_health_metrics
        ] if user_health_metrics else ["No health metrics found."],
        "Calorie Intake": [f"Meal: {intake.meal_name}, Description: {intake.meal_description}, Portion Size: {intake.portion_size}, Date: {intake.date_recorded}" for intake in calorie_intake] if calorie_intake else ["No calorie intake data found."],
    }
    message = "No data found for the past month."
    client = OpenAI(api_key=settings.OPENAI_KEY) # Initialize OpenAI client
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", 
                 "content": f"Generate a detailed summary based on the following data that gives the user a high level view of their goals, health data, and how their caloric intake relates to those goals. Start the response off with a friendly welcoming tone.: {formatted_data}. If there is no data, please respond with the following message: {message}"
                 },
            ],
        )
        summary_text = response.choices[0].message.content
    except Exception as e:
        # Handle exceptions or log errors
        return {"message": f"An error occurred: {str(e)}"}

    UserSummary.objects.update_or_create(user=user, defaults={'summary': summary_text})

    return {"message": "Summary generated successfully."}


@shared_task
def process_user_message(request, message_id, assistant_id):
    try:
        formatted_outputs = []
        user_message = UserMessage.objects.get(id=message_id)
        user = user_message.user
        question = user_message.message
        thread_id = user_message.thread.openai_thread_id  # Assuming 'thread' is a field storing thread ID

        # Creating a message in the OpenAI thread
        try:
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=question
            )
        except OpenAIError as e:
            if 'Can\'t add messages to thread' in str(e) and 'while a run' in str(e) and 'is active' in str(e):
                # Extract the run ID from the error message
                match = re.search(r'run (\w+)', str(e))
                if match:
                    run_id = match.group(1)
                    # Cancel the active run
                    client.beta.threads.runs.cancel(run_id, thread_id=thread_id)
                    # Try to create the message again
                    client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=question
                    )
            else:
                logger.error(f'Failed to create message: {str(e)}')
                user_message.response = f"Sorry, I was unable to send your message. Please try again."
                user_message.save()
                return  # Stopping the task if message creation fails

        # Running the Assistant
        try:
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id  # Assuming the user has an associated assistant ID
            )
        except Exception as e:
            logger.error(f'Failed to create run: {str(e)}')
            user_message.response = "I'm sorry, I'm still processing your request. Please try again or start a new chat."
            user_message.save()
            return  # Stopping the task if run creation fails

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
                    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                        # Execute the function call and get the result
                        tool_call_result = ai_call(tool_call, request)
                        # Extracting the tool_call_id and the output
                        tool_call_id = tool_call_result['tool_call_id']
                        output = tool_call_result['output']
                        # Assuming 'output' needs to be serialized as a JSON string
                        # If it's already a string or another format is required, adjust this line accordingly
                        output_json = json.dumps(output)
                        # Prepare the output in the required format
                        formatted_output = {
                            "tool_call_id": tool_call_id,
                            "output": output_json
                        }
                        tool_outputs.append(formatted_output)

                        formatted_outputs.append(formatted_output)
                    # Chef if the run is still active before submitting the tool outputs
                        run_status_check = client.beta.threads.runs.retrieve(
                            thread_id=thread_id,
                            run_id=run.id
                        )
                    if run_status_check not in ['queued', 'in_progress', 'requires_action', 'running']:   
                        client.beta.threads.runs.submit_tool_outputs(
                            thread_id=thread_id,
                            run_id=run.id,
                            tool_outputs=tool_outputs,
                        )
                        continue
            except Exception as e:
                logger.critical(f'Critical error occurred: {e}', exc_info=True)
        # Check the status of the Run and retrieve responses
        #TODO: Move the context and formatted_context part to the function where a message response is received from the assistant
        try:
            # Retrieve messages and log them
            messages = client.beta.threads.messages.list(thread_id)
            last_assistant_message = next((msg.content[0].text.value for msg in (messages.data) if msg.role == 'assistant'), None)               

            # Updating the UserMessage instance with the response
            user_message.response = last_assistant_message
            user_message.save()
        except Exception as e:
            logger.error(f'Failed to list messages: {str(e)}')
            user_message.response = f"Sorry, I was unable to retrieve the message. Please try again."
            return 

    except Exception as e:
        logger.error(f'Error processing message: {str(e)}')
        # Optionally update the message with an error notice
        user_message = UserMessage.objects.get(id=message_id)  # Re-fetch in case of failure before initial fetch
        user_message.response = f"Sorry, I was unable to process your request. Please try again."
        user_message.save()
        return
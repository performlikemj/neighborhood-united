# might have to move this to the root or the shared folder
from celery import shared_task
from meals.models import Meal, Dish, Ingredient
from chefs.models import Chef  # Adjust the import path based on your project structure
from openai import OpenAI
from django.conf import settings
from custom_auth.models import CustomUser
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake, UserSummary
from django.utils import timezone
from datetime import timedelta

client = OpenAI(api_key=settings.OPENAI_KEY)

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding if response.data else None

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

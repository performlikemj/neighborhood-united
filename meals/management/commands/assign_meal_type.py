# meals/management/commands/assign_meal_type.py

import os
import logging
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from meals.models import Meal
import openai
from django.conf import settings
import dotenv
from openai import OpenAIError, RateLimitError
import re
from meals.pydantic_models import MealTypeAssignment

dotenv.load_dotenv()

class Command(BaseCommand):
    help = 'Assign meal_type to existing meals using OpenAI Chat Completion API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of meals to process in each batch (default: 10)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the assignment without saving changes to the database'
        )
        parser.add_argument(
            '--sleep',
            type=int,
            default=1,
            help='Seconds to sleep between API calls to respect rate limits (default: 1)'
        )

    def handle(self, *args, **options):
        # Configure logging
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Retrieve OpenAI API key
        openai_api_key = os.getenv('OPENAI_KEY') or getattr(settings, 'OPENAI_KEY', None)
        if not openai_api_key:
            logger.error('OpenAI API key not found. Please set the OPENAI_KEY environment variable.')
            return

        client = openai.Client(api_key=openai_api_key)

        batch_size = options['batch_size']
        dry_run = options['dry_run']
        sleep_duration = options['sleep']

        # Fetch meals without a valid meal_type
        meals_to_process = Meal.objects.all()

        total_meals = meals_to_process.count()
        logger.info(f'Total meals to process: {total_meals}')

        if total_meals == 0:
            logger.info('No meals require meal_type assignment.')
            return

        processed = 0

        for meal in meals_to_process.iterator():
            processed += 1
            logger.info(f'Processing Meal ID {meal.id}: {meal.name}')

            # Prepare the prompt
            prompt = (
                f"Determine the appropriate meal type for the following meal based on its name and description.\n\n"
                f"Name: {meal.name}\n"
                f"Description: {meal.description}\n\n"
                f"Meal Type (Breakfast, Lunch, Dinner):"
            )

            try:
                # Call OpenAI Chat Completion API
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "developer",
                            "content": (
                                "You are a helpful assistant that classifies meals into Breakfast, Lunch, or Dinner based on their names and descriptions."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    # Define the response_format using Pydantic's model_json_schema
                    response_format={
                        'type': 'json_schema',
                        'json_schema': {
                            "name": "MealTypeAssignment",
                            "schema": MealTypeAssignment.model_json_schema()  # Pydantic v2 method
                        }
                    },
                    temperature=0  # Set to 0 for deterministic output
                )

                # Extract the meal_type from the response
                assistant_message = response.choices[0].message.content.strip()

                # Use regex to find 'Breakfast', 'Lunch', or 'Dinner' in the message
                match = re.search(r'\b(Breakfast|Lunch|Dinner)\b', assistant_message, re.IGNORECASE)
                if match:
                    meal_type = match.group(1).capitalize()
                else:
                    meal_type = None

                if meal_type not in ['Breakfast', 'Lunch', 'Dinner']:
                    logger.warning(
                        f"Invalid meal_type '{assistant_message}' returned for Meal ID {meal.id}. Skipping assignment."
                    )
                    continue
                else:
                    # Assign the meal_type
                    if not dry_run:
                        with transaction.atomic():
                            meal.meal_type = meal_type
                            meal.save()
                            logger.info(f"Assigned meal_type '{meal_type}' to Meal ID {meal.id}")
            except RateLimitError:
                logger.error('Rate limit exceeded. Sleeping before retrying...')
                time.sleep(60)  # Wait for a minute before retrying
                continue
            except OpenAIError as e:
                logger.error(f'OpenAI API error for Meal ID {meal.id}: {e}')
                continue
            except Exception as e:
                logger.error(f'Unexpected error for Meal ID {meal.id}: {e}')
                continue

            # Sleep to respect rate limits
            time.sleep(sleep_duration)

        logger.info('Meal type assignment process completed.')
        if dry_run:
            logger.info('Dry run enabled. No changes were saved to the database.')

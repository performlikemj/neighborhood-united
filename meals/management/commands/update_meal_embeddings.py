from django.core.management.base import BaseCommand
from meals.models import Meal
from django.db import transaction
import logging
from tqdm import tqdm  # Import tqdm for progress bar
from shared.utils import is_valid_embedding
import numpy as np

logger = logging.getLogger(__name__)

def ensure_flat_embedding(embedding, expected_length=1536):
    """Ensure the embedding is a flat list of floats with the expected length."""
    if isinstance(embedding, list):
        if all(isinstance(x, float) for x in embedding):
            if len(embedding) == expected_length:
                return embedding
            else:
                logger.error(f"Embedding length {len(embedding)} does not match expected {expected_length}.")
                return None
        else:
            logger.error("Embedding contains non-float elements.")
            return None
    elif isinstance(embedding, np.ndarray):
        # Convert to list and validate
        embedding = embedding.flatten().tolist()
        if is_valid_embedding(embedding):
            return embedding
        else:
            logger.error("Embedding contains non-float elements after flattening.")
            return None
    else:
        logger.error("Embedding is not a list or NumPy array.")
        return None

class Command(BaseCommand):
    help = 'Updates embeddings for all meals in the database.'

    def handle(self, *args, **options):
        meals = Meal.objects.all()
        total_meals = meals.count()
        logger.info(f"Starting embedding update for {total_meals} meals.")

        for meal in tqdm(meals, desc="Updating Embeddings", unit="meal"):
            try:
                # Generate embedding using the get_meal_embedding method
                embedding = meal.get_meal_embedding()
                
                if embedding is None:
                    logger.warning(f"Meal ID {meal.id} - '{meal.name}': Failed to generate embedding. Skipping.")
                    continue

                # Ensure the embedding is flat and has the correct length
                embedding = ensure_flat_embedding(embedding)
                if embedding is None:
                    logger.warning(f"Meal ID {meal.id} - '{meal.name}': Invalid embedding structure. Skipping.")
                    continue

                # Update the meal_embedding field
                meal.meal_embedding = embedding
                meal.save(update_fields=['meal_embedding'])
                logger.info(f"Meal ID {meal.id} - '{meal.name}': Embedding updated.")

            except Exception as e:
                logger.error(f"Meal ID {meal.id} - '{meal.name}': Error updating embedding - {e}")

        logger.info("Completed embedding update for all meals.")
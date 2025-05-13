"""
Audio processing utilities for pantry item management.
This module provides functionality to process audio recordings of pantry items
and extract relevant information using OpenAI's Whisper API.
"""
import os
import re
import logging
import tempfile
from datetime import datetime
from typing import Dict, Optional, Tuple, Any, List
from decimal import Decimal
from meals.pydantic_models import PantryItemSchema
from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = settings.OPENAI_KEY
client = OpenAI(api_key=OPENAI_API_KEY)



def transcribe_audio(audio_file) -> str:
    """
    Transcribe an audio file using OpenAI's Whisper API.
    
    Args:
        audio_file: The audio file to transcribe (can be Django's UploadedFile)
        
    Returns:
        str: The transcribed text
    """
    try:
        # Create a temporary file to handle Django's UploadedFile
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_file.name.split('.')[-1]}") as temp_file:
            # For Django's UploadedFile, we need to read chunks and write them
            for chunk in audio_file.chunks():
                temp_file.write(chunk)
            temp_file.flush()
            
            # Use the temporary file for the API call
            with open(temp_file.name, 'rb') as file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=file,  # Pass the opened file object
                    response_format="text"
                )
                
        # Clean up the temporary file
        try:
            os.unlink(temp_file.name)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file: {e}")
            
        # Return the transcription result
        # When response_format="text", the API returns the text directly
        return transcription
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise

def extract_pantry_item_info(transcription: str) -> Dict[str, Any]:
    """
    Extract pantry item information from a transcription.
    
    Args:
        transcription: The transcribed text from the audio
        
    Returns:
        Dict containing extracted pantry item information:
        - item_name: str
        - quantity: int
        - expiration_date: date or None
        - item_type: str (one of the valid choices)
        - notes: str or None
        - weight_per_unit: decimal or None
        - weight_unit: str or None
    """
    # Use GPT to extract structured information from the transcription
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "developer", "content": ("""
                 # Identity

                    You are an assistant that helps the user convert the user's audio input into pantry item information. Identify the weight and the corresponding unit, then convert the unit into a standardized format using specific mappings.

                    - **Weight Unit Conversion**: 
                    - Convert and map the units as follows:
                        - "ounces" or "oz" to `'oz'`
                        - "pounds" or "lbs" to `'lb'`
                        - "grams" to `'g'`
                        - "kilograms" or "kg" to `'kg'`
                        - "liters" or "L" approximately to `'kg'` (1L ≈ 1kg)
                        - "milliliters" or "mL" approximately to `'g'` (1mL ≈ 1g)

                    # Instructions

                    1. **Identify Item Information**: 
                    - Listen to or transcribe the user's audio to extract pantry item details such as item name, quantity, and weight.
                    2. **Standardize Units**:
                    - Use the mappings above to standardize the units of measurement.
                    3. **Provide Output**:
                    - Clearly list out the pantry item information including the standardized weight unit.

                    # Output Format

                    Produce the output in a structured JSON format as follows:
                    ```json
                    {
                    "item_name": "placeholder_name",
                    "quantity": "placeholder_quantity",
                    "expiration_date": "placeholder_date",
                    "item_type": Canned/Dry,
                    "notes": "placeholder_notes",
                    "weight_per_unit": "placeholder_weight",
                    "weight_unit": oz/lbs/g etc.
                    }
                    ```

                    # Notes

                    - Ensure accurate extraction of item names and quantities.
                    - The standardization of units is based on approximate conversions for liters and milliliters.
                    - This task assumes ideal conditions where audio correctly translates into transcribable text.
                """)},
                {"role": "user", "content": transcription}
            ],
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'pantry_item',
                    'schema': PantryItemSchema.model_json_schema()
                }
            }
        )
        
        # Parse the response to extract information
        content = response.output_text
        import json
        data = json.loads(content)
        
        # Process the expiration date if present
        expiration_date = None
        if data.get('expiration_date'):
            try:
                # Handle various date formats
                date_str = data['expiration_date']
                # Try different date formats
                for date_format in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y', '%b %d, %Y']:
                    try:
                        expiration_date = datetime.strptime(date_str, date_format).date()
                        break
                    except ValueError:
                        continue
            except Exception as e:
                logger.warning(f"Could not parse expiration date: {str(e)}")
        
        # Ensure item_type is one of the valid choices
        item_type = data.get('item_type', 'Canned')
        if item_type not in ['Canned', 'Dry']:
            item_type = 'Canned'  # Default to Canned if not specified or invalid
        
        # Process weight_per_unit
        weight_per_unit = None
        if data.get('weight_per_unit') is not None:
            try:
                weight_per_unit = float(data.get('weight_per_unit'))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert weight_per_unit to float: {data.get('weight_per_unit')}")
        
        # Process weight_unit - Pydantic should already validate this
        weight_unit = data.get('weight_unit')
        
        # Return the structured data
        return {
            'item_name': data.get('item_name', ''),
            'quantity': data.get('quantity', 1),
            'expiration_date': expiration_date,
            'item_type': item_type,
            'notes': data.get('notes'),
            'weight_per_unit': weight_per_unit,
            'weight_unit': weight_unit
        }
    except Exception as e:
        logger.error(f"Error extracting pantry item info: {str(e)}")
        # Return default values if extraction fails
        return {
            'item_name': '',
            'quantity': 1,
            'expiration_date': None,
            'item_type': 'Canned',
            'notes': f"Error processing transcription: {transcription}",
            'weight_per_unit': None,
            'weight_unit': None
        }

def process_audio_for_pantry_item(audio_file) -> Dict[str, Any]:
    """
    Process an audio file to extract pantry item information.
    
    Args:
        audio_file: The audio file to process
        
    Returns:
        Dict containing extracted pantry item information
    """
    # Transcribe the audio
    transcription = transcribe_audio(audio_file)
    
    # Extract pantry item information from the transcription
    pantry_item_info = extract_pantry_item_info(transcription)
    
    # Add the original transcription to the result
    pantry_item_info['transcription'] = transcription
    
    return pantry_item_info 
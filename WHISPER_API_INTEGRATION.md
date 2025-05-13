# Voice-Based Pantry Item Addition

This document explains how to integrate the OpenAI Whisper API for voice-based pantry item addition into your existing Streamlit application.

## Implementation Overview

The implementation consists of three main components:

1. **Backend API Endpoint**: A Django API endpoint that processes audio files, transcribes them using OpenAI's Whisper API, and extracts pantry item information.
2. **Utility Functions**: Helper functions for audio processing and extracting structured information from transcriptions.
3. **Streamlit Frontend**: A UI component that allows users to record audio and send it to the backend.

## Files Added/Modified

- `meals/audio_utils.py`: Utility functions for audio processing using OpenAI's APIs
- `meals/views.py`: Added a new API endpoint `api_pantry_item_from_audio`
- `meals/urls.py`: Added a URL path for the new endpoint
- `streamlit_pantry_voice.py`: Streamlit component for voice input integration

## How to Integrate with Your Existing Pantry Page

### Add as a Tab

The simplest way to integrate is to add a "Voice Input" tab to your existing pantry page:

```python
import streamlit as st
from streamlit_pantry_voice import add_pantry_item_from_voice

# In your pantry page:
tab_list, tab_voice = st.tabs(["List View", "Voice Input"])
            
with tab_list:
    # Your existing pantry list view code
    # ...

with tab_voice:
    # Add the voice input component
    add_pantry_item_from_voice()
```

## How It Works

1. User speaks into their microphone via the Streamlit `st.audio_input()` widget
2. The audio is sent to the Django backend API
3. Backend transcribes the audio using OpenAI's Whisper API
4. The transcription is processed by GPT-4.1-nano to extract pantry item details
5. A new pantry item is created with the extracted information
6. The result is returned to the Streamlit frontend

## Tips for Optimal Use

1. **Clear Audio**: Encourage users to speak clearly and in a quiet environment

2. **Complete Information**: Users should mention all required details in their description:
   - Item name (e.g., "black beans")
   - Quantity (e.g., "3 cans")
   - Expiration date (optional, e.g., "expires December 2025")
   - Type (e.g., "canned" or "dry goods")
   - Weight or volume (optional, e.g., "16 ounces", "2 liters")

3. **Weight and Volume Units**: The system supports various units:
   - Volume measurements (e.g., "2 liters of milk", "500 milliliters of cream")
   - Weight measurements (e.g., "16 ounces of flour", "1 kilogram of rice")
   - These will be converted to appropriate units in the system

4. **Example Prompts**: Provide example prompts for users to follow, such as:
   - "Two cans of organic black beans, expires January 15th, 2025. Canned goods."
   - "Five packages of whole wheat pasta, dry goods, expires end of 2024."
   - "One bottle of olive oil, 750 milliliters, dry goods, expires 2025."
   - "A 2-liter bottle of apple juice, expires next month."

## Troubleshooting

- **Audio Not Processing**: Check browser microphone permissions and ensure the user has allowed microphone access
- **Transcription Errors**: If the transcription is incorrect, the user can try again with clearer pronunciation
- **Extraction Errors**: If the extracted information is inaccurate, users can manually edit the item after it's added
- **Unit Conversion Issues**: If units aren't recognized, try using standard abbreviations (oz, lb, g, kg, ml, l)

## Security Considerations

- The audio files are processed securely and not stored permanently
- All communication between the frontend and backend should use HTTPS
- Proper authentication is required to use this feature (using your existing auth system)

## Technical Requirements

- OpenAI API key configured in Django settings
- Streamlit 1.42.0 or newer for `st.audio_input()` support
- Browser with microphone support
- Proper CORS configuration if running Streamlit on a different domain 
import os
import urllib.parse
from django.http import JsonResponse
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib import messages

def standardize_stripe_response(success, message, redirect_url=None, data=None, status_code=200):
    """
    Standardize the response format for Stripe-related operations.
    Returns a JSON response that the Streamlit app can handle.
    """
    response_data = {
        "success": success,
        "message": message,
        "status": "success" if success else "error"
    }
    
    if redirect_url:
        response_data["redirect_url"] = redirect_url
    
    if data:
        response_data.update(data)
    
    return Response(response_data, status=status_code)

def handle_stripe_error(request, error_message, status_code=400):
    """
    Handle Stripe errors consistently across the application.
    Returns JSON response that Streamlit can handle.
    """
    return Response({
        "success": False,
        "status": "error",
        "message": str(error_message),
        "error_details": str(error_message)
    }, status=status_code)

def get_stripe_return_urls(success_path="", cancel_path=""):
    """
    Generate standard success and cancel URLs for Stripe sessions.
    Uses environment variables to determine the full URLs for redirects.
    """
    streamlit_url = os.getenv("STREAMLIT_URL")
    if not streamlit_url:
        # Fallback if STREAMLIT_URL is not set
        streamlit_url = "http://localhost:8501"
        
    # If success_path starts with /api/, it's a backend endpoint (doesn't need streamlit_url prefix)
    if success_path.startswith("/api/"):
        base_url = os.getenv("BACKEND_URL", streamlit_url)  # Use BACKEND_URL if defined
        success_url = f"{base_url}{success_path}"
        # If success_path doesn't contain session_id parameter, add it
        if "{CHECKOUT_SESSION_ID}" not in success_path:
            success_url += ("&" if "?" in success_path else "?") + "session_id={CHECKOUT_SESSION_ID}"
    else:
        # For frontend paths, use the Streamlit URL with appropriate paths
        # Remove leading slash if present to avoid double slashes
        success_path = success_path.lstrip('/')
        cancel_path = cancel_path.lstrip('/')
        
        # Default to payment-success and payment-cancelled if paths are just "/"
        if success_path == "/":
            success_path = "" 
        if cancel_path == "/":
            cancel_path = ""
            
        success_url = f"{streamlit_url}/{success_path}"
        
    # For cancel URL, also handle API endpoints vs frontend paths
    if cancel_path.startswith("/api/"):
        base_url = os.getenv("BACKEND_URL", streamlit_url)
        cancel_url = f"{base_url}{cancel_path}"
    else:
        # Remove leading slash if present
        cancel_path = cancel_path.lstrip('/')
        if cancel_path == "/":
            cancel_path = ""
        cancel_url = f"{streamlit_url}/{cancel_path}"
        
    return {
        "success_url": success_url,
        "cancel_url": cancel_url
    }
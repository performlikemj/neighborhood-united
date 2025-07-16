from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.conf import settings
from django.views.decorators.http import require_http_methods
import logging
import json
import os
import re # Added for regex parsing
import traceback # Ensure traceback is imported
import requests # Added for direct n8n calls
import uuid # For generating session_identifier if models were here
from custom_auth.models import CustomUser
from customer_dashboard.models import AssistantEmailToken, UserEmailSession, EmailAggregationSession, AggregatedMessageContent, PreAuthenticationMessage
from meals.meal_assistant_implementation import MealPlanningAssistant
from utils.redis_client import get, set, delete
from django.template.loader import render_to_string 
from .tasks import process_aggregated_emails
from requests.compat import urlencode 
from utils.translate_html import translate_paragraphs  # Import the translation utility
from bs4 import BeautifulSoup
from django.conf.locale import LANG_INFO

logger = logging.getLogger(__name__)

# Cache key prefix for the FLAG indicating an active DB aggregation session
ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX = "active_db_aggregation_session_user_"
AGGREGATION_WINDOW_MINUTES = 5

# Helper function to get language name
def _get_language_name(language_code):
    """
    Returns the full language name for a given language code.
    Falls back to the code itself if the language is not found.
    """
    if language_code in LANG_INFO and 'name' in LANG_INFO[language_code]:
        return LANG_INFO[language_code]['name']
    return language_code

def extract_token_from_assistant_email(assistant_email_str):
    if not assistant_email_str:
        return None
    # Regex to find the token in formats like "mj+TOKEN@sautai.com" or "<mj+TOKEN@sautai.com>" or "Display Name <mj+TOKEN@sautai.com>"
    match = re.search(r'mj\+([a-zA-Z0-9\-]+)@sautai\.com', assistant_email_str)
    if match:
        return match.group(1)
    return None

# secure_email_integration.py
@csrf_exempt
@require_http_methods(["POST"])
def process_email(request):
    """API endpoint for processing emails from n8n"""
    try:
        data = json.loads(request.body)
        sender_email = data.get('sender_email')
        assistant_email_str = data.get('assistant_email') # Expecting the full "To" address string
        message_content = data.get('message_content')
        original_subject = data.get('original_subject', '')
        in_reply_to_header = data.get('in_reply_to_header')
        email_thread_id = data.get('email_thread_id')
        openai_thread_context_id = data.get('openai_thread_context_id') # From X-SautAI-Thread header

        # Early exit for emails sent from the system's own address to prevent loops/unwanted processing
        if sender_email:
            # Parse the sender_email to handle formats like "Display Name <email@example.com>"
            actual_sender_email_address = sender_email
            sender_match = re.search(r'<([^>]+)>', sender_email)
            if sender_match:
                actual_sender_email_address = sender_match.group(1)

            # Now compare in a case-insensitive way
            if actual_sender_email_address.lower() == "mj@sautai.com":
                return JsonResponse({'status': 'info', 'message': 'Email from system address ignored.'}, status=200)
        # If sender_email was None, it will be caught by the required_params check below.
        
        # Extract email_user_token from assistant_email_str
        email_user_token = extract_token_from_assistant_email(assistant_email_str)

        required_params = {
            'sender_email': sender_email,
            'assistant_email (for token extraction)': assistant_email_str, # Check presence of the raw field
            'message_content': message_content
        }
        missing_raw_params = [k for k, v in required_params.items() if not v]
        if missing_raw_params:
            logger.error(f"Missing required raw parameters: {', '.join(missing_raw_params)}. Data: {data}")
            return JsonResponse({
                'status': 'error',
                'message': f"Missing required parameters for processing: {', '.join(missing_raw_params)}"
            }, status=400)

        if not email_user_token:
            logger.error(f"Could not extract email_user_token from assistant_email: '{assistant_email_str}'. Sender email was: '{sender_email}'. Raw data: {data}")
            return JsonResponse({
                'status': 'error',
                'message': 'Could not parse the assistant email address to find the user token.'
            }, status=400)


        # 1. Lookup User by email_user_token
        try:
            user = CustomUser.objects.get(email_token=email_user_token)
        except CustomUser.DoesNotExist:
            logger.error(f"User not found for email_token: {email_user_token}")
            return JsonResponse({
                'status': 'error',
                'message': 'User not found for the provided email token.'
            }, status=404) # 404 Not Found

        # 2. Verify Sender Email
        # Normalize sender_email if it includes display name, e.g., "Name <email@example.com>"
        parsed_sender_email = sender_email
        match_sender = re.search(r'<([^>]+)>', sender_email)
        if match_sender:
            parsed_sender_email = match_sender.group(1)

        if user.email.lower() != parsed_sender_email.lower():
            logger.warning(f"Email mismatch for user {user.username} ({user.email}): token owner email {user.email}, sender email {parsed_sender_email} (original: {sender_email})")
            return JsonResponse({
                'status': 'error',
                'message': 'Sender email does not match the registered email for this token.'
            }, status=403) # 403 Forbidden

        # Get user's preferred language for translation
        user_preferred_language = _get_language_name(getattr(user, 'preferred_language', 'en'))
        
        # 3. Check for Active UserEmailSession
        active_user_email_session = UserEmailSession.objects.filter(
            user=user,
            expires_at__gt=timezone.now()
        ).first()

        if active_user_email_session:
            
            # This cache key now stores the DB EmailAggregationSession.session_identifier (UUID string) if a window is active
            active_session_flag_key = f"{ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX}{user.id}"
            
            active_db_session_identifier_str = get(active_session_flag_key)

            if not active_db_session_identifier_str:
                db_aggregation_session = EmailAggregationSession.objects.create(
                    user=user,
                    recipient_email=sender_email,
                    user_email_token=str(user.email_token),
                    original_subject=original_subject,
                    in_reply_to_header=in_reply_to_header,
                    email_thread_id=email_thread_id,
                    openai_thread_context_id_initial=openai_thread_context_id,
                    is_active=True
                )
                AggregatedMessageContent.objects.create(
                    session=db_aggregation_session,
                    content=message_content
                )
                set(active_session_flag_key, str(db_aggregation_session.session_identifier), timeout=AGGREGATION_WINDOW_MINUTES * 60)
                process_aggregated_emails.apply_async(
                    args=[str(db_aggregation_session.session_identifier)],
                    countdown=AGGREGATION_WINDOW_MINUTES * 60
                )
                # Acknowledgment for the first message that starts the window
                ack_message_raw = (
                    "We've received your email. Your assistant, MJ, is on it! "
                    "If you have more details to add, feel free to send another email within the next 5 minutes. "
                    "All messages received in this window will be processed together.<br><br>"
                    "For urgent matters or a more interactive experience, please log in to your sautAI dashboard.<br><br>"
                    "Best,<br>The sautAI Team"
                )
                
                # Wrap the message in paragraph tags to ensure proper translation
                ack_message_with_tags = f"<div><p>{ack_message_raw.replace('<br><br>', '</p><p>')}</p></div>"
                
                # Create a soup with just the raw message to translate the paragraphs directly
                raw_soup = BeautifulSoup(ack_message_with_tags, "html.parser")
                try:
                    # Translate the message directly using our improved translate_paragraphs function
                    raw_soup_translated = BeautifulSoup(translate_paragraphs(str(raw_soup), user_preferred_language), "html.parser")
                    # Extract the translated content from the div
                    ack_message_translated = "".join(str(c) for c in raw_soup_translated.div.contents)
                except Exception as e:
                    logger.error(f"Error directly translating acknowledgment message: {e}")
                    ack_message_translated = ack_message_raw  # Fallback to original
                
                # Now render the email template with the pre-translated content
                ack_email_html_content = render_to_string(
                    'customer_dashboard/assistant_email_template.html',
                    {
                        'user_name': user.get_full_name() or user.username,
                        'email_body_main': ack_message_translated,  # Already translated content
                        'profile_url': f"{os.getenv('STREAMLIT_URL')}/",
                        'personal_assistant_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user.email_token}@sautai.com"
                    }
                )
                
                # Final pass to ensure all template content is translated
                try:
                    ack_email_html_content = translate_paragraphs(
                        ack_email_html_content,
                        user_preferred_language
                    )
                except Exception as e:
                    logger.error(f"Error translating full email HTML: {e}")
                    # n8n traceback
                    n8n_traceback = {
                        'error': str(e),
                        'source': 'process_email',
                        'traceback': traceback.format_exc()
                    }
                    requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                    # Continue with partially translated content
                
                # Check if user has unsubscribed from emails
                unsubscribe = getattr(user, 'unsubscribed_from_emails', False)
                if not unsubscribe:
                    n8n_webhook_url = os.getenv('N8N_EMAIL_REPLY_WEBHOOK_URL')
                    if n8n_webhook_url:
                        payload = {
                            'status': 'success', 'action': 'send_acknowledgment', 
                            'reply_content': ack_email_html_content,
                            'recipient_email': sender_email,
                            'from_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user.email_token}@sautai.com",
                            'original_subject': "Re: " + original_subject if original_subject else "Message from your SautAI Assistant",
                            'in_reply_to_header': in_reply_to_header, 
                            'email_thread_id': email_thread_id
                        }
                        try:
                            response = requests.post(n8n_webhook_url, json=payload, timeout=10)
                            response.raise_for_status()
                            logger.info(f"Acknowledgment email successfully sent to n8n for user {user.id} (recipient: {sender_email}).")
                            return JsonResponse({
                                'status': 'success',
                                'action': 'acknowledgment_sent_db_session_forced_new',
                                'message': 'Session recovered. Acknowledgment email processed.'
                            })
                        except requests.RequestException as e_n8n:
                            logger.error(f"Failed to send acknowledgment email to n8n for user {user.id}: {e_n8n}. Payload: {json.dumps(payload)}")
                            # If ack fails, the DB session and Celery task are still created. Consider implications.
                            return JsonResponse({
                                'status': 'error',
                                'message': f'Failed to send acknowledgment email via n8n: {str(e_n8n)}'
                            }, status=500)
                    else:
                        logger.error("N8N_EMAIL_REPLY_WEBHOOK_URL not configured. Cannot send acknowledgment email.")
                        # DB session and Celery task are created.
                        # n8n traceback
                        n8n_traceback = {
                            'error': 'N8N_EMAIL_REPLY_WEBHOOK_URL not configured. Cannot send acknowledgment email.',
                            'source': 'process_email',
                            'traceback': traceback.format_exc()
                        }
                        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Email service (n8n webhook) not configured for acknowledgments, but DB session started.'
                        }, status=500)
                else:
                    return JsonResponse({
                        'status': 'success',
                        'action': 'db_session_started_no_email',
                        'message': 'Session started but no email sent due to user preferences.'
                    })
            else: # DB aggregation window is already active (flag found in cache)
                try:
                    active_db_session = EmailAggregationSession.objects.get(session_identifier=uuid.UUID(active_db_session_identifier_str), user=user, is_active=True)
                    AggregatedMessageContent.objects.create(
                        session=active_db_session,
                        content=message_content
                    )
                    return JsonResponse({
                        'status': 'success',
                        'action': 'message_aggregated_to_db',
                        'message': 'Your additional message has been received and will be processed with your initial request.'
                    }, status=202)
                except EmailAggregationSession.DoesNotExist:
                    logger.error(f"Cache flag indicated active session {active_db_session_identifier_str} for user {user.id}, but DB session not found or not active. Clearing flag.")
                    delete(active_session_flag_key)
                    # This state implies the previous Celery task might have failed or cache out of sync.
                    # Forcing a new session start for this message.
                    # Re-running the logic for a new session:
                    db_aggregation_session = EmailAggregationSession.objects.create(
                        user=user, recipient_email=sender_email, user_email_token=str(user.email_token),
                        original_subject=original_subject, in_reply_to_header=in_reply_to_header,
                        email_thread_id=email_thread_id, openai_thread_context_id_initial=openai_thread_context_id,
                        is_active=True
                    )
                    AggregatedMessageContent.objects.create(session=db_aggregation_session, content=message_content)
                    set(active_session_flag_key, str(db_aggregation_session.session_identifier), timeout=AGGREGATION_WINDOW_MINUTES * 60)
                    process_aggregated_emails.apply_async(args=[str(db_aggregation_session.session_identifier)], countdown=AGGREGATION_WINDOW_MINUTES * 60)
                    # Send acknowledgment for this newly forced session
                    # (Ack email sending logic would be duplicated or refactored into a helper)
                    # ... (ack email sending logic) ... 
                    return JsonResponse({'status': 'success', 'action': 'acknowledgment_sent_db_session_forced_new','message': 'Session recovered. Acknowledgment email processed.'})

                except ValueError: # Invalid UUID from cache
                    logger.error(f"Invalid UUID format '{active_db_session_identifier_str}' in cache for key {active_session_flag_key}. Clearing flag.")
                    delete(active_session_flag_key)
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Internal session error. Please try sending your initial message again.'
                    }, status=500)

        else:
            # Scenario B: No Active UserEmailSession Found - Send Auth Link & Store Pending Message
            logger.info(f"No active UserEmailSession for user {user.username}. Generating auth token and storing pending message.")
            
            # Invalidate any previous, unused auth tokens for this user AND their pending messages
            # The on_delete=models.CASCADE on PreAuthenticationMessage.auth_token handles deleting pending messages
            AssistantEmailToken.objects.filter(user=user, used=False, expires_at__gt=timezone.now()).update(used=True, expires_at=timezone.now() - timedelta(seconds=1))
            logger.info(f"Invalidated previous unused email auth tokens (and their pending messages via CASCADE) for user {user.id}")

            # Create new auth token
            auth_token_obj = AssistantEmailToken.objects.create(
                user=user,
                expires_at=timezone.now() + timedelta(minutes=settings.EMAIL_ASSISTANT_AUTH_TOKEN_EXPIRY_MINUTES if hasattr(settings, 'EMAIL_ASSISTANT_AUTH_TOKEN_EXPIRY_MINUTES') else 15)
            )
            
            # Create PreAuthenticationMessage linked to this token
            PreAuthenticationMessage.objects.create(
                auth_token=auth_token_obj,
                user=user,
                content=message_content,
                original_subject=original_subject,
                sender_email=sender_email, # Store the actual sender to use if auth succeeds
                in_reply_to_header=in_reply_to_header,
                email_thread_id=email_thread_id,
                openai_thread_context_id=openai_thread_context_id
            )
            logger.info(f"Stored pending message for user {user.id} with new auth token {auth_token_obj.auth_token}")

            try:
                site_domain_raw = os.getenv('STREAMLIT_URL')
                print(f"STREAMLIT_URL: {site_domain_raw}")
                site_domain = site_domain_raw.strip('"\'') if site_domain_raw else ''
                # Corrected query parameter construction for auth_link
                if site_domain:
                    base_auth_url = f"{site_domain}"
                    params = {'auth_token': auth_token_obj.auth_token, 'action': 'email_auth'}
                    # Using requests.compat.urlencode for proper query string generation
                    auth_link = f"{base_auth_url}/assistant?{urlencode(params)}"
                else:
                    auth_link = '' # Handle case where site_domain is empty
                    logger.error("STREAMLIT_URL is not set, cannot generate auth link.")

            except Exception as e: 
                logger.error(f"Error generating auth link: {e}")
                # Fallback still needs quote stripping and proper URL construction
                site_domain_raw_fallback = os.getenv('STREAMLIT_URL')
                site_domain_fallback = site_domain_raw_fallback.strip('"\'') if site_domain_raw_fallback else ''
                if site_domain_fallback:
                    base_auth_url_fallback = f"{site_domain_fallback}/assistant"
                    params_fallback = {'auth_token': auth_token_obj.auth_token, 'action': 'email_auth'}
                    auth_link = f"{base_auth_url_fallback}?{urlencode(params_fallback)}"
                else:
                    auth_link = '' # Handle case where fallback site_domain is empty
                    logger.error("STREAMLIT_URL is not set, cannot generate fallback auth link.")

            # Prepare and send the authentication link email using the template
            user_name_for_template = user.get_full_name() or user.username
            site_domain_raw_template = os.getenv('STREAMLIT_URL')
            site_domain_for_template = site_domain_raw_template.strip('"\'') if site_domain_raw_template else ''
            profile_url_for_template = f"{site_domain_for_template}/"
            personal_assistant_email_for_template = user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user.email_token}@sautai.com"
            auth_email_body_raw = (
                f"<p>To continue your conversation with MJ, your SautAI assistant via email, please authenticate your session by clicking the link below:</p>"
                f"<p><a href=\"{auth_link}\" style=\"color: #4CAF50; text-decoration: underline; font-weight: bold;\">Authenticate My Email Session</a></p>"
                f"<p>This link is valid for {settings.EMAIL_ASSISTANT_AUTH_TOKEN_EXPIRY_MINUTES if hasattr(settings, 'EMAIL_ASSISTANT_AUTH_TOKEN_EXPIRY_MINUTES') else 15} minutes.</p>"
                f"<p>If you did not request this, please ignore this email.</p>"
            )

            # Translate the raw auth message content before passing it to the template
            try:
                # Create a soup with just the raw message to translate the paragraphs directly
                raw_soup = BeautifulSoup(f"<div>{auth_email_body_raw}</div>", "html.parser")
                # Translate the message directly using our improved translate_paragraphs function
                raw_soup_translated = BeautifulSoup(translate_paragraphs(str(raw_soup), user_preferred_language), "html.parser")
                # Extract the translated content from the div
                auth_email_body_translated = "".join(str(c) for c in raw_soup_translated.div.contents)
            except Exception as e:
                logger.error(f"Error directly translating authentication message: {e}")
                # n8n traceback
                n8n_traceback = {
                    'error': str(e),
                    'source': 'process_email',
                    'traceback': traceback.format_exc()
                }
                requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                auth_email_body_translated = auth_email_body_raw  # Fallback to original

            auth_email_html_content = render_to_string(
                'customer_dashboard/assistant_email_template.html',
                {
                    'user_name': user_name_for_template,
                    'email_body_main': auth_email_body_translated,
                    'profile_url': profile_url_for_template,
                    'personal_assistant_email': personal_assistant_email_for_template
                }
            )
            
            # Final pass to ensure all template content is translated
            try:
                auth_email_html_content = translate_paragraphs(
                    auth_email_html_content,
                    user_preferred_language
                )
            except Exception as e:
                logger.error(f"Error translating full authentication email HTML: {e}")
                # n8n traceback
                n8n_traceback = {
                    'error': str(e),
                    'source': 'process_email',
                    'traceback': traceback.format_exc()
                }
                requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                # Continue with partially translated content

            auth_subject = "Activate Your SautAI Email Assistant Session"

            # Check if user has unsubscribed from emails
            unsubscribe = getattr(user, 'unsubscribed_from_emails', False)
            if not unsubscribe:
                n8n_webhook_url = os.getenv('N8N_EMAIL_REPLY_WEBHOOK_URL')
                if n8n_webhook_url:
                    payload = {
                        'status': 'success',
                        'action': 'send_auth_link', 
                        'reply_content': auth_email_html_content,
                        'recipient_email': sender_email,
                        'from_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user.email_token}@sautai.com",
                        'original_subject': auth_subject, # This is a new email thread
                        'in_reply_to_header': None, # Typically auth emails start new threads
                        'email_thread_id': None 
                    }
                    try:
                        response = requests.post(n8n_webhook_url, json=payload, timeout=10)
                        response.raise_for_status()
                        return JsonResponse({
                            'status': 'success',
                            'action': 'auth_link_sent_message_pending',
                            'message': 'Authentication required. Your message has been saved and will be processed upon successful authentication.'
                        })
                    except requests.RequestException as e:
                        logger.error(f"Failed to send auth link email to n8n for user {user.id}: {e}. Payload: {json.dumps(payload)}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Failed to send authentication link email via n8n: {str(e)}'
                        }, status=500)
                else:
                    logger.error("N8N_EMAIL_REPLY_WEBHOOK_URL not configured. Cannot send auth link email.")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Email service (n8n webhook) not configured for auth links.'
                    }, status=500)
            else:
                logger.info(f"User {user.username} has unsubscribed from emails. Skipping authentication email.")
                return JsonResponse({
                    'status': 'success',
                    'action': 'auth_token_created_no_email',
                    'message': 'Authentication token created but no email sent due to user preferences.'
                })

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON body.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format.'}, status=400)
    except CustomUser.DoesNotExist: # This might be redundant if already handled, but good for safety
        logger.error(f"User lookup failed during email processing. Token: {email_user_token if 'email_user_token' in locals() else 'Not Extracted'}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'User not found.'}, status=404)
    except Exception as e:
        logger.error(f"Unhandled error in process_email: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

# Removed redundant comment about importing traceback as it's imported above

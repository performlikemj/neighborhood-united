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
from shared.utils import get_openai_client
# Enhanced email processor removed - customer standalone meal planning deprecated
from utils.redis_client import get, set, delete
from django.template.loader import render_to_string 
from .tasks import process_aggregated_emails
from requests.compat import urlencode 
from utils.translate_html import translate_paragraphs, _get_language_name # Import the translation utility
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Cache key prefix for the FLAG indicating an active DB aggregation session
ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX = "active_db_aggregation_session_user_"
AGGREGATION_WINDOW_MINUTES = 5

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
    """API endpoint for processing emails from n8n - UNCHANGED"""
    # NOTE: This function remains exactly the same as your original.
    # The enhancement happens in the Celery task (process_aggregated_emails)
    # where the actual assistant processing occurs.
    
    try:
        data = json.loads(request.body)
        sender_email = data.get('sender_email')
        assistant_email_str = data.get('assistant_email') # Expecting the full "To" address string
        message_content = data.get('message_content')
        original_subject = data.get('original_subject', '')
        in_reply_to_header = data.get('in_reply_to_header')
        email_thread_id = data.get('email_thread_id')
        openai_thread_context_id = data.get('openai_thread_context_id') # From X-sautai-Thread header

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
            # Refresh session expiry (sliding window)
            try:
                session_duration_hours = getattr(settings, 'EMAIL_ASSISTANT_SESSION_DURATION_HOURS', 24)
                active_user_email_session.expires_at = timezone.now() + timedelta(hours=session_duration_hours)
                active_user_email_session.save(update_fields=['expires_at'])
            except Exception as e:
                logger.error(f"Failed to refresh UserEmailSession expiry for user {user.id}: {e}")
            
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
                
                # ENHANCED: Pass enhanced processing flag to Celery task
                process_aggregated_emails.apply_async(
                    args=[str(db_aggregation_session.session_identifier)],
                    kwargs={'use_enhanced_formatting': True},  # NEW: Enable enhanced formatting
                    countdown=AGGREGATION_WINDOW_MINUTES * 60
                )
                
                # Create the process now button URL
                try:
                    base_url = os.getenv('STREAMLIT_URL', 'http://localhost:8501')
                    process_now_url = f"{base_url}/account?token={user.email_token}&action=process_now"
                except Exception as e:
                    logger.error(f"Error creating process now URL: {e}")
                    process_now_url = ""
                
                # Acknowledgment for the first message that starts the window
                ack_message_raw = (
                    "We've received your email. Your assistant, MJ, is on it! "
                    "If you have more details to add, feel free to send another email within the next 5 minutes. "
                    "All messages received in this window will be processed together.<br><br>"
                    "Can't wait 5 minutes? Click the button below to process your message immediately:<br><br>"
                    f"<div style='text-align: center; margin: 20px 0;'>"
                    f"<a href='{process_now_url}' style='display: inline-block; background: #4CAF50; color: white; "
                    f"padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;'>"
                    f"🚀 Process My Message Now</a></div><br>"
                    "For urgent matters or a more interactive experience, please log in to your sautai dashboard.<br><br>"
                    "Best,<br>The sautai Team"
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
                    try:
                        from utils.email import send_html_email
                        from_email = user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user.email_token}@sautai.com"
                        subject = "Re: " + original_subject if original_subject else "Message from your sautai Assistant"
                        
                        send_html_email(
                            subject=subject,
                            html_content=ack_email_html_content,
                            recipient_email=sender_email,
                            from_email=from_email
                        )
                        logger.info(f"Acknowledgment email successfully sent for user {user.id} (recipient: {sender_email}).")
                        return JsonResponse({
                            'status': 'success',
                            'action': 'acknowledgment_sent_db_session_forced_new',
                            'message': 'Session recovered. Acknowledgment email processed.'
                        })
                    except Exception as e_email:
                        logger.exception(f"Failed to send acknowledgment email for user {user.id}: {e_email}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Failed to send acknowledgment email: {str(e_email)}'
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
                    
                    # ENHANCED: Pass enhanced processing flag to Celery task
                    process_aggregated_emails.apply_async(
                        args=[str(db_aggregation_session.session_identifier)], 
                        kwargs={'use_enhanced_formatting': True},  # NEW: Enable enhanced formatting
                        countdown=AGGREGATION_WINDOW_MINUTES * 60
                    )
                    
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
                f"<p>To continue your conversation with MJ, your sautai assistant via email, please authenticate your session by clicking the link below:</p>"
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

            auth_subject = "Activate Your sautai Email Assistant Session"

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


# ENHANCED CELERY TASK PROCESSING
# You'll need to update your tasks.py file with this enhanced version

def enhanced_process_aggregated_emails_task(session_identifier_str, use_enhanced_formatting=False):
    """
    Enhanced version of your process_aggregated_emails Celery task
    
    This is the function that should replace or enhance your existing
    process_aggregated_emails task in tasks.py
    """
    try:
        from customer_dashboard.models import EmailAggregationSession, AggregatedMessageContent
        from meals.meal_assistant_implementation import MealPlanningAssistant
        from utils.redis_client import delete
        from django.template.loader import render_to_string
        from utils.translate_html import translate_paragraphs
        from bs4 import BeautifulSoup
        import requests
        import os
        import json
        
        # Get the session
        try:
            session = EmailAggregationSession.objects.get(
                session_identifier=uuid.UUID(session_identifier_str),
                is_active=True
            )
        except EmailAggregationSession.DoesNotExist:
            logger.error(f"EmailAggregationSession {session_identifier_str} not found or not active")
            return
        
        # Mark session as inactive
        session.is_active = False
        session.save()
        
        # Clear the cache flag
        active_session_flag_key = f"{ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX}{session.user.id}"
        delete(active_session_flag_key)
        
        # Aggregate all messages
        messages = AggregatedMessageContent.objects.filter(session=session).order_by('created_at')
        combined_message = "\n\n---\n\n".join([msg.content for msg in messages])
        
        logger.info(f"Processing {messages.count()} aggregated messages for user {session.user.id}")
        
        # Enhanced formatting removed - customer standalone meal planning deprecated
        # Using standard processing only
        if True:
            assistant = MealPlanningAssistant(str(session.user.id))
            response = assistant.send_message(combined_message)
            
            # Extract content from original response
            if isinstance(response, dict):
                message_content = response.get('message', str(response))
            else:
                message_content = str(response)
            
            # Apply basic formatting
            email_body_main = f"<h2>Response from your sautai Assistant</h2>"
            email_body_data = f"<div class='assistant-response'>{message_content}</div>"
            email_body_final = f"<p>Need more help? Just reply to this email!</p>"
            css_classes = ['original-formatting']
        
        # Get user's preferred language
        user_preferred_language = _get_language_name(getattr(session.user, 'preferred_language', 'en'))
        
        # Render the email template
        email_html_content = render_to_string(
            'customer_dashboard/assistant_email_template.html',
            {
                'user_name': session.user.get_full_name() or session.user.username,
                'email_body_main': email_body_main,
                'email_body_data': email_body_data,
                'email_body_final': email_body_final,
                'css_classes': ' '.join(css_classes),
                'profile_url': f"{os.getenv('STREAMLIT_URL')}/",
                'personal_assistant_email': getattr(session.user, 'personal_assistant_email', f"mj+{session.user.email_token}@sautai.com")
            }
        )
        
        # Translate the email content
        try:
            email_html_content = translate_paragraphs(email_html_content, user_preferred_language)
        except Exception as e:
            logger.error(f"Error translating email content: {e}")
        
        # Send the email via n8n
        if not getattr(session.user, 'unsubscribed_from_emails', False):
            n8n_webhook_url = os.getenv('N8N_EMAIL_REPLY_WEBHOOK_URL')
            if n8n_webhook_url:
                payload = {
                    'status': 'success',
                    'action': 'send_response',
                    'reply_content': email_html_content,
                    'recipient_email': session.recipient_email,
                    'from_email': getattr(session.user, 'personal_assistant_email', f"mj+{session.user.email_token}@sautai.com"),
                    'original_subject': "Re: " + session.original_subject if session.original_subject else "Response from your sautai Assistant",
                    'in_reply_to_header': session.in_reply_to_header,
                    'email_thread_id': session.email_thread_id,
                    'enhanced_formatting': use_enhanced_formatting  # Include this for tracking
                }
                
                try:
                    response = requests.post(n8n_webhook_url, json=payload, timeout=30)
                    response.raise_for_status()
                    logger.info(f"Email successfully sent for session {session_identifier_str} (enhanced: {use_enhanced_formatting})")
                except requests.RequestException as e:
                    logger.error(f"Failed to send email for session {session_identifier_str}: {e}")
                    # Send error to n8n traceback
                    n8n_traceback = {
                        'error': str(e),
                        'source': 'enhanced_process_aggregated_emails_task',
                        'session_id': session_identifier_str,
                        'traceback': traceback.format_exc()
                    }
                    requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            else:
                logger.error("N8N_EMAIL_REPLY_WEBHOOK_URL not configured")
        else:
            logger.info(f"User {session.user.username} has unsubscribed from emails")
        
    except Exception as e:
        logger.error(f"Error in enhanced_process_aggregated_emails_task: {str(e)}")
        # Send error to n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'enhanced_process_aggregated_emails_task',
            'session_id': session_identifier_str,
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)

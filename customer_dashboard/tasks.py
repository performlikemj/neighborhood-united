try:
    from groq import Groq
except ImportError:
    Groq = None
from django.conf import settings
import logging
from django.utils import timezone
from datetime import timedelta
import json
import hashlib
import pytz
from zoneinfo import ZoneInfo
from utils.redis_client import get, set, delete
import requests
import traceback
import uuid
import os
from .models import ChatThread, ChatSessionSummary, UserChatSummary, EmailAggregationSession, AggregatedMessageContent
from custom_auth.models import CustomUser
from meals.meal_assistant_implementation import MealPlanningAssistant
# Enhanced email processor and Instacart formatters removed - customer standalone meal planning deprecated
from utils.translate_html import translate_paragraphs, _get_language_name
from shared.utils import get_groq_client
from django.template.loader import render_to_string
import re

# Define constants for cache keys. These should ideally match those in secure_email_integration.py
EMAIL_AGGREGATION_MESSAGES_KEY_PREFIX = "email_aggregation_messages_user_"
EMAIL_AGGREGATION_WINDOW_KEY_PREFIX = "email_aggregation_window_user_"
ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX = "active_db_aggregation_session_user_"

logger = logging.getLogger(__name__)

def generate_chat_title(thread_id):
    """
    Celery task to generate and set the title for a ChatThread asynchronously.
    """
    try:
        thread = ChatThread.objects.get(pk=thread_id)
        # Ensure we still need to generate a title
        if thread.title not in ["Chat with Assistant", "", None] or not thread.openai_input_history:
            return

        first_user_message_content = None
        
        # Log the type and structure of history for debugging
        history_type = type(thread.openai_input_history).__name__
        history_length = len(thread.openai_input_history) if hasattr(thread.openai_input_history, '__len__') else 'unknown'
        logger.debug(f"Thread {thread_id} history type: {history_type}, length: {history_length}")
        
        # Find the first message with role 'user'
        try:
            if isinstance(thread.openai_input_history, list):
                for message in thread.openai_input_history:
                    if isinstance(message, dict) and message.get('role') == 'user':
                        first_user_message_content = message.get('content')
                        break
                    elif isinstance(message, dict) and message.get('type') == 'message' and message.get('from_') == 'user':
                        # Alternative format
                        first_user_message_content = message.get('content', '')
                        break
        except Exception as e:
            logger.error(f"Error parsing message history for ChatThread {thread_id}: {e}", exc_info=True)
            return

        if not first_user_message_content:
            logger.warning(f"Could not find first user message in history for ChatThread {thread_id}. Cannot generate title.")
            return

        logger.debug(f"Found first user message for ChatThread {thread_id}: '{first_user_message_content[:50]}...'")
        try:
            client = Groq(api_key=getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY"))
            prompt = f"Generate a very short, concise title (max 5 words) for a chat conversation that starts with this user message: '{first_user_message_content}'. Do not use quotes in the title."
            response = client.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates concise chat titles based on the user's message."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )

            new_title = response.choices[0].message.content
            if new_title:
                ChatThread.objects.filter(pk=thread_id).update(title=new_title)
            else:
                 logger.warning(f"OpenAI returned an empty title for ChatThread {thread_id}")

        except Exception as e:
            logger.error(f"Error calling OpenAI to generate title for ChatThread {thread_id}: {e}", exc_info=True)

    except ChatThread.DoesNotExist:
        logger.error(f"ChatThread with id {thread_id} not found.")
    except Exception as e:
        logger.error(f"Unexpected error in generate_chat_title task for thread_id {thread_id}: {e}", exc_info=True)

def summarize_user_chat_sessions():
    """
    Hourly task to summarize chat sessions for users when it's 3:30 AM in their timezone.
    """
    
    # Get current UTC time
    now_utc = timezone.now()
    
    # Find users where it's currently 3:30 AM in their timezone
    # We'll process users where local time is between 3:30 AM and 4:29 AM
    eligible_users = []
    
    try:
        # Get all active users
        users = CustomUser.objects.filter(is_active=True)
        
        for user in users:
            try:
                # Skip users without timezone info
                if not user.timezone:
                    continue
                
                # Convert UTC time to user's local time
                user_tz = ZoneInfo(user.timezone)
                user_local_time = now_utc.astimezone(user_tz)
                
                # Check if it's between 3:30 AM and 4:29 AM for this user
                is_summary_hour = (
                    user_local_time.hour == 3 and user_local_time.minute >= 30
                ) or (
                    user_local_time.hour == 4 and user_local_time.minute < 30
                )
                
                if is_summary_hour:
                    eligible_users.append(user)
            except Exception as e:
                logger.error(f"Error processing timezone for user {user.id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error retrieving users: {e}", exc_info=True)
    
    if not eligible_users:
        return 0
    
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    
    # Process only threads belonging to eligible users
    count = 0
    for user in eligible_users:
        # Find active threads for this specific user
        active_threads = ChatThread.objects.filter(
            user=user,
            is_active=True,
            messages__created_at__date=yesterday  # That had messages sent yesterday
        ).distinct()
        
        for thread in active_threads:
            try:
                # Check if we already have a summary for this thread and date
                existing_summary = ChatSessionSummary.objects.filter(
                    thread=thread, 
                    summary_date=yesterday
                ).first()
                
                if existing_summary and existing_summary.status == ChatSessionSummary.COMPLETED:
                    logger.debug(f"Summary already exists for thread {thread.id} on {yesterday}")
                    continue
                    
                # Find the last message processed time, if any
                last_processed = None
                if existing_summary and existing_summary.last_message_processed:
                    last_processed = existing_summary.last_message_processed
                
                # Get messages since the last summary (or only yesterday's messages if no previous summary)
                if last_processed:
                    recent_messages = thread.messages.filter(
                        created_at__gt=last_processed,
                        created_at__date=yesterday
                    ).order_by('created_at')
                else:
                    recent_messages = thread.messages.filter(
                        created_at__date=yesterday
                    ).order_by('created_at')
                
                # Only proceed if there are new messages
                if not recent_messages.exists():
                    logger.debug(f"No new messages for thread {thread.id} on {yesterday}")
                    continue
                
                # Create or update the summary task
                summary_obj, created = ChatSessionSummary.objects.get_or_create(
                    user=thread.user,
                    thread=thread,
                    summary_date=yesterday,
                    defaults={
                        'status': ChatSessionSummary.PENDING
                    }
                )
                
                # Generate the summary
                generate_chat_session_summary(summary_obj.id)
                count += 1
                
            except Exception as e:
                logger.error(f"Error processing thread {thread.id}: {e}", exc_info=True)
                # n8n traceback
                n8n_traceback = {
                    'error': str(e),
                    'source': 'summarize_user_chat_sessions',
                    'traceback': traceback.format_exc()
                }
                requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
    
    # If any summaries were created/updated, run the consolidated summary
    if count > 0:
        consolidate_user_chat_summaries()
    
    return count

def generate_chat_session_summary(summary_id):
    """
    Generate a summary for a specific chat session.
    """
    try:
        summary_obj = ChatSessionSummary.objects.get(id=summary_id)
        
        # Only proceed if pending or error
        if summary_obj.status == ChatSessionSummary.COMPLETED:
            return f"Summary {summary_id} already completed"
        
        thread = summary_obj.thread
        last_processed = summary_obj.last_message_processed
        
        # Get messages to process
        if last_processed:
            messages = thread.messages.filter(
                created_at__gt=last_processed,
                created_at__date=summary_obj.summary_date
            ).order_by('created_at')
        else:
            messages = thread.messages.filter(
                created_at__date=summary_obj.summary_date
            ).order_by('created_at')
        
        if not messages.exists():
            summary_obj.status = ChatSessionSummary.COMPLETED
            summary_obj.summary = "No messages to summarize for this date."
            summary_obj.save()
            return f"No messages to summarize for summary {summary_id}"
        
        # Format conversation for the API
        conversation = []
        for msg in messages:
            conversation.append({
                "role": "user",
                "content": msg.message
            })
            if msg.response:
                conversation.append({
                    "role": "assistant",
                    "content": msg.response
                })
        
        # Only proceed if we have a conversation to summarize
        if not conversation:
            summary_obj.status = ChatSessionSummary.COMPLETED
            summary_obj.summary = "No dialogue to summarize."
            summary_obj.save()
            return f"No dialogue to summarize for summary {summary_id}"
        
        # Call OpenAI API for summarization
        client = Groq(api_key=getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY"))
        
        input_messages = [
            {
                "role": "system",
                "content": """
                Summarize the interactions between the user and assistant, focusing on key details that will be beneficial in future conversations. Emphasize information relevant to the goals of helping the user with meal planning and finding local chefs in their area to prepare meals.

                # Steps

                1. Analyze the messages between the user and the assistant.
                2. Identify and extract key details related to:
                   - User preferences for meal planning.
                   - Specific dietary requirements or restrictions.
                   - Locations or regions of interest for finding chefs.
                   - Any repeated questions or subjects that indicate user priorities.
                   - Feedback or follow-up requests from previous interactions.
                3. Compile these details into a coherent summary.

                # Output Format

                Provide the summary in a structured format, consisting of bullet points for clarity:
                - User Preferences: [Detailed preferences about meal planning]
                - Dietary Requirements: [Any dietary restrictions or requirements]
                - Location Interests: [Regions or areas for finding local chefs]
                - Key Repeated Topics: [Subjects or questions frequently addressed by the user]
                - User Feedback: [Summary of user feedback or requests for follow-up]

                # Example

                **Example Input:**
                1. User: "I am looking for vegan meal plans for a week."
                2. Assistant: "Here are some options for vegan meal planning, including grocery lists and recipes."
                3. User: "Can you find a chef in the San Francisco area?"

                **Example Output:**
                - User Preferences: Interested in vegan meal plans.
                - Dietary Requirements: Vegan.
                - Location Interests: San Francisco area.
                - Key Repeated Topics: Meal planning and local chefs.
                - User Feedback: None.

                # Notes

                - Prioritize information that directly relates to the goals of meal planning and finding local chefs.
                - Condense the information without losing critical context needed for assisting the user in the future.
                """
            },
            {
                "role": "user",
                "content": f"Here is a conversation between a user and a meal planning assistant. Please summarize according to the instructions:\n\n{json.dumps(conversation)}"
            }
        ]
        
        try:
            response = client.chat.completions.create(
                model="gpt-5-mini",
                input=input_messages,
                stream=False
            )
            
            summary_text = response.choices[0].message.content.strip()
            
            # Update the summary
            summary_obj.summary = summary_text
            summary_obj.last_message_processed = messages.last().created_at
            summary_obj.status = ChatSessionSummary.COMPLETED
            summary_obj.save()
            
            return f"Successfully generated summary for {summary_id}"
            
        except Exception as api_error:
            logger.error(f"OpenAI API error for summary {summary_id}: {api_error}", exc_info=True)
            summary_obj.status = ChatSessionSummary.ERROR
            summary_obj.save()
            # n8n traceback
            n8n_traceback = {
                'error': str(api_error),
                'source': 'generate_chat_session_summary',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            return f"API error for summary {summary_id}: {str(api_error)}"
    
    except ChatSessionSummary.DoesNotExist:
        logger.error(f"ChatSessionSummary with id {summary_id} not found")
        return f"ChatSessionSummary with id {summary_id} not found"
    except Exception as e:
        logger.error(f"Error generating chat session summary {summary_id}: {e}", exc_info=True)
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'generate_chat_session_summary',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        return f"Error for summary {summary_id}: {str(e)}"

def consolidate_user_chat_summaries():
    """
    Create consolidated summaries for each user who just had chat sessions summarized.
    Only processes users in their appropriate timezone window.
    """
    yesterday = timezone.localdate() - timedelta(days=1)
    
    # Find users who:
    # 1. Have chat summaries from yesterday
    # 2. Those summaries are completed
    # This ensures we're only processing users whose chat summaries were just generated
    users_with_summaries = CustomUser.objects.filter(
        chat_session_summaries__summary_date=yesterday,
        chat_session_summaries__status=ChatSessionSummary.COMPLETED,
        # Filtering based on the session's creation time, which should be recent
        chat_session_summaries__created_at__gte=timezone.now() - timedelta(hours=1)
    ).distinct()
    
    count = 0
    for user in users_with_summaries:
        try:
            # Get all completed summaries for this user
            completed_summaries = ChatSessionSummary.objects.filter(
                user=user,
                status=ChatSessionSummary.COMPLETED
            ).order_by('-summary_date')
            
            # Create or update the user's consolidated summary
            user_summary, created = UserChatSummary.objects.get_or_create(
                user=user,
                defaults={'status': UserChatSummary.PENDING}
            )
            
            # Only update if we have a new summary date
            if user_summary.last_summary_date and user_summary.last_summary_date >= yesterday:
                continue
            
            # Generate the consolidated summary
            generate_consolidated_user_summary(user.id)
            count += 1
            
        except Exception as e:
            logger.error(f"Error processing consolidated summary for user {user.id}: {e}", exc_info=True)
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'consolidate_user_chat_summaries',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
    return count

def generate_consolidated_user_summary(user_id):
    """
    Generate a consolidated summary for a specific user based on all their chat session summaries.
    """
    try:
        user = CustomUser.objects.get(id=user_id)
        user_summary, created = UserChatSummary.objects.get_or_create(
            user=user,
            defaults={'status': UserChatSummary.PENDING}
        )
        
        # Get all summaries for this user
        session_summaries = ChatSessionSummary.objects.filter(
            user=user,
            status=ChatSessionSummary.COMPLETED
        ).order_by('-summary_date')[:10]  # Limit to most recent 10 to avoid overloading API
        
        if not session_summaries.exists():
            user_summary.status = UserChatSummary.COMPLETED
            user_summary.summary = "No chat session summaries available."
            user_summary.save()
            return f"No summaries available for user {user_id}"
        
        # Collect all summary texts
        summaries_text = [s.summary for s in session_summaries if s.summary]
        
        if not summaries_text:
            user_summary.status = UserChatSummary.COMPLETED
            user_summary.summary = "No content in chat session summaries."
            user_summary.save()
            return f"No content in summaries for user {user_id}"
        
        # Call OpenAI API for consolidation
        client = Groq(api_key=getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY"))
        
        input_messages = [
            {
                "role": "system",
                "content": """
                Distill and deduplicate summaries to produce a consolidated summary of interactions between the user and assistant, eliminating repeated details and focusing exclusively on essential information.

                # Steps

                1. Analyze the individual summaries of chat interactions.
                2. Identify and extract non-redundant key details related to:
                   - User preferences for meal planning.
                   - Specific dietary requirements or restrictions.
                   - Locations or regions of interest for finding chefs.
                   - Persistent questions or themes across the summaries that indicate user priorities.
                   - Feedback or follow-up requests mentioned consistently.
                3. Compile these into a concise, non-redundant summary.

                # Output Format

                Provide the consolidated summary in a structured and concise format using bullet points for clarity:
                - User Preferences: [Distinct preferences about meal planning]
                - Dietary Requirements: [Consistent dietary restrictions or requirements]
                - Location Interests: [Dedicated regions or areas for finding local chefs]
                - Key Repeated Topics: [Common subjects or questions frequently addressed]
                - User Feedback: [Generalized summary of feedback or requests for follow-up]

                # Example

                **Example Input:**
                1. Summary 1: User interested in vegan meal plans, seeks chefs in SF.
                2. Summary 2: Vegan meal plans wanted, mentions SF area chefs, requests grocery lists.

                **Example Output:**
                - User Preferences: Interested in vegan meal plans.
                - Dietary Requirements: Vegan.
                - Location Interests: San Francisco area.
                - Key Repeated Topics: Meal planning and local chefs.
                - User Feedback: Requested grocery lists.

                # Notes

                - Focus on a concise output eliminating duplicates while ensuring critical information for future assistance is retained.
                - Prioritize clarity and relevance to the primary goals of meal planning and finding chefs.
                """
            },
            {
                "role": "user",
                "content": f"Here are several summaries of conversations with the same user. Please consolidate them into a single non-redundant summary according to the instructions:\n\n{json.dumps(summaries_text)}"
            }
        ]
        
        try:
            response = client.chat.completions.create(
                model="gpt-5-mini",
                input=input_messages,
                stream=False
            )
            
            consolidated_summary = response.choices[0].message.content.strip()
            
            # Update the user summary
            user_summary.summary = consolidated_summary
            user_summary.last_summary_date = timezone.localdate()
            user_summary.status = UserChatSummary.COMPLETED
            user_summary.save()
            
            return f"Successfully generated consolidated summary for user {user_id}"
            
        except Exception as api_error:
            logger.error(f"OpenAI API error for user summary {user_id}: {api_error}", exc_info=True)
            user_summary.status = UserChatSummary.ERROR
            user_summary.save()
            # n8n traceback
            n8n_traceback = {
                'error': str(api_error),
                'source': 'generate_consolidated_user_summary',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            return f"API error for user summary {user_id}: {str(api_error)}"
    
    except CustomUser.DoesNotExist:
        logger.error(f"CustomUser with id {user_id} not found")
        return f"CustomUser with id {user_id} not found"
    except Exception as e:
        logger.error(f"Error generating consolidated summary for user {user_id}: {e}", exc_info=True)
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'generate_consolidated_user_summary',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        return f"Error for user summary {user_id}: {str(e)}"

def process_aggregated_emails(session_identifier_str, use_enhanced_formatting=False):
    """
    ENHANCED Celery task to process aggregated emails with intent-based formatting
    
    Args:
        session_identifier_str: UUID string of the EmailAggregationSession
        use_enhanced_formatting: Boolean flag to enable enhanced formatting (NEW)
    """
    try:
        from customer_dashboard.models import EmailAggregationSession, AggregatedMessageContent
        from meals.meal_assistant_implementation import MealPlanningAssistant
        
        logger.info(f"Processing aggregated emails for session {session_identifier_str} (enhanced: {use_enhanced_formatting})")
        
        # Idempotency key for final send step
        EMAIL_SENT_KEY_PREFIX = "email_session_sent_"
        email_sent_key = f"{EMAIL_SENT_KEY_PREFIX}{session_identifier_str}"

        # Get the session
        try:
            session = EmailAggregationSession.objects.get(
                session_identifier=uuid.UUID(session_identifier_str),
                is_active=True
            )
        except EmailAggregationSession.DoesNotExist:
            # Session might have been marked inactive earlier in a prior attempt
            try:
                inactive_session = EmailAggregationSession.objects.get(
                    session_identifier=uuid.UUID(session_identifier_str),
                    is_active=False
                )
                # If we never actually sent the email, continue processing anyway (resilient retry)
                if not get(email_sent_key, default=False):
                    logger.warning(
                        f"Resuming processing for inactive session {session_identifier_str} because no send confirmation was recorded"
                    )
                    session = inactive_session
                else:
                    logger.info(
                        f"📨 Session {session_identifier_str} already processed and email sent — skipping duplicate send"
                    )
                    return {
                        'status': 'success', 
                        'message': 'Session already processed by earlier task',
                        'session_id': session_identifier_str,
                        'note': 'Idempotent skip: email already sent'
                    }
            except EmailAggregationSession.DoesNotExist:
                # Session truly doesn't exist - this is a real error
                logger.error(f"❌ EmailAggregationSession {session_identifier_str} not found in database - this is unexpected")
                return {'status': 'error', 'message': 'Session not found in database'}
        
        # Mark session as inactive early to prevent concurrent processors
        # (If the worker dies before sending, we rely on the idempotency key to resume.)
        if session.is_active:
            session.is_active = False
            session.save()
        
        # Clear the cache flag
        active_session_flag_key = f"{ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX}{session.user.id}"
        delete(active_session_flag_key)
        
        # Aggregate all messages
        messages = AggregatedMessageContent.objects.filter(session=session).order_by('timestamp')
        
        # 🔍 DIAGNOSTIC: Log each individual message
        logger.info(f"=== HEADER DIAGNOSTIC START - Session {session_identifier_str} ===")
        for i, msg in enumerate(messages):
            content_preview = repr(msg.content[:300])
            logger.info(f"MESSAGE {i} CONTENT: {content_preview}")
            
            # Check for headers in individual messages
            if any(header in msg.content for header in ['From:', 'Date:', 'Subject:']):
                logger.warning(f"⚠️ HEADERS FOUND IN MESSAGE {i}: {content_preview}")
        
        combined_message = "\n\n---\n\n".join([msg.content for msg in messages])
        
        # 🔍 DIAGNOSTIC: Log combined message
        combined_preview = repr(combined_message[:500])
        logger.info(f"COMBINED MESSAGE: {combined_preview}")
        
        if any(header in combined_message for header in ['From:', 'Date:', 'Subject:']):
            logger.warning(f"⚠️ HEADERS FOUND IN COMBINED MESSAGE: {combined_preview}")
        
        # Strip email headers from combined message before processing  
        def strip_email_headers(message_content: str) -> str:
            """Strip email headers from the message content"""
            if not message_content:
                return message_content
                
            # Define header patterns to detect and remove
            header_patterns = [
                r'From:\s*[^\n\r]+',
                r'Date:\s*[^\n\r]+', 
                r'Subject:\s*[^\n\r]+',
                r'To:\s*[^\n\r]+',
                r'Message-ID:\s*[^\n\r]+',
                r'In-Reply-To:\s*[^\n\r]+',
                r'References:\s*[^\n\r]+',
                r'Return-Path:\s*[^\n\r]+',
                r'Message from your sautai assistant[^\n\r]*',
                r'Your latest meal plan[^\n\r]*',
                r'-IMAGE REMOVED-[^\n\r]*'
            ]
            
            cleaned_content = message_content
            
            # Remove each header pattern
            for pattern in header_patterns:
                cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.IGNORECASE)
            
            # Clean up extra whitespace and line breaks
            cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
            cleaned_content = cleaned_content.strip()
            
            return cleaned_content
        
        # Clean the combined message
        cleaned_combined_message = strip_email_headers(combined_message)
        
        # 🔍 DIAGNOSTIC: Log header stripping results
        logger.info(f"=== HEADER STRIPPING IN CELERY TASK ===")
        logger.info(f"Original length: {len(combined_message)}, Cleaned length: {len(cleaned_combined_message)}")
        if len(cleaned_combined_message) != len(combined_message):
            logger.info(f"✅ Headers removed: {len(combined_message) - len(cleaned_combined_message)} characters")
        else:
            logger.warning(f"⚠️ No headers detected/removed in Celery task")
        
        logger.info(f"Processing {messages.count()} aggregated messages for user {session.user.id}")
        
        # Initialize variables for email content
        email_body_main = ""
        email_body_data = ""
        email_body_final = ""
        css_classes = []
        processing_metadata = {}
        
        # ENHANCED PROCESSING - This is the key enhancement
        if use_enhanced_formatting:
            try:
                logger.info(f"Starting enhanced processing for session {session_identifier_str}")
                
                # Use intent analysis but with Django formatter instead of tool-specific override
                openai_client = get_groq_client()
                assistant = MealPlanningAssistant(str(session.user.id))
                
                # Prepare user context for intent analysis
                dietary_prefs = getattr(session.user, 'dietary_preferences', None)
                user_preferences = []
                if dietary_prefs is not None:
                    try:
                        user_preferences = [str(pref) for pref in dietary_prefs.all()]
                    except AttributeError:
                        user_preferences = []
                
                user_context = {
                    'user_id': str(session.user.id),
                    'sender_email': session.recipient_email,
                    'session_id': session_identifier_str,
                    'message_count': messages.count(),
                    'original_subject': session.original_subject,
                    'email_thread_id': session.email_thread_id,
                    'openai_thread_context_id': session.openai_thread_context_id_initial,
                    'user_preferences': user_preferences,
                    'user_language': getattr(session.user, 'preferred_language', 'en')
                }
                
                # Step 1: Analyze intent (keeping this valuable analysis)
                from meals.intent_analyzer import EmailIntentAnalyzer
                intent_analyzer = EmailIntentAnalyzer(openai_client)
                intent_result = intent_analyzer.analyze_intent(cleaned_combined_message, user_context)
                
                logger.info(f"Intent analysis: {intent_result.intent.primary_intent} (confidence: {intent_result.intent.confidence:.2f})")
                
                # Step 2: Process with assistant (standard processing)
                logger.info(f"Processing with assistant (predicted tools: {intent_result.intent.predicted_tools})")
                assistant_response = assistant.send_message(cleaned_combined_message)
                
                # Step 3: Use Django Template Formatter with intent context (NOT tool-specific override!)
                raw_reply_content = assistant_response.get('message', str(assistant_response))
                
                # Create intent context for Django formatter
                intent_context = {
                    'primary_intent': intent_result.intent.primary_intent,
                    'predicted_tools': intent_result.intent.predicted_tools,
                    'content_structure': intent_result.intent.content_structure,
                    'confidence': intent_result.intent.confidence,
                    'user_action_required': intent_result.intent.user_action_required
                }
                
                # Get structured Django template sections with intent awareness
                django_body = assistant._get_django_template_sections(raw_reply_content, intent_context)
                
                # Extract the Django formatting results
                email_body_main = django_body.email_body_main
                email_body_data = django_body.email_body_data
                email_body_final = django_body.email_body_final
                css_classes = ['enhanced-formatting', 'intent-aware', f'intent-{intent_result.intent.primary_intent}']
                
                processing_metadata = {
                    'formatting_type': 'django_intent_aware',
                    'intent_analysis': intent_result.intent.model_dump(),
                    'content_analysis': django_body.content_analysis.model_dump(),
                    'processing_time': 0,  # Will be calculated later
                    'tools_used': [],  # Extract from assistant_response if needed
                    'formatting_applied': True,
                    'session_id': session_identifier_str,
                    'message_count': messages.count(),
                    'enhanced_processing': True,
                    'user_id': str(session.user.id)
                }
                
                logger.info(f"✅ Django template formatting applied successfully for session {session_identifier_str}")
                logger.info(f"Intent detected: {intent_result.intent.primary_intent}")
                logger.info(f"Django sections - Main: {len(email_body_main)}, Data: {len(email_body_data)}, Final: {len(email_body_final)}")
                
            except Exception as e:
                logger.error(f"Enhanced processing failed for session {session_identifier_str}: {str(e)}")
                logger.warning("Falling back to original processing")
                use_enhanced_formatting = False
                
            except Exception as e:
                logger.error(f"Enhanced processing error for session {session_identifier_str}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Send error to n8n traceback for monitoring
                try:
                    n8n_traceback = {
                        'error': f"Enhanced processing failed: {str(e)}",
                        'source': 'process_aggregated_emails_enhanced',
                        'session_id': session_identifier_str,
                        'user_id': str(session.user.id),
                        'traceback': traceback.format_exc()
                    }
                    requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback, timeout=5)
                except:
                    pass  # Don't let traceback reporting break the main flow
                
                # Fall back to original processing
                use_enhanced_formatting = False
        
        # Original processing (fallback or when enhanced is disabled)
        if not use_enhanced_formatting:
            logger.info(f"Using original processing for session {session_identifier_str}")
            
            try:
                assistant = MealPlanningAssistant(str(session.user.id))
                response = assistant.send_message(cleaned_combined_message)
                
                # Extract content from original response
                if isinstance(response, dict):
                    message_content = response.get('message', str(response))
                else:
                    message_content = str(response)
                
                # Apply basic formatting to match the three-section structure
                email_body_main = f"<h2>📧 Response from your sautai Assistant</h2><p>Here's the response to your message:</p>"
                
                # Format the message content with basic HTML
                formatted_content = message_content.replace('\n\n', '</p><p>').replace('\n', '<br>')
                if formatted_content:
                    formatted_content = f'<p>{formatted_content}</p>'
                
                email_body_data = f"<div class='assistant-response'>{formatted_content}</div>"
                streamlit_url = os.getenv('STREAMLIT_URL')
                if settings.LEGACY_MEAL_PLAN_ENABLED and streamlit_url:
                    email_body_final = (
                        f"<p>Need more help? Just reply to this email or visit your "
                        f"<a href='{streamlit_url}/meal-plans'>sautai dashboard</a>!</p>"
                    )
                else:
                    email_body_final = "<p>Need more help? Just reply to this email.</p>"
                css_classes = ['original-formatting']
                
                processing_metadata = {
                    'session_id': session_identifier_str,
                    'message_count': messages.count(),
                    'enhanced_processing': False,
                    'user_id': str(session.user.id),
                    'processing_type': 'original'
                }
                
                logger.info(f"Original processing completed for session {session_identifier_str}")
                
            except Exception as e:
                logger.error(f"Original processing error for session {session_identifier_str}: {str(e)}")
                logger.error(f"Original processing traceback: {traceback.format_exc()}")
                # Create error email content
                email_body_main = "<h2>❌ Processing Error</h2>"
                email_body_data = "<p>We encountered an error processing your request. Please try again.</p>"
                email_body_final = "<p>If the problem persists, please contact support.</p>"
                css_classes = ['error-formatting']
                
                processing_metadata = {
                    'session_id': session_identifier_str,
                    'message_count': messages.count(),
                    'enhanced_processing': False,
                    'user_id': str(session.user.id),
                    'processing_type': 'error',
                    'error': str(e)
                }
        
        logger.info(f"=== HEADER DIAGNOSTIC END ===")
        
        # Get user preferred language
        user_preferred_language = _get_language_name(getattr(session.user, 'preferred_language', 'en'))
        
        # Render the email template with the processed content
        try:
            email_html_content = render_to_string(
                'customer_dashboard/assistant_email_template.html',
                {
                    'user_name': session.user.get_full_name() or session.user.username,
                    'email_body_main': email_body_main,
                    'email_body_data': email_body_data,
                    'email_body_final': email_body_final,
                    'css_classes': ' '.join(css_classes),
                    'profile_url': f"{os.getenv('STREAMLIT_URL')}/profile",
                    'personal_assistant_email': getattr(session.user, 'personal_assistant_email', f"mj+{session.user.email_token}@sautai.com"),
                    # Add metadata for debugging (optional)
                    'debug_info': processing_metadata if os.getenv('DEBUG') == 'True' else {}
                }
            )
        except Exception as e:
            logger.error(f"Error rendering email template for session {session_identifier_str}: {str(e)}")
            # Create a simple fallback email
            email_html_content = f"""
            <html>
            <body>
                <h2>Response from your sautai Assistant</h2>
                {email_body_data}
                <p>Best regards,<br>Your sautai Team</p>
            </body>
            </html>
            """
        
        # Translate the email content
        try:
            email_html_content = translate_paragraphs(email_html_content, user_preferred_language)
            logger.info(f"Email content translated to {user_preferred_language} for session {session_identifier_str}")
        except Exception as e:
            logger.error(f"Error translating email content for session {session_identifier_str}: {e}")
            # Continue with untranslated content
        
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
                    # Include metadata for tracking and analytics
                    'enhanced_formatting': use_enhanced_formatting,
                    'intent_detected': processing_metadata.get('intent_analysis', {}).get('primary_intent', 'unknown') if use_enhanced_formatting else 'original_processing',
                    'tools_used': processing_metadata.get('tools_used', []) if use_enhanced_formatting else [],
                    'processing_time': processing_metadata.get('processing_time', 0),
                    'message_count': messages.count()
                }
                
                try:
                    response = requests.post(n8n_webhook_url, json=payload, timeout=30)
                    response.raise_for_status()
                    logger.info(f"Email successfully sent for session {session_identifier_str} (enhanced: {use_enhanced_formatting})")
                    # Mark idempotency key so retries/duplicates don’t resend
                    set(email_sent_key, True, timeout=7 * 24 * 60 * 60)  # 7 days
                    
                    return {
                        'status': 'success',
                        'message': 'Email processed and sent successfully',
                        'session_id': session_identifier_str,
                        'enhanced_formatting': use_enhanced_formatting,
                        'metadata': processing_metadata
                    }
                    
                except requests.RequestException as e:
                    logger.error(f"Failed to send email for session {session_identifier_str}: {e}")
                    
                    # Send error to n8n traceback
                    try:
                        n8n_traceback = {
                            'error': f"Failed to send email: {str(e)}",
                            'source': 'process_aggregated_emails_send_email',
                            'session_id': session_identifier_str,
                            'user_id': str(session.user.id),
                            'traceback': traceback.format_exc()
                        }
                        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback, timeout=5)
                    except:
                        pass
                    
                    # Retry the task
                    raise self.retry(exc=e, countdown=60)
            else:
                logger.error("N8N_EMAIL_REPLY_WEBHOOK_URL not configured")
                return {
                    'status': 'error',
                    'message': 'Email service not configured',
                    'session_id': session_identifier_str
                }
        else:
            logger.info(f"User {session.user.username} has unsubscribed from emails")
            # Consider the session completed to avoid repeated processing
            set(email_sent_key, True, timeout=7 * 24 * 60 * 60)
            return {
                'status': 'success',
                'message': 'Processing completed but email not sent due to user preferences',
                'session_id': session_identifier_str
            }
        
    except Exception as e:
        logger.error(f"Critical error in process_aggregated_emails for session {session_identifier_str}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Send critical error to n8n traceback
        try:
            n8n_traceback = {
                'error': f"Critical task error: {str(e)}",
                'source': 'process_aggregated_emails_critical',
                'session_id': session_identifier_str,
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback, timeout=5)
        except:
            pass
        
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

# Additional helper tasks for monitoring and maintenance

def cleanup_expired_sessions():
    """
    Cleanup task to remove expired email aggregation sessions
    """
    try:
        from customer_dashboard.models import EmailAggregationSession
        from django.utils import timezone
        from datetime import timedelta
        
        # Clean up sessions older than 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        expired_sessions = EmailAggregationSession.objects.filter(
            created_at__lt=cutoff_time,
            is_active=False
        )
        
        count = expired_sessions.count()
        expired_sessions.delete()
        
        logger.info(f"Cleaned up {count} expired email aggregation sessions")
        return {'status': 'success', 'cleaned_sessions': count}
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_sessions: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def monitor_enhanced_formatting_performance():
    """
    Monitoring task to track enhanced formatting performance
    """
    try:
        from customer_dashboard.models import EmailAggregationSession
        from django.utils import timezone
        from datetime import timedelta
        
        # Get sessions from the last 24 hours
        yesterday = timezone.now() - timedelta(hours=24)
        recent_sessions = EmailAggregationSession.objects.filter(
            created_at__gte=yesterday,
            is_active=False
        )
        
        total_sessions = recent_sessions.count()
        
        # This would require additional tracking in your models to be fully functional
        # For now, it's a placeholder for performance monitoring
        
        logger.info(f"Performance monitoring: {total_sessions} sessions processed in last 24h")
        
        return {
            'status': 'success',
            'total_sessions_24h': total_sessions,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in monitor_enhanced_formatting_performance: {str(e)}")
        return {'status': 'error', 'message': str(e)}

import openai
from celery import shared_task
from django.conf import settings
import logging
from django.utils import timezone
from datetime import timedelta
import json
import hashlib
import pytz
from django.core.cache import cache
import requests
import traceback
import uuid

from .models import ChatThread, ChatSessionSummary, UserChatSummary, EmailAggregationSession, AggregatedMessageContent
from custom_auth.models import CustomUser
from meals.meal_assistant_implementation import MealPlanningAssistant

# Define constants for cache keys. These should ideally match those in secure_email_integration.py
EMAIL_AGGREGATION_MESSAGES_KEY_PREFIX = "email_aggregation_messages_user_"
EMAIL_AGGREGATION_WINDOW_KEY_PREFIX = "email_aggregation_window_user_"
ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX = "active_db_aggregation_session_user_"

logger = logging.getLogger(__name__)

@shared_task
def generate_chat_title(thread_id):
    """
    Celery task to generate and set the title for a ChatThread asynchronously.
    """
    try:
        thread = ChatThread.objects.get(pk=thread_id)
        logger.info(f"Task started: Generating title for ChatThread {thread_id}")

        # Ensure we still need to generate a title
        if thread.title not in ["Chat with Assistant", "", None] or not thread.openai_input_history:
            logger.info(f"Skipping title generation for ChatThread {thread_id} - title already set or no history.")
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
            client = openai.OpenAI(api_key=settings.OPENAI_KEY)
            prompt = f"Generate a very short, concise title (max 5 words) for a chat conversation that starts with this user message: '{first_user_message_content}'. Do not use quotes in the title."
            response = client.responses.create(
                model="gpt-4.1-nano",
                input=[
                    {"role": "developer", "content": "You are a helpful assistant that creates concise chat titles based on the user's message."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )

            new_title = response.output_text
            if new_title:
                logger.info(f"Generated title for ChatThread {thread_id}: '{new_title}'")
                ChatThread.objects.filter(pk=thread_id).update(title=new_title)
                logger.info(f"Successfully updated title for ChatThread {thread_id}")
            else:
                 logger.warning(f"OpenAI returned an empty title for ChatThread {thread_id}")

        except Exception as e:
            logger.error(f"Error calling OpenAI to generate title for ChatThread {thread_id}: {e}", exc_info=True)

    except ChatThread.DoesNotExist:
        logger.error(f"ChatThread with id {thread_id} not found.")
    except Exception as e:
        logger.error(f"Unexpected error in generate_chat_title task for thread_id {thread_id}: {e}", exc_info=True)

@shared_task
def summarize_user_chat_sessions():
    """
    Hourly task to summarize chat sessions for users when it's 3:30 AM in their timezone.
    """
    logger.info("Starting hourly chat session summarization task")
    
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
                user_tz = pytz.timezone(user.timezone)
                user_local_time = now_utc.astimezone(user_tz)
                
                # Check if it's between 3:30 AM and 4:29 AM for this user
                is_summary_hour = (
                    user_local_time.hour == 3 and user_local_time.minute >= 30
                ) or (
                    user_local_time.hour == 4 and user_local_time.minute < 30
                )
                
                if is_summary_hour:
                    eligible_users.append(user)
                    logger.info(f"User {user.username} (TZ: {user.timezone}) is eligible for summary generation")
            except Exception as e:
                logger.error(f"Error processing timezone for user {user.id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error retrieving users: {e}", exc_info=True)
    
    if not eligible_users:
        logger.info("No users eligible for summary generation in this timezone window")
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
                
                # Generate the summary in a separate task
                generate_chat_session_summary.delay(summary_obj.id)
                count += 1
                
            except Exception as e:
                logger.error(f"Error processing thread {thread.id}: {e}", exc_info=True)
    
    logger.info(f"Scheduled {count} chat session summaries for generation")
    
    # If any summaries were created/updated, schedule the consolidated summary task
    if count > 0:
        consolidate_user_chat_summaries.delay()
    
    return count

@shared_task
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
        client = openai.OpenAI(api_key=settings.OPENAI_KEY)
        
        input_messages = [
            {
                "role": "developer",
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
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=input_messages,
                stream=False
            )
            
            summary_text = response.output_text.strip()
            
            # Update the summary
            summary_obj.summary = summary_text
            summary_obj.last_message_processed = messages.last().created_at
            summary_obj.status = ChatSessionSummary.COMPLETED
            summary_obj.save()
            
            logger.info(f"Successfully generated summary for chat session {summary_id}")
            return f"Successfully generated summary for {summary_id}"
            
        except Exception as api_error:
            logger.error(f"OpenAI API error for summary {summary_id}: {api_error}", exc_info=True)
            summary_obj.status = ChatSessionSummary.ERROR
            summary_obj.save()
            return f"API error for summary {summary_id}: {str(api_error)}"
    
    except ChatSessionSummary.DoesNotExist:
        logger.error(f"ChatSessionSummary with id {summary_id} not found")
        return f"ChatSessionSummary with id {summary_id} not found"
    except Exception as e:
        logger.error(f"Error generating chat session summary {summary_id}: {e}", exc_info=True)
        return f"Error for summary {summary_id}: {str(e)}"

@shared_task
def consolidate_user_chat_summaries():
    """
    Create consolidated summaries for each user who just had chat sessions summarized.
    Only processes users in their appropriate timezone window.
    """
    logger.info("Starting task to consolidate user chat summaries")
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
                logger.debug(f"User {user.id} already has a consolidated summary for {yesterday} or later")
                continue
            
            # Generate the consolidated summary
            generate_consolidated_user_summary.delay(user.id)
            count += 1
            
        except Exception as e:
            logger.error(f"Error processing consolidated summary for user {user.id}: {e}", exc_info=True)
    
    logger.info(f"Scheduled {count} consolidated user summaries for generation")
    return count

@shared_task
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
        client = openai.OpenAI(api_key=settings.OPENAI_KEY)
        
        input_messages = [
            {
                "role": "developer",
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
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=input_messages,
                stream=False
            )
            
            consolidated_summary = response.output_text.strip()
            
            # Update the user summary
            user_summary.summary = consolidated_summary
            user_summary.last_summary_date = timezone.localdate()
            user_summary.status = UserChatSummary.COMPLETED
            user_summary.save()
            
            logger.info(f"Successfully generated consolidated summary for user {user_id}")
            return f"Successfully generated consolidated summary for user {user_id}"
            
        except Exception as api_error:
            logger.error(f"OpenAI API error for user summary {user_id}: {api_error}", exc_info=True)
            user_summary.status = UserChatSummary.ERROR
            user_summary.save()
            return f"API error for user summary {user_id}: {str(api_error)}"
    
    except CustomUser.DoesNotExist:
        logger.error(f"CustomUser with id {user_id} not found")
        return f"CustomUser with id {user_id} not found"
    except Exception as e:
        logger.error(f"Error generating consolidated summary for user {user_id}: {e}", exc_info=True)
        return f"Error for user summary {user_id}: {str(e)}"

@shared_task
def process_aggregated_emails(session_identifier_str: str):
    """
    Processes aggregated emails for a user from a DB-backed EmailAggregationSession.
    Args:
        session_identifier_str: The UUID string of the EmailAggregationSession.
    """
    task_id_str = process_aggregated_emails.request.id if process_aggregated_emails.request else 'N/A'
    logger.info(f"Task {task_id_str}: Starting to process aggregated emails for DB session identifier {session_identifier_str}.")

    active_session_flag_key = None # Will be set if session is found
    db_session = None

    try:
        session_uuid = uuid.UUID(session_identifier_str)
        db_session = EmailAggregationSession.objects.select_related('user').get(session_identifier=session_uuid)

        if not db_session.is_active:
            logger.warning(f"Task {task_id_str}: EmailAggregationSession {session_identifier_str} is already marked inactive. Skipping.")
            return

        user = db_session.user
        active_session_flag_key = f"{ACTIVE_DB_AGGREGATION_SESSION_FLAG_PREFIX}{user.id}"

        # Retrieve all messages for this session, ordered by timestamp
        aggregated_messages = db_session.messages.all().order_by('timestamp')
        print(f"DEBUG: Aggregated messages for user {user.id} (DB session {session_identifier_str}):\n{aggregated_messages}")
        if not aggregated_messages:
            logger.warning(f"Task {task_id_str}: No messages found in DB for EmailAggregationSession {session_identifier_str} for user {user.id}. Marking session inactive.")
            db_session.is_active = False
            db_session.save()
            cache.delete(active_session_flag_key)
            return

        # Combine message content
        # Consider if subjects of individual messages need to be part of combined_content
        combined_content = "\n\n---\n\n".join([item.content for item in aggregated_messages])
        print(f"DEBUG: Combined content for user {user.id} (DB session {session_identifier_str}):\n{combined_content}")
        logger.info(f"Task {task_id_str}: Processing {len(aggregated_messages)} aggregated email(s) from DB for user {user.id}. Session: {session_identifier_str}. Combined content length: {len(combined_content)}.")

        assistant = MealPlanningAssistant(user_id=user.id)
        print(f"DEBUG: Processing aggregated emails for user {user.id} (DB session {session_identifier_str}).")
        # Call the method in MealPlanningAssistant to handle processing and n8n reply
        # Pass metadata from the db_session object
        email_reply_result = assistant.process_and_reply_to_email(
            message_content=combined_content,
            recipient_email=db_session.recipient_email, # From the first email that started the session
            user_email_token=db_session.user_email_token, # User's main token stored in session
            original_subject=db_session.original_subject, # From the first email
            in_reply_to_header=db_session.in_reply_to_header, # From the first email
            email_thread_id=db_session.email_thread_id, # From the first email
            openai_thread_context_id_initial=db_session.openai_thread_context_id_initial # From the first email
        )

        if email_reply_result.get("status") == "success":
            logger.info(f"Task {task_id_str}: Successfully processed and triggered email reply for user {user.id} (DB session {session_identifier_str}). Result: {email_reply_result.get('message')}")
        else:
            logger.error(f"Task {task_id_str}: Failed to process/send email reply for user {user.id} (DB session {session_identifier_str}). Error: {email_reply_result.get('message')}")
            # Decide on retry logic or if session should remain active for a manual check

        # Mark session as processed (inactive)
        db_session.is_active = False
        db_session.save()
        logger.info(f"Task {task_id_str}: Marked EmailAggregationSession {session_identifier_str} as inactive.")

    except EmailAggregationSession.DoesNotExist:
        logger.error(f"Task {task_id_str}: EmailAggregationSession with identifier {session_identifier_str} not found in DB. Cannot process.")
        # No specific user ID to clear a flag if session not found by identifier alone
    except ValueError: # Invalid UUID format
        logger.error(f"Task {task_id_str}: Invalid UUID format for session identifier '{session_identifier_str}'. Cannot process.")
    except CustomUser.DoesNotExist: # Should not happen if session exists and has a user
        logger.error(f"Task {task_id_str}: User not found for DB session {session_identifier_str}. Session might be corrupted.")
    except Exception as e:
        logger.error(f"Task {task_id_str}: Error processing aggregated emails for DB session {session_identifier_str}: {str(e)}\nTraceback: {traceback.format_exc()}.")
        # Consider if db_session should be marked inactive on general error, or if it should be retried.
        # If db_session was fetched, it might be good to mark it inactive to prevent re-processing of a failing task unless retries are configured.
        if db_session and db_session.is_active:
            # db_session.is_active = False # Potentially mark as inactive on failure too
            # db_session.save()
            pass # Decide on error handling strategy for is_active
    finally:
        # Clean up cache flag for this user if we identified the user and session
        if active_session_flag_key: # This key is set if db_session was found and user identified
            cache.delete(active_session_flag_key)
            logger.info(f"Task {task_id_str}: Cleaned up cache flag {active_session_flag_key} for user after DB aggregation task for session {session_identifier_str}.")
        else:
            # This case can happen if EmailAggregationSession.DoesNotExist or ValueError on UUID occurred early.
            # We don't have a user.id to construct the cache key for cleanup in that scenario.
            logger.info(f"Task {task_id_str}: No cache flag to clean as user/session was not fully identified for session_id {session_identifier_str}.")

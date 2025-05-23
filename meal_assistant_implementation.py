from typing import Dict, Optional
from django.contrib.auth.models import CustomUser
from django.utils.log import logger

class MealPlanningAssistant:
    def process_and_reply_to_email(
        self, 
        message_content: str, 
        recipient_email: str, 
        user_email_token: str, 
        original_subject: str, 
        in_reply_to_header: Optional[str], 
        email_thread_id: Optional[str],
        openai_thread_context_id_initial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes an aggregated email message, gets a response from the assistant,
        and then triggers n8n to send the reply email.
        This is a non-streaming method.
        Assumes self.user_id is already set correctly for an authenticated user.
        """
        if self._is_guest(self.user_id):
            logger.error(f"process_and_reply_to_email called for a guest user ID: {self.user_id}. This should not happen.")
            return {"status": "error", "message": "Email processing is only for authenticated users."}

        logger.info(f"MealPlanningAssistant: Processing email for user {self.user_id}, to_recipient: {recipient_email}")

        # Get the current active thread for this user
        chat_thread = self._get_or_create_thread(self.user_id)
        
        # Check if user has unsubscribed from emails
        try:
            user = CustomUser.objects.get(id=self.user_id)
            if user.unsubscribed_from_emails:
                logger.info(f"MealPlanningAssistant: User {self.user_id} has unsubscribed from emails. Skipping email reply.")
                return {"status": "skipped", "message": "User has unsubscribed from emails."}
        except CustomUser.DoesNotExist:
            logger.error(f"MealPlanningAssistant: User {self.user_id} not found when checking unsubscribe status.")
            return {"status": "error", "message": "User not found."}
        
        # 1. Get the assistant's response using send_message_for_email logic
        # This handles history, model selection, tool calls, iterations, and persistence.
        print(f"DEBUG: Sending message with content:\n{message_content}")
        assistant_response_data = self.send_message_for_email(message_content=message_content)
        print(f"DEBUG: Assistant response data for user {self.user_id}:\n{assistant_response_data}")
        if assistant_response_data.get("status") == "error":
            logger.error(f"MealPlanningAssistant: Error getting response from send_message_for_email for user {self.user_id}: {assistant_response_data.get('message')}")
            # Still attempt to send a generic error reply via email
            raw_reply_content = "I encountered an issue processing your request. Please try again later or contact support if the problem persists."
            new_openai_response_id = None
        else:
            raw_reply_content = assistant_response_data.get('message', 'Could not process your request at this time. Please try again later via the web interface.')
            new_openai_response_id = assistant_response_data.get('response_id', None)
            logger.info(f"MealPlanningAssistant: Received response for user {self.user_id}. OpenAI response ID: {new_openai_response_id}")
            print(f"DEBUG: Raw reply content from LLM for user {self.user_id}:\n{raw_reply_content}") 
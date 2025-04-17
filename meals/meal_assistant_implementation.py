"""
Updated MealPlanningAssistant implementation with fixed guest user handling.

This version properly handles thread_id parameter for guest users and ensures
conversation state is maintained across messages.
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Generator

from django.conf import settings
from openai import OpenAI

from .tool_registration import get_all_tools, handle_tool_call
from .guest_tool_registration import handle_guest_tool_call, get_guest_tool_definitions
from customer_dashboard.models import ChatThread, UserMessage, ToolCall
from custom_auth.models import CustomUser

logger = logging.getLogger(__name__)

class MealPlanningAssistant:
    """
    Meal Planning Assistant using the OpenAI Responses API with proper state management.
    
    This class provides the core functionality for the meal planning assistant,
    including conversation management using the Responses API's previous_response_id,
    message handling, and tool integration with database logging.
    
    For guest users, no data is saved to the database - conversation state is managed
    entirely through the OpenAI Responses API.
    """
    
    def __init__(self):
        """Initialize the meal planning assistant."""
        self.client = OpenAI(api_key=settings.OPENAI_KEY)
        self.tools = get_all_tools()
        
        # In-memory cache for guest conversation state
        # Maps guest_id -> response_id
        self.guest_conversation_state = {}
        
        # System message that defines the assistant's behavior
        self.system_message = f"""
        You are a helpful meal planning assistant for the company sautAI that helps users plan their meals, manage their pantry,
        connect with local chefs, and process payments. You can help users with the following tasks:
        
        1. Creating and modifying meal plans based on dietary preferences and restrictions
        2. Managing pantry items and generating shopping lists
        3. Finding local chefs and ordering meals from them
        4. Processing payments for chef meals and subscriptions
        5. Managing dietary preferences and checking meal compatibility
        
        Always be friendly, helpful, and concise in your responses. When users ask for help with
        meal planning or related tasks, use the appropriate tools to assist them.

        You are considerate of security and privacy. You do not share personal information without permission, 
        and you avoid sharing data based on the user providing you a username or user id.

        You have access to the following tools:
        For guests:
        {get_guest_tool_definitions()}

        For authenticated users:
        {self.tools}
        
        If a user is not authenticated, you should only use the guest tools and nudge them to sign up for an account for a better experience.
        """
    
    def send_message(self, user_id: str, message: str, thread_id: str = None) -> Dict[str, Any]:
        """
        Send a message to the assistant and get a response.
        
        Args:
            user_id: The ID of the user sending the message (can be a guest ID like 'guest_guest')
            message: The message text
            thread_id: The thread ID (which is actually the response ID) for continuing a conversation
            
        Returns:
            Dict containing the assistant's response
        """
        try:
            # Check if this is a guest user
            is_guest = self._is_guest_user(user_id)
            
            # Prepare the input for the OpenAI Responses API
            input_data = message
            
            # Get previous response ID based on user type
            previous_response_id = thread_id  # Use the provided thread_id if available
            
            if not previous_response_id:
                if is_guest:
                    # For guests, use in-memory state if thread_id is not provided
                    previous_response_id = self.guest_conversation_state.get(user_id)
                else:
                    # For authenticated users, get or create chat thread
                    chat_thread = self._get_or_create_chat_thread(user_id)
                    
                    # If we have a previous response ID stored, use it to continue the conversation
                    if chat_thread.openai_thread_id:  # We're repurposing this field to store the latest response ID
                        previous_response_id = chat_thread.openai_thread_id
                    
                    # Save the user message to the database (only for authenticated users)
                    user_message = self._save_user_message(user_id, message, chat_thread)
            else:
                # If thread_id is provided, use it directly
                if not is_guest:
                    # For authenticated users, get or create chat thread
                    chat_thread = self._get_or_create_chat_thread(user_id)
                    
                    # Save the user message to the database (only for authenticated users)
                    user_message = self._save_user_message(user_id, message, chat_thread)
            
            # Determine which tool definitions to use (restrict for guests)
            tool_defs = get_guest_tool_definitions() if is_guest else self.tools
            # Call the OpenAI Responses API
            create_kwargs = {
                "model": "gpt-4o-mini",
                "input": input_data,
                "tools": tool_defs,
                "stream": True
            }
            if previous_response_id:
                create_kwargs["previous_response_id"] = previous_response_id
            response = self.client.responses.create(**create_kwargs)
            
            # Update state based on user type
            if is_guest:
                # For guests, update in-memory state
                self.guest_conversation_state[user_id] = response.id
            else:
                # For authenticated users, update database
                chat_thread.openai_thread_id = response.id
                chat_thread.save()
            
            # Process the response
            result = self._process_response(response, user_id, user_message if not is_guest else None, is_guest)
            
            # Add the response ID to the result
            result['response_id'] = response.id
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending message for user {user_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to send message: {str(e)}"
            }
    
    def stream_message(self, user_id: str, message: str, thread_id: str = None) -> Generator[Dict[str, Any], None, None]:
        """
        Stream a message to the assistant and get a response.
        
        Args:
            user_id: The ID of the user sending the message (can be a guest ID like 'guest_guest')
            message: The message text
            thread_id: The thread ID (which is actually the response ID) for continuing a conversation
            
        Yields:
            Chunks of the assistant's response
        """
        try:
            is_guest = self._is_guest_user(user_id)
            input_data = message
            previous_response_id = thread_id  # Use the provided thread_id if available
            user_message = None
            chat_thread = None
            
            if not previous_response_id:
                if is_guest:
                    # For guests, use in-memory state if thread_id is not provided
                    previous_response_id = self.guest_conversation_state.get(user_id)
                else:
                    # For authenticated users, get or create chat thread
                    chat_thread = self._get_or_create_chat_thread(user_id)
                    
                    # If we have a previous response ID stored, use it to continue the conversation
                    if chat_thread.openai_thread_id:  # We're repurposing this field to store the latest response ID
                        previous_response_id = chat_thread.openai_thread_id
                    
                    # Save the user message to the database (only for authenticated users)
                    user_message = self._save_user_message(user_id, message, chat_thread)
            else:
                # If thread_id is provided, use it directly
                if not is_guest:
                    # For authenticated users, get or create chat thread
                    chat_thread = self._get_or_create_chat_thread(user_id)
                    
                    # Save the user message to the database (only for authenticated users)
                    user_message = self._save_user_message(user_id, message, chat_thread)
            
            # Determine which tool definitions to use (restrict for guests)
            tool_defs = get_guest_tool_definitions() if is_guest else self.tools
            stream_kwargs = {
                "model": "gpt-4o-mini",
                "input": input_data,
                "tools": tool_defs,
                "stream": True
            }
            if previous_response_id:
                stream_kwargs["previous_response_id"] = previous_response_id
            stream = self.client.responses.create(**stream_kwargs)
            new_response_id = None
            
            # Process the streaming response
            accumulated_message = ""
            tool_calls_data = []

            for chunk in stream:
                print(f"[DEBUG] guest_stream_message received chunk: {chunk!r}")
                # Handle tool calls for guests
                if hasattr(chunk, "type") and chunk.type == "tool_call_chunk":
                    func_name = chunk["content"]["function"]["name"]
                    func_args_json = chunk["content"]["function"]["arguments"]
                    print(f"[DEBUG] guest_stream_message handling tool_call_chunk: name={func_name}, args_json={func_args_json!r}")
                    try:
                        args = json.loads(func_args_json)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] guest_stream_message failed to parse tool args JSON: {e}")
                        args = {}
                    from .guest_tool_registration import handle_guest_tool_call
                    tool_output = handle_guest_tool_call(func_name, **args)
                    print(f"[DEBUG] guest_stream_message tool_output: {tool_output!r}")
                    yield f"data: {json.dumps({'type':'response.tool','name':func_name,'output':tool_output})}\n\n"
                    continue

                # Handle text deltas from Responses API
                if hasattr(chunk, 'delta'):
                    delta_text = chunk.delta
                    accumulated_message += delta_text
                    
                    yield {
                        "type": "text",
                        "content": delta_text
                    }

                # Capture and yield the new response ID once
                if new_response_id is None:
                    # Try to extract the ID from event or response object
                    resp_id = None
                    if hasattr(chunk, 'id') and chunk.id:
                        resp_id = chunk.id
                    elif hasattr(chunk, 'response') and hasattr(chunk.response, 'id'):
                        resp_id = chunk.response.id
                    if resp_id:
                        new_response_id = resp_id
                        
                        yield { "type": "response_id", "id": new_response_id }

                # Process text output
                if hasattr(chunk, 'output_text') and chunk.output_text:
                    accumulated_message += chunk.output_text
                    
                    yield {
                        "type": "text",
                        "content": chunk.output_text
                    }
                
                # Process tool calls
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    for tool_call_chunk in chunk.tool_calls:
                        # Process tool call chunks
                        yield {
                            "type": "tool_call_chunk",
                            "content": {
                                "id": tool_call_chunk.id,
                                "index": tool_call_chunk.index,
                                "function": {
                                    "name": tool_call_chunk.function.name if tool_call_chunk.function.name else "",
                                    "arguments": tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                                }
                            }
                        }
                        
                        # Collect tool call data
                        found = False
                        for tc in tool_calls_data:
                            if tc["index"] == tool_call_chunk.index:
                                if tool_call_chunk.function.name:
                                    tc["function"]["name"] += tool_call_chunk.function.name
                                if tool_call_chunk.function.arguments:
                                    tc["function"]["arguments"] += tool_call_chunk.function.arguments
                                found = True
                                break
                        
                        if not found and tool_call_chunk.index is not None:
                            tool_calls_data.append({
                                "id": tool_call_chunk.id,
                                "index": tool_call_chunk.index,
                                "function": {
                                    "name": tool_call_chunk.function.name if tool_call_chunk.function.name else "",
                                    "arguments": tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                                }
                            })
                # Handle tool call chunks
                if hasattr(chunk, "type") and chunk.type == "tool_call_chunk":
                    yield {
                        "type": "tool_call_chunk",
                        "content": {
                            "id": chunk.content.id,
                            "index": chunk.content.index,
                            "function": {
                                "name": chunk.content.function.name,
                                "arguments": chunk.content.function.arguments
                            }
                        }
                    }
                    continue

                # Handle tool result
                if hasattr(chunk, "type") and chunk.type == "tool_result":
                    yield {
                        "type": "tool_result",
                        "tool_call_id": chunk.tool_call_id,
                        "content": chunk.content
                    }
                    continue

                # Handle final response
                if hasattr(chunk, "type") and chunk.type == "final_response":
                    yield {
                        "type": "final_response",
                        "content": chunk.content
                    }
                    continue
            
            response_to_retrieve = new_response_id or thread_id
            response = self.client.responses.retrieve(response_to_retrieve)
            
            if is_guest:
                self.guest_conversation_state[user_id] = new_response_id or response.id
            else:
                chat_thread.openai_thread_id = new_response_id or response.id
                chat_thread.save()
                
                # Save the assistant response to the database (only for authenticated users)
                self._save_assistant_response(user_message, accumulated_message)
            
            # Process any tool calls
            if tool_calls_data:
                for tool_call_data in tool_calls_data:
                    # Create a tool call object
                    class ToolCall:
                        def __init__(self, tc_data):
                            self.id = tc_data['id']
                            self.function = type('obj', (object,), {
                                'name': tc_data['function']['name'],
                                'arguments': tc_data['function']['arguments']
                            })
                    
                    tool_call = ToolCall(tool_call_data)
                    
                    # Handle the tool call
                    tool_result = handle_tool_call(tool_call)
                    
                    # Save the tool call to the database (only for authenticated users)
                    if not is_guest:
                        self._save_tool_call(user_id, tool_call, tool_result)
                    
                yield {
                    "type": "tool_result",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                }
            
                # Prepare tool outputs for the final call
                tool_outputs = [
                    {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"], "result": tool_result}
                    for tc, tool_result in zip(tool_calls_data, [handle_tool_call(type('obj', (object,), {
                        'id': tc['id'],
                        'function': type('obj', (object,), {'name': tc['function']['name'], 'arguments': tc['function']['arguments']})
                    })) for tc in tool_calls_data])
                ]
            
                # Get a final response after tool calls
                final_response = self.client.responses.create(
                    model="gpt-4o-mini",
                    input="",
                    previous_response_id=response.id,
                    tools=self.tools,
                    tool_outputs=tool_outputs
                )
                
                # Update state based on user type
                if is_guest:
                    self.guest_conversation_state[user_id] = new_response_id or final_response.id
                else:
                    chat_thread.openai_thread_id = new_response_id or final_response.id
                    chat_thread.save()
                
                # Extract the message content from the final response
                final_message = self._extract_message_content(final_response)
                
                # Save the final response to the database (only for authenticated users)
                if not is_guest:
                    self._save_assistant_response(user_message, final_message)
                
                
                yield {
                    "type": "final_response",
                    "content": final_message
                }
                
        except Exception as e:
            logger.error(f"Error streaming message for user {user_id}: {str(e)}")
            yield {
                "status": "error",
                "message": f"Failed to stream message: {str(e)}"
            }
            
    
    def reset_conversation(self, user_id: str) -> Dict[str, Any]:
        """
        Reset a conversation for a user.
        
        Args:
            user_id: The ID of the user (can be a guest ID like 'guest_guest')
            
        Returns:
            Dict containing the new conversation
        """
        try:
            # Check if this is a guest user
            is_guest = self._is_guest_user(user_id)
            
            if is_guest:
                # For guests, clear in-memory state
                if user_id in self.guest_conversation_state:
                    del self.guest_conversation_state[user_id]
                
                return {
                    "status": "success",
                    "message": "Conversation reset successfully"
                }
            else:
                # For authenticated users, create a new thread in the database
                chat_thread = self._create_chat_thread(user_id)
                
                return {
                    "status": "success",
                    "message": "Conversation reset successfully",
                    "thread_id": chat_thread.id
                }
            
        except Exception as e:
            logger.error(f"Error resetting conversation for user {user_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to reset conversation: {str(e)}"
            }
    
    def get_conversation_history(self, user_id: str) -> Dict[str, Any]:
        """
        Get the conversation history for a user.
        
        Args:
            user_id: The ID of the user (can be a guest ID like 'guest_guest')
            
        Returns:
            Dict containing the conversation history
        """
        try:
            # Check if this is a guest user
            is_guest = self._is_guest_user(user_id)
            
            # Get the response ID based on user type
            response_id = None
            
            if is_guest:
                # For guests, use in-memory state
                response_id = self.guest_conversation_state.get(user_id)
            else:
                # For authenticated users, get from database
                chat_thread = self._get_or_create_chat_thread(user_id)
                response_id = chat_thread.openai_thread_id
            
            # If we have a response ID, retrieve the conversation from OpenAI
            if response_id:
                response = self.client.responses.retrieve(response_id)
                
                # Format the conversation history
                history = []
                
                # Add the input messages
                if isinstance(response.input, list):
                    for msg in response.input:
                        history.append({
                            "role": msg.role,
                            "content": msg.content
                        })
                elif response.input:
                    history.append({
                        "role": "user",
                        "content": response.input
                    })
                
                # Add the output messages
                if hasattr(response, 'output') and response.output:
                    for output_item in response.output:
                        if hasattr(output_item, 'type') and output_item.type == 'message':
                            if hasattr(output_item, 'role') and hasattr(output_item, 'content'):
                                # Handle the nested content structure
                                content_text = ""
                                if isinstance(output_item.content, list):
                                    for content_item in output_item.content:
                                        if hasattr(content_item, 'type') and content_item.type == 'output_text':
                                            if hasattr(content_item, 'text'):
                                                content_text += content_item.text
                                else:
                                    content_text = output_item.content
                                    
                                history.append({
                                    "role": output_item.role,
                                    "content": content_text
                                })
                
                return {
                    "status": "success",
                    "conversation_id": response_id,
                    "messages": history,
                    "language": "en"  # Default language
                }
            else:
                return {
                    "status": "error",
                    "message": "No conversation found for this user"
                }
            
        except Exception as e:
            logger.error(f"Error getting conversation history for user {user_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to get conversation history: {str(e)}"
            }
    
    def _is_guest_user(self, user_id: str) -> bool:
        """
        Check if a user is a guest user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            True if the user is a guest, False otherwise
        """
        return user_id.startswith('guest_') or user_id == 'guest'
    
    def _get_or_create_chat_thread(self, user_id: str) -> ChatThread:
        """
        Get or create a chat thread for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            The chat thread
        """
        try:
            # Get the user
            user = CustomUser.objects.get(id=user_id)
            
            # Get the most recent active thread or create a new one
            try:
                chat_thread = ChatThread.objects.filter(user=user, is_active=True).latest('created_at')
            except ChatThread.DoesNotExist:
                chat_thread = self._create_chat_thread(user_id)
            
            return chat_thread
        except Exception as e:
            logger.error(f"Error getting or creating chat thread for user {user_id}: {str(e)}")
            raise
    
    def _create_chat_thread(self, user_id: str) -> ChatThread:
        """
        Create a new chat thread for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            The new chat thread
        """
        try:
            # Get the user
            user = CustomUser.objects.get(id=user_id)
            
            # Create a new thread
            chat_thread = ChatThread.objects.create(
                user=user,
                is_active=True,
                openai_thread_id=None  # Will be updated with the response ID
            )
            
            return chat_thread
        except Exception as e:
            logger.error(f"Error creating chat thread for user {user_id}: {str(e)}")
            raise
    
    def _save_user_message(self, user_id: str, message: str, thread: ChatThread) -> UserMessage:
        """
        Save a user message to the database.
        
        Args:
            user_id: The ID of the user
            message: The message text
            thread: The chat thread
            
        Returns:
            The saved user message
        """
        try:
            # Create a new user message
            user_message = UserMessage.objects.create(
                thread=thread,
                role='user',
                content=message
            )
            
            return user_message
        except Exception as e:
            logger.error(f"Error saving user message for user {user_id}: {str(e)}")
            raise
    
    def _save_assistant_response(self, user_message: UserMessage, response_text: str) -> UserMessage:
        """
        Save an assistant response to the database.
        
        Args:
            user_message: The user message that triggered the response
            response_text: The response text
            
        Returns:
            The saved assistant message
        """
        try:
            # Create a new assistant message
            assistant_message = UserMessage.objects.create(
                thread=user_message.thread,
                role='assistant',
                content=response_text,
                parent=user_message
            )
            
            return assistant_message
        except Exception as e:
            logger.error(f"Error saving assistant response: {str(e)}")
            raise
    
    def _save_tool_call(self, user_id: str, tool_call, tool_result: str) -> ToolCall:
        """
        Save a tool call to the database.
        
        Args:
            user_id: The ID of the user
            tool_call: The tool call
            tool_result: The tool result
            
        Returns:
            The saved tool call
        """
        try:
            # Get the user
            user = CustomUser.objects.get(id=user_id)
            
            # Get the most recent active thread
            chat_thread = ChatThread.objects.filter(user=user, is_active=True).latest('created_at')
            
            # Create a new tool call
            tool_call_obj = ToolCall.objects.create(
                thread=chat_thread,
                tool_call_id=tool_call.id,
                function_name=tool_call.function.name,
                function_arguments=tool_call.function.arguments,
                function_result=tool_result
            )
            
            return tool_call_obj
        except Exception as e:
            logger.error(f"Error saving tool call for user {user_id}: {str(e)}")
            raise
    
    def _process_response(self, response, user_id: str, user_message: Optional[UserMessage] = None, is_guest: bool = False) -> Dict[str, Any]:
        """
        Process a response from the OpenAI Responses API.
        
        Args:
            response: The response from the OpenAI Responses API
            user_id: The ID of the user
            user_message: The user message that triggered the response (None for guests)
            is_guest: Whether the user is a guest
            
        Returns:
            Dict containing the processed response
        """
        try:
            # Extract the message content from the response
            message_content = self._extract_message_content(response)
            
            # Save the assistant response to the database (only for authenticated users)
            if not is_guest and user_message:
                self._save_assistant_response(user_message, message_content)
            
            # Return the response
            return {
                "status": "success",
                "message": message_content,
                "response_id": response.id
            }
        except Exception as e:
            logger.error(f"Error processing response for user {user_id}: {str(e)}")
            raise
    
    def _extract_message_content(self, response) -> str:
        """
        Extract the message content from a response.
        
        Args:
            response: The response from the OpenAI Responses API
            
        Returns:
            The message content
        """
        message_content = ""
        
        # Handle the case where output is a list of message objects
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                # Check if this is a message item
                if hasattr(output_item, 'type') and output_item.type == 'message':
                    # Extract content from the message
                    if hasattr(output_item, 'content') and output_item.content:
                        for content_item in output_item.content:
                            if hasattr(content_item, 'type') and content_item.type == 'output_text':
                                if hasattr(content_item, 'text'):
                                    message_content += content_item.text
        
        # Fallback to output_text if the above structure isn't found
        if not message_content and hasattr(response, 'output_text'):
            message_content = response.output_text
        
        return message_content

# Function to generate a unique guest ID
def generate_guest_id() -> str:
    """
    Generate a unique guest ID.
    
    Returns:
        A unique guest ID
    """
    return f"guest_{uuid.uuid4().hex[:8]}"

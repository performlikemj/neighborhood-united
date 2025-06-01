# meals/meal_assistant_implementation.py
import json, logging, uuid, traceback
import time
from typing import Dict, Any, List, Generator, Optional, Union
import numbers
from datetime import date, datetime
import re
from bs4 import BeautifulSoup   
from django.conf import settings
from django.conf.locale import LANG_INFO  # Add this import
from django.core.cache import cache
from django.utils import timezone
from openai import OpenAI
from openai.types.responses import (
    # high‑level lifecycle events
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    ResponseCompletedEvent,
    # assistant message streaming
    ResponseOutputMessage,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseContentPartAddedEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    # function‑calling events
    ResponseFunctionToolCall,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
)
from openai import BadRequestError
from pydantic import BaseModel, Field, ConfigDict
from .tool_registration import get_all_tools, get_all_guest_tools, handle_tool_call
from customer_dashboard.models import ChatThread, UserMessage, WeeklyAnnouncement, UserDailySummary, UserChatSummary, AssistantEmailToken
from custom_auth.models import CustomUser
from shared.utils import generate_user_context
from utils.model_selection import choose_model
import pytz
from local_chefs.models import ChefPostalCode
from django.db.models import F
from meals.models import ChefMealEvent
from dotenv import load_dotenv
import os
import requests # Added for n8n webhook call
import traceback
from django.template.loader import render_to_string # Added for rendering email templates

# Add the translation utility
from utils.translate_html import translate_paragraphs

# Add helper function for getting language name
def _get_language_name(language_code):
    """
    Returns the full language name for a given language code.
    Falls back to the code itself if the language is not found.
    """
    if language_code in LANG_INFO and 'name' in LANG_INFO[language_code]:
        return LANG_INFO[language_code]['name']
    return language_code

load_dotenv()

# Pydantic model for email body formatting
class EmailBody(BaseModel):
    """
    Pydantic model for ensuring consistent email body formatting.
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    
    content: str = Field(..., description="The formatted HTML content for the email body")

# Pydantic model for email responses
class EmailResponse(BaseModel):
    """
    Pydantic model for ensuring consistent email responses.
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    
    message: str = Field(..., description="The response message without any follow-up questions or fluff")

# Global dictionary to maintain guest state across request instances
GLOBAL_GUEST_STATE: Dict[str, Dict[str, Any]] = {}

# Default prompt templates in case they're not available in environment variables
DEFAULT_GUEST_PROMPT = """
You are MJ, sautAI's friendly meal-planning consultant. Your role is to help guests with their food, nutrition, recipe, and meal-planning inquiries. Deliver guidance in a warm, business-casual tone, embodying the character of MJ—a Jamaica-born and Brooklyn, NY-raised individual who is thoughtful, considerate, confident, and knowledgeable about sautAI and food-related topics. 

# Goals
- Provide clear and accurate answers to food/nutrition/recipe/meal-planning questions.
- Suggest the next sensible step toward the user's cooking or health goal based on their message.
- Explain tool access limitations for guests, and suggest the benefits of creating a free account without being pushy.
- Ensure all interactions remain within the scope of food topics—decline unrelated requests politely.

# Tone
- Business-casual, warm, and helpful.
- Maintain a thoughtful and considerate approach, yet be straightforward on sautAI and food-related subjects.

# Constraints
- You are limited to guest tools and must provide general nutrition guidance only. Medical advice is not permissible.
- Users do not need details on tool calls or IDs.

# Style
- Use short paragraphs (3-4 sentences).
- Incorporate bullet points or numbered lists for steps or options.
- Conclude most (but not all) responses with a brief invitation, such as "Anything else I can help you with?"

# Output Format
- Maintain a conversational style with short, clear, and friendly sentences.
- Deliver answers and advice in structured formats using lists and bullet points where applicable.
"""

DEFAULT_AUTH_PROMPT = """
#Introduction
You are MJ, sautAI's friendly meal-planning consultant. The company's mission is to ensure ease of access to food, saving user's time it takes to plan and prepare food (time that can be spent doing things they love) and battling dietary illnesses by providing healthy meal options and connecting user's to local chefs in their area. Currently, you are experiencing an issue and cannot fully function to the best of your ability. Inform the user of this but feel free to answer high-level food-related questions.


#Tone
Business-Casual—warm, helpful, never pushy. The actual MJ you are embodying is a Jamaica born, and Brooklyn, NY raised person who tries to be thoughtful and considerate, but also confident and straightforward on the topic of everything sautAI and food related. 

#Mission
Answer food/nutrition/recipe/meal-planning questions clearly and accurately. 
Suggest the next sensible step toward their cooking or health goal stated in their message.

#Safety & Scope
General nutrition guidance only—no medical advice. 
It is of vital importance you stay on food topics; besides general cordial greetings and communication, gently refused unrelated or disallowed requests.
The user will never need to know how your tool call works and will never have to provide user id, meal id or any other id number for ensuring a tool is run. 

#Style
Short paragraphs (≤ 3‑4 sentences). Use bullet points or numbered lists for steps or options. 
End most (not every) turns with a brief invitation such as 'Anything else I can help you with?'
"""

# Get template from environment, fallback to defaults if not available
GUEST_PROMPT_TEMPLATE = os.getenv("GUEST_PROMPT_TEMPLATE", DEFAULT_GUEST_PROMPT)
AUTH_PROMPT_TEMPLATE = os.getenv("AUTH_PROMPT_TEMPLATE", DEFAULT_AUTH_PROMPT)

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────────────
#  Constants
# ───────────────────────────────────────────────────────────────────────────────
# Default fallback models if model selection fails
MODEL_AUTH_FALLBACK = "gpt-4.1-mini"
MODEL_GUEST_FALLBACK = "gpt-4.1-nano"

#  ▸ A < 50‑token teaser shown to guests every turn
TOOL_TEASER = (
    "- create_meal_plan: build and manage a weekly plan\n"
    "- approve_meal_plan: checkout & pay for plans that include your local and personal chef (when available)\n"
    "- list_upcoming_meals: see what's next\n"
    "- …and 20 more when you sign up! As well as having your own personal sautAI assistant."
)


# ───────────────────────────────────────────────────────────────────────────────
#  Assistant class
# ───────────────────────────────────────────────────────────────────────────────
class MealPlanningAssistant:
    """sautAI meal‑planning assistant with guest/auth modes and parallel‑tool support."""

    def __init__(self, user_id: Optional[Union[int, str]] = None):
        self.client = OpenAI(api_key=settings.OPENAI_KEY)
        # Better detection of numeric user IDs (authenticated users)
        if user_id is not None:
            if isinstance(user_id, numbers.Number) or (isinstance(user_id, str) and user_id.isdigit()):
                self.user_id = int(user_id)
            elif isinstance(user_id, str) and user_id:
                # Keep provided string user_id (guest_id from session or request)
                # Strip any "guest:" prefix for consistency if it exists
                self.user_id = user_id.replace("guest:", "") if user_id.startswith("guest:") else user_id
                print(f"MEAL_ASSISTANT: Using guest ID: {self.user_id}")
            else:
                # Only generate a new one if None or empty string provided
                self.user_id = generate_guest_id()
                print(f"MEAL_ASSISTANT: Generated new guest ID: {self.user_id}")
        else:
            self.user_id = generate_guest_id()
            print(f"MEAL_ASSISTANT: No user_id provided, generated: {self.user_id}")
            
        self.auth_tools = [t for t in get_all_tools() if not t["name"].startswith("guest")]
        self.guest_tools = get_all_guest_tools()

        self.system_message = (
            "You are sautAI's helpful meal‑planning assistant. "
            "Answer questions about food, nutrition and meal plans."
        )

    # ─────────────────────────────────────────  public entry points
    def send_message(
        self, message: str, thread_id: Optional[str] = None # Not used for auth users anymore
    ) -> Dict[str, Any]:
        """Send a message using database-backed history (non-streaming)."""
        is_guest = self._is_guest(self.user_id)
        
        # Select the appropriate model based on user status and message complexity
        model = choose_model(
            user_id=self.user_id,
            is_guest=is_guest,
            question=message
        )
        
        # Fallback if model selection fails
        if not model:
            model = MODEL_GUEST_FALLBACK if is_guest else MODEL_AUTH_FALLBACK

        # For guests, use in-memory history if available
        if is_guest:
            guest_data = GLOBAL_GUEST_STATE.get(self.user_id, {})
            if guest_data and "history" in guest_data:
                # Get existing history and append new message
                history = guest_data["history"].copy()
                history.append({"role": "user", "content": message})
                print(f"GUEST_HISTORY: Using existing history with {len(history)} messages")
            else:
                # Initialize new history
                history = [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message},
                ]
                print(f"GUEST_HISTORY: Starting new conversation")
            
            prev_resp_id = guest_data.get("response_id")
            chat_thread = None
        else:
            # For auth users, load history from DB
            chat_thread = self._get_or_create_thread(self.user_id)
            history = chat_thread.openai_input_history or []
            if not history:
                 history.append({"role": "system", "content": self.system_message})
            history.append({"role": "user", "content": message})
            prev_resp_id = None # Send full history


        try:
            resp = self.client.responses.create(
                model=model,
                input=history,
                instructions=self._instructions(is_guest),
                tools=self.guest_tools if is_guest else self.auth_tools,
                parallel_tool_calls=True,
                # We send full history for auth, maybe not needed for guest either?
                # Consider setting previous_response_id=None always if full history works
                previous_response_id=prev_resp_id, 
            )
            
            final_response_id = resp.id
            # Log the raw response object from OpenAI to understand its structure
            logger.debug(f"OpenAI API Response object for user {self.user_id} (response_id: {final_response_id}): {resp}")
            # If the above is too verbose or doesn't show the crucial part, log resp.output directly
            # logger.debug(f"OpenAI API Response output for user {self.user_id} (response_id: {final_response_id}): {getattr(resp, 'output', 'N/A')}")

            final_output_text = self._extract(resp) # Extract text before modifying history

            # If the response involved tool calls, OpenAI might implicitly add them to resp.input
            # Or we might need to reconstruct history if tools were called (less common in non-streaming)
            # For simplicity, let's assume resp.input contains the final state or reconstruct minimally.
            
            final_history = history.copy() # Start with what we sent
            # Add assistant response
            if final_output_text:
                 final_history.append({"role": "assistant", "content": final_output_text})
            # TODO: If non-streaming responses can include tool calls, need to add them here correctly.
            # Example: Check resp.output for function calls/outputs and append them.
            
            # Persist the final state
            if not is_guest:
                self._persist_state(self.user_id, final_response_id, is_guest, final_history)
                # Also save the user message and response text in UserMessage model
                if chat_thread:
                    self._save_turn(self.user_id, message, final_output_text, chat_thread)
            elif is_guest:
                # Store both response_id and history for guests
                GLOBAL_GUEST_STATE[self.user_id] = {
                    "response_id": final_response_id,
                    "history": final_history
                }
                print(f"GUEST_HISTORY: Saved conversation with {len(final_history)} messages")

            return {
                "status": "success",
                "message": final_output_text,
                "response_id": final_response_id,
            }
        except Exception as e:
             logger.error(f"Error in send_message for user {self.user_id}: {str(e)}")
             traceback.print_exc()
             return {"status": "error", "message": f"An error occurred: {str(e)}"}

    def stream_message(
        self, message: str, thread_id: Optional[str] = None # thread_id is the DB ChatThread ID, not OpenAI's
    ) -> Generator[Dict[str, Any], None, None]:

        """Stream a message using database-backed history."""
        is_guest = self._is_guest(self.user_id)
        
        # Select the appropriate model based on user status and message complexity
        model = choose_model(
            user_id=self.user_id,
            is_guest=is_guest,
            question=message
        )
        
        # Fallback if model selection fails
        if not model:
            model = MODEL_GUEST_FALLBACK if is_guest else MODEL_AUTH_FALLBACK
        

        # For guests, use in-memory history if available
        if is_guest:
            guest_data = GLOBAL_GUEST_STATE.get(self.user_id, {})
            if guest_data and "history" in guest_data:
                # Get existing history and append new message
                history = guest_data["history"].copy()
                history.append({"role": "user", "content": message})
                print(f"GUEST_HISTORY: Using existing history with {len(history)} messages")
            else:
                # Initialize new history
                history = [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message},
                ]
                print(f"GUEST_HISTORY: Starting new conversation")
            
            # Guest state might still use previous_response_id for short-term continuity
            prev_resp_id = guest_data.get("response_id")
            chat_thread = None
            user_msg = None
        else:
            # For auth users, load history from DB
            chat_thread = self._get_or_create_thread(self.user_id)
            history = chat_thread.openai_input_history or [] # Load history
            if not history: # If history is empty, initialize with system message
                 history.append({"role": "system", "content": self.system_message})
            history.append({"role": "user", "content": message}) # Add current message
            prev_resp_id = None # We send full history, so no previous_response_id needed
            user_msg = (
                 self._save_user_message(self.user_id, message, chat_thread) if chat_thread else None
            )
        
        
        yield from self._process_stream(
            model=model,
            history=history, # Send the loaded/updated history
            instructions=self._instructions(is_guest),
            tools=self.guest_tools if is_guest else self.auth_tools,
            previous_response_id=prev_resp_id, # Set to None for auth users
            user_id=self.user_id,
            is_guest=is_guest,
            chat_thread=chat_thread, # Pass thread for saving later
            user_msg=user_msg,
        )

    # ─────────────────────────────────────────  core streaming logic
    def _process_stream(
        self,
        *,
        model: str,
        history: List[Dict[str, Any]],
        instructions: str,
        tools: List[Dict[str, Any]],
        previous_response_id: Optional[str],
        user_id: int,
        is_guest: bool,
        chat_thread: Optional[ChatThread],
        user_msg: Optional[UserMessage],
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streams one assistant turn, handles parallel tool calls by:
          - yielding text and function_call events as they arrive
          - appending both the function_call and its output into `history`
          - looping back so the model can continue with that new context.
        """
        
        print(f"\n===== DEBUG: Starting _process_stream =====")
        print(f"User ID: {user_id} | Is Guest: {is_guest} | Model: {model}")
        print(f"Previous Response ID: {previous_response_id}")
        print(f"Available Tools: {[t['name'] for t in tools]}")
        
        # If previous_response_id is None and this is a guest, try to fetch from cache
        if previous_response_id is None and is_guest:
            prev_resp_id = cache.get(f"last_resp:{self.user_id}")
            if prev_resp_id:
                previous_response_id = prev_resp_id
                print(f"DEBUG: Restored previous response ID from cache: {previous_response_id}")
        
        start_ts = time.time()
        current_history = history[:] # Work on a copy
        final_response_id = None # Track the final OpenAI response ID

        while True:
            # 1) Start streaming from the Responses API
            # for i, item in enumerate(current_history):
            #     item_type = item.get('type') or item.get('role', 'unknown')
            
            print(f"\n----- DEBUG: Starting New Stream Request -----")
            print(f"Current history length: {len(current_history)}")
            print(f"Last few history items: {current_history[-3:] if len(current_history) > 3 else current_history}")
            
            stream = self.client.responses.create(
                model=model,
                input=current_history, # Use the current history copy
                instructions=instructions,
                tools=tools,
                previous_response_id=previous_response_id,
                stream=True,
                parallel_tool_calls=True,
            )

            new_id = None
            buf = ""
            calls: List[Dict[str, Any]] = []
            wrapper_to_call: Dict[str, str] = {}
            latest_id_in_stream = previous_response_id # Initialize with previous ID

            # 2) Consume the event stream
            for ev in stream:
                # 2a) Capture the new response ID
                if isinstance(ev, ResponseCreatedEvent):
                    new_id = ev.response.id
                    latest_id_in_stream = new_id # Always update with the latest ID
                    final_response_id = new_id # Track the latest ID received
                    print(f"DEBUG: New response ID created: {new_id}")
                    yield {"type": "response_id", "id": new_id}
                    continue

                # 2b) End of this assistant turn
                if isinstance(ev, ResponseCompletedEvent):
                    print(f"DEBUG: Response completed event received")
                    break

                # 2c) Stream text deltas
                if isinstance(ev, ResponseTextDeltaEvent):
                    if ev.delta and not buf.endswith(ev.delta):
                        buf += ev.delta
                        yield {"type": "text", "content": ev.delta}
                    continue
                if isinstance(ev, ResponseTextDoneEvent):
                    if ev.text and not buf.endswith(ev.text):
                        buf += ev.text
                        yield {"type": "text", "content": ev.text}
                    print(f"DEBUG: Text response complete: '{buf[:50]}...' (truncated)")
                    continue

                # 2d) Function‑call argument fragments
                if isinstance(ev, ResponseFunctionCallArgumentsDeltaEvent):
                    # Map wrapper_id → real call_id if we haven't yet
                    if ev.item_id not in wrapper_to_call and getattr(ev, "item", None):
                        cid = getattr(ev.item, "call_id", None)
                        if cid:
                            wrapper_to_call[ev.item_id] = cid
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)

                    # Accumulate arguments
                    tgt = next((c for c in calls if c["id"] == real_id), None)
                    if not tgt:
                        tgt = {"id": real_id, "name": None, "args": ""}
                        calls.append(tgt)
                    tgt["args"] += ev.delta
                    continue

                # 2e) End‑of‑args: emit function_call and append to history
                if isinstance(ev, ResponseFunctionCallArgumentsDoneEvent):
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)
                    entry = next((c for c in calls if c["id"] == real_id), None)
                    if not entry:
                        continue

                    args_json = entry["args"]
                    args_obj  = json.loads(args_json)
                    
                    print(f"\nDEBUG: FUNCTION CALL ARGUMENTS DONE EVENT")
                    print(f"Function Name: {entry['name']}")
                    print(f"Arguments: {args_json}")
                    
                    # Fix the user_id in the arguments if needed
                    fixed_args_json = self._fix_function_args(entry["name"], args_json)
                    if fixed_args_json != args_json:
                        print(f"DEBUG: Fixed user_id in arguments - Original: {args_json}")
                        print(f"DEBUG: Fixed to: {fixed_args_json}")
                        args_json = fixed_args_json
                        args_obj = json.loads(args_json)
                    
                    # 1) Tell front‑end the call is happening
                    yield {
                        "type": "response.function_call",
                        "name": entry["name"],
                        "arguments": args_obj,
                        "call_id": real_id,
                    }

                    # 2) Inject the function_call into CURRENT history
                    call_entry = {
                        "type":       "function_call",
                        "name":       entry["name"],
                        "arguments":  args_json,
                        "call_id":    real_id
                    }
                    current_history.append(call_entry)
                    # Removed cache logic
                    continue

                # 2f) Wrapper event: new function_call header
                if isinstance(ev, ResponseOutputItemAddedEvent) and isinstance(ev.item, ResponseFunctionToolCall):
                    item       = ev.item
                    wrapper_id = item.id
                    call_id    = item.call_id
                    name       = item.name

                    wrapper_to_call[wrapper_id] = call_id
                    calls.append({"id": call_id, "name": name, "args": ""})

                    print(f"DEBUG: New function call requested: {name} (call_id: {call_id})")
                    yield {
                        "type":        "response.tool",
                        "tool_call_id": call_id,
                        "name":        name,
                        "output":      None,
                    }
                    continue

                # 2g) Other output items – ignore
                if isinstance(ev, ResponseOutputItemDoneEvent):
                    continue

            # 3) Flush any buffered text
            if buf:
                yield {"type": "text", "content": buf}

                # Also persist the assistant's reply into the running history
                current_history.append({
                    "role": "assistant",
                    "content": buf.strip()
                })
                
            # Store the final response ID in Redis for this user (expires in 24h)
            if final_response_id:
                cache.set(f"last_resp:{self.user_id}", final_response_id, 86400)
                print(f"DEBUG: Stored response ID in cache: {final_response_id}")

            # 4) If no function calls were requested, finish up
            if not calls:
                print("DEBUG: No function calls requested. Completing response.")
                yield {"type": "response.completed"}
                break # Exit the while loop

            # 5) Drop any stray wrapper‑only entries
            calls = [c for c in calls if not c["id"].startswith("fc_")]
            print(f"\nDEBUG: Processing {len(calls)} function calls")

            # 6) Execute all parallel calls
            for call in calls:
                call_id = call["id"]
                
                print(f"\n----- DEBUG: Executing Function Call -----")
                print(f"Call ID: {call_id}")
                print(f"Function Name: {call['name']}")
                print(f"Raw Arguments: {call['args']}")
                
                args_obj = json.loads(call["args"] or "{}")
                
                # Fix the user_id in the arguments if needed
                fixed_args_json = self._fix_function_args(call["name"], call["args"] or "{}")
                if fixed_args_json != (call["args"] or "{}"):
                    print(f"DEBUG: Fixed user_id in arguments before execution")
                    print(f"DEBUG: Original: {call['args']}")
                    print(f"DEBUG: Fixed to: {fixed_args_json}")
                    args_obj = json.loads(fixed_args_json)
                
                try:
                    print(f"DEBUG: About to handle tool call: {call['name']} with args: {args_obj}")
                    result = handle_tool_call(
                        type("Call", (), {
                            "call_id": call_id,
                            "function": type("F", (), {
                                "name":      call["name"],
                                "arguments": json.dumps(args_obj)
                            })
                        })
                    )
                    print(f"DEBUG: Tool call result type: {type(result)}")
                    print(f"DEBUG: Tool call result: {result if isinstance(result, (str, int, float, bool)) else str(result)[:200]+'...' if isinstance(result, dict) else 'Complex object'}")
                except Exception as e:
                    print(f"DEBUG: ERROR executing tool call: {type(e).__name__}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    result = {"status": "error", "message": str(e)}

                # Emit tool_result
                yield {
                    "type":        "tool_result",
                    "tool_call_id": call_id,
                    "name":        call["name"],
                    "output":      result,
                }

                # 7a) Inject the function_call_output into CURRENT history
                result_json = json.dumps(result)
                output_entry = {
                    "type":     "function_call_output",
                    "call_id":  call_id,
                    "output":   result_json,
                }
                current_history.append(output_entry)
                # Removed cache logic

            # Debug: Print the history being sent to the next request
            for i, item in enumerate(current_history):
                item_type = item.get("type", item.get("role", "unknown"))

            # 8) Loop back: Prepare for the next API call within the same turn
            previous_response_id = latest_id_in_stream # Use the ID from the segment just processed
            print(f"DEBUG: Continuing with updated history, previous_response_id={previous_response_id}")
            # IMPORTANT: We continue the loop, sending the *updated* current_history

        # --- End of while loop ---
        
        processing_time = time.time() - start_ts
        print(f"\n===== DEBUG: Completed _process_stream =====")
        print(f"Total processing time: {processing_time:.2f}s")
        print(f"Final response ID: {final_response_id}")
        
        # Persist the *final* state after the loop completes
        if not is_guest and final_response_id:
             # Pass the final history state and the final response ID
            self._persist_state(user_id, final_response_id, is_guest, current_history)
        elif is_guest and final_response_id:
             # Update guest state with final ID
             GLOBAL_GUEST_STATE[user_id] = {
                 "response_id": final_response_id,
                 "history": current_history
             }

    # ────────────────────────────────────────────────────────────────────
    #  Prompt helpers
    # ────────────────────────────────────────────────────────────────────
    def build_prompt(self, is_guest: bool) -> str:
        """
        Build the system prompt for the assistant based on whether the user is a guest or authenticated
        """
        all_tools = self.auth_tools
        if is_guest:
            guest_tools = self.guest_tools
            return GUEST_PROMPT_TEMPLATE.format(guest_tools=guest_tools, all_tools=all_tools)
        else:
            user = None
            try:
                user = CustomUser.objects.get(id=self.user_id)
                user_ctx = generate_user_context(user)
                username = user.username
                admin_blurb = self._current_admin_blurb(user)
                admin_section = ""
                if admin_blurb:
                    admin_section = f"\nWEEKLY UPDATE\n{admin_blurb}\n\n"
                    admin_section += "Make sure to subtly acknowledge this announcement information early in the conversation. Only mention once per entire conversation and only if it's natural in the context. Do not prefix with 'Weekly Update'.\n\n"
                
                # Get the user's chat summary if available
                user_chat_summary = self._get_user_chat_summary(user)
                
                # Generate information about local chefs and meal events
                local_chef_and_meal_events = self._local_chef_and_meal_events(user)
                
                # Ensure AUTH_PROMPT_TEMPLATE has placeholders for all these values
                # Example: {username}, {user_ctx}, {admin_section}, {all_tools}, {user_chat_summary}, {local_chef_and_meal_events}
                return AUTH_PROMPT_TEMPLATE.format(
                    username=username,
                    user_ctx=user_ctx,
                    admin_section=admin_section,
                    all_tools=", ".join([t['name'] for t in self.auth_tools]),
                    user_chat_summary=user_chat_summary,
                    local_chef_and_meal_events=local_chef_and_meal_events
                )
            except CustomUser.DoesNotExist:
                logger.warning(f"User with ID {self.user_id} not found while building prompt. Using fallback.")
                return f"You are MJ, sautAI's friendly meal-planning consultant. You are currently experiencing issues with your setup and functionality. You cannot help with any of the user's requests at the moment but please let them know the sautAI team has been notified and will look into it as soon as possible."
            except Exception as e:
                logger.error(f"Error generating prompt for user {self.user_id}: {str(e)}")
                # Return a simple fallback prompt
                username_str = user.username if user else f"user ID {self.user_id}"
                return f"You are MJ, sautAI's friendly meal-planning consultant. You are currently chatting with {username_str} and experiencing issues with your setup and functionality. You cannot help with any of the user's requests at the moment but please let them know the sautAI team has been notified and will look into it as soon as possible."

    def _instructions(self, is_guest: bool) -> str:
        """
        Return the system‑prompt string that steers GPT for this turn.
        We keep two variants: a lightweight guest prompt and a fuller
        authenticated‑user prompt.  Both are < 350 tokens.
        """
        return self.build_prompt(is_guest)

    # ────────────────────────────────────────────────────────────────────
    #  Conversation‑reset helper
    # ────────────────────────────────────────────────────────────────────
    def reset_conversation(self) -> Dict[str, Any]:
        """
        Clears conversation state so the next message starts a brand‑new thread.

        * Guests → removes their entry from the in‑memory dict.
        * Auth users → marks all active ChatThread rows inactive in a single
          bulk‑update (cheap DB call).
        """
        if self._is_guest(self.user_id):
            # Safely drop the key; dict.pop(k, None) returns None if missing.
            GLOBAL_GUEST_STATE.pop(self.user_id, None)
            return {"status": "success", "message": "Guest context cleared."}

        # Authenticated user: bulk‑update threads instead of iterating row‑by‑row.
        try:
            user = CustomUser.objects.get(id=self.user_id)
        except CustomUser.DoesNotExist:
            return {"status": "error", "message": "User not found."}

        ChatThread.objects.filter(user=user, is_active=True).update(is_active=False)
        return {"status": "success", "message": "Conversation reset for user."}
    
    # ────────────────────────────────────────────────────────────────────
    #  DB + state helpers
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_guest(user_id) -> bool:
        # only strings can startwith()
        if isinstance(user_id, str):
            return user_id.startswith("guest_") or user_id == "guest"
        # everything else (ints, UUIDs, etc.) is an auth user
        return False

    def _persist_state(self, user_id: int, resp_id: str, is_guest: bool, history: List[Dict[str, Any]]) -> None:
        """Persist the final response ID and the full conversation history to the DB for auth users, or update guest state."""
        if is_guest:
            # Store both response_id and history for guests
            GLOBAL_GUEST_STATE[user_id] = {
                "response_id": resp_id,
                "history": history
            }
            print(f"GUEST_HISTORY: Persisted conversation with {len(history)} messages")
        else:
            try:
                thread = self._get_or_create_thread(user_id)
                
                # Store as a list to ensure proper lookup
                if isinstance(thread.openai_thread_id, list):
                    thread.openai_thread_id.append(resp_id)
                else:
                    # If it's a string or None, create a new list
                    old_value = thread.openai_thread_id
                    thread.openai_thread_id = [resp_id]
                
                # Also update latest_response_id for reference
                thread.latest_response_id = resp_id
                thread.openai_input_history = history # Save the complete history
                
                # Mark announcement as shown (if we included one)
                today = timezone.localdate()
                user = CustomUser.objects.get(id=user_id)
                admin_blurb = self._current_admin_blurb(user)
                if admin_blurb and not thread.announcement_shown:
                    thread.announcement_shown = today
                
                thread.save()
            except Exception as e:
                logger.error(f"Failed to persist state for user {user_id}: {str(e)}")
                traceback.print_exc()

    # ── Thread & message helpers
    def _get_or_create_thread(self, user_id: int) -> ChatThread:
        user = CustomUser.objects.get(id=user_id)
        try:
            thread = ChatThread.objects.filter(user=user, is_active=True).latest("created_at")
            
            # Log the thread ID and openai_thread_id for debugging
            if thread:
                thread_id = thread.id
                openai_id = thread.openai_thread_id
                latest_id = thread.latest_response_id
            return thread
            
        except ChatThread.DoesNotExist:
            new_thread = ChatThread.objects.create(user=user, is_active=True, openai_thread_id=[])
            return new_thread

    @staticmethod
    def _save_user_message(user_id: int, txt: str, thread: ChatThread) -> UserMessage:
        user = CustomUser.objects.get(id=user_id)
        return UserMessage.objects.create(thread=thread, user=user, message=txt)

    @staticmethod
    def _save_assistant_response(msg: UserMessage, resp: str) -> None:
        msg.response = resp
        msg.save(update_fields=["response"])

    @staticmethod
    def _save_turn(user_id: int, message: str, response: str, thread: ChatThread) -> Optional[UserMessage]:
        """Save the user message and assistant response to the database for an authenticated user's turn."""
        if not thread:
             logger.error(f"Cannot save turn for user {user_id}: ChatThread object is missing.")
             return None
        try:
            # Create user message with response. User is implicitly linked via the thread.
            user_msg = UserMessage.objects.create(thread=thread, user_id=user_id, message=message, response=response)
            return user_msg
        except Exception as e:
            logger.error(f"Error saving conversation turn to UserMessage for thread {thread.id}: {str(e)}")
            traceback.print_exc()
            return None

    # ── util
    @staticmethod
    def _extract(response) -> str:
        """
        Extract text content from an OpenAI response, handling different response formats.
        
        This method is flexible and will extract text from various OpenAI response structures,
        including direct output_text, message contents, and text delta events.
        """
        # Most common case with simple output_text attribute
        if hasattr(response, "output_text"):
            formatted_text = response.output_text
        else:
            # Fall back to iterating through output items
            text = ""
            for item in getattr(response, "output", []):
                # Handle message type items
                if getattr(item, "type", None) == "message":
                    for c in getattr(item, "content", []):
                        if getattr(c, "type", None) == "output_text":
                            text += getattr(c, "text", "")
                # Handle direct text items
                elif getattr(item, "type", None) == "text":
                    text += getattr(item, "text", "")
            formatted_text = text

        # ------------------------------------------------------------------
        # PHASE 1: PROPER UNICODE NORMALIZATION AT SOURCE
        # This prevents hex corruption from occurring in the first place
        # ------------------------------------------------------------------
        import unicodedata
        import re
        
        try:
            # Ensure proper UTF-8 encoding/decoding to prevent hex corruption
            formatted_text = formatted_text.encode('utf-8', errors='replace').decode('utf-8')
            # Normalize Unicode characters (NFC = canonical composition)
            formatted_text = unicodedata.normalize('NFC', formatted_text)
        except (UnicodeEncodeError, UnicodeDecodeError) as e:
            # Fallback: just normalize what we can if encoding fails
            formatted_text = unicodedata.normalize('NFC', formatted_text)
            logger.warning(f"Unicode encoding issue in _extract: {e}")

        # Strip non‑printable / control characters that sometimes creep in
        formatted_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", formatted_text)

        # ------------------------------------------------------------------
        # PHASE 3: MINIMAL SAFETY NET FOR EXTREME EDGE CASES
        # Only keep the most critical patterns as backup
        # ------------------------------------------------------------------
        critical_patterns = [
            (r'(\d{3})b0C\b', r'\1°C'),     # Only 220b0C -> 220°C (very specific)
            (r'(\d{3})f\b', r'\1°F'),       # Only 425f -> 425°F (3 digits only)
        ]
        for pattern, replacement in critical_patterns:
            formatted_text = re.sub(pattern, replacement, formatted_text)

        # Remove any leading "Subject: ..." line the LLM might prepend
        formatted_text = re.sub(r"^Subject:[^\n\r]*[\n\r]+", "", formatted_text, flags=re.IGNORECASE)

        formatted_text = formatted_text.strip()
        return formatted_text

    def _fix_function_args(self, function_name: str, args_str: str) -> str:
        """Ensure that user_id is correctly set in function arguments."""
        try:
            print(f"DEBUG: Fixing function args for {function_name}")
            args = json.loads(args_str)
            
            # If the function has a user_id parameter and it's not the current user
            if "user_id" in args:
                print(f"DEBUG: Args contains user_id: {args['user_id']}, current user: {self.user_id}")
                if args["user_id"] != self.user_id:
                    print(f"DEBUG: Correcting user_id from {args['user_id']} to {self.user_id}")
                    args["user_id"] = self.user_id
                    return json.dumps(args)
            
            # Special case for chef-meal related functions
            chef_meal_funcs = ['replace_meal_plan_meal', 'place_chef_meal_event_order', 'generate_payment_link']
            if function_name in chef_meal_funcs:
                print(f"DEBUG: Special processing for chef meal function: {function_name}")
                print(f"DEBUG: Args before: {args}")
                
                # Add logging for specific functions
                if function_name == 'replace_meal_plan_meal':
                    print(f"DEBUG: replace_meal_plan_meal args:")
                    print(f"  user_id: {args.get('user_id')}")
                    print(f"  meal_plan_meal_id: {args.get('meal_plan_meal_id')}")
                    print(f"  chef_meal_id: {args.get('chef_meal_id')}")
                    print(f"  event_id: {args.get('event_id')}")
                    
                elif function_name == 'generate_payment_link':
                    print(f"DEBUG: generate_payment_link args:")
                    print(f"  user_id: {args.get('user_id')}")
                    print(f"  order_id: {args.get('order_id')}")
                    
                elif function_name == 'place_chef_meal_event_order':
                    print(f"DEBUG: place_chef_meal_event_order args:")
                    print(f"  user_id: {args.get('user_id')}")
                    print(f"  meal_event_id: {args.get('meal_event_id')}")
                    print(f"  quantity: {args.get('quantity')}")
                    print(f"  special_instructions: {args.get('special_instructions')}")
            
            return args_str
        except Exception as e:
            print(f"DEBUG: Error in _fix_function_args: {type(e).__name__}: {str(e)}")
            return args_str

    def _current_admin_blurb(self, user) -> Optional[str]:
        """
        Return the announcement for this user's locale, if any.
        Includes both global and region-specific announcements.
        """
        today = timezone.localdate()
        iso_week = today.isocalendar()  # (year, week, weekday)
        week_start = date.fromisocalendar(iso_week[0], iso_week[1], 1)  # Monday
        
        # Figure out user's country (via Address model)
        try:
            country_code = user.address.country.code if hasattr(user, 'address') and user.address and user.address.country else ""
        except AttributeError:
            country_code = ""
        
        # Check cache first
        cache_key = f"blurb:{week_start}:{country_code or 'GLOBAL'}"
        cached = cache.get(cache_key)
        if cached is not None:  # Empty string means "none this week"
            return cached or None
        
        # Get global announcement
        global_qs = WeeklyAnnouncement.objects.filter(
            week_start=week_start,
            country__isnull=True
        )
        global_blurb = global_qs.first().content.strip() if global_qs.exists() else ""
        
        # Get country-specific announcement if applicable
        regional_blurb = ""
        if country_code:
            regional_qs = WeeklyAnnouncement.objects.filter(
                week_start=week_start,
                country=country_code
            )
            if regional_qs.exists():
                regional_blurb = regional_qs.first().content.strip()
        
        # Combine the announcements
        combined_blurb = ""
        if regional_blurb and global_blurb:
            # Both regional and global announcements exist, combine them
            combined_blurb = f"{regional_blurb}\n\n*******\n\n{global_blurb}"
        elif regional_blurb:
            # Only regional announcement exists
            combined_blurb = regional_blurb
        elif global_blurb:
            # Only global announcement exists
            combined_blurb = global_blurb
        
        # Cache for an hour
        cache.set(cache_key, combined_blurb, 60 * 60)
        return combined_blurb or None

    def _add_previous_context(self, prev_id: Optional[str], history: List[Dict[str, Any]]) -> None:
        """Add context (function calls/outputs) from cache using the previous response ID."""
        if not prev_id:
            return
            

        if prev_id in self.function_calls_cache:
            cached_turn_data = self.function_calls_cache[prev_id]
            
            # Track which call IDs are already in history (e.g., if manually added)
            call_ids_in_history = set()
            for item in history:
                if item.get('type') == 'function_call' and 'call_id' in item:
                    call_ids_in_history.add(item['call_id'])
                if item.get('type') == 'function_call_output' and 'call_id' in item:
                    call_ids_in_history.add(item['call_id'])
            
            # Add calls and outputs from the cache, ensuring pairs
            added_calls = 0
            # Sort by call_id just for deterministic order if needed
            sorted_call_ids = sorted(cached_turn_data.keys())
            
            for call_id in sorted_call_ids:
                call_data = cached_turn_data[call_id]
                # Only add if both call and output exist and aren't already in history
                if call_data.get("call") and call_data.get("output") and call_id not in call_ids_in_history:
                    history.append(call_data["call"])
                    history.append(call_data["output"])
                    added_calls += 1

    # ─────────────────────────────────────────  user summary streaming
    def stream_user_summary(self, summary_date=None) -> Generator[Dict[str, Any], None, None]:
        """
        Stream the generation of a user daily summary.
        
        Creates or fetches a UserDailySummary record and streams its generation process.
        Returns a generator yielding status events as the summary is generated.
        
        Args:
            summary_date: Optional date for the summary (default: today in user's timezone)
            
        Returns:
            Generator yielding event dictionaries with progress and result information
        """
        from customer_dashboard.models import UserDailySummary
        import uuid
        
        if self._is_guest(self.user_id):
            yield {"type": "error", "message": "User summaries are only available for authenticated users"}
            return
            
        try:
            user = CustomUser.objects.get(id=self.user_id)
            
            # Generate a unique ticket for tracking this summary request
            ticket = f"sum_{uuid.uuid4().hex[:8]}"
            
            # Set summary_date to today in user's timezone if not provided
            if summary_date is None:
                user_timezone = pytz.timezone(user.timezone if user.timezone else 'UTC')
                summary_date = timezone.now().astimezone(user_timezone).date()
            elif isinstance(summary_date, str):
                # If it's a string, parse it as a date
                summary_date = datetime.strptime(summary_date, '%Y-%m-%d').date()
                
            # Emit initial status
            yield {"type": "status", "status": "starting", "ticket": ticket}
            
            # Check for existing summary
            summary = UserDailySummary.objects.filter(
                user=user,
                summary_date=summary_date,
                status=UserDailySummary.COMPLETED
            ).first()
            
            if summary:
                # Return existing summary immediately
                yield {"type": "status", "status": "completed", "ticket": ticket}
                yield {"type": "summary", 
                       "summary": summary.summary,
                       "summary_date": summary.summary_date.strftime('%Y-%m-%d'),
                       "created_at": summary.created_at.isoformat() if summary.created_at else None,
                       "updated_at": summary.updated_at.isoformat() if summary.updated_at else None
                }
                return
                
            # No completed summary exists - create or update a pending one
            summary, created = UserDailySummary.objects.get_or_create(
                user=user,
                summary_date=summary_date,
                defaults={'status': UserDailySummary.PENDING, 'ticket': ticket}
            )
            
            if not created and summary.status != UserDailySummary.COMPLETED:
                # Update existing non-completed summary
                summary.status = UserDailySummary.PENDING
                summary.ticket = ticket
                summary.save(update_fields=["status", "ticket"])
            
            # Start generating the summary in background
            from meals.email_service import generate_user_summary
            generate_user_summary.delay(user.id, summary_date.strftime('%Y-%m-%d'))
            
            # Inform frontend that generation has started
            yield {"type": "status", "status": "pending", "ticket": ticket}
            
            # Poll for updates until the summary is complete or fails
            max_attempts = 12  # 30 seconds total (12 * 2.5s)
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(2.5)  # Wait 2.5 seconds between checks
                
                # Refresh the summary from the database
                summary.refresh_from_db()
                
                # Check if the summary is completed or has an error
                if summary.status == UserDailySummary.COMPLETED:
                    yield {"type": "status", "status": "completed", "ticket": ticket}
                    yield {"type": "summary", 
                           "summary": summary.summary,
                           "summary_date": summary.summary_date.strftime('%Y-%m-%d'),
                           "created_at": summary.created_at.isoformat() if summary.created_at else None,
                           "updated_at": summary.updated_at.isoformat() if summary.updated_at else None
                    }
                    return
                elif summary.status == UserDailySummary.ERROR:
                    yield {"type": "error", "message": "Error generating summary", "ticket": ticket}
                    return
                
                # Still pending - yield a progress update
                yield {"type": "status", "status": "pending", "ticket": ticket, 
                       "progress": f"{attempt + 1}/{max_attempts}"}
                
                attempt += 1
            
            # If we've exhausted our attempts but the summary is still pending
            yield {"type": "status", "status": "pending", "ticket": ticket, 
                   "message": "Summary generation is taking longer than expected. Please check back later."}
                       
        except Exception as e:
            logger.error(f"Error in stream_user_summary for user {self.user_id}: {str(e)}")
            traceback.print_exc()
            yield {"type": "error", "message": f"An error occurred: {str(e)}"}
            return

    def _local_chef_and_meal_events(self, user: CustomUser) -> str:
        """
        Get information about local chefs and their upcoming meal events for a user.
        Returns a formatted string suitable for inclusion in the prompt.
        """
        try:
            # Get user's postal code from their address
            if not hasattr(user, 'address') or not user.address or not user.address.input_postalcode:
                return "No local chef information available (address not set)."

            postal_code = user.address.input_postalcode

            # Find chefs that serve this postal code
            chef_ids = ChefPostalCode.objects.filter(
                postal_code__code=postal_code
            ).values_list('chef_id', flat=True)

            if not chef_ids:
                return "No chefs currently serve your area."

            # Get upcoming events from these chefs
            now = timezone.now()
            events = ChefMealEvent.objects.filter(
                chef_id__in=chef_ids,
                event_date__gte=now.date(),
                status__in=['scheduled', 'open'],
                order_cutoff_time__gt=now,
                orders_count__lt=F('max_orders')
            ).select_related('chef', 'chef__user', 'meal').order_by('event_date', 'event_time')[:20]  # Limit to 20 upcoming events

            if not events:
                return "No upcoming meal events from local chefs at this time."

            # Format the information
            event_info = []
            for event in events:
                event_info.append(
                    f"• {event.meal.name} by Chef {event.chef.user.username} "
                    f"on {event.event_date.strftime('%A, %B %d')} at {event.event_time.strftime('%I:%M %p')} "
                    f"(${float(event.current_price):.2f}/serving)"
                )

            return (
                "LOCAL CHEF UPDATES\n"
                f"You have {len(chef_ids)} local chef{'s' if len(chef_ids) > 1 else ''} in your area. "
                "Here are some upcoming meals:\n"
                f"{chr(10).join(event_info)}"
            )

        except Exception as e:
            logger.error(f"Error getting local chef information: {str(e)}")
            return "Unable to retrieve local chef information at this time."

    def _get_user_chat_summary(self, user: CustomUser) -> str:
        """
        Retrieve the consolidated chat summary for a user if available
        """
        try:
            user_summary = UserChatSummary.objects.filter(
                user=user,
                status=UserChatSummary.COMPLETED
            ).first()
            
            if user_summary and user_summary.summary:
                return f"USER CHAT HISTORY SUMMARY\n{user_summary.summary}\n\n"
            
            return ""
        except Exception as e:
            logger.error(f"Error retrieving user chat summary: {str(e)}")
            return ""

    # ────────────────────────────────────────────────────────────────────
    #  Internal Helper for Formatting Email Content
    # ────────────────────────────────────────────────────────────────────
    def _format_text_for_email_body(self, raw_text: str) -> str:
        """
        Ask the LLM to transform a plain-text assistant reply into
        tight, semantic HTML (p/ul/ol/li/h3 and table markup only),
        then run a final sanitation pass so no hidden bytes or weird
        punctuation break Mail clients.

        It returns **just** the inner-HTML string ready to drop into
        our Django template.
        """

        # --------------------------- guard rails ---------------------------
        if not raw_text.strip():
            return ""

        if not getattr(self, "client", None):      # Offline fallback
            safe_fallback = raw_text.replace("\n", "<br>")
            return f"<p>{safe_fallback}</p>"

        # ── Unicode normalisation & smart‑punctuation clean‑up ──────────────────
        import unicodedata
        # 1.  Collapse compatibility forms so fancy quotes / dashes become single code‑points
        raw_text = unicodedata.normalize("NFKC", raw_text)
        # 2.  Downgrade common "smart" punctuation to plain ASCII so later ASCII‑only
        #     paths don't emit stray control bytes ( \u0011, \u0019 → 9, etc.)
        smart_to_ascii = {
            "\u2018": "'", "\u2019": "'",
            "\u201C": '"', "\u201D": '"',
            "\u2013": "-", "\u2014": "--",
            "\u2026": "...",
        }
        for bad, good in smart_to_ascii.items():
            raw_text = raw_text.replace(bad, good)

        # Clean up multiple spaces and trim (moved from end of removed section)
        import re
        raw_text = re.sub(r'\s+', ' ', raw_text).strip()

        # ----------------------- build LLM prompt -------------------------
        html_template = """
            <!DOCTYPE html>
            {% load meal_filters %}
            <html>
            <head>
                <meta charset="UTF-8">
                <!-- Ensures mobile responsiveness in most modern clients -->
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Assistant Communication</title>
                <style>
                    /* Basic reset & body styling */
                    body { 
                        margin: 0; 
                        padding: 0; 
                        width: 100% !important; 
                        background-color: #f8f8f8; /* Subtle background to distinguish content area */
                    }

                    /* Container for the "white card" look */
                    .container {
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #ffffff; /* White background inside the container */
                    }

                    /* Typography */
                    h1, h2, h3, p {
                        margin-top: 0;
                        font-family: Arial, sans-serif;
                        color: #333333;
                    }
                    h1 {
                        font-size: 24px; 
                        color: #4CAF50;
                    }
                    h2 {
                        font-size: 20px; 
                        color: #5cb85c; 
                        border-bottom: 1px solid #dddddd; 
                        padding-bottom: 10px;
                    }
                    h3 {
                        font-size: 18px; 
                    }
                    p {
                        font-size: 16px; 
                        line-height: 1.5; 
                        margin: 0 0 10px;
                    }

                    /* Card-like option sections */
                    .option {
                        border: 1px solid #dddddd; 
                        border-radius: 5px; 
                        padding: 15px; 
                        margin-bottom: 20px; 
                    }
                    .option h3 {
                        margin-bottom: 10px;
                    }

                    /* Bulletproof buttons: We're using table-based code for broad compatibility */
                    .btn-table {
                        border-collapse: collapse;
                        margin: 0 auto;
                    }
                    .btn-table td {
                        border-radius: 5px;
                        text-align: center;
                    }
                    .btn-link {
                        display: inline-block;
                        font-size: 16px;
                        font-family: Arial, sans-serif;
                        text-decoration: none;
                        padding: 12px 24px;
                        border-radius: 5px;
                        margin-top: 15px;
                        white-space: nowrap; /* Prevents text wrap in narrow clients */
                    }
                    /* Specific button variations */
                    .bulk-btn {
                        background-color: #4CAF50;
                        color: #ffffff;
                    }
                    .daily-btn {
                        background-color: #2196F3;
                        color: #ffffff;
                    }

                    /* email body */
                    .email-body {
                        padding: 20px 30px;
                        line-height: 1.6;
                        font-size: 16px;
                    }
                    .email-body h2 {
                        color: #4CAF50;
                        font-size: 20px;
                        margin-top: 0;
                    }
                    .email-body p {
                        margin-bottom: 15px;
                    }
                    .email-body ul, .email-body ol {
                        margin-bottom: 15px;
                        padding-left: 20px;
                    }

                    /* Footer */
                    .footer {
                        text-align: center; 
                        color: #777777; 
                        font-size: 12px; 
                        padding: 10px; 
                        margin-top: 20px; 
                    }
                    .footer a { 
                        color: #007BFF; 
                        text-decoration: none; 
                    }

                    /* Logo */
                    .logo { 
                        text-align: center; 
                        margin-bottom: 20px; 
                    }
                    .logo img { 
                        max-width: 200px; 
                        height: auto; 
                    }
                </style>
            </head>
            <body>
                <!-- Full-width "wrapper" table to accommodate background color in older email clients -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8f8;">
                    <tr>
                        <td align="center" valign="top">
                            <div class="container">
                                <!-- Logo Section -->
                                <div class="logo">
                                    <!-- Include descriptive alt text for accessibility -->
                                    <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" />
                                </div>

                                <div class="email-body">
                                    <p>Hi {{ user_name|default:'there' }},</p>


                                    {% if personal_assistant_email %}
                                    <div style="background: #f0f8ff; border-left: 4px solid #4CAF50; border-radius: 8px; margin: 24px 0; padding: 20px 16px;">
                                        <h3 style="margin: 0 0 8px; font-family: Arial, sans-serif; color: #2196F3; font-size: 18px; display: flex; align-items: center;">
                                            🤖 Contact Your AI Assistant
                                        </h3>
                                        <p style="margin: 0 0 12px; color: #333; font-size: 16px; line-height: 1.5;">
                                            Need something personalized? Just email your assistant directly:
                                        </p>
                                        <a href="mailto:{{ personal_assistant_email }}" 
                                        style="display: inline-block; background: #4CAF50; color: #fff; padding: 12px 28px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 16px;">
                                            {{ personal_assistant_email }}
                                        </a>
                                    </div>
                                    {% endif %}
                                    <div class="content-section">
                                        {% autoescape off %}
                                        {{ email_body_content|safe }}
                                        {% endautoescape %}
                                    </div>
                        
                                    {% if profile_url %}
                                    <div class="button-container">
                                        <a href="{{ profile_url }}" class="button">Access Your Dashboard</a>
                                            </div>
                                            {% endif %}
                                
                                            <p>If you have any questions, feel free to email your personal assistant at <a href="mailto:{{ personal_assistant_email }}">{{ personal_assistant_email }}</a> or email us at <a href="mailto:support@sautai.com">support@sautai.com</a>.</p>
                                            <p>Best regards,<br>The SautAI Team</p>
                                        </div>

                                        </div>
                                        <!-- Footer -->
                                        <p style="color: #777; font-size: 12px; margin-top: 20px;">
                                            <strong>Disclaimer:</strong> SautAI uses generative AI for meal planning, 
                                            shopping list generation, and other suggestions, which may produce inaccuracies. 
                                            Always double-check crucial information.
                                        </p>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </body>
                    </html>
        """
        if not raw_text.strip():
            return ""

        # Fallback if the OpenAI client is not available
        if not getattr(self, "client", None):
            safe_fallback = raw_text.replace("\n", "<br>")
            return f"<p>{safe_fallback}</p>"

        prompt_content = (
            "You are a professional, expert email formatter. Convert the AI response text (after --- BEGIN RAW TEXT ---) into clean, accessible HTML.\n\n"
            "RULES:\n"
            "1. Use standard HTML tags: <p>, <h3>, <ul>/<li>, <ol>/<li>, and <table> for structured data only.\n"
            "2. If there's a list, use proper <ul> or <ol> with <li> elements.\n"
            "3. Create tight, semantic HTML (no <div>s needed).\n"
            "4. For meal plans or shopping lists, always use appropriate HTML structure.\n"
            "5. When there's a clear heading (like \"Shopping List:\" or \"Meal Plan:\"), make it an <h3>.\n"
            "6. Only return the BODY content (don't include <html>, <head>, or <body> tags).\n"
            "7. Maintain any links (<a href>) but ensure they open in a new tab with target=\"_blank\" rel=\"noopener noreferrer\".\n"
            "8. Be precise, clean, but leave no words or meaning out from the original text.\n"
            "9. IMPORTANT: Absolutely DO NOT ask for feedback.\n "
            "10. If a paragraph ends with \":\", convert it to <h3> and start a new bullet list below it.\n\n"
            f"--- BEGIN RAW TEXT ---\n{raw_text}\n--- END RAW TEXT ---"
        )

        try:
            response = self.client.responses.create(
                model="gpt-4.1-mini",  
                input=[
                    {"role": "developer", "content": "You are a precise HTML email formatter. Return ONLY HTML content without follow-up questions."},
                    {"role": "user", "content": prompt_content}
                ],
                stream=False,
                text={
                    "format": {
                        'type': 'json_schema',
                        'name': 'email_body',
                        'schema': EmailBody.model_json_schema()
                    }
                }
            )
            
            # Parse the response with Pydantic to ensure format consistency
            try:
                # First check if it looks like valid JSON
                if response.output_text.strip().startswith("{") and "content" in response.output_text:
                    email_body = EmailBody.model_validate_json(response.output_text)
                    formatted_text = email_body.content
                else:
                    # Try to extract just the HTML content if it's not in expected format
                    formatted_text = response.output_text.strip()
                    logger.warning(f"Email body not in expected JSON format, using raw output")
            except Exception as e:
                logger.error(f"Failed to validate email body format: {e}")
                formatted_text = response.output_text.strip()
            
            # ------------------- FINAL CLEAN-UP (critical) --------------------
            import re
            # strip non-printable/control bytes
            formatted_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", formatted_text)
            formatted_text = re.sub(r"[\x80-\x9F]", "", formatted_text)
            # normalise stray punctuation / smart quotes / dashes
            replacements = {
                "\uFFFD": "",
                "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
                "\u2018": "'",  "\u2019": "'", "\u201B": "'",
                "\u201C": '"',  "\u201D": '"',
            }
            for bad, good in replacements.items():
                formatted_text = formatted_text.replace(bad, good)

            # Clean up common temperature formats that might still appear
            formatted_text = re.sub(r'(\d+)\s*degrees?\s*([CF])', r'\1°\2', formatted_text, flags=re.IGNORECASE)
            formatted_text = re.sub(r'\s+', ' ', formatted_text)

            # nuke any "Subject: …" line the model accidentally prepends
            formatted_text = re.sub(r"^Subject:[^\n\r]*[\n\r]+", "", formatted_text, flags=re.IGNORECASE)

            # ------------------- INSTACART BUTTON FORMATTING --------------------
            # Replace any Instacart links with properly formatted buttons according to brand guidelines
            
            # Use BeautifulSoup to properly parse and process the HTML
            try:
                # Determine if the content appears to be recipe-related
                is_recipe = "recipe" in formatted_text.lower()
                copy_type = "recipe" if is_recipe else "ingredients"
                
                # Use the BeautifulSoup helper function to replace Instacart links
                formatted_text = _replace_instacart_links(formatted_text, copy_type)
                logger.debug("Successfully processed Instacart links with BeautifulSoup")
            except Exception as e:
                logger.error(f"Error processing Instacart links: {e}")
                # Continue with the original text if there's an error

            return formatted_text.strip()
            
        except Exception as e:
            # Log and fall back to simple formatting
            logger.error(f"Email body formatting via LLM failed: {e}")
            safe_fallback = raw_text.replace("\n", "<br>")
            return f"<p>{safe_fallback}</p>"

    # ────────────────────────────────────────────────────────────────────
    #  Email Processing Method
    # ────────────────────────────────────────────────────────────────────
    def send_message_for_email(self, message_content: str) -> Dict[str, Any]:
        """
        Processes a message for email reply, handling iterative tool calls
        until a final textual response is obtained from the assistant.

        This method is designed for authenticated users and asynchronous processing
        (e.g., via Celery tasks for email replies). It manages conversation
        history and state persistence.

        Args:
            message_content (str): The aggregated message content from the user's email(s).

        Returns:
            Dict[str, Any]: A dictionary containing:
                - "status" (str): "success" or "error".
                - "message" (str): The final textual response from the assistant.
                                   Can be an empty string if the assistant provides
                                   no text or a fallback error message.
                - "response_id" (str, optional): The ID of the *final* OpenAI
                                                 response in the conversational turn.
        """
        # 3.1. Initial Setup & Pre-checks
        # User Authentication Check
        if self._is_guest(self.user_id):
            logger.error(f"send_message_for_email called for a guest user ID: {self.user_id}. This is not supported.")
            return {"status": "error", "message": "Email processing is for authenticated users only.", "response_id": None}
            
        # Model Selection
        model = choose_model(
            user_id=self.user_id,
            is_guest=False, 
            question=message_content
        )
        
        # Fallback if model selection fails
        if not model:
            model = MODEL_AUTH_FALLBACK
            
        # History Initialization
        chat_thread = self._get_or_create_thread(self.user_id)
        current_history = chat_thread.openai_input_history.copy() if chat_thread.openai_input_history else []
        if not current_history:
            current_history.append({"role": "system", "content": self.system_message})
        current_history.append({"role": "user", "content": message_content})
            
        # State Variables
        final_output_text = ""
        final_response_id = None
        prev_resp_id_for_api = None
        max_tool_iterations = 5
        iterations = 0
        # Initialize tool_calls_in_response before the loop
        tool_calls_in_response = []
        user = CustomUser.objects.get(id=self.user_id)

        # 3.2. Main Processing Loop (Iterative Tool Calling)
        try:
            while iterations < max_tool_iterations:
                iterations += 1
                logger.debug(f"send_message_for_email: Iteration {iterations}/{max_tool_iterations} for user {self.user_id}. History length: {len(current_history)}")
                
                # OpenAI API Call - Use structured output on final iteration if no tools are called
                if iterations == max_tool_iterations or not tool_calls_in_response:
                    try:
                        resp = self.client.responses.create(
                            model=model,
                            input=current_history,
                            instructions=self._instructions(is_guest=False) + "\n\nIMPORTANT: Do not include any follow-up questions or phrases like 'Is there anything else?' or 'Let me know if you need more help'. Respond only with the relevant information. The user can only reply via their personal assistant email address which is: " + user.personal_assistant_email + " and not by replying to this email.",
                            tools=self.auth_tools,
                            parallel_tool_calls=True,
                            previous_response_id=prev_resp_id_for_api,
                            text={
                                "format": {
                                    'type': 'json_schema',
                                    'name': 'email_response',
                                    'schema': EmailResponse.model_json_schema()
                                }
                            } if not tool_calls_in_response else None  # Only use structured output when no tools are expected
                        )
                    except Exception as structured_error:
                        logger.error(f"Error using structured output for email: {structured_error}. Falling back to standard format.")
                        # Fallback to standard format if structured output fails
                        resp = self.client.responses.create(
                            model=model,
                            input=current_history,
                            instructions=self._instructions(is_guest=False) + "\n\nIMPORTANT: Do not include any follow-up questions.",
                            tools=self.auth_tools,
                            parallel_tool_calls=True,
                            previous_response_id=prev_resp_id_for_api,
                        )
                else:
                    # Standard call for intermediate iterations
                    resp = self.client.responses.create(
                        model=model,
                        input=current_history,
                        instructions=self._instructions(is_guest=False),
                        tools=self.auth_tools,
                        parallel_tool_calls=True,
                        previous_response_id=prev_resp_id_for_api,
                    )
                
                final_response_id = resp.id
                prev_resp_id_for_api = final_response_id
                logger.debug(f"send_message_for_email: OpenAI API Response for user {self.user_id} (iter {iterations}, resp_id: {final_response_id}): {resp}")
                
                # Extract Tool Calls
                tool_calls_in_response = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
                
                # Condition: No Tool Calls in Response (End of Turn)
                if not tool_calls_in_response:
                    # Try to parse the structured output if it was requested
                    try:
                        extracted_text = self._extract(resp)
                        
                        # Check if the response is in JSON format from structured output
                        if extracted_text.strip().startswith('{') and '"message"' in extracted_text:
                            try:
                                parsed_response = EmailResponse.model_validate_json(extracted_text)
                                final_output_text = parsed_response.message
                                logger.info(f"send_message_for_email: Successfully parsed structured output for user {self.user_id}")
                            except Exception as parse_error:
                                logger.warning(f"send_message_for_email: Failed to parse structured output: {parse_error}. Using raw text.")
                                final_output_text = extracted_text
                        else:
                            final_output_text = extracted_text
                    except Exception as extract_error:
                        logger.error(f"send_message_for_email: Error extracting text: {extract_error}")
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
                        requests.post(n8n_traceback_url, json={"error": str(extract_error), "source":"send_message_for_email", "traceback": traceback.format_exc()})
                        final_output_text = "I'm sorry, but I encountered an issue processing your message. Please try again or contact support."
                    
                    if final_output_text:
                        current_history.append({"role": "assistant", "content": final_output_text})
                    logger.info(f"send_message_for_email: No tool calls. Extracted text: '{final_output_text[:100]}...' for user {self.user_id}")
                    break
                    
                # Condition: Tool Calls Present
                logger.info(f"send_message_for_email: Found {len(tool_calls_in_response)} tool call(s) for user {self.user_id}.")
                for tool_call_item in tool_calls_in_response:
                    # Append function_call to history
                    call_entry = {
                        "type": "function_call",
                        "name": tool_call_item.name,
                        "arguments": tool_call_item.arguments,
                        "call_id": tool_call_item.call_id
                    }
                    current_history.append(call_entry)
                    logger.debug(f"send_message_for_email: Appended tool call to history: {tool_call_item.name} (ID: {tool_call_item.call_id}) for user {self.user_id}")
                    
                    # Execute Tool
                    args_json_str = tool_call_item.arguments
                    fixed_args_json_str = self._fix_function_args(tool_call_item.name, args_json_str)
                    tool_result_data = None
                    try:
                        logger.info(f"send_message_for_email: Executing tool {tool_call_item.name} with args: {fixed_args_json_str} for user {self.user_id}")
                        mock_call_object = type("Call", (), {
                            "call_id": tool_call_item.call_id,
                            "function": type("F", (), {
                                "name": tool_call_item.name,
                                "arguments": fixed_args_json_str
                            })
                        })
                        tool_result_data = handle_tool_call(mock_call_object)
                        logger.info(f"send_message_for_email: Tool {tool_call_item.name} result: {str(tool_result_data)[:200]}... for user {self.user_id}")
                    except Exception as e_tool:
                        logger.error(f"send_message_for_email: Error executing tool {tool_call_item.name} for user {self.user_id}: {e_tool}", exc_info=True)
                        tool_result_data = {"status": "error", "message": f"Error executing tool {tool_call_item.name}: {str(e_tool)}"}
                        
                    # Append function_call_output to history
                    output_entry = {
                        "type": "function_call_output",
                        "call_id": tool_call_item.call_id,
                        "output": json.dumps(tool_result_data)
                    }
                    current_history.append(output_entry)
                    logger.debug(f"send_message_for_email: Appended tool output to history for call_id {tool_call_item.call_id} for user {self.user_id}")
                
                # Max Iterations Check
                if iterations >= max_tool_iterations and tool_calls_in_response:
                    logger.warning(f"send_message_for_email: Reached max tool iterations ({max_tool_iterations}) for user {self.user_id}. API may still want to call tools.")
                    final_output_text = "I'm encountering some complexity with your request. Could you please try again, perhaps simplifying it, or use the web interface for a more detailed interaction?"
                    current_history.append({"role": "assistant", "content": final_output_text})
                    break
            
            # 3.3. Post-Loop Processing & Persistence
            logger.info(f"send_message_for_email: Loop finished for user {self.user_id}. Final text: '{final_output_text[:100]}...'")
            
            # Clean up the output text to ensure it's consistent
            if final_output_text:
                # Check for common follow-up questions and remove them
                follow_up_patterns = [
                    "How does this look?",
                    "Is this format acceptable?",
                    "Does this work for you?",
                    "Let me know if",
                    "Is there anything else",
                    "Do you want me to make any changes",
                    "Would you like me to",
                    "I hope this helps",
                    "I'm here to help",
                    "Feel free to reach out"
                ]
                
                # Remove any follow-up questions from the end of the text
                clean_text = final_output_text
                for pattern in follow_up_patterns:
                    if pattern.lower() in clean_text.lower():
                        clean_text = clean_text[:clean_text.lower().find(pattern.lower())].strip()
                
                # If we made changes, update the final output
                if clean_text != final_output_text:
                    logger.info(f"send_message_for_email: Cleaned up output text for user {self.user_id}, removed follow-up questions")
                    final_output_text = clean_text
            
            # Persist State
            if final_response_id:
                self._persist_state(self.user_id, final_response_id, is_guest=False, history=current_history)
                if chat_thread and message_content and final_output_text:
                    self._save_turn(self.user_id, message_content, final_output_text, chat_thread)
            else:
                logger.warning(f"send_message_for_email: No final_response_id was captured for user {self.user_id}. State may not be fully persisted.")
                
            # Return Success
            return {"status": "success", "message": final_output_text, "response_id": final_response_id}
            
        # 3.4. Outer Error Handling
        except Exception as e_outer:
            logger.error(f"send_message_for_email: Unhandled error for user {self.user_id}: {e_outer}", exc_info=True)
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e_outer), "source":"send_message_for_email", "traceback": traceback.format_exc()})
            return {
                "status": "error", 
                "message": f"An unexpected error occurred during email processing: {str(e_outer)}", 
                "response_id": final_response_id
            }

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

        # 2. Format the raw reply content for email body
        formatted_email_body = self._format_text_for_email_body(raw_reply_content)
        print(f"DEBUG: Formatted email body for user {self.user_id}:\n{formatted_email_body}")

        # 3. Render the full email using the new template
        try:
            user = CustomUser.objects.get(id=self.user_id) # Fetch user for their name
            user_name = user.get_full_name() or user.username
            
            # Check if the user has unsubscribed from emails
            if getattr(user, 'unsubscribed_from_emails', False):
                logger.info(f"MealPlanningAssistant: User {self.user_id} has unsubscribed from emails. Skipping email reply.")
                return {"status": "skipped", "message": "User has unsubscribed from emails."}
                
            # Get user's preferred language for translation
            user_preferred_language = getattr(user, 'preferred_language', 'en')
        except CustomUser.DoesNotExist:
            user_name = "there" # Fallback name
            user_preferred_language = 'en'  # Default to English if user not found
            logger.warning(f"User {self.user_id} not found when preparing email, using fallback name.")
        
        site_domain = os.getenv('STREAMLIT_URL')
        profile_url = f"{site_domain}/profile" # Adjust if your profile URL is different

        email_html_content = render_to_string(
            'customer_dashboard/assistant_email_template.html',
            {
                'user_name': user_name,
                'email_body_content': formatted_email_body,
                'profile_url': profile_url,
                'personal_assistant_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') else None
            }
        )
        
        # Translate the email content if needed
        try:
            email_html_content = translate_paragraphs(
                email_html_content,
                user_preferred_language
            )
            logger.info(f"Successfully translated email content to {_get_language_name(user_preferred_language)} ({user_preferred_language}) for user {self.user_id}")
        except Exception as e:
            logger.error(f"Error translating email content for user {self.user_id} to {_get_language_name(user_preferred_language)} ({user_preferred_language}): {e}")
            # Continue with the original English content as fallback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"translate_email_content", "traceback": traceback.format_exc()})
        
        print(f"DEBUG: Final HTML email content (after translation) for user {self.user_id}:\n{email_html_content}")

        # 4. Trigger n8n to send this reply_content back to recipient_email
        n8n_webhook_url = os.getenv('N8N_EMAIL_REPLY_WEBHOOK_URL')
        if not n8n_webhook_url:
            logger.error(f"MealPlanningAssistant: N8N_EMAIL_REPLY_WEBHOOK_URL not configured. Cannot send email reply for user {self.user_id}.")
            # Log the intended reply locally if n8n is not configured
            logger.info(f"Intended email reply for {recipient_email} (User ID: {self.user_id}):\nSubject: Re: {original_subject}\nBody:\n{formatted_email_body}")
            return {"status": "error", "message": "N8N_EMAIL_REPLY_WEBHOOK_URL not configured."}

        # Ensure original_subject has content
        if not original_subject or original_subject.strip() == "":
            logger.warning(f"Empty subject received for user {self.user_id}. Using default subject.")
            original_subject = "Message from your SautAI Assistant"
        
        # Handle reply prefix
        subject_prefix = "Re: "
        if original_subject.lower().startswith("re:") or original_subject.lower().startswith("aw:"):
            subject_prefix = ""
        final_subject = f"{subject_prefix}{original_subject}"

        payload = {
            'status': 'success', 
            'action': 'send_reply', 
            'reply_content': email_html_content, # Send the fully rendered HTML
            'recipient_email': recipient_email,
            'from_email': user.personal_assistant_email if hasattr(user, 'personal_assistant_email') and user.personal_assistant_email else f"mj+{user_email_token}@sautai.com", 
            'original_subject': final_subject,
            'in_reply_to_header': in_reply_to_header,
            'email_thread_id': email_thread_id,
            'openai_response_id': new_openai_response_id,
            'chat_thread_id': chat_thread.id if chat_thread else None
        }
        print(f"DEBUG: Payload for n8n webhook for user {self.user_id}:\n{json.dumps(payload, indent=2)}")

        try:
            logger.info(f"MealPlanningAssistant: Posting to n8n webhook for user {self.user_id}. URL: {n8n_webhook_url}")
            response = requests.post(n8n_webhook_url, json=payload, timeout=15)
            response.raise_for_status() 
            logger.info(f"MealPlanningAssistant: Successfully posted assistant reply to n8n for user {self.user_id}. Status: {response.status_code}")
            return {"status": "success", "message": "Email reply successfully sent to n8n.", "n8n_response_status": response.status_code}
        except requests.RequestException as e:
            logger.error(f"MealPlanningAssistant: Failed to post assistant reply to n8n for user {self.user_id}: {e}. Payload: {json.dumps(payload)}")
            # Log the intended reply if n8n call failed
            logger.info(f"Failed n8n call. Intended email reply for {recipient_email} (User ID: {self.user_id}):\nSubject: {final_subject}\nBody:\n{formatted_email_body}")
            return {"status": "error", "message": f"Failed to send email via n8n: {str(e)}"}
        except Exception as e_general: # Catch any other unexpected errors during payload prep or call
            logger.error(f"MealPlanningAssistant: Unexpected error during n8n email sending for user {self.user_id}: {e_general}. Payload: {json.dumps(payload if 'payload' in locals() else 'Payload not generated')}", exc_info=True)
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e_general), "source":"process_and_reply_to_email", "traceback": traceback.format_exc()})
            return {"status": "error", "message": f"Unexpected error during email sending preparation: {str(e_general)}"}

    @classmethod
    def send_notification_via_assistant(cls, user_id: int, message_content: str, subject: str = None) -> Dict[str, Any]:
        """
        Static utility method that wraps process_and_reply_to_email to allow tasks to
        send emails through the assistant.
        
        This method is designed to be called from Celery tasks to route notifications 
        through the assistant rather than sending them directly.
        
        Args:
            user_id: The ID of the user to notify
            message_content: The message content to send
            subject: Optional subject line (defaults to "Update from your meal assistant")
            
        Returns:
            Dict with status and result information
        """
        try:
            # Get user
            user = CustomUser.objects.get(id=user_id)
            
            # Skip if email not confirmed
            if not user.email_confirmed:
                logger.warning(f"Skipping notification for user {user_id} with unconfirmed email")
                return {"status": "skipped", "reason": "email_not_confirmed"}
                
            # Skip if user has unsubscribed from emails
            if getattr(user, 'unsubscribed_from_emails', False):
                logger.warning(f"Skipping notification for user {user_id} who has unsubscribed from emails")
                return {"status": "skipped", "reason": "user_unsubscribed"}
                
            # Initialize assistant
            assistant = cls(user_id=user_id)
            
            # Use user's email, fallback to a default
            recipient_email = user.email
            
            # Build the subject line
            if not subject:
                subject = "Update from your meal assistant"
                
            # Call process_and_reply_to_email (most params are None for first-contact emails)
            result = assistant.process_and_reply_to_email(
                message_content=message_content,
                recipient_email=recipient_email,
                user_email_token=str(user.email_token) if hasattr(user, 'email_token') else None,
                original_subject=subject,
                in_reply_to_header=None,
                email_thread_id=None
            )
            
            return result
        except CustomUser.DoesNotExist:
            logger.error(f"User with ID {user_id} not found when sending notification")
            return {"status": "error", "reason": "user_not_found"}
        except Exception as e:
            logger.error(f"Error sending notification via assistant for user {user_id}: {e}")
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"send_notification_via_assistant", "traceback": traceback.format_exc()})
            return {"status": "error", "reason": str(e)}

def generate_guest_id() -> str:
    return f"guest_{uuid.uuid4().hex[:8]}"

# ────────────────────────────────────────────────────────────────────
#  Helper: build branded Instacart CTA button
# ────────────────────────────────────────────────────────────────────
def _format_instacart_button(url: str, text: str) -> str:
    """
    Return the Instacart call‑to‑action HTML that meets the latest
    partner‑branding specifications.

    • Height: 46px (div container)
    • Dynamic width: grows with text
    • Padding: 16px vertical × 18px horizontal
    • Logo: 22px tall
    • Border: #E8E9EB solid 0.5px
    • Background: #FFFFFF
    • Text color: #000000, 16px, semi-bold
    
    Button text options:
    • "Get Recipe Ingredients" (for recipe context)
    • "Get Ingredients" (when recipes are not included)
    • "Shop with Instacart" (legal approved)
    • "Order with Instacart" (legal approved)
    """
    # Validate button text is one of the approved options
    approved_texts = [
        "Get Recipe Ingredients", 
        "Get Ingredients", 
        "Shop with Instacart", 
        "Order with Instacart"
    ]
    
    if text not in approved_texts:
        # Default to "Shop with Instacart" if not an approved text
        text = "Shop with Instacart"
    
    return (
        f'<a href="{url}" target="_blank" style="text-decoration:none;">'
        f'<div style="height:46px;display:inline-flex;align-items:center;'
        f'padding:16px 18px;background:#FFFFFF;border:0.5px solid #E8E9EB;'
        f'border-radius:8px;">'
        f'<img src="https://live.staticflickr.com/65535/54538897116_fb233f397f_m.jpg" '
        f'alt="Instacart" style="height:22px;width:auto;margin-right:10px;">'
        f'<span style="font-family:Arial,sans-serif;font-size:16px;'
        f'font-weight:500;color:#000000;white-space:nowrap;">{text}</span>'
        f'</div></a>'
    )

# ────────────────────────────────────────────────────────────────────
#  Helper: replace Instacart hyperlinks with branded CTA (BeautifulSoup)
# ────────────────────────────────────────────────────────────────────
def _replace_instacart_links(html: str, copy_type: str = "recipe") -> str:
    """
    Scan the HTML for <a> tags pointing to Instacart and replace each with
    our branded CTA button.

    Args:
        html:      Raw HTML fragment.
        copy_type: Not used anymore, always uses "Get Ingredients"

    Returns:
        Modified HTML with Instacart links swapped out.
    """
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "instacart.com" in href or "instacart.tools" in href or "instacart.tool" in href:
            # Always use "Get Ingredients" as the button text
            btn_text = "Get Ingredients"
            cta_html = _format_instacart_button(href, btn_text)
            a.replace_with(BeautifulSoup(cta_html, "html.parser"))
    
    return str(soup)
# meals/meal_assistant_implementation.py
import json, logging, uuid, traceback
import time
from typing import Dict, Any, List, Generator, Optional, Union
import numbers
from datetime import date, datetime

from django.conf import settings
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
from .tool_registration import get_all_tools, get_all_guest_tools, handle_tool_call
from customer_dashboard.models import ChatThread, UserMessage, WeeklyAnnouncement, UserDailySummary, UserChatSummary
from custom_auth.models import CustomUser
from shared.utils import generate_user_context
from utils.model_selection import choose_model
import pytz
from local_chefs.models import ChefPostalCode
from django.db.models import F
from meals.models import ChefMealEvent
from dotenv import load_dotenv
import os

load_dotenv()

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
                
                return AUTH_PROMPT_TEMPLATE.format(
                    username=username,
                    user_ctx=user_ctx,
                    admin_section=admin_section,
                    all_tools=", ".join([t['name'] for t in self.auth_tools]),
                    user_chat_summary=user_chat_summary,
                    local_chef_and_meal_events=local_chef_and_meal_events
                )
            except Exception as e:
                logger.error(f"Error generating prompt for user {self.user_id}: {str(e)}")
                # Return a simple fallback prompt
                username = user.username if user else "user"
                return f"You are MJ, sautAI's friendly meal-planning consultant. You are currently chatting with {username} and experiencing issues with your setup and functionality. You cannot help with any of the user's requests at the moment but please let them know the sautAI team has been notified and will look into it as soon as possible."

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
        if hasattr(response, "output_text"):
            return response.output_text
        text = ""
        for item in getattr(response, "output", []):
            if item.type == "message":
                for c in item.content:
                    if c.type == "output_text":
                        text += c.text
        return text

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

def generate_guest_id() -> str:
    return f"guest_{uuid.uuid4().hex[:8]}"
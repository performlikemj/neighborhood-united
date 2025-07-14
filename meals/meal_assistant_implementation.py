# meals/meal_assistant_implementation.py
import json, logging, uuid, traceback
import time
from typing import Dict, Any, List, Generator, Optional, Union, ClassVar
import numbers
from datetime import date, datetime
import re
from bs4 import BeautifulSoup   
from django.conf import settings
from django.conf.locale import LANG_INFO  # Add this import
from utils.redis_client import get, set, delete
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
from shared.utils import generate_user_context, _get_language_name
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


load_dotenv()

class PasswordPrompt(BaseModel):
    """Structured output emitted by the model whenever it wants the user to enter
    their account password."""
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    assistant_message: str = Field(
        ...,
        description="The natural-language text that will be displayed verbatim in the UI."
    )
    is_password_request: bool = Field(
        ...,
        description="Must be true when the assistant requests the user's password."
    )

    example: ClassVar[Dict[str, Any]] = {
        "assistant_message": "For security we need your account password.",
        "is_password_request": True
    }

class EmailBody(BaseModel):
    """
    Structured HTML content for email generation.

    * main_section – primary response content (HTML allowed)
    * data_visualization – OPTIONAL additional HTML (tables/charts) for structured data
    * final_message – closing paragraph guiding the user on next steps or summarising key points
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    main_section: str = Field(..., description="Primary response content in HTML")
    data_visualization: Optional[str] = Field(
        ..., description="Optional HTML block for charts/tables/lists"
    )
    final_message: str = Field(..., description="Closing message in HTML. This should be a short message that guides the user on next steps or summarises key points without being too verbose.")

# EmailResponse model removed - EmailBody now handles all email formatting

# Global dictionary to maintain guest state across request instances
GLOBAL_GUEST_STATE: Dict[str, Dict[str, Any]] = {}

# Default prompt templates in case they're not available in environment variables
DEFAULT_GUEST_PROMPT = """
<!-- =================================================================== -->
<!-- ===============  G U E S T   P R O M P T   T E M P L A T E  ======= -->
<!-- =================================================================== -->
<PromptTemplate id="guest" version="2025-06-13">
  <Identity>
    <Role>MJ, sautAI's friendly meal‑planning consultant</Role>
    <Persona origin="Jamaica" raisedIn="Brooklyn, NY"
             traits="thoughtful, considerate, confident, food‑savvy"/>
  </Identity>

  <Mission>
    <Primary>
      Provide clear, accurate answers to food, nutrition, recipe and
      meal‑planning questions.
    </Primary>
    <Secondary>
      Suggest the next sensible step toward the user's cooking or health goal.
    </Secondary>
    <Scope>
      Guests have access only to general nutrition advice; no medical guidance.
    </Scope>
  </Mission>

  <Tone style="business‑casual" warmth="warm" approach="supportive" />

  <Guidelines>
    <OutputEfficiency>
      • Write in short paragraphs (≤ 4 sentences).  
      • Use bullet‑ or numbered‑lists for steps/options.  
      • Omit tool IDs and internal implementation details.  
    </OutputEfficiency>

    <GraphAndData>
      When quantitative data will aid understanding,  
      ① present a concise table **or** dataset snippet, then  
      ② describe (in one line) the graph that would best visualise it.  
      (If the runtime supports code‑execution, emit the plot; otherwise
      describe it clearly.)
    </GraphAndData>

    <FollowUp>
      Conclude most—but not every—turn with a brief invitation such as  
      "Anything else I can help you with?"
    </FollowUp>

    <Safety>
      Politely refuse any request outside food topics.  
      No medical, legal, or non‑food advice.
    </Safety>
  </Guidelines>

  <ExampleFormat>
    <Paragraph>An answer introduction …</Paragraph>
    <Bullets>
      <Item>Key point 1</Item>
      <Item>Key point 2</Item>
      <Item>Key point 3</Item>
    </Bullets>
    <OptionalInvite>Anything else I can help you with?</OptionalInvite>
  </ExampleFormat>
</PromptTemplate>
"""

DEFAULT_AUTH_PROMPT = """
<!-- ==================  S A U T A I   A S S I S T A N T   ================== -->
<!--  Runs on: gpt-4o (primary) | gpt-o4-mini (fallback)                     -->
<!--  Version: 2025-07-03                                                   -->
<PromptTemplate id="authenticated" version="2025-07-03">

  <!-- ───── 1. IDENTITY ───── -->
  <Identity>
    <Role>MJ — sautAI's friendly meal-planning consultant</Role>
    <Persona origin="Jamaica"
             raisedIn="Brooklyn, NY"
             traits="thoughtful, considerate, confident, food-savvy"/>
    <User name="{username}" />
  </Identity>

  <!-- ───── 2. CONTEXT ───── -->
  <Context>
    <RecentConversation>{user_chat_summary}</RecentConversation>
    <Personalization>{user_ctx}</Personalization>
    <AdminNotice revealOnce="true">{admin_section}</AdminNotice>
  </Context>

  <!-- ───── 3. MISSION ───── -->
  <Mission>
    <Primary>
      • Answer food, nutrition, recipe, and meal-planning questions.  
      • Suggest actionable next steps and proactive follow-ups.  
    </Primary>
    <ConnectWithChefs>
      Match users with **local chefs** so they save time and eat better.
    </ConnectWithChefs>
  </Mission>

  <!-- ───── 4. CAPABILITIES (TOOLS) ───── -->
  <Capabilities>{all_tools}</Capabilities>

  <!-- ───── 5. OPERATING INSTRUCTIONS ───── -->
  <OperatingInstructions>

    <!-- 5-A. TOOL USAGE RULES -->
    <Tools>
      <Rule>Invoke tools whenever they materially improve the answer.</Rule>
      <Bundling>Batch related tool calls in one turn when feasible.</Bundling>

      <!-- Meal-plan management -->
      <MealPlans>
        • Use <code>list_user_meal_plans</code> before guessing.  
        • Remind users to approve pending plans before creating new ones.  
        • Respect week context via <code>get_current_date</code>,
          <code>adjust_week_shift</code>, <code>reset_current_week</code>.  
        • Create plans with <code>create_meal_plan</code> then swap meals
          via <code>replace_meal_plan_meal</code> when mixing AI & chef meals.  
      </MealPlans>

      <!-- Macro-nutrients & media -->
      <MealPlanPrepping>
        • After generating or editing a meal, call
          <code>update_meal_macros</code> (your macro tool) so totals are accurate.  
        • Offer to add a YouTube tutorial link **on request** (use
          <code>attach_youtube_tutorial</code> if available).  
      </MealPlanPrepping>

      <!-- Pantry & shopping -->
      <PantryManagement>
        • Once per week suggest a pantry audit, highlighting environmental,
          financial, and health benefits of minimizing waste.  
      </PantryManagement>
      <Instacart>
        • Provide <code>instacart_shopping_list</code> links; note US/Canada
          availability if user locale ≠ US/CA.  
      </Instacart>

      <!-- Payments -->
      <PaymentLinks>
        • Stripe links must be full, valid URLs.  
      </PaymentLinks>
    </Tools>

    <!-- 5-B. OUTPUT & STYLE -->
    <Format>
      <Paragraph maxSentences="3-4"/>
      <Lists>Use bulleted or numbered lists where logical.</Lists>
      <Data>
        When numbers matter, return **both**  
        ① a concise table and  
        ② either an in-context graph (if runtime supports) **or** a one-line
           description of the ideal visual.  
        Use light formats (small PNG, SVG, or summarized JSON).  
      </Data>
      <FollowUp>
        End most replies with a brief invitation or a creative suggestion
        (e.g., pantry audit, local chef collab).  
      </FollowUp>
    </Format>

    <!-- 5-C. SAFETY & SCOPE -->
    <Safety>
      Provide general nutrition guidance only — no medical advice.  
      Politely decline off-topic or unsafe requests.  
    </Safety>

    <!-- 5-D. TOKEN BUDGET GUIDANCE -->
    <TokenBudget>
      • Target ≤ 600 tokens/completion for gpt-o4-mini compatibility.  
      • Omit unnecessary repetition; prioritize tool calls over long prose.  
    </TokenBudget>

  </OperatingInstructions>
</PromptTemplate>
"""

# Get template from environment, fallback to defaults if not available
GUEST_PROMPT_TEMPLATE = DEFAULT_GUEST_PROMPT
AUTH_PROMPT_TEMPLATE = DEFAULT_AUTH_PROMPT

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
            else:
                # Only generate a new one if None or empty string provided
                self.user_id = generate_guest_id()
        else:
            self.user_id = generate_guest_id()
            
        # Don't cache tools - load them fresh each time to pick up changes
        # self.auth_tools and self.guest_tools are loaded in _get_tools_for_user()
        
        self.system_message = (
            "You are sautAI's helpful meal‑planning assistant. "
            "Answer questions about food, nutrition and meal plans."
        )
        
        # Log initialization details
        is_guest = self._is_guest(self.user_id)

    def _get_tools_for_user(self, is_guest: bool) -> List[Dict[str, Any]]:
        """Load tools fresh each time to pick up any code changes."""
        if is_guest:
            tools = get_all_guest_tools()
        else:
            tools = [t for t in get_all_tools() if not t["name"].startswith("guest")]
        

        
        return tools

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
            else:
                # Initialize new history
                history = [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message},
                ]
            
            prev_resp_id = guest_data.get("response_id")
            chat_thread = None
        else:
            # For auth users, load history from DB
            chat_thread = self._get_or_create_thread(self.user_id)
            history = chat_thread.openai_input_history or []
            if not history:
                 history.append({"role": "system", "content": self.system_message})
            history.append({"role": "user", "content": message})
            # Truncate history to prevent context length exceeded errors
            history = self._truncate_history_if_needed(history, max_messages=30, max_tokens=25000)
            prev_resp_id = None # Send full history


        try:
            resp = self.client.responses.create(
                model=model,
                input=history,
                instructions=self._instructions(is_guest),
                tools=self._get_tools_for_user(is_guest),
                parallel_tool_calls=True,
                # We send full history for auth, maybe not needed for guest either?
                # Consider setting previous_response_id=None always if full history works
                previous_response_id=prev_resp_id, 
            )
            
            final_response_id = resp.id
            # Log the raw response object from OpenAI to understand its structure
            
            # Check for tool calls in response
            tool_calls_in_response = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
            
            # If the response involved tool calls, OpenAI might implicitly add them to resp.input
            # Or we might need to reconstruct history if tools were called (less common in non-streaming)
            # For simplicity, let's assume resp.input contains the final state or reconstruct minimally.
            
            final_output_text = self._extract(resp) # Extract text before modifying history

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

            return {
                "status": "success",
                "message": final_output_text,
                "response_id": final_response_id,
            }
        except Exception as e:
             logger.error(f"Error in send_message for user {self.user_id}: {str(e)}")
             # n8n traceback
             n8n_traceback = {
                 'error': str(e),
                 'source': 'send_message',
                 'traceback': f"Guest ID: {self.user_id} | {traceback.format_exc()}"
             }
             requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
            else:
                # Initialize new history
                history = [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message},
                ]
            
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
            # Truncate history to prevent context length exceeded errors
            history = self._truncate_history_if_needed(history, max_messages=30, max_tokens=25000)
            prev_resp_id = None # We send full history, so no previous_response_id needed
            user_msg = (
                 self._save_user_message(self.user_id, message, chat_thread) if chat_thread else None
            )
        
        
        yield from self._process_stream(
            model=model,
            history=history, # Send the loaded/updated history
            instructions=self._instructions(is_guest),
            tools=self._get_tools_for_user(is_guest),
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
        
        
        # If previous_response_id is None and this is a guest, try to fetch from cache
        if previous_response_id is None and is_guest:
            prev_resp_id = get(f"last_resp:{self.user_id}")
            if prev_resp_id:
                previous_response_id = prev_resp_id
        
        start_ts = time.time()
        current_history = history[:] # Work on a copy
        final_response_id = None # Track the final OpenAI response ID
        loop_iteration = 0
        max_iterations = 10  # Prevent infinite loops

        while True:
            loop_iteration += 1
            
            # Safety check to prevent infinite loops
            if loop_iteration > max_iterations:
                yield {"type": "response.completed"}
                break
            
            # 1) Start streaming from the Responses API
            # for i, item in enumerate(current_history):
            #     item_type = item.get('type') or item.get('role', 'unknown')
            
            
            # Truncate history before each API call to prevent context length issues
            current_history = self._truncate_history_if_needed(current_history, max_messages=30, max_tokens=25000)
            # Validate and clean history before sending to OpenAI
            current_history = self._validate_and_clean_history(current_history)
            
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
            response_completed = False

            # 2) Consume the event stream
            for ev in stream:
                # 2a) Capture the new response ID
                if isinstance(ev, ResponseCreatedEvent):
                    new_id = ev.response.id
                    latest_id_in_stream = new_id # Always update with the latest ID
                    final_response_id = new_id # Track the latest ID received
                    yield {"type": "response_id", "id": new_id}
                    continue

                # 2b) End of this assistant turn
                if isinstance(ev, ResponseCompletedEvent):
                    response_completed = True
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
                    
                    
                    # Fix the user_id in the arguments if needed
                    fixed_args_json = self._fix_function_args(entry["name"], args_json)
                    if fixed_args_json != args_json:
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
                set(f"last_resp:{self.user_id}", final_response_id, 86400)

            # 4) If response was completed and we have text content, break the loop
            # This is the key fix - if response completed and we have text, we're done
            if response_completed and buf:
                yield {"type": "response.completed"}
                break
            
            # 4.1) If no function calls were requested, finish up
            
            if not calls:
                yield {"type": "response.completed"}
                break # Exit the while loop
            
            # 4.2) If response was completed but there are function calls, we need to handle them first
            # If response was completed and no function calls, we should have already broken above
            if response_completed and not calls:
                yield {"type": "response.completed"}
                break

            # 5) Drop any stray wrapper‑only entries
            calls = [c for c in calls if not c["id"].startswith("fc_")]
            
            # 5.1) If response was completed and we have no function calls after filtering, break
            if response_completed and not calls:
                yield {"type": "response.completed"}
                break

            # 6) Execute all parallel calls
            for call in calls:
                call_id = call["id"]
                
                
                args_obj = json.loads(call["args"] or "{}")
                
                # Fix the user_id in the arguments if needed
                fixed_args_json = self._fix_function_args(call["name"], call["args"] or "{}")
                if fixed_args_json != (call["args"] or "{}"):
                    args_obj = json.loads(fixed_args_json)
                
                try:
                    
                    # Time the tool execution
                    tool_start_time = time.time()
                    result = handle_tool_call(
                        type("Call", (), {
                            "call_id": call_id,
                            "function": type("F", (), {
                                "name":      call["name"],
                                "arguments": json.dumps(args_obj)
                            })
                        })
                    )
                    tool_execution_time = time.time() - tool_start_time
                    
                        
                except Exception as e:
                    #n8n traceback
                    n8n_traceback = {
                        'error': str(e),
                        'source': 'tool_call',
                        'traceback': traceback.format_exc()
                    }
                    requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
            # IMPORTANT: We continue the loop, sending the *updated* current_history

        # --- End of while loop ---
        
        processing_time = time.time() - start_ts
        
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
        all_tools = self._get_tools_for_user(is_guest)
        if is_guest:
            guest_tools = self._get_tools_for_user(is_guest)
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
                
                # Get user's preferred language for instructions
                user_preferred_language = _get_language_name(getattr(user, 'preferred_language', 'en'))
                language_instruction = ""
                if user_preferred_language and user_preferred_language.lower() != 'en':
                    language_name = _get_language_name(user_preferred_language)
                    language_instruction = f"\n#LANGUAGE PREFERENCE\nThis user's preferred language is {language_name}. Please respond in {language_name} unless the user specifically requests English or another language.\n\n"
                
                # Ensure AUTH_PROMPT_TEMPLATE has placeholders for all these values
                # Example: {username}, {user_ctx}, {admin_section}, {all_tools}, {user_chat_summary}, {local_chef_and_meal_events}
                prompt = AUTH_PROMPT_TEMPLATE.format(
                    username=username,
                    user_ctx=user_ctx,
                    admin_section=admin_section,
                    all_tools=", ".join([t['name'] for t in self._get_tools_for_user(is_guest)]),
                    user_chat_summary=user_chat_summary,
                    local_chef_and_meal_events=local_chef_and_meal_events
                )
                
                # Add language instruction if needed
                return prompt + language_instruction
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
            args = json.loads(args_str)
            
            # If the function has a user_id parameter and it's not the current user
            if "user_id" in args:
                if args["user_id"] != self.user_id:
                    args["user_id"] = self.user_id
                    return json.dumps(args)
            
            # Special case for chef-meal related functions
            chef_meal_funcs = ['replace_meal_plan_meal', 'place_chef_meal_event_order', 'generate_payment_link']
            if function_name in chef_meal_funcs:
                logger.info(f"DEBUG: Special processing for chef meal function: {function_name}")
                logger.info(f"DEBUG: Args before: {args}")
                
                # Add logging for specific functions
                if function_name == 'replace_meal_plan_meal':
                    logger.info(f"DEBUG: replace_meal_plan_meal args:")
                    logger.info(f"  user_id: {args.get('user_id')}")
                    logger.info(f"  meal_plan_meal_id: {args.get('meal_plan_meal_id')}")
                    logger.info(f"  chef_meal_id: {args.get('chef_meal_id')}")
                    logger.info(f"  event_id: {args.get('event_id')}")
                    
                elif function_name == 'generate_payment_link':
                    logger.info(f"DEBUG: generate_payment_link args:")
                    logger.info(f"  user_id: {args.get('user_id')}")
                    logger.info(f"  order_id: {args.get('order_id')}")
                    
                elif function_name == 'place_chef_meal_event_order':
                    logger.info(f"DEBUG: place_chef_meal_event_order args:")
                    logger.info(f"  user_id: {args.get('user_id')}")
                    logger.info(f"  meal_event_id: {args.get('meal_event_id')}")
                    logger.info(f"  quantity: {args.get('quantity')}")
                    logger.info(f"  special_instructions: {args.get('special_instructions')}")
            
            return args_str
        except Exception as e:
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'fix_function_args',
                'traceback': f"Guest ID: {self.user_id} | {traceback.format_exc()}"
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
        cached = get(cache_key)
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
        set(cache_key, combined_blurb, 60 * 60)
        return combined_blurb or None

    def _validate_and_clean_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and clean history to ensure all function call outputs have matching function calls.
        This prevents the OpenAI API error about missing tool calls for function call outputs.
        """
        # Track function calls and their outputs
        function_calls = {}  # call_id -> function_call_item
        function_outputs = {}  # call_id -> function_output_item
        other_items = []  # Non-function items
        
        # Separate function calls, outputs, and other items
        for item in history:
            if item.get('type') == 'function_call' and 'call_id' in item:
                function_calls[item['call_id']] = item
            elif item.get('type') == 'function_call_output' and 'call_id' in item:
                function_outputs[item['call_id']] = item
            else:
                other_items.append(item)
        
        # Build clean history: only include function calls that have matching outputs
        clean_history = []
        for item in history:
            if item.get('type') == 'function_call' and 'call_id' in item:
                call_id = item['call_id']
                # Only add if there's a matching output
                if call_id in function_outputs:
                    clean_history.append(item)
                else:
                    logger.warning(f"Removing orphaned function call with call_id {call_id}")
            elif item.get('type') == 'function_call_output' and 'call_id' in item:
                call_id = item['call_id']
                # Only add if there's a matching call
                if call_id in function_calls:
                    clean_history.append(item)
                else:
                    logger.warning(f"Removing orphaned function output with call_id {call_id}")
            else:
                # Keep all non-function items
                clean_history.append(item)
        
        return clean_history

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
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"stream_user_summary", "traceback": traceback.format_exc()})
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
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"_local_chef_and_meal_events", "traceback": traceback.format_exc()})
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
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"_get_user_chat_summary", "traceback": traceback.format_exc()})
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

        # ── Minimal text cleanup - preserve Unicode characters ──────────────────
        import re
        
        # Only clean up excess whitespace
        raw_text = re.sub(r'\s+', ' ', raw_text).strip()

        # ────────────────── URL PROTECTION WITH PLACEHOLDERS ──────────────────
        # Extract URLs and replace with placeholders to prevent LLM corruption
        url_pattern = r'https?://[^\s<>"\'()]+[^\s<>"\'.!?;,)]'
        urls = re.findall(url_pattern, raw_text)
        url_placeholders = {}
        
        # Replace URLs with placeholders
        protected_text = raw_text
        for i, url in enumerate(urls):
            placeholder = f"__URL_PLACEHOLDER_{i}__"
            url_placeholders[placeholder] = url
            protected_text = protected_text.replace(url, placeholder)
        

        # ----------------------- build LLM prompt -------------------------
        prompt_content = f"""
        You are an **EmailBody HTML formatter**.

        --- TASK ---
        Convert the RAW TEXT below into **valid HTML strings** and return them
        inside a **single JSON object** that EXACTLY matches the `EmailBody`
        schema:

        {{
        "main_section": "HTML-string",
        "data_visualization": "HTML-string or empty string",
        "final_message": "HTML-string"
        }}

        • **No extra keys.**  
        • **Do not wrap** the JSON in code-fences or Markdown.  
        • If no chart/table is needed, set `"data_visualization": ""`.

        --- HTML RULES ---
        1. Use only: `<p>`, `<h3>`, `<ul>/<li>`, `<ol>/<li>`, `<table>` (plus
        `<thead>/<tbody>/<tr>/<th>/<td>` as needed).  
        2. Lists → `<ul>` or `<ol>` with nested `<li>`.  
        3. Headings → promote clear section titles (e.g., "Shopping List") to `<h3>`.  
        4. **No structural `<div>` or `<span>` wrappers.**  
        5. Preserve **all** numbers, units, and Unicode exactly
        (e.g., `200°C`, `2 ½ cups`).  
        6. Links must include `target="_blank" rel="noopener noreferrer"`.  
        7. Return only body content — omit `<html>`, `<head>`, `<body>`.  
        8. **Absolutely no follow-up questions, commentary, or feedback requests.**
        9. **IMPORTANT: Preserve all __URL_PLACEHOLDER_X__ tokens exactly as they appear.**

        --- BEGIN RAW TEXT ---
        {protected_text}
        --- END RAW TEXT ---
        """

        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",  
                input=[
                    {"role": "developer", "content": "You are a precise HTML email formatter. Return ONLY HTML content without follow-up questions. PRESERVE ALL text exactly as written - do not modify numbers, measurements, Unicode characters like °, ½, ¼, etc., or any __URL_PLACEHOLDER_X__ tokens."},
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
                if response.output_text.strip().startswith("{"):
                    email_body = EmailBody.model_validate_json(response.output_text)
                    formatted_text = "".join(
                        part for part in [
                            email_body.main_section,
                            email_body.data_visualization or "",
                            email_body.final_message
                        ] if part
                    )
                else:
                    # Try to extract just the HTML content if it's not in expected format
                    formatted_text = response.output_text.strip()
                    logger.warning(f"Email body not in expected JSON format, using raw output")
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"_format_text_for_email_body", "traceback": traceback.format_exc()})
                formatted_text = response.output_text.strip()
            
            # ────────────────── RESTORE ORIGINAL URLS ──────────────────
            # Replace placeholders back with original URLs
            for placeholder, original_url in url_placeholders.items():
                formatted_text = formatted_text.replace(placeholder, original_url)
            
            
            # ------------------- MINIMAL FINAL CLEAN-UP --------------------
            import re
            
            # Clean up excess whitespace only
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
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"_format_text_for_email_body", "traceback": traceback.format_exc()})
                # Continue with the original text if there's an error

            return formatted_text.strip()
            
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"_format_text_for_email_body", "traceback": traceback.format_exc()})
            
            # Fallback: Restore URLs in the original text and provide simple HTML
            fallback_text = raw_text
            for placeholder, original_url in url_placeholders.items():
                fallback_text = fallback_text.replace(placeholder, original_url)
            
            paragraphs = fallback_text.split('\n\n')
            html_paragraphs = [f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip()]
            return ''.join(html_paragraphs) if html_paragraphs else f"<p>{fallback_text.replace(chr(10), '<br>')}</p>"

    # ────────────────────────────────────────────────────────────────────
    #  Email Processing Method
    # ────────────────────────────────────────────────────────────────────
    def generate_email_response(self, message_content: str) -> Dict[str, Any]:
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
            logger.error(f"generate_email_response called for a guest user ID: {self.user_id}. This is not supported.")
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
        
        # Truncate history if it's getting too long to prevent context length exceeded errors
        current_history = self._truncate_history_if_needed(current_history, max_messages=30, max_tokens=25000)
            
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
                

                
                # Validate and clean history before sending to OpenAI
                current_history = self._validate_and_clean_history(current_history)
                
                # Debug: Log history structure before API call
                if logger.isEnabledFor(logging.DEBUG):
                    call_ids = set()
                    output_ids = set()
                    for item in current_history:
                        if item.get('type') == 'function_call' and 'call_id' in item:
                            call_ids.add(item['call_id'])
                        elif item.get('type') == 'function_call_output' and 'call_id' in item:
                            output_ids.add(item['call_id'])
                
                # OpenAI API Call - Standard call for all iterations
                try:
                    resp = self.client.responses.create(
                        model=model,
                        input=current_history,
                        instructions=self._instructions(is_guest=False),
                        tools=self._get_tools_for_user(False),
                        parallel_tool_calls=True,
                        previous_response_id=prev_resp_id_for_api,
                    )
                except Exception as api_error:
                    # Handle context length exceeded errors specifically
                    if "context_length_exceeded" in str(api_error).lower() or "context window" in str(api_error).lower():
                        logger.warning(f"Context length exceeded for user {self.user_id}. Attempting with more aggressive truncation.")
                        # More aggressive truncation and retry
                        current_history = self._truncate_history_if_needed(current_history, max_messages=20, max_tokens=16000)
                        # Validate and clean history after truncation
                        current_history = self._validate_and_clean_history(current_history)
                        try:
                            resp = self.client.responses.create(
                                model=model,
                                input=current_history,
                                instructions=self._instructions(is_guest=False),
                                tools=self._get_tools_for_user(False),
                                parallel_tool_calls=True,
                                previous_response_id=None,  # Don't use previous response ID on retry
                            )
                        except Exception as retry_error:
                            # n8n traceback
                            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                            requests.post(n8n_traceback_url, json={"error": str(retry_error), "source":"generate_email_response", "traceback": traceback.format_exc()})
                            raise retry_error
                    else:
                        # Re-raise if it's not a context length error
                        raise api_error
                
                final_response_id = resp.id
                prev_resp_id_for_api = final_response_id
                
                # Extract Tool Calls
                tool_calls_in_response = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
                
                # Condition: No Tool Calls in Response (End of Turn)
                if not tool_calls_in_response:
                    # Extract the response text directly
                    try:
                        final_output_text = self._extract(resp)
                    except Exception as extract_error:
                        logger.error(f"generate_email_response: Error extracting text: {extract_error}")
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
                        requests.post(n8n_traceback_url, json={"error": str(extract_error), "source":"generate_email_response", "traceback": traceback.format_exc()})
                        final_output_text = "I'm sorry, but I encountered an issue processing your message. Please try again or contact support."
                    
                    if final_output_text:
                        current_history.append({"role": "assistant", "content": final_output_text})
                    logger.info(f"generate_email_response: No tool calls. Extracted text: '{final_output_text[:100]}...' for user {self.user_id}")
                    break
                    
                # Condition: Tool Calls Present
                logger.info(f"generate_email_response: Found {len(tool_calls_in_response)} tool call(s) for user {self.user_id}.")
                
                for tool_call_item in tool_calls_in_response:
                    # Append function_call to history
                    call_entry = {
                        "type": "function_call",
                        "name": tool_call_item.name,
                        "arguments": tool_call_item.arguments,
                        "call_id": tool_call_item.call_id
                    }
                    current_history.append(call_entry)
                    
                    # Execute Tool
                    args_json_str = tool_call_item.arguments
                    fixed_args_json_str = self._fix_function_args(tool_call_item.name, args_json_str)
                    
                    tool_result_data = None
                    try:
                        logger.info(f"generate_email_response: Executing tool {tool_call_item.name} with args: {fixed_args_json_str} for user {self.user_id}")
                        
                        # Time the tool execution
                        email_tool_start_time = time.time()
                        mock_call_object = type("Call", (), {
                            "call_id": tool_call_item.call_id,
                            "function": type("F", (), {
                                "name": tool_call_item.name,
                                "arguments": fixed_args_json_str
                            })
                        })
                        tool_result_data = handle_tool_call(mock_call_object)
                        email_tool_execution_time = time.time() - email_tool_start_time
                        
                        logger.info(f"generate_email_response: Tool {tool_call_item.name} result: {str(tool_result_data)[:200]}... for user {self.user_id}")
                            
                    except Exception as e_tool:
                        logger.error(f"generate_email_response: Error executing tool {tool_call_item.name} for user {self.user_id}: {e_tool}", exc_info=True)
                        #n8n traceback
                        n8n_traceback = {
                            'error': str(e_tool),
                            'source': 'tool_call',
                            'traceback': traceback.format_exc()
                        }
                        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                        tool_result_data = {"status": "error", "message": f"Error executing tool {tool_call_item.name}: {str(e_tool)}"}
                        
                    # Append function_call_output to history
                    output_entry = {
                        "type": "function_call_output",
                        "call_id": tool_call_item.call_id,
                        "output": json.dumps(tool_result_data)
                    }
                    current_history.append(output_entry)
                
                # Max Iterations Check
                if iterations >= max_tool_iterations and tool_calls_in_response:
                    logger.warning(f"generate_email_response: Reached max tool iterations ({max_tool_iterations}) for user {self.user_id}. API may still want to call tools.")
                    final_output_text = "I'm encountering some complexity with your request. Could you please try again, perhaps simplifying it, or use the web interface for a more detailed interaction?"
                    current_history.append({"role": "assistant", "content": final_output_text})
                    break
            
            # 3.3. Post-Loop Processing & Persistence
            logger.info(f"generate_email_response: Loop finished for user {self.user_id}. Final text: '{final_output_text[:100]}...'")
            
            # No text cleanup needed - allow natural assistant responses
            
            # Persist State
            if final_response_id:
                self._persist_state(self.user_id, final_response_id, is_guest=False, history=current_history)
                if chat_thread and message_content and final_output_text:
                    self._save_turn(self.user_id, message_content, final_output_text, chat_thread)
            else:
                logger.warning(f"generate_email_response: No final_response_id was captured for user {self.user_id}. State may not be fully persisted.")
                
            # Return Success
            return {"status": "success", "message": final_output_text, "response_id": final_response_id}
            
        # 3.4. Outer Error Handling
        except Exception as e_outer:
            logger.error(f"generate_email_response: Unhandled error for user {self.user_id}: {e_outer}", exc_info=True)
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e_outer), "source":"generate_email_response", "traceback": traceback.format_exc()})
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
        
        # 1. Get the assistant's response using generate_email_response logic
        # This handles history, model selection, tool calls, iterations, and persistence.
        assistant_response_data = self.generate_email_response(message_content=message_content)
        if assistant_response_data.get("status") == "error":
            logger.error(f"MealPlanningAssistant: Error getting response from generate_email_response for user {self.user_id}: {assistant_response_data.get('message')}")
            # Still attempt to send a generic error reply via email
            raw_reply_content = "I encountered an issue processing your request. Please try again later or contact support if the problem persists."
            new_openai_response_id = None
        else:
            raw_reply_content = assistant_response_data.get('message', 'Could not process your request at this time. Please try again later via the web interface.')
            new_openai_response_id = assistant_response_data.get('response_id', None)
            logger.info(f"MealPlanningAssistant: Received response for user {self.user_id}. OpenAI response ID: {new_openai_response_id}")

        # 2. Format the raw reply content for email body
        formatted_email_body = self._format_text_for_email_body(raw_reply_content)

        # 3. Render the full email using the new template
        try:
            user = CustomUser.objects.get(id=self.user_id) # Fetch user for their name
            user_name = user.get_full_name() or user.username
            
            # Check if the user has unsubscribed from emails
            if getattr(user, 'unsubscribed_from_emails', False):
                logger.info(f"MealPlanningAssistant: User {self.user_id} has unsubscribed from emails. Skipping email reply.")
                return {"status": "skipped", "message": "User has unsubscribed from emails."}
                
            # Get user's preferred language for translation
            user_preferred_language = _get_language_name(getattr(user, 'preferred_language', 'en'))
        except CustomUser.DoesNotExist:
            user_name = "there" # Fallback name
            user_preferred_language = 'en'  # Default to English if user not found
            logger.warning(f"User {self.user_id} not found when preparing email, using fallback name.")
        
        site_domain = os.getenv('STREAMLIT_URL')
        profile_url = f"{site_domain}/" # Adjust if your profile URL is different

        email_html_content = render_to_string(
            'customer_dashboard/assistant_email_template.html',
            {
                'user_name': user_name,
                'email_body_main': formatted_email_body,
                'email_body_data': '',  # Empty for now, can be used for structured data
                'email_body_final': '',  # Empty for now, can be used for closing messages
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
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": "User with ID {user_id} not found when sending notification", "source":"send_notification_via_assistant", "traceback": traceback.format_exc()})
            return {"status": "error", "reason": "user_not_found"}
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"send_notification_via_assistant", "traceback": traceback.format_exc()})
            return {"status": "error", "reason": str(e)}

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of tokens for a given text.
        Approximates ~4 characters per token for English text.
        """
        return len(text) // 4
    
    def _truncate_history_if_needed(self, history: List[Dict[str, Any]], max_messages: int = 50, max_tokens: int = 32000) -> List[Dict[str, Any]]:
        """
        Truncate conversation history if it's too long, keeping the system message 
        and the most recent messages. Uses both message count and token estimation.
        Special handling for function calls to maintain call/output pairs.
        
        Args:
            history: The conversation history list
            max_messages: Maximum number of messages to keep (default 50)
            max_tokens: Maximum estimated tokens to keep (default 32000 for most models)
            
        Returns:
            Truncated history list
        """
        if len(history) <= max_messages:
            # Still check token count even if message count is OK
            total_tokens = sum(self._estimate_tokens(str(msg.get("content", ""))) for msg in history)
            if total_tokens <= max_tokens:
                return history
        
        # Group messages to preserve function call pairs
        grouped_items = []
        i = 0
        while i < len(history):
            msg = history[i]
            if msg.get("type") == "function_call" and "call_id" in msg:
                # Look for the matching output
                call_id = msg["call_id"]
                output_found = False
                for j in range(i + 1, len(history)):
                    if (history[j].get("type") == "function_call_output" and 
                        history[j].get("call_id") == call_id):
                        # Group the call and output together
                        grouped_items.append([msg, history[j]])
                        output_found = True
                        # Skip both items in the main loop
                        if j == i + 1:
                            i += 2  # They're consecutive
                        else:
                            # Mark the output as processed
                            history[j] = {"_processed": True}
                            i += 1
                        break
                if not output_found:
                    # Orphaned function call, treat as single item
                    grouped_items.append([msg])
                    i += 1
            elif msg.get("type") == "function_call_output" and not msg.get("_processed"):
                # Orphaned output, treat as single item  
                grouped_items.append([msg])
                i += 1
            elif not msg.get("_processed"):
                # Regular message
                grouped_items.append([msg])
                i += 1
            else:
                i += 1
        
        # Always keep the system message groups (first few items)
        system_groups = []
        non_system_groups = []
        
        for group in grouped_items:
            if any(msg.get("role") == "system" for msg in group):
                system_groups.append(group)
            else:
                non_system_groups.append(group)
        
        # Calculate tokens for system groups
        system_tokens = 0
        for group in system_groups:
            for msg in group:
                system_tokens += self._estimate_tokens(str(msg.get("content", "") or msg.get("output", "") or str(msg)))
        
        # Keep the most recent groups within token and count limits
        available_tokens = max_tokens - system_tokens
        recent_groups = []
        current_tokens = 0
        total_messages = sum(len(group) for group in system_groups)
        
        # Add groups from most recent, checking token count and message count
        for group in reversed(non_system_groups):
            group_tokens = 0
            for msg in group:
                group_tokens += self._estimate_tokens(str(msg.get("content", "") or msg.get("output", "") or str(msg)))
            
            group_message_count = len(group)
            
            if (total_messages + len(recent_groups) * 2 + group_message_count <= max_messages and 
                current_tokens + group_tokens <= available_tokens):
                recent_groups.insert(0, group)  # Insert at beginning to maintain order
                current_tokens += group_tokens
                total_messages += group_message_count
            else:
                break
        
        # Flatten the groups back to a single list
        truncated_history = []
        for group in system_groups + recent_groups:
            truncated_history.extend(group)
        
        if len(history) > len(truncated_history):
            logger.warning(f"Truncated conversation history from {len(history)} to {len(truncated_history)} messages to fit context window (estimated {current_tokens + system_tokens} tokens)")
        
        return truncated_history

def generate_guest_id() -> str:
    return f"guest_{uuid.uuid4().hex[:8]}"


class OnboardingAssistant:
    """Independent assistant dedicated to chat-based user registration with PasswordPrompt support."""

    def __init__(self, user_id: Optional[Union[int, str]] = None):
        self.client = OpenAI(api_key=settings.OPENAI_KEY)
        
        # Handle user ID assignment for guests
        if user_id is not None:
            if isinstance(user_id, numbers.Number) or (isinstance(user_id, str) and user_id.isdigit()):
                self.user_id = int(user_id)
            elif isinstance(user_id, str) and user_id:
                # Keep provided string user_id (guest_id from session or request)
                self.user_id = user_id.replace("guest:", "") if user_id.startswith("guest:") else user_id
            else:
                self.user_id = generate_guest_id()
        else:
            self.user_id = generate_guest_id()
            
        self.system_message = (
            "You are MJ, sautAI's friendly onboarding assistant. "
            "Help users create their account through a simple conversation.\n\n"

            "### PROCESS\n"
            "1. Ask for username\n"
            "2. Ask for email\n"
            "3. Ask for preferred language (e.g., English, Spanish, French, Japanese, etc)\n"
            "4. Ask for dietary preferences (e.g., Vegan, Vegetarian, Gluten-Free, Keto, etc.)\n"
            "5. Ask for allergies (e.g., Peanuts, Tree nuts, Milk, Egg, Wheat, etc.)\n"
            "6. Optionally ask for household members (name, age, dietary preferences)\n"
            "7. When you have username AND email AND language AND dietary preferences AND allergies, call `onboarding_request_password`\n"
            "8. Then ask for password\n\n"

            "### TOOLS\n"
            "• `onboarding_save_progress` – call with individual params (username, email, preferred_language, dietary_preferences, custom_dietary_preferences, allergies, custom_allergies, household_members)\n"
            "• `onboarding_request_password` – call ONLY when you have username AND email AND language AND dietary preferences AND allergies\n\n"

            "### RULES\n"
            "• Be friendly and brief\n"
            "• Save progress after collecting data\n"
            "• Ages should be numbers only (e.g., 3 not \"3 years\")\n"
            "• For dietary preferences, use standard names like 'Vegan', 'Vegetarian', 'Gluten-Free', 'Keto', 'Paleo', 'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium', 'High-Protein', 'Dairy-Free', 'Nut-Free', 'Raw Food', 'Whole 30', 'Low-FODMAP', 'Diabetic-Friendly', 'Everything'\n"
            "• For allergies, use standard names like 'Peanuts', 'Tree nuts', 'Milk', 'Egg', 'Wheat', 'Soy', 'Fish', 'Shellfish', 'Sesame', 'None'\n"
            "• If user mentions dietary preferences or allergies not in standard list, use custom_dietary_preferences or custom_allergies arrays\n"
            "• Password will be entered securely in a modal\n"
        )


    def _get_onboarding_tools(self) -> List[Dict[str, Any]]:
        """Get tools specific to onboarding."""
        from .guest_tools import get_guest_tools
        return [t for t in get_guest_tools() if t.get("name") in {"guest_register_user", "onboarding_save_progress", "onboarding_request_password"}]

    def _build_onboarding_prompt(self) -> str:
        """
        Build the system prompt for chat‑based onboarding.
        Collects username, email, language, dietary preferences, allergies, then household data, then triggers secure‑password modal.
        """

        base_prompt = (
            "You are MJ, sautAI's friendly onboarding assistant. "
            "Help users create their account through a simple conversation.\n\n"

            "### PROCESS\n"
            "1. Ask for username\n"
            "2. Ask for email\n"
            "3. Ask for preferred language (e.g., English, Spanish, French)\n"
            "4. Ask for dietary preferences (e.g., Vegan, Vegetarian, Gluten-Free, Keto, etc.)\n"
            "5. Ask for allergies (e.g., Peanuts, Tree nuts, Milk, Egg, Wheat, etc.)\n"
            "6. Optionally ask for household members (name, age, dietary preferences)\n"
            "7. When you have username AND email AND language AND dietary preferences AND allergies, call `onboarding_request_password`\n"
            "8. Then ask for password\n\n"

            "### TOOLS\n"
            "• `onboarding_save_progress` – call with individual params (username, email, preferred_language, dietary_preferences, custom_dietary_preferences, allergies, custom_allergies, household_members)\n"
            "• `onboarding_request_password` – call ONLY when you have username AND email AND language AND dietary preferences AND allergies\n\n"

            "### RULES\n"
            "• Be friendly and brief\n"
            "• Save progress after collecting data\n"
            "• Ages should be numbers only (e.g., 3 not \"3 years\")\n"
            "• For dietary preferences, use standard names like 'Vegan', 'Vegetarian', 'Gluten-Free', 'Keto', 'Paleo', 'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium', 'High-Protein', 'Dairy-Free', 'Nut-Free', 'Raw Food', 'Whole 30', 'Low-FODMAP', 'Diabetic-Friendly', 'Everything'\n"
            "• For allergies, use standard names like 'Peanuts', 'Tree nuts', 'Milk', 'Egg', 'Wheat', 'Soy', 'Fish', 'Shellfish', 'Sesame', 'None'\n"
            "• If user mentions dietary preferences or allergies not in standard list, use custom_dietary_preferences or custom_allergies arrays\n"
            "• Password will be entered securely in a modal\n"
        )

        # ── append current saved progress ───────────────────────────────────────────
        try:
            from custom_auth.models import OnboardingSession
            session = OnboardingSession.objects.filter(guest_id=str(self.user_id)).first()
            if session and session.data:
                progress = json.dumps(session.data, indent=2)
                base_prompt += f"\n### CURRENT SAVED DATA\n```json\n{progress}\n```\n"

                data = session.data
                has_username = bool(data.get('username') or data.get('user', {}).get('username'))
                has_email    = bool(data.get('email')    or data.get('user', {}).get('email'))
                has_language = bool(data.get('preferred_language'))
                has_dietary  = bool(data.get('dietary_preferences') or data.get('custom_dietary_preferences'))
                has_allergies = bool(data.get('allergies') or data.get('custom_allergies'))
                has_pw       = bool(data.get('password') or data.get('user', {}).get('password'))
                members      = data.get('household_members', [])

                # determine next question
                if not has_username:
                    base_prompt += "\nNEXT STEP → Ask for username.\n"
                elif not has_email:
                    base_prompt += "\nNEXT STEP → Ask for email address.\n"
                elif not has_language:
                    base_prompt += "\nNEXT STEP → Ask for preferred language (e.g., English, Spanish, French).\n"
                elif not has_dietary:
                    base_prompt += "\nNEXT STEP → Ask for dietary preferences. If user says 'none' or 'everything', use 'Everything'.\n"
                elif not has_allergies:
                    base_prompt += "\nNEXT STEP → Ask for allergies. If user says 'none', use 'None'.\n"
                elif has_username and has_email and has_language and has_dietary and has_allergies and not members:
                    base_prompt += (
                        "\nNEXT STEP → Offer to collect household‑member details "
                        "(name, age, dietary notes). If the user says 'skip', continue.\n"
                    )
                elif has_username and has_email and has_language and has_dietary and has_allergies and not has_pw:
                    base_prompt += "\nNEXT STEP → Call `onboarding_request_password` and then ask for password.\n"
        except Exception as e:
            logger.warning(f"Could not load onboarding progress for {self.user_id}: {e}")

        return base_prompt


    def _get_onboarding_history(self) -> List[Dict[str, Any]]:
        """Get conversation history for onboarding, stored in memory."""
        guest_data = GLOBAL_GUEST_STATE.get(str(self.user_id), {})
        if guest_data and "onboarding_history" in guest_data:
            history = guest_data["onboarding_history"].copy()
            return history
        else:
            # Initialize with system message
            initial_history = [{"role": "system", "content": self.system_message}]
            return initial_history

    def _save_onboarding_history(self, history: List[Dict[str, Any]]) -> None:
        """Save conversation history for onboarding."""
        if str(self.user_id) not in GLOBAL_GUEST_STATE:
            GLOBAL_GUEST_STATE[str(self.user_id)] = {}
        GLOBAL_GUEST_STATE[str(self.user_id)]["onboarding_history"] = history

    def send_message(self, message: str) -> Dict[str, Any]:
        """Send a message and get a response, potentially with PasswordPrompt structure."""
        
        history = self._get_onboarding_history()
        history.append({"role": "user", "content": message})
        
        try:
            # Check if we should expect a password prompt based on the message content
            should_use_password_prompt = self._should_use_password_prompt()
            
            if should_use_password_prompt:
                # Use structured output for password prompts
                # NOTE: Don't include tools when using structured text format - they conflict
                resp = self.client.responses.create(
                    model="gpt-4o-mini",  # Use a reliable model for onboarding
                    input=history,
                    instructions=self._build_onboarding_prompt(),
                    # tools=self._get_onboarding_tools(),  # ← REMOVED: Tools conflict with structured text format
                    text={
                        "format": {
                            'type': 'json_schema',
                            'name': 'password_prompt',
                            'schema': PasswordPrompt.model_json_schema()
                        }
                    }
                )
                
                
                # Parse the structured response
                try:
                    password_prompt = PasswordPrompt.model_validate_json(resp.output_text)
                    response_text = password_prompt.assistant_message
                    
                    # Add to history
                    history.append({"role": "assistant", "content": response_text})
                    self._save_onboarding_history(history)
                    
                    return {
                        "status": "success",
                        "message": response_text,
                        "is_password_request": password_prompt.is_password_request,
                        "response_id": resp.id
                    }
                except Exception as e:
                    # n8n traceback
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    requests.post(n8n_traceback_url, json={"error": str(e), "source":"_parse_password_prompt_response", "traceback": traceback.format_exc()})
                    # Fall back to regular response
                    response_text = resp.output_text
            else:
                # Regular response with tools
                resp = self.client.responses.create(
                    model="gpt-4o-mini",
                    input=history,
                    instructions=self._build_onboarding_prompt(),
                    tools=self._get_onboarding_tools(),
                    parallel_tool_calls=True
                )
                response_text = self._extract_response_text(resp)
            
            # Handle tool calls if present
            tool_calls = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
            
            if tool_calls:
                # Execute tool calls
                for tool_call in tool_calls:
                    # Add function call to history
                    call_entry = {
                        "type": "function_call",
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                        "call_id": tool_call.call_id
                    }
                    history.append(call_entry)
                    
                    # Execute the tool
                    try:
                        args_json = self._fix_onboarding_args(tool_call.name, tool_call.arguments)
                        
                        mock_call = type("Call", (), {
                            "call_id": tool_call.call_id,
                            "function": type("F", (), {
                                "name": tool_call.name,
                                "arguments": args_json
                            })
                        })
                        
                        from .tool_registration import handle_tool_call
                        result = handle_tool_call(mock_call)
                        
                        # Add result to history
                        output_entry = {
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": json.dumps(result)
                        }
                        history.append(output_entry)
                        
                    except Exception as e:
                        logger.error(f"Error executing onboarding tool {tool_call.name}: {e}")
                        # n8n traceback
                        n8n_traceback = {
                            'error': str(e),
                            'source': f'onboarding_tool_{tool_call.name}',
                            'traceback': f"Guest ID: {self.user_id} | {traceback.format_exc()}"
                        }
                        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                        error_result = {"status": "error", "message": str(e)}
                        output_entry = {
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": json.dumps(error_result)
                        }
                        history.append(output_entry)
            
            # Add assistant response to history if we have one
            if response_text:
                history.append({"role": "assistant", "content": response_text})
            
            self._save_onboarding_history(history)
            
            final_result = {
                "status": "success",
                "message": response_text,
                "is_password_request": False,
                "response_id": resp.id
            }
            return final_result
            
        except Exception as e:
            logger.error(f"Error in OnboardingAssistant.send_message: {e}")
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'send_message',
                'traceback': f"Guest ID: {self.user_id} | {traceback.format_exc()}"
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            return {
                "status": "error",
                "message": f"An error occurred: {str(e)}",
                "is_password_request": False
            }

    def _process_onboarding_stream(
        self,
        *,
        model: str,
        history: List[Dict[str, Any]],
        instructions: str,
        tools: List[Dict[str, Any]],
        previous_response_id: Optional[str],
        user_id: Union[int, str],
        message: str,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streams one onboarding assistant turn, handles parallel tool calls by:
          - yielding text and function_call events as they arrive
          - appending both the function_call and its output into `history`
          - looping back so the model can continue with that new context.
        """
        
        
        start_ts = time.time()
        current_history = history[:] # Work on a copy
        final_response_id = None # Track the final OpenAI response ID
        loop_iteration = 0
        max_iterations = 10  # Prevent infinite loops

        # Track if we processed any tool calls that might trigger password request
        processed_password_request_tool = False

        while True:
            loop_iteration += 1
            
            # Safety check to prevent infinite loops
            if loop_iteration > max_iterations:
                yield {"type": "response.completed"}
                break
            
            # Check if we should use password prompt ONLY if we processed password request tool in previous iteration
            if processed_password_request_tool:
                should_use_password_prompt = self._should_use_password_prompt()
                
                if should_use_password_prompt:
                    # For password prompts, use non-streaming with structured output
                    # NOTE: Don't include tools when using structured text format - they conflict
                    resp = self.client.responses.create(
                        model=model,
                        input=current_history,
                        instructions=instructions,
                        # tools=tools,  # ← REMOVED: Tools conflict with structured text format
                        previous_response_id=previous_response_id,
                        text={
                            "format": {
                                'type': 'json_schema',
                                'name': 'password_prompt',
                                'schema': PasswordPrompt.model_json_schema()
                            }
                        }
                    )
                    
                    final_response_id = resp.id
                    
                    # Yield response ID
                    yield {"type": "response_id", "id": resp.id}
                    
                    try:
                        # Parse the structured response
                        password_prompt = PasswordPrompt.model_validate_json(resp.output_text)
                        response_text = password_prompt.assistant_message
                        
                        # Yield the text content
                        yield {"type": "text", "content": response_text}
                        
                        # Yield the password request flag
                        yield {"type": "password_request", "is_password_request": password_prompt.is_password_request}
                        
                        # Add to history
                        current_history.append({"role": "assistant", "content": response_text})
                        
                        yield {"type": "response.completed"}
                        break
                        
                    except Exception as e:
                        # n8n traceback
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        requests.post(n8n_traceback_url, json={"error": str(e), "source":"_process_onboarding_stream", "traceback": traceback.format_exc()})
                        # Fall back to regular streaming
                        response_text = resp.output_text
                        yield {"type": "text", "content": response_text}
                        yield {"type": "password_request", "is_password_request": False}
                        current_history.append({"role": "assistant", "content": response_text})
                        yield {"type": "response.completed"}
                        break
            
            # Reset flag for this iteration
            processed_password_request_tool = False
            
            # 1) Start streaming from the Responses API
            
            stream = self.client.responses.create(
                model=model,
                input=current_history,
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
            latest_id_in_stream = previous_response_id
            response_completed = False

            # 2) Consume the event stream
            for ev in stream:
                # 2a) Capture the new response ID
                if isinstance(ev, ResponseCreatedEvent):
                    new_id = ev.response.id
                    latest_id_in_stream = new_id
                    final_response_id = new_id
                    yield {"type": "response_id", "id": new_id}
                    continue

                # 2b) End of this assistant turn
                if isinstance(ev, ResponseCompletedEvent):
                    response_completed = True
                    break

                # 2c) Stream text deltas
                if isinstance(ev, ResponseTextDeltaEvent):
                    if ev.delta and not buf.endswith(ev.delta):
                        # Add safeguard against extremely long text responses
                        if len(buf) > 5000:  # 5KB limit
                            yield {"type": "error", "message": "AI response too long - please try again"}
                            return
                        
                        buf += ev.delta
                        yield {"type": "text", "content": ev.delta}
                    continue
                    
                if isinstance(ev, ResponseTextDoneEvent):
                    if ev.text and not buf.endswith(ev.text):
                        buf += ev.text
                        yield {"type": "text", "content": ev.text}
                    continue

                # 2d) Function‑call argument fragments
                if isinstance(ev, ResponseFunctionCallArgumentsDeltaEvent):
                    # Map wrapper_id → real call_id if we haven't yet
                    if ev.item_id not in wrapper_to_call and getattr(ev, "item", None):
                        cid = getattr(ev.item, "call_id", None)
                        if cid:
                            wrapper_to_call[ev.item_id] = cid
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)

                    # Accumulate arguments with safety check
                    tgt = next((c for c in calls if c["id"] == real_id), None)
                    if not tgt:
                        tgt = {"id": real_id, "name": None, "args": ""}
                        calls.append(tgt)
                    
                    # Add safeguard against extremely long arguments
                    if len(tgt["args"]) > 5000:  # 5KB limit
                        yield {"type": "error", "message": "AI response too long - please try again"}
                        return
                    
                    tgt["args"] += ev.delta
                    continue

                # 2e) End‑of‑args: emit function_call and append to history
                if isinstance(ev, ResponseFunctionCallArgumentsDoneEvent):
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)
                    entry = next((c for c in calls if c["id"] == real_id), None)
                    if not entry:
                        continue

                    args_json = entry["args"]
                    
                    
                    # Fix the arguments if needed
                    fixed_args_json = self._fix_onboarding_args(entry["name"], args_json)
                    if fixed_args_json != args_json:
                        args_json = fixed_args_json
                    
                    try:
                        args_obj = json.loads(args_json)
                    except json.JSONDecodeError as e:
                        args_obj = {}
                    
                    # 1) Tell front‑end the call is happening
                    yield {
                        "type": "response.function_call",
                        "name": entry["name"],
                        "arguments": args_obj,
                        "call_id": real_id,
                    }

                    # 2) Inject the function_call into CURRENT history
                    call_entry = {
                        "type": "function_call",
                        "name": entry["name"],
                        "arguments": args_json,
                        "call_id": real_id
                    }
                    current_history.append(call_entry)
                    continue

                # 2f) Wrapper event: new function_call header
                if isinstance(ev, ResponseOutputItemAddedEvent) and isinstance(ev.item, ResponseFunctionToolCall):
                    item = ev.item
                    wrapper_id = item.id
                    call_id = item.call_id
                    name = item.name

                    wrapper_to_call[wrapper_id] = call_id
                    calls.append({"id": call_id, "name": name, "args": ""})

                    yield {
                        "type": "response.tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "output": None,
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

            # 4) If response was completed and we have text content, check if we need to continue
            if response_completed and buf:
                
                # Check if we need to continue for password request
                should_continue_for_password = False
                if not processed_password_request_tool:
                    # Check if we have all required fields but haven't called password request tool yet
                    try:
                        from custom_auth.models import OnboardingSession
                        session = OnboardingSession.objects.filter(guest_id=str(user_id)).first()
                        if session and session.data:
                            data = session.data
                            has_username = bool(data.get('username'))
                            has_email = bool(data.get('email'))
                            has_language = bool(data.get('preferred_language'))
                            has_dietary = bool(data.get('dietary_preferences') or data.get('custom_dietary_preferences'))
                            has_allergies = bool(data.get('allergies') or data.get('custom_allergies'))
                            has_pw_request = bool(data.get('ready_for_password'))
                            
                            # If we have all required fields but haven't requested password yet, continue
                            if has_username and has_email and has_language and has_dietary and has_allergies and not has_pw_request:
                                should_continue_for_password = True
                    except Exception as e:
                        # n8n traceback
                        n8n_traceback = {
                            'error': str(e),
                            'source': 'onboarding_progress_check',
                            'traceback': f"Guest ID: {user_id} | {traceback.format_exc()}"
                        }
                        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
                
                if not should_continue_for_password:
                    yield {"type": "password_request", "is_password_request": False}
                    yield {"type": "response.completed"}
                    break


            # 4.1) If no function calls were requested, finish up
            
            if not calls:
                yield {"type": "password_request", "is_password_request": False}
                yield {"type": "response.completed"}
                break
            
            # 4.2) If response was completed but there are function calls, we need to handle them first
            if response_completed and not calls:
                yield {"type": "password_request", "is_password_request": False}
                yield {"type": "response.completed"}
                break

            # 5) Drop any stray wrapper‑only entries
            calls = [c for c in calls if not c["id"].startswith("fc_")]
            
            # 5.1) If response was completed and we have no function calls after filtering, break
            if response_completed and not calls:
                yield {"type": "password_request", "is_password_request": False}
                yield {"type": "response.completed"}
                break

            # 6) Execute all parallel calls
            from .tool_registration import handle_tool_call
            
            for call in calls:
                call_id = call["id"]
                
                
                try:
                    args_obj = json.loads(call["args"] or "{}")
                except json.JSONDecodeError:
                    args_obj = {}
                
                # Fix the arguments if needed
                fixed_args_json = self._fix_onboarding_args(call["name"], call["args"] or "{}")
                if fixed_args_json != (call["args"] or "{}"):
                    try:
                        args_obj = json.loads(fixed_args_json)
                    except json.JSONDecodeError:
                        args_obj = {}
                
                try:
                    
                    # Time the tool execution
                    tool_start_time = time.time()
                    result = handle_tool_call(
                        type("Call", (), {
                            "call_id": call_id,
                            "function": type("F", (), {
                                "name": call["name"],
                                "arguments": json.dumps(args_obj)
                            })
                        })
                    )
                    tool_execution_time = time.time() - tool_start_time
                    
                        
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    result = {"status": "error", "message": str(e)}

                # Emit tool_result
                yield {
                    "type": "tool_result",
                    "tool_call_id": call_id,
                    "name": call["name"],
                    "output": result,
                }
                
                # Check if this was the password request tool
                if call["name"] == "onboarding_request_password":
                    processed_password_request_tool = True

                # 7a) Inject the function_call_output into CURRENT history
                result_json = json.dumps(result)
                output_entry = {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result_json,
                }
                current_history.append(output_entry)

            # 8) Loop back: Prepare for the next API call within the same turn
            previous_response_id = latest_id_in_stream

        # --- End of while loop ---
        
        processing_time = time.time() - start_ts
        # Save the final history
        self._save_onboarding_history(current_history)

    def stream_message(self, message: str) -> Generator[Dict[str, Any], None, None]:
        """Stream a message response for onboarding with robust architecture."""
        
        history = self._get_onboarding_history()
        history.append({"role": "user", "content": message})
        
        try:
            # Use the robust streaming architecture
            yield from self._process_onboarding_stream(
                model="gpt-4o-mini",
                history=history,
                instructions=self._build_onboarding_prompt(),
                tools=self._get_onboarding_tools(),
                previous_response_id=None,
                user_id=self.user_id,
                message=message,
            )
            
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"stream_message", "traceback": traceback.format_exc()})
            yield {"type": "error", "message": str(e)}

    def reset_conversation(self) -> Dict[str, Any]:
        """Reset the onboarding conversation."""
        try:
            if str(self.user_id) in GLOBAL_GUEST_STATE:
                # Clear onboarding history but keep other guest state
                if "onboarding_history" in GLOBAL_GUEST_STATE[str(self.user_id)]:
                    old_history_length = len(GLOBAL_GUEST_STATE[str(self.user_id)]["onboarding_history"])
                    del GLOBAL_GUEST_STATE[str(self.user_id)]["onboarding_history"]
            return {"status": "success", "message": "Onboarding conversation reset."}
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"reset_conversation", "traceback": traceback.format_exc()})

    def _should_use_password_prompt(self) -> bool:
        """
        Determine if we should request a password prompt from the user.
        This should only happen when we have username, email, and all essential onboarding data.
        """
        try:
            from custom_auth.models import OnboardingSession
            session = OnboardingSession.objects.filter(guest_id=str(self.user_id)).first()
            if not session or not session.data:
                return False
            
            data = session.data
            
            # Check if we have all required fields
            has_username = bool(data.get('username'))
            has_email = bool(data.get('email'))
            has_language = bool(data.get('preferred_language'))
            has_dietary = bool(data.get('dietary_preferences') or data.get('custom_dietary_preferences'))
            has_allergies = bool(data.get('allergies') or data.get('custom_allergies'))
            has_password = bool(data.get('password'))
            
            
            # Only prompt for password if we have all essential data but no password
            should_prompt = has_username and has_email and has_language and has_dietary and has_allergies and not has_password
            
            logger.info(f"_should_use_password_prompt: username={has_username}, email={has_email}, language={has_language}, dietary={has_dietary}, allergies={has_allergies}, password={has_password} -> {should_prompt}")
            return should_prompt
            
        except Exception as e:
            logger.error(f"Error in _should_use_password_prompt: {e}")
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': '_should_use_password_prompt',
                'traceback': f"Guest ID: {self.user_id} | {traceback.format_exc()}"
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            return False

    def _extract_response_text(self, response) -> str:
        """Extract text from OpenAI response."""
        if hasattr(response, "output_text"):
            return response.output_text
        
        # Fallback extraction
        text = ""
        for item in getattr(response, "output", []):
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []):
                    if getattr(c, "type", None) == "output_text":
                        text += getattr(c, "text", "")
            elif getattr(item, "type", None) == "text":
                text += getattr(item, "text", "")
        
        return text.strip()

    def _fix_onboarding_args(self, function_name: str, args_str: str) -> str:
        """Fix function arguments for onboarding tools."""
        try:
            # Safety check: prevent extremely long arguments (AI loop detection)
            if len(args_str) > 5000:  # 5KB limit
                args_str = args_str[:5000]
            
            args = json.loads(args_str)
            
            # Ensure guest_id is set correctly for onboarding functions
            if function_name in ["onboarding_save_progress", "guest_register_user", "onboarding_request_password"]:
                if "guest_id" in args and args["guest_id"] != str(self.user_id):
                    args["guest_id"] = str(self.user_id)
                elif "guest_id" not in args:
                    args["guest_id"] = str(self.user_id)
                    
                # Additional safety: if guest_id is extremely long, fix it
                if isinstance(args.get("guest_id"), str) and len(args["guest_id"]) > 50:
                    args["guest_id"] = str(self.user_id)
            
            # Special handling for onboarding_save_progress with flat parameters
            if function_name == "onboarding_save_progress":
                # Clean up individual parameters to prevent extremely long values
                for key in ["username", "email"]:
                    if key in args and isinstance(args[key], str):
                        if len(args[key]) <= 100:
                            pass  # Keep as is
                        else:
                            args[key] = args[key][:100]
                
                # Clean up household_members if present
                if "household_members" in args and isinstance(args["household_members"], list):
                    cleaned_members = []
                    for member in args["household_members"][:10]:  # Max 10 members
                        if isinstance(member, dict):
                            cleaned_member = {}
                            if "name" in member and isinstance(member["name"], str):
                                cleaned_member["name"] = member["name"][:50]  # Max 50 chars
                            if "age" in member and isinstance(member["age"], (int, str)):
                                try:
                                    cleaned_member["age"] = int(member["age"])
                                except:
                                    pass
                            if "dietary_preferences" in member and isinstance(member["dietary_preferences"], str):
                                cleaned_member["dietary_preferences"] = member["dietary_preferences"][:200]  # Max 200 chars
                            if cleaned_member:
                                cleaned_members.append(cleaned_member)
                    args["household_members"] = cleaned_members
                
            
            return json.dumps(args)
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"_fix_onboarding_args", "traceback": traceback.format_exc()})
            # If JSON parsing fails, create minimal valid args
            return json.dumps({"guest_id": str(self.user_id)})

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

# ────────────────────────────────────────────────────────────────────
#  Tool information and debugging helpers
# ────────────────────────────────────────────────────────────────────



# ────────────────────────────────────────────────────────────────────
#  Conversation‑reset helper
# ────────────────────────────────────────────────────────────────────
# meals/sous_chef_assistant.py
"""
Sous Chef Assistant - Family-focused AI assistant for chefs.

This assistant helps chefs make better meal planning and preparation decisions
by providing context about specific families they serve. Each conversation is
scoped to a single family (either a platform customer or CRM lead).
"""

import json
import logging
import traceback
import time
import os
from typing import Dict, Any, List, Generator, Optional, Union, Literal
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from openai import OpenAI
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURED OUTPUT SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class TextBlock(BaseModel):
    """A paragraph of text content."""
    type: Literal["text"] = "text"
    content: str = Field(description="The text content of this block")


class TableBlock(BaseModel):
    """A table with headers and rows."""
    type: Literal["table"] = "table"
    headers: List[str] = Field(description="Column headers for the table")
    rows: List[List[str]] = Field(description="Table rows, each row is a list of cell values")


class ListBlock(BaseModel):
    """A bulleted or numbered list."""
    type: Literal["list"] = "list"
    items: List[str] = Field(description="List items")
    ordered: bool = Field(default=False, description="True for numbered list, False for bulleted")


class SousChefResponse(BaseModel):
    """Structured response from Sous Chef containing content blocks."""
    blocks: List[Union[TextBlock, TableBlock, ListBlock]] = Field(
        description="Array of content blocks that make up the response"
    )

try:
    from groq import Groq
except Exception:
    Groq = None

from customer_dashboard.models import SousChefThread, SousChefMessage
from chefs.models import Chef
from custom_auth.models import CustomUser
from crm.models import Lead
from shared.utils import generate_family_context_for_chef
from utils.model_selection import choose_model
from utils.groq_rate_limit import groq_call_with_retry

logger = logging.getLogger(__name__)

# Model configuration
MODEL_PRIMARY = "gpt-4o"
MODEL_FALLBACK = "gpt-4o-mini"


# ═══════════════════════════════════════════════════════════════════════════════
# SOUS CHEF SYSTEM PROMPT TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════
SOUS_CHEF_PROMPT_TEMPLATE = """
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!--                    S O U S   C H E F   A S S I S T A N T                    -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<PromptTemplate id="sous_chef" version="2025-12-03">

  <!-- ───── 1. IDENTITY ───── -->
  <Identity>
    <Role>Sous Chef — Your personal AI kitchen assistant for meal planning</Role>
    <Persona traits="knowledgeable, precise, supportive, safety-conscious"/>
    <Chef name="{chef_name}" />
  </Identity>

  <!-- ───── 2. CURRENT FAMILY CONTEXT ───── -->
  <FamilyContext>
{family_context}
  </FamilyContext>

  <!-- ───── 3. MISSION ───── -->
  <Mission>
    <Primary>
      Help {chef_name} plan and prepare meals for this family by:
      • Suggesting menu ideas that comply with ALL household dietary restrictions
      • Flagging potential allergen conflicts before they become problems
      • Scaling recipes appropriately for the household size
      • Recalling what has worked well in previous orders
    </Primary>
    <Secondary>
      • Help document important notes about family preferences
      • Suggest ways to delight this family based on their history
      • Optimize prep efficiency when planning multiple dishes
    </Secondary>
    <Critical>
      ⚠️ NEVER suggest ingredients that conflict with ANY household member's allergies.
      When in doubt, ask for clarification rather than risk an allergic reaction.
    </Critical>
  </Mission>

  <!-- ───── 4. CAPABILITIES (TOOLS) ───── -->
  <Capabilities>
    You have access to the following tools to help the chef:
{all_tools}
  </Capabilities>

  <!-- ───── 5. OPERATING INSTRUCTIONS ───── -->
  <OperatingInstructions>

    <!-- 5-A. SAFETY FIRST -->
    <AllergyProtocol>
      • Before suggesting ANY recipe or ingredient, mentally check against the 
        family's allergy list in the context above.
      • If a recipe contains a potential allergen, explicitly call it out.
      • Offer safe substitutions when possible.
      • When scaling recipes, verify that substitutions don't introduce new allergens.
    </AllergyProtocol>

    <!-- 5-B. DIETARY COMPLIANCE -->
    <DietaryCompliance>
      • A dish is only compliant if it works for ALL household members.
      • When members have different restrictions, find meals that satisfy everyone.
      • Clearly indicate which restrictions a suggested meal satisfies.
    </DietaryCompliance>

    <!-- 5-C. CONTEXTUAL AWARENESS -->
    <UseContext>
      • Reference the family's order history when suggesting dishes.
      • Note any patterns (e.g., "They usually order your meal prep service").
      • If notes mention preferences, incorporate them in suggestions.
    </UseContext>

    <!-- 5-D. OUTPUT FORMAT -->
    <Format>
      <Markdown>
        Render replies in **GitHub-Flavored Markdown (GFM)**.
        Use headings, lists, and tables where helpful.
      </Markdown>
      <Concise>
        Keep responses focused and actionable.
        Chefs are busy — prioritize clarity over verbosity.
      </Concise>
      <Tables>
        For menu suggestions, use tables:
        `| Day | Meal | Compliant For | Notes |`
      </Tables>
    </Format>

    <!-- 5-E. PROFESSIONAL BOUNDARIES -->
    <Scope>
      • Focus on culinary and meal planning topics.
      • Do not provide medical advice — dietary restrictions are about food, not treatment.
      • Politely redirect off-topic questions back to meal planning.
    </Scope>

  </OperatingInstructions>
</PromptTemplate>
"""


def _safe_json_dumps(obj) -> str:
    """Safely serialize objects to JSON with fallback for special types."""
    def _default(o):
        if isinstance(o, Decimal):
            return float(o)
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, default=_default)


class SousChefAssistant:
    """
    AI assistant for chefs to help with family-specific meal planning.
    
    Each instance is scoped to a specific chef + family combination.
    The assistant has full context about the family's dietary needs,
    household composition, and order history with this chef.
    """

    def __init__(
        self,
        chef_id: int,
        family_id: int,
        family_type: str = 'customer'  # 'customer' or 'lead'
    ):
        """
        Initialize a Sous Chef assistant for a specific chef and family.
        
        Args:
            chef_id: The ID of the Chef using the assistant
            family_id: The ID of the family (CustomUser or Lead)
            family_type: Either 'customer' or 'lead'
        """
        self.chef_id = chef_id
        self.family_id = family_id
        self.family_type = family_type
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=settings.OPENAI_KEY)
        
        # Optional Groq client
        self.groq = None
        try:
            groq_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
            if groq_key and Groq is not None:
                self.groq = Groq(api_key=groq_key)
        except Exception:
            pass
        
        # Load chef and family
        self.chef = Chef.objects.select_related('user').get(id=chef_id)
        self.customer = None
        self.lead = None
        
        if family_type == 'customer':
            self.customer = CustomUser.objects.get(id=family_id)
        elif family_type == 'lead':
            self.lead = Lead.objects.get(id=family_id)
        else:
            raise ValueError(f"Invalid family_type: {family_type}")
        
        # Generate family context
        self.family_context = generate_family_context_for_chef(
            chef=self.chef,
            customer=self.customer,
            lead=self.lead
        )
        
        # Build system instructions
        self.instructions = self._build_instructions()
        
        # Debug mode
        try:
            self._stream_debug = os.getenv('ASSISTANT_STREAM_DEBUG', '').lower() in ('1', 'true', 'yes', 'on') or getattr(settings, 'DEBUG', False)
        except Exception:
            self._stream_debug = False

    def _dbg(self, msg: str):
        """Debug logging helper."""
        if getattr(self, '_stream_debug', False):
            try:
                logger.info(f"SOUS_CHEF_DEBUG: {msg}")
            except Exception:
                pass

    def _build_instructions(self) -> str:
        """Build the system instructions with chef and family context."""
        # Get chef name
        chef_name = self.chef.user.get_full_name() or self.chef.user.username
        
        # Get tool descriptions
        tools = self._get_tools()
        tool_descriptions = []
        for tool in tools:
            name = tool.get('name', 'unknown')
            desc = tool.get('description', 'No description')
            tool_descriptions.append(f"    • {name}: {desc}")
        
        all_tools_str = '\n'.join(tool_descriptions) if tool_descriptions else "    No tools available."
        
        return SOUS_CHEF_PROMPT_TEMPLATE.format(
            chef_name=chef_name,
            family_context=self.family_context,
            all_tools=all_tools_str
        )

    def _get_tools(self) -> List[Dict[str, Any]]:
        """Get the tools available for sous chef operations."""
        from .sous_chef_tools import get_sous_chef_tools
        return get_sous_chef_tools()

    def _get_or_create_thread(self) -> SousChefThread:
        """Get or create a conversation thread for this chef + family."""
        filter_kwargs = {
            'chef': self.chef,
            'is_active': True,
        }
        
        if self.family_type == 'customer':
            filter_kwargs['customer'] = self.customer
            filter_kwargs['lead__isnull'] = True
        else:
            filter_kwargs['lead'] = self.lead
            filter_kwargs['customer__isnull'] = True
        
        try:
            thread = SousChefThread.objects.filter(**filter_kwargs).latest('updated_at')
            return thread
        except SousChefThread.DoesNotExist:
            # Create new thread
            create_kwargs = {
                'chef': self.chef,
                'is_active': True,
            }
            if self.family_type == 'customer':
                create_kwargs['customer'] = self.customer
            else:
                create_kwargs['lead'] = self.lead
            
            return SousChefThread.objects.create(**create_kwargs)

    def _save_message(self, thread: SousChefThread, role: str, content: str, tool_calls: List = None) -> SousChefMessage:
        """Save a message to the thread."""
        return SousChefMessage.objects.create(
            thread=thread,
            role=role,
            content=content,
            tool_calls=tool_calls or []
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of tokens for a given text.
        Approximates ~4 characters per token for English text.
        """
        return len(text) // 4

    def _truncate_history(self, history: List[Dict], max_messages: int = 30, max_tokens: int = 25000) -> List[Dict]:
        """
        Truncate conversation history if it's too long, keeping the system message 
        and the most recent messages. Uses both message count and token estimation.
        Special handling for function calls to maintain call/output pairs.
        
        Args:
            history: The conversation history list
            max_messages: Maximum number of messages to keep (default 30)
            max_tokens: Maximum estimated tokens to keep (default 25000)
            
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

    def _generate_conversation_summary(self, messages_to_summarize: List[Dict]) -> str:
        """
        Generate AI summary of older messages using Groq OSS model (free, fast).
        Falls back to OpenAI if Groq is unavailable.
        
        Args:
            messages_to_summarize: List of message dicts to summarize
            
        Returns:
            Summary string
        """
        # Build conversation text from messages
        conversation_text = "\n".join([
            f"{m.get('role', 'unknown')}: {m.get('content', '')[:500]}"
            for m in messages_to_summarize
            if m.get('role') not in ('system',) and m.get('content')
        ])
        
        if not conversation_text.strip():
            return ""
        
        system_prompt = "You are a concise summarizer. Create brief summaries focusing on key decisions and preferences."
        user_prompt = f"""Summarize this chef/Sous Chef conversation about a client family.
Focus on: dietary decisions, menu preferences, important notes, issues raised.
Max 200 words.

Conversation:
{conversation_text}"""
        
        # Use Groq OSS model (free, fast) - already initialized as self.groq in __init__
        if self.groq:
            try:
                raw_create = getattr(getattr(self.groq.chat, 'completions', None), 'with_raw_response', None)
                if raw_create:
                    raw_create = self.groq.chat.completions.with_raw_response.create
                groq_resp = groq_call_with_retry(
                    raw_create_fn=raw_create,
                    create_fn=self.groq.chat.completions.create,
                    desc='sous_chef.conversation_summary',
                    model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    stream=False,
                )
                return groq_resp.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq summarization failed, falling back to OpenAI: {e}")
        
        # Fallback to OpenAI only if Groq unavailable
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt}, 
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to generate conversation summary: {e}")
            return ""

    def _truncate_with_summarization(self, history: List[Dict], thread: SousChefThread, 
                                      max_messages: int = 30, max_tokens: int = 25000) -> List[Dict]:
        """
        Truncate history with intelligent summarization of dropped messages.
        
        Instead of simply dropping old messages, this method:
        1. Identifies messages that would be dropped
        2. Generates an AI summary of those messages
        3. Stores the summary in the thread
        4. Injects the summary into the returned history
        
        Args:
            history: The conversation history list
            thread: The SousChefThread to store the summary
            max_messages: Maximum number of messages to keep (default 30)
            max_tokens: Maximum estimated tokens to keep (default 25000)
            
        Returns:
            Truncated history with summary injection if applicable
        """
        # Check if truncation is needed
        total_tokens = sum(self._estimate_tokens(str(msg.get("content", ""))) for msg in history)
        if len(history) <= max_messages and total_tokens <= max_tokens:
            # Inject existing summary if present (from previous truncations)
            if thread.conversation_summary:
                return self._inject_summary_into_history(history, thread.conversation_summary)
            return history
        
        # Separate system messages and regular messages
        system_msgs = [h for h in history if h.get('role') == 'system']
        other_msgs = [h for h in history if h.get('role') != 'system']
        
        # Calculate how many messages to keep (keeping last 15 regular messages)
        keep_recent = 15
        if len(other_msgs) <= keep_recent:
            # Not enough to truncate meaningfully
            if thread.conversation_summary:
                return self._inject_summary_into_history(history, thread.conversation_summary)
            return history
        
        # Messages to be dropped (excluding recent ones we're keeping)
        messages_to_drop = other_msgs[:-keep_recent]
        messages_to_keep = other_msgs[-keep_recent:]
        
        # Generate summary if we're dropping significant content (at least 6 messages = 3 exchanges)
        if len(messages_to_drop) >= 6:
            try:
                new_summary = self._generate_conversation_summary(messages_to_drop)
                if new_summary:
                    # Combine with existing summary if present
                    if thread.conversation_summary:
                        combined_summary = f"{thread.conversation_summary}\n\n[More recent context]: {new_summary}"
                        # Truncate combined summary if it gets too long
                        if len(combined_summary) > 2000:
                            combined_summary = new_summary  # Use only new summary
                    else:
                        combined_summary = new_summary
                    
                    # Save to thread
                    thread.conversation_summary = combined_summary
                    thread.summary_generated_at = timezone.now()
                    thread.messages_summarized_count += len(messages_to_drop)
                    thread.save(update_fields=['conversation_summary', 'summary_generated_at', 'messages_summarized_count'])
                    
                    logger.info(f"Generated conversation summary for thread {thread.id}, summarized {len(messages_to_drop)} messages")
            except Exception as e:
                logger.error(f"Failed to generate/save conversation summary: {e}")
        
        # Build truncated history: system + recent messages
        truncated_history = system_msgs + messages_to_keep
        
        # Inject summary if available
        if thread.conversation_summary:
            truncated_history = self._inject_summary_into_history(truncated_history, thread.conversation_summary)
        
        logger.info(f"Truncated history from {len(history)} to {len(truncated_history)} messages")
        return truncated_history

    def _inject_summary_into_history(self, history: List[Dict], summary: str) -> List[Dict]:
        """
        Inject conversation summary into history as a system message after the main system prompt.
        
        Args:
            history: The conversation history
            summary: The summary to inject
            
        Returns:
            History with summary injected
        """
        if not summary:
            return history
        
        summary_message = {
            "role": "system",
            "content": f"[Previous conversation summary - use this context to maintain continuity]:\n{summary}"
        }
        
        # Find position after first system message
        result = []
        system_found = False
        summary_injected = False
        
        for msg in history:
            result.append(msg)
            if not summary_injected and msg.get('role') == 'system':
                system_found = True
            elif system_found and not summary_injected:
                # Inject summary right after the first system message
                result.insert(-1, summary_message)
                summary_injected = True
        
        # If no system message found, prepend the summary
        if not summary_injected:
            result.insert(0, summary_message)
        
        return result

    def new_conversation(self) -> Dict[str, Any]:
        """Start a new conversation by deactivating the current thread."""
        # Deactivate existing threads
        filter_kwargs = {
            'chef': self.chef,
            'is_active': True,
        }
        if self.family_type == 'customer':
            filter_kwargs['customer'] = self.customer
        else:
            filter_kwargs['lead'] = self.lead
        
        SousChefThread.objects.filter(**filter_kwargs).update(is_active=False)
        
        # Create new thread
        thread = self._get_or_create_thread()
        
        return {
            'status': 'success',
            'thread_id': thread.id,
            'family_name': thread.family_name
        }

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history for the current thread."""
        thread = self._get_or_create_thread()
        messages = thread.messages.all().order_by('created_at')
        
        result = []
        for msg in messages:
            content = msg.content
            is_structured = False
            
            # Check if assistant message is structured JSON
            if msg.role == 'assistant' and content:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and 'blocks' in parsed:
                        # This is structured content - return as-is
                        is_structured = True
                except (json.JSONDecodeError, TypeError):
                    # Not JSON - this is legacy plain text
                    pass
            
            result.append({
                'role': msg.role,
                'content': content,
                'is_structured': is_structured,
                'created_at': msg.created_at.isoformat(),
            })
        return result

    def send_message(self, message: str) -> Dict[str, Any]:
        """Send a message and get a response (non-streaming)."""
        thread = self._get_or_create_thread()
        
        # Build history from thread
        history = thread.openai_input_history or []
        if not history:
            history.append({"role": "system", "content": self.instructions})
        history.append({"role": "user", "content": message})
        
        # Truncate with summarization if needed (preserves context via AI summary)
        history = self._truncate_with_summarization(history, thread)
        
        # Select model
        model = choose_model(
            user_id=self.chef.user_id,
            is_guest=False,
            question=message
        ) or MODEL_PRIMARY
        
        # Save user message
        self._save_message(thread, 'chef', message)
        
        current_history = history.copy()
        final_response_id = None
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                resp = self.client.responses.create(
                    model=model,
                    input=current_history,
                    instructions=self.instructions,
                    tools=self._get_tools(),
                    parallel_tool_calls=True,
                )
                
                final_response_id = resp.id
                
                # Check for tool calls
                tool_calls = [item for item in getattr(resp, "output", []) if getattr(item, 'type', None) == "function_call"]
                
                # Extract text response
                response_text = self._extract_text(resp)
                
                if response_text:
                    current_history.append({"role": "assistant", "content": response_text})
                
                # If no tool calls, we're done
                if not tool_calls:
                    break
                
                # Execute tool calls
                for tool_call in tool_calls:
                    call_id = getattr(tool_call, 'call_id', None)
                    name = getattr(tool_call, 'name', None)
                    arguments = getattr(tool_call, 'arguments', '{}')
                    
                    # Add function call to history
                    current_history.append({
                        "type": "function_call",
                        "name": name,
                        "arguments": arguments,
                        "call_id": call_id
                    })
                    
                    # Execute the tool
                    try:
                        from .sous_chef_tools import handle_sous_chef_tool_call
                        result = handle_sous_chef_tool_call(
                            name=name,
                            arguments=arguments,
                            chef=self.chef,
                            customer=self.customer,
                            lead=self.lead
                        )
                    except Exception as e:
                        logger.error(f"Tool call error: {e}")
                        result = {"status": "error", "message": str(e)}
                    
                    # Add result to history
                    current_history.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result)
                    })
                
            except Exception as e:
                logger.error(f"Error in send_message: {e}")
                return {"status": "error", "message": str(e)}
        
        # Save assistant response
        if response_text:
            self._save_message(thread, 'assistant', response_text)
        
        # Update thread history
        thread.openai_input_history = current_history
        thread.latest_response_id = final_response_id
        thread.save(update_fields=['openai_input_history', 'latest_response_id', 'updated_at'])
        
        return {
            "status": "success",
            "message": response_text or "",
            "response_id": final_response_id,
            "thread_id": thread.id
        }

    def send_structured_message(self, message: str) -> Dict[str, Any]:
        """
        Send a message and get a structured JSON response.
        Uses OpenAI's structured output to ensure consistent formatting.
        """
        thread = self._get_or_create_thread()
        
        # Build history for chat completions format
        history = thread.openai_input_history or []
        
        # Convert to chat format
        chat_messages = []
        
        # Add system message with structured output instructions
        structured_instructions = self.instructions + """

IMPORTANT: You MUST respond using the structured JSON format.
Your response should be an array of content blocks:
- Use "text" blocks for paragraphs of text
- Use "table" blocks for tabular data (with headers and rows arrays)
- Use "list" blocks for bulleted or numbered lists (with items array and ordered boolean)

Example response structure:
{
  "blocks": [
    {"type": "text", "content": "Here are three nut-free alternatives:"},
    {"type": "table", "headers": ["Option", "Dish", "Time", "Notes"], "rows": [["A", "Grilled salmon", "25 min", "Light and fresh"]]},
    {"type": "text", "content": "Let me know which option works best!"}
  ]
}
"""
        chat_messages.append({"role": "system", "content": structured_instructions})
        
        # Add conversation history
        for item in history:
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and content:
                chat_messages.append({"role": role, "content": content})
        
        # Add new user message
        chat_messages.append({"role": "user", "content": message})
        
        # Select model (gpt-4o supports structured output)
        model = "gpt-4o"
        
        # Save user message
        self._save_message(thread, 'chef', message)
        
        try:
            # Use structured output with Pydantic model
            completion = self.client.beta.chat.completions.parse(
                model=model,
                messages=chat_messages,
                response_format=SousChefResponse,
            )
            
            response_message = completion.choices[0].message
            
            if response_message.parsed:
                # Successfully parsed structured response
                structured_response = response_message.parsed
                # Convert to JSON string for storage
                response_json = structured_response.model_dump_json()
                
                # Save to thread history
                chat_messages.append({"role": "assistant", "content": response_json})
                thread.openai_input_history = chat_messages
                thread.save(update_fields=['openai_input_history', 'updated_at'])
                
                # Save message to database
                self._save_message(thread, 'assistant', response_json)
                
                return {
                    "status": "success",
                    "content": structured_response.model_dump(),
                    "thread_id": thread.id
                }
            elif response_message.refusal:
                # Model refused to respond
                return {
                    "status": "error",
                    "message": response_message.refusal,
                    "thread_id": thread.id
                }
            else:
                # Unexpected response
                return {
                    "status": "error",
                    "message": "Unexpected response format",
                    "thread_id": thread.id
                }
                
        except Exception as e:
            logger.error(f"Error in send_structured_message: {e}\n{traceback.format_exc()}")
            # Fallback: return error
            return {
                "status": "error",
                "message": str(e),
                "thread_id": thread.id
            }

    def stream_message(self, message: str) -> Generator[Dict[str, Any], None, None]:
        """Stream a message response."""
        thread = self._get_or_create_thread()
        
        # Build history
        history = thread.openai_input_history or []
        if not history:
            history.append({"role": "system", "content": self.instructions})
        history.append({"role": "user", "content": message})
        
        # Truncate with summarization if needed (preserves context via AI summary)
        history = self._truncate_with_summarization(history, thread)
        
        # Select model
        model = choose_model(
            user_id=self.chef.user_id,
            is_guest=False,
            question=message
        ) or MODEL_PRIMARY
        
        # Save user message
        self._save_message(thread, 'chef', message)
        
        yield from self._process_stream(
            model=model,
            history=history,
            thread=thread
        )

    def _process_stream(
        self,
        model: str,
        history: List[Dict[str, Any]],
        thread: SousChefThread
    ) -> Generator[Dict[str, Any], None, None]:
        """Core streaming logic."""
        from openai.types.responses import (
            ResponseCreatedEvent,
            ResponseCompletedEvent,
            ResponseTextDeltaEvent,
            ResponseTextDoneEvent,
            ResponseFunctionToolCall,
            ResponseFunctionCallArgumentsDeltaEvent,
            ResponseFunctionCallArgumentsDoneEvent,
            ResponseOutputItemAddedEvent,
            ResponseOutputItemDoneEvent,
        )
        
        current_history = history[:]
        final_response_id = None
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            stream = self.client.responses.create(
                model=model,
                input=current_history,
                instructions=self.instructions,
                tools=self._get_tools(),
                stream=True,
                parallel_tool_calls=True,
            )
            
            buf = ""
            calls: List[Dict[str, Any]] = []
            wrapper_to_call: Dict[str, str] = {}
            response_completed = False
            
            for ev in stream:
                # Response created
                if isinstance(ev, ResponseCreatedEvent):
                    final_response_id = ev.response.id
                    yield {"type": "response_id", "id": final_response_id}
                    continue
                
                # Response completed
                if isinstance(ev, ResponseCompletedEvent):
                    response_completed = True
                    break
                
                # Text delta
                if isinstance(ev, ResponseTextDeltaEvent):
                    if ev.delta:
                        buf += ev.delta
                        yield {"type": "text", "content": ev.delta}
                    continue
                
                if isinstance(ev, ResponseTextDoneEvent):
                    if ev.text and not buf:
                        buf = ev.text
                        yield {"type": "text", "content": ev.text}
                    continue
                
                # Function call arguments delta
                if isinstance(ev, ResponseFunctionCallArgumentsDeltaEvent):
                    if ev.item_id not in wrapper_to_call and getattr(ev, "item", None):
                        cid = getattr(ev.item, "call_id", None)
                        if cid:
                            wrapper_to_call[ev.item_id] = cid
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)
                    
                    tgt = next((c for c in calls if c["id"] == real_id), None)
                    if not tgt:
                        tgt = {"id": real_id, "name": None, "args": ""}
                        calls.append(tgt)
                    tgt["args"] += ev.delta
                    continue
                
                # Function call arguments done
                if isinstance(ev, ResponseFunctionCallArgumentsDoneEvent):
                    real_id = wrapper_to_call.get(ev.item_id, ev.item_id)
                    entry = next((c for c in calls if c["id"] == real_id), None)
                    if not entry:
                        continue
                    
                    args_json = entry["args"]
                    args_obj = json.loads(args_json) if args_json else {}
                    
                    yield {
                        "type": "response.function_call",
                        "name": entry["name"],
                        "arguments": args_obj,
                        "call_id": real_id,
                    }
                    
                    current_history.append({
                        "type": "function_call",
                        "name": entry["name"],
                        "arguments": args_json,
                        "call_id": real_id
                    })
                    continue
                
                # Function call header
                if isinstance(ev, ResponseOutputItemAddedEvent) and isinstance(ev.item, ResponseFunctionToolCall):
                    item = ev.item
                    wrapper_to_call[item.id] = item.call_id
                    calls.append({"id": item.call_id, "name": item.name, "args": ""})
                    
                    yield {
                        "type": "response.tool",
                        "tool_call_id": item.call_id,
                        "name": item.name,
                        "output": None,
                    }
                    continue
            
            # Flush buffered text
            if buf:
                current_history.append({"role": "assistant", "content": buf.strip()})
                
                # Emit render payload
                yield {
                    "type": "tool_result",
                    "tool_call_id": "render_1",
                    "name": "response.render",
                    "output": {"markdown": buf},
                }
            
            # If completed with text and no calls, we're done
            if response_completed and buf and not calls:
                # Save to DB
                self._save_message(thread, 'assistant', buf)
                thread.openai_input_history = current_history
                thread.latest_response_id = final_response_id
                thread.save(update_fields=['openai_input_history', 'latest_response_id', 'updated_at'])
                
                yield {"type": "response.completed"}
                break
            
            # If no calls, we're done
            if not calls:
                if buf:
                    self._save_message(thread, 'assistant', buf)
                    thread.openai_input_history = current_history
                    thread.latest_response_id = final_response_id
                    thread.save(update_fields=['openai_input_history', 'latest_response_id', 'updated_at'])
                yield {"type": "response.completed"}
                break
            
            # Execute tool calls
            for call in calls:
                call_id = call["id"]
                args_obj = json.loads(call["args"] or "{}")
                
                try:
                    from .sous_chef_tools import handle_sous_chef_tool_call
                    result = handle_sous_chef_tool_call(
                        name=call["name"],
                        arguments=json.dumps(args_obj),
                        chef=self.chef,
                        customer=self.customer,
                        lead=self.lead
                    )
                except Exception as e:
                    logger.error(f"Tool call error: {e}")
                    result = {"status": "error", "message": str(e)}
                
                yield {
                    "type": "tool_result",
                    "tool_call_id": call_id,
                    "name": call["name"],
                    "output": result,
                }
                
                current_history.append({
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": _safe_json_dumps(result),
                })
            
            # Clear calls for next iteration
            calls = []
        
        # Final save if we exited the loop
        if buf:
            thread.openai_input_history = current_history
            thread.latest_response_id = final_response_id
            thread.save(update_fields=['openai_input_history', 'latest_response_id', 'updated_at'])

    def _extract_text(self, response) -> str:
        """Extract text content from an OpenAI response."""
        for item in getattr(response, "output", []):
            if getattr(item, 'type', None) == 'message':
                for content in getattr(item, 'content', []):
                    if getattr(content, 'type', None) == 'output_text':
                        return getattr(content, 'text', '')
        return ""


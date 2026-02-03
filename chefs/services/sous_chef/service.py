# chefs/services/sous_chef/service.py
"""
Unified Sous Chef Service - Channel-aware AI assistant for chefs.

This is the main interface for interacting with Sous Chef.
It handles:
- Channel-aware tool loading
- Conversation management
- Groq API integration
- Response streaming (for web)
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Generator

from django.conf import settings

from .agent_factory import SousChefAgentFactory
from .thread_manager import ThreadManager
from .tools import get_tool_schemas_for_channel

logger = logging.getLogger(__name__)


def _get_groq_model() -> str:
    """Get the Groq model from settings."""
    return getattr(settings, 'GROQ_MODEL', None) or os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')


class SousChefService:
    """
    Unified interface for Sous Chef AI assistant.
    
    Usage:
        # Web dashboard (full functionality)
        service = SousChefService(chef_id=1, channel="web")
        result = service.send_message("Help me plan a meal")
        
        # Telegram (no navigation tools)
        service = SousChefService(chef_id=1, channel="telegram")
        result = service.send_message("What orders do I have?")
        
        # With family context
        service = SousChefService(
            chef_id=1, 
            channel="web",
            family_id=123,
            family_type="customer"
        )
    """
    
    def __init__(
        self,
        chef_id: int,
        channel: str = "web",
        family_id: Optional[int] = None,
        family_type: Optional[str] = None,
    ):
        """
        Initialize the service.
        
        Args:
            chef_id: ID of the chef
            channel: Channel type ('web', 'telegram', 'line', 'api')
            family_id: Optional family/customer ID
            family_type: 'customer' or 'lead' if family_id provided
        """
        self.chef_id = chef_id
        self.channel = channel
        self.family_id = family_id
        self.family_type = family_type
        
        # Initialize components
        self.factory = SousChefAgentFactory(
            chef_id=chef_id,
            channel=channel,
            family_id=family_id,
            family_type=family_type,
        )
        
        self.thread_manager = ThreadManager(
            chef_id=chef_id,
            family_id=family_id,
            family_type=family_type,
            channel=channel,
        )
        
        # Lazy init Groq client
        self._groq = None
        self._model = _get_groq_model()
    
    @property
    def groq(self):
        """Lazy initialize Groq client."""
        if self._groq is None:
            try:
                from groq import Groq
                self._groq = Groq()
            except ImportError:
                raise ImportError("groq package required. Run: pip install groq")
        return self._groq
    
    def send_message(self, message: str) -> Dict[str, Any]:
        """
        Send a message and get a response (synchronous).
        
        Args:
            message: The user's message
        
        Returns:
            Dict with status, message, thread_id
        """
        try:
            # Get thread and history
            thread = self.thread_manager.get_or_create_thread()
            history = self.thread_manager.get_history_for_groq(limit=20)
            
            # Build messages for Groq
            messages = [
                {"role": "system", "content": self.factory.build_system_prompt()}
            ]
            messages.extend(history)
            messages.append({"role": "user", "content": message})
            
            # Get tools for this channel
            tools = self.factory.get_tools()
            
            # Call Groq
            response_text = self._run_agent_loop(messages, tools)
            
            # Save the turn
            self.thread_manager.save_turn(message, response_text)
            
            return {
                "status": "success",
                "message": response_text,
                "thread_id": thread.id,
            }
            
        except Exception as e:
            logger.error(f"SousChefService error: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "thread_id": self.thread_manager.thread_id,
            }
    
    def _run_agent_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_iterations: int = 10,
    ) -> str:
        """
        Run the agent loop with tool execution.
        
        Args:
            messages: Conversation messages
            tools: Available tools
            max_iterations: Max tool call iterations
        
        Returns:
            Final response text
        """
        from .tools.loader import execute_tool
        
        context = self.factory.get_context()
        
        for iteration in range(max_iterations):
            # Call Groq
            response = self.groq.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools if tools else None,
            )
            
            choice = response.choices[0] if response.choices else None
            if not choice:
                return "I couldn't generate a response."
            
            assistant_message = choice.message
            response_text = assistant_message.content or ""
            tool_calls = assistant_message.tool_calls or []
            
            # If no tool calls, we're done
            if not tool_calls:
                return response_text
            
            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": response_text or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            })
            
            # Execute tool calls with channel-aware sensitive data handling
            for tool_call in tool_calls:
                try:
                    # Parse arguments
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    
                    # Execute with channel awareness (sensitive tools blocked on restricted channels)
                    result = execute_tool(
                        tool_name=tool_call.function.name,
                        args=args,
                        chef=context.get("chef"),
                        customer=context.get("customer"),
                        lead=context.get("lead"),
                        channel=self.channel,  # Key: pass channel for sensitive data handling
                    )
                except Exception as e:
                    logger.error(f"Tool call error ({tool_call.function.name}): {e}")
                    result = {"status": "error", "message": str(e)}
                
                # Add tool result
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    "tool_call_id": tool_call.id,
                })
        
        # Max iterations reached
        return response_text or "I completed the requested actions."
    
    def stream_message(self, message: str) -> Generator[Dict[str, Any], None, None]:
        """
        Stream a response (for web UI).
        
        Args:
            message: The user's message
        
        Yields:
            Dict events: {"type": "text", "content": "..."} or {"type": "done"}
        """
        try:
            # Get thread and history
            thread = self.thread_manager.get_or_create_thread()
            history = self.thread_manager.get_history_for_groq(limit=20)
            
            # Build messages
            messages = [
                {"role": "system", "content": self.factory.build_system_prompt()}
            ]
            messages.extend(history)
            messages.append({"role": "user", "content": message})
            
            # Get tools
            tools = self.factory.get_tools()
            
            # Stream from Groq
            full_response = ""
            
            for chunk in self._stream_agent_loop(messages, tools):
                if chunk.get("type") == "text":
                    full_response += chunk.get("content", "")
                yield chunk
            
            # Save the turn
            if full_response:
                self.thread_manager.save_turn(message, full_response)
            
            yield {"type": "done", "thread_id": thread.id}
            
        except Exception as e:
            logger.error(f"SousChefService stream error: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}
    
    def _stream_agent_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_iterations: int = 10,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream the agent loop with tool execution.
        
        Yields text chunks and tool events.
        """
        from .tools.loader import execute_tool
        
        context = self.factory.get_context()
        
        for iteration in range(max_iterations):
            # Stream from Groq
            stream = self.groq.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools if tools else None,
                stream=True,
            )
            
            response_text = ""
            tool_calls_data = {}  # Accumulate tool call data
            
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue
                
                # Stream text content
                if delta.content:
                    response_text += delta.content
                    yield {"type": "text", "content": delta.content}
                
                # Accumulate tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": ""
                            }
                        if tc.id:
                            tool_calls_data[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_data[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_data[idx]["arguments"] += tc.function.arguments
            
            # If no tool calls, we're done
            if not tool_calls_data:
                return
            
            # Process tool calls
            yield {"type": "tool_start", "count": len(tool_calls_data)}
            
            # Add assistant message to history
            messages.append({
                "role": "assistant",
                "content": response_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        }
                    }
                    for tc in tool_calls_data.values()
                ]
            })
            
            # Execute tool calls with channel-aware sensitive data handling
            for tc in tool_calls_data.values():
                try:
                    yield {"type": "tool_call", "name": tc["name"]}
                    
                    # Parse arguments
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    
                    # Execute with channel awareness
                    result = execute_tool(
                        tool_name=tc["name"],
                        args=args,
                        chef=context.get("chef"),
                        customer=context.get("customer"),
                        lead=context.get("lead"),
                        channel=self.channel,  # Key: pass channel for sensitive data handling
                    )
                except Exception as e:
                    logger.error(f"Tool error ({tc['name']}): {e}")
                    result = {"status": "error", "message": str(e)}
                
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    "tool_call_id": tc["id"],
                })
                
                yield {"type": "tool_result", "name": tc["name"]}
        
        # Max iterations
        yield {"type": "max_iterations"}
    
    def new_conversation(self) -> Dict[str, Any]:
        """
        Start a new conversation (clear history).
        
        Returns:
            Dict with status and new thread_id
        """
        thread = self.thread_manager.new_conversation()
        return {
            "status": "success",
            "thread_id": thread.id,
            "family_name": thread.family_name,
        }
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get conversation history.
        
        Returns:
            List of message dicts
        """
        return self.thread_manager.get_history()

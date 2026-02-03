# chefs/services/sous_chef/agents_service.py
"""
Sous Chef service using OpenAI Agents SDK.

Drop-in replacement for SousChefService that uses the Agents SDK
with Groq via LiteLLM as the backend.
"""

import logging
from typing import Dict, Any, Optional, Generator

from .agents_factory import AgentsSousChefFactory
from .thread_manager import ThreadManager
from .tools.agents_tools import ToolContext

logger = logging.getLogger(__name__)

# Check if Agents SDK is available
try:
    from agents import Runner
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Runner = None


class AgentsSousChefService:
    """
    Sous Chef service using OpenAI Agents SDK.
    
    This is a drop-in replacement for SousChefService that uses
    the Agents SDK for agent orchestration instead of manual
    Groq API calls.
    
    Usage:
        service = AgentsSousChefService(chef_id=1, channel="telegram")
        result = service.send_message("What orders do I have?")
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
        if not AGENTS_SDK_AVAILABLE:
            raise ImportError(
                "OpenAI Agents SDK not installed. "
                "Run: pip install 'openai-agents[litellm]>=0.6.0'"
            )
        
        self.chef_id = chef_id
        self.channel = channel
        self.family_id = family_id
        self.family_type = family_type
        
        # Initialize factory
        self.factory = AgentsSousChefFactory(
            chef_id=chef_id,
            channel=channel,
            family_id=family_id,
            family_type=family_type,
        )
        
        # Initialize thread manager
        self.thread_manager = ThreadManager(
            chef_id=chef_id,
            family_id=family_id,
            family_type=family_type,
            channel=channel,
        )
        
        # Create agent
        self.agent = self.factory.create_agent()
        
        # Set tool context
        ToolContext.set(
            chef=self.factory.chef,
            customer=self.factory.customer,
            lead=self.factory.lead,
            channel=channel,
        )
    
    def send_message(self, message: str) -> Dict[str, Any]:
        """
        Send a message and get a response (synchronous).
        
        Args:
            message: The user's message
        
        Returns:
            Dict with status, message, and thread_id
        """
        try:
            # Get or create thread
            thread = self.thread_manager.get_or_create_thread()
            
            # Build message with history context
            # TODO: Investigate how to pass history to Agents SDK
            # For now, we include recent history in the message
            history_context = self._get_history_context()
            
            if history_context:
                full_message = f"{history_context}\n\nUser: {message}"
            else:
                full_message = message
            
            # Run agent
            result = Runner.run_sync(self.agent, full_message)
            response = result.final_output or "I processed your request."
            
            # Save turn to thread
            self.thread_manager.save_turn(message, response)
            
            return {
                "status": "success",
                "message": response,
                "thread_id": thread.id,
            }
            
        except Exception as e:
            logger.error(f"AgentsSousChefService error: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "thread_id": getattr(self.thread_manager, 'thread_id', None),
            }
    
    async def send_message_async(self, message: str) -> Dict[str, Any]:
        """
        Send a message and get a response (asynchronous).
        
        Args:
            message: The user's message
        
        Returns:
            Dict with status, message, and thread_id
        """
        try:
            thread = self.thread_manager.get_or_create_thread()
            
            history_context = self._get_history_context()
            if history_context:
                full_message = f"{history_context}\n\nUser: {message}"
            else:
                full_message = message
            
            result = await Runner.run(self.agent, full_message)
            response = result.final_output or "I processed your request."
            
            self.thread_manager.save_turn(message, response)
            
            return {
                "status": "success",
                "message": response,
                "thread_id": thread.id,
            }
            
        except Exception as e:
            logger.error(f"AgentsSousChefService async error: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "thread_id": getattr(self.thread_manager, 'thread_id', None),
            }
    
    def stream_message(self, message: str) -> Generator[Dict[str, Any], None, None]:
        """
        Stream a response (for web UI).
        
        Note: Agents SDK streaming support may be limited.
        Falls back to non-streaming if not available.
        
        Args:
            message: The user's message
        
        Yields:
            Dict events with type and content
        """
        try:
            thread = self.thread_manager.get_or_create_thread()
            
            # Check if streaming is supported
            if hasattr(Runner, 'run_streamed'):
                # Use streaming if available
                history_context = self._get_history_context()
                if history_context:
                    full_message = f"{history_context}\n\nUser: {message}"
                else:
                    full_message = message
                
                # TODO: Implement proper streaming when SDK supports it
                # For now, fall back to sync
                result = Runner.run_sync(self.agent, full_message)
                response = result.final_output or ""
                
                # Simulate streaming by yielding the full response
                yield {"type": "text", "content": response}
                
                self.thread_manager.save_turn(message, response)
                yield {"type": "done", "thread_id": thread.id}
            else:
                # Fallback to sync
                result = self.send_message(message)
                yield {"type": "text", "content": result.get("message", "")}
                yield {"type": "done", "thread_id": result.get("thread_id")}
                
        except Exception as e:
            logger.error(f"AgentsSousChefService stream error: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}
    
    def _get_history_context(self, max_turns: int = 5) -> str:
        """
        Get recent conversation history as context string.
        
        Args:
            max_turns: Maximum conversation turns to include
        
        Returns:
            Formatted history string or empty string
        """
        try:
            history = self.thread_manager.get_history(limit=max_turns * 2)
            
            if not history:
                return ""
            
            # Format as conversation
            lines = ["Recent conversation:"]
            for msg in history[-max_turns * 2:]:
                role = "User" if msg.get("role") == "chef" else "Assistant"
                content = msg.get("content", "")[:500]  # Truncate long messages
                lines.append(f"{role}: {content}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.warning(f"Failed to get history context: {e}")
            return ""
    
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
    
    def get_history(self) -> list:
        """
        Get conversation history.
        
        Returns:
            List of message dicts
        """
        return self.thread_manager.get_history()

# chefs/services/sous_chef/thread_manager.py
"""
Thread management for Sous Chef conversations.

Handles persistence of conversation history using existing Django models.
"""

import logging
from typing import List, Dict, Any, Optional

from django.db import transaction

logger = logging.getLogger(__name__)


class ThreadManager:
    """
    Manages conversation threads for Sous Chef.
    
    Uses existing SousChefThread and SousChefMessage models for persistence.
    """
    
    def __init__(
        self,
        chef_id: int,
        family_id: Optional[int] = None,
        family_type: Optional[str] = None,
        channel: str = "web",
    ):
        self.chef_id = chef_id
        self.family_id = family_id
        self.family_type = family_type
        self.channel = channel
        self._thread = None
    
    def get_or_create_thread(self):
        """
        Get the active thread or create a new one.
        
        Returns:
            SousChefThread instance
        """
        from customer_dashboard.models import SousChefThread
        
        if self._thread is not None:
            return self._thread
        
        # Build filter for finding existing thread
        filter_kwargs = {
            "chef_id": self.chef_id,
            "is_active": True,
        }
        
        if self.family_id and self.family_type:
            filter_kwargs["family_id"] = self.family_id
            filter_kwargs["family_type"] = self.family_type
        else:
            # General mode (no family)
            filter_kwargs["family_id__isnull"] = True
        
        # Try to find existing active thread
        thread = SousChefThread.objects.filter(**filter_kwargs).first()
        
        if thread is None:
            # Create new thread
            thread = SousChefThread.objects.create(
                chef_id=self.chef_id,
                family_id=self.family_id,
                family_type=self.family_type or "customer",
                family_name=self._get_family_name(),
                is_active=True,
            )
            logger.info(f"Created new thread {thread.id} for chef {self.chef_id}")
        
        self._thread = thread
        return thread
    
    def _get_family_name(self) -> str:
        """Get the family name for thread display."""
        if not self.family_id:
            return "General Assistant"
        
        try:
            if self.family_type == "customer":
                from custom_auth.models import CustomUser
                user = CustomUser.objects.get(id=self.family_id)
                return f"{user.first_name} {user.last_name}".strip() or user.username
            elif self.family_type == "lead":
                from crm.models import Lead
                lead = Lead.objects.get(id=self.family_id)
                return f"{lead.first_name} {lead.last_name}".strip()
        except Exception as e:
            logger.warning(f"Could not get family name: {e}")
        
        return f"Family {self.family_id}"
    
    def save_message(self, role: str, content: str) -> None:
        """
        Save a message to the thread.
        
        Args:
            role: 'chef' or 'assistant'
            content: Message content
        """
        from customer_dashboard.models import SousChefMessage
        
        thread = self.get_or_create_thread()
        
        SousChefMessage.objects.create(
            thread=thread,
            role=role,
            content=content,
        )
    
    def save_turn(self, user_message: str, assistant_message: str) -> None:
        """
        Save a complete conversation turn.
        
        Args:
            user_message: The chef's message
            assistant_message: The assistant's response
        """
        with transaction.atomic():
            self.save_message("chef", user_message)
            self.save_message("assistant", assistant_message)
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get conversation history for context.
        
        Args:
            limit: Max number of messages to retrieve
        
        Returns:
            List of {"role": str, "content": str} dicts
        """
        thread = self.get_or_create_thread()
        
        messages = thread.messages.order_by('created_at')
        
        if limit:
            # Get last N messages
            messages = messages.order_by('-created_at')[:limit]
            messages = reversed(list(messages))
        
        history = []
        for msg in messages:
            # Map 'chef' role to 'user' for LLM format
            role = "user" if msg.role == "chef" else "assistant"
            history.append({
                "role": role,
                "content": msg.content,
            })
        
        return history
    
    def get_history_for_groq(self, limit: Optional[int] = 20) -> List[Dict[str, str]]:
        """
        Get history formatted for Groq chat completions.
        
        Args:
            limit: Max messages to include (default 20)
        
        Returns:
            List ready for Groq messages parameter
        """
        return self.get_history(limit=limit)
    
    def clear_history(self) -> None:
        """Clear the current thread's history (start fresh)."""
        thread = self.get_or_create_thread()
        thread.messages.all().delete()
        logger.info(f"Cleared history for thread {thread.id}")
    
    def new_conversation(self) -> "SousChefThread":
        """
        Start a new conversation (deactivate old, create new).
        
        Returns:
            New SousChefThread instance
        """
        from customer_dashboard.models import SousChefThread
        
        # Deactivate any existing active threads
        filter_kwargs = {
            "chef_id": self.chef_id,
            "is_active": True,
        }
        
        if self.family_id and self.family_type:
            filter_kwargs["family_id"] = self.family_id
            filter_kwargs["family_type"] = self.family_type
        else:
            filter_kwargs["family_id__isnull"] = True
        
        SousChefThread.objects.filter(**filter_kwargs).update(is_active=False)
        
        # Reset cached thread
        self._thread = None
        
        # Create new thread
        return self.get_or_create_thread()
    
    @property
    def thread_id(self) -> Optional[int]:
        """Get current thread ID if exists."""
        if self._thread:
            return self._thread.id
        return None

# chefs/services/sous_chef/tests/test_thread_manager.py
"""Tests for conversation thread management."""
import pytest
from django.test import TestCase


@pytest.mark.django_db
class TestThreadManagerInit:
    """Test ThreadManager initialization."""
    
    def test_initializes_with_chef_id(self, test_chef):
        """Should initialize with chef_id."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        
        assert manager.chef_id == test_chef.id
        assert manager.channel == "telegram"
    
    def test_initializes_with_family_context(self, test_chef, test_customer):
        """Should initialize with family context."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(
            chef_id=test_chef.id,
            family_id=test_customer.id,
            family_type="customer",
            channel="web",
        )
        
        assert manager.family_id == test_customer.id
        assert manager.family_type == "customer"


@pytest.mark.django_db
class TestGetOrCreateThread:
    """Test thread creation and retrieval."""
    
    def test_creates_new_thread(self, test_chef):
        """Should create thread if none exists."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        from customer_dashboard.models import SousChefThread
        
        initial_count = SousChefThread.objects.count()
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        thread = manager.get_or_create_thread()
        
        assert thread is not None
        assert thread.chef_id == test_chef.id
        assert thread.is_active is True
        assert SousChefThread.objects.count() == initial_count + 1
    
    def test_returns_existing_thread(self, test_chef):
        """Should return existing active thread."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        thread1 = manager.get_or_create_thread()
        thread2 = manager.get_or_create_thread()
        
        assert thread1.id == thread2.id
    
    def test_separate_threads_for_different_families(self, test_chef, test_customer):
        """Should create separate threads for different families."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        # General mode
        manager1 = ThreadManager(chef_id=test_chef.id, channel="telegram")
        thread1 = manager1.get_or_create_thread()
        
        # Family mode
        manager2 = ThreadManager(
            chef_id=test_chef.id,
            family_id=test_customer.id,
            family_type="customer",
            channel="telegram",
        )
        thread2 = manager2.get_or_create_thread()
        
        assert thread1.id != thread2.id
    
    def test_thread_has_family_name(self, test_chef):
        """Thread should have a family name."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        thread = manager.get_or_create_thread()
        
        assert thread.family_name is not None
        # General mode should say "General Assistant"
        assert "General" in thread.family_name or "Assistant" in thread.family_name


@pytest.mark.django_db
class TestSaveMessage:
    """Test message saving."""
    
    def test_save_message_creates_record(self, test_chef):
        """save_message should create a message record."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        from customer_dashboard.models import SousChefMessage
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        thread = manager.get_or_create_thread()
        
        manager.save_message("chef", "Hello")
        
        message = SousChefMessage.objects.filter(thread=thread, role="chef").first()
        assert message is not None
        assert message.content == "Hello"
    
    def test_save_turn_creates_both_messages(self, test_chef):
        """save_turn should create chef and assistant messages."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        from customer_dashboard.models import SousChefMessage
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        thread = manager.get_or_create_thread()
        
        manager.save_turn("Hello!", "Hi there, how can I help?")
        
        messages = SousChefMessage.objects.filter(thread=thread)
        assert messages.count() == 2
        assert messages.filter(role="chef", content="Hello!").exists()
        assert messages.filter(role="assistant", content="Hi there, how can I help?").exists()


@pytest.mark.django_db
class TestGetHistory:
    """Test history retrieval."""
    
    def test_get_history_returns_messages(self, test_chef):
        """get_history should return conversation messages."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        manager.save_turn("First", "Response 1")
        manager.save_turn("Second", "Response 2")
        
        history = manager.get_history()
        
        assert len(history) == 4
    
    def test_get_history_maps_roles(self, test_chef):
        """get_history should map 'chef' to 'user'."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        manager.save_turn("Hello", "Hi there")
        
        history = manager.get_history()
        
        # First message should be user (chef)
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        
        # Second should be assistant
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there"
    
    def test_get_history_with_limit(self, test_chef):
        """get_history should respect limit."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        for i in range(10):
            manager.save_turn(f"Msg {i}", f"Response {i}")
        
        history = manager.get_history(limit=4)
        
        assert len(history) == 4
    
    def test_get_history_for_groq(self, test_chef):
        """get_history_for_groq should return properly formatted messages."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        manager.save_turn("Test message", "Test response")
        
        history = manager.get_history_for_groq()
        
        assert all("role" in msg and "content" in msg for msg in history)


@pytest.mark.django_db
class TestNewConversation:
    """Test starting new conversations."""
    
    def test_new_conversation_deactivates_old(self, test_chef):
        """new_conversation should deactivate existing thread."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        from customer_dashboard.models import SousChefThread
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        old_thread = manager.get_or_create_thread()
        old_id = old_thread.id
        
        new_thread = manager.new_conversation()
        
        assert new_thread.id != old_id
        
        old_thread.refresh_from_db()
        assert old_thread.is_active is False
    
    def test_new_conversation_creates_fresh_thread(self, test_chef):
        """new_conversation should create a fresh active thread."""
        from chefs.services.sous_chef.thread_manager import ThreadManager
        
        manager = ThreadManager(chef_id=test_chef.id, channel="telegram")
        manager.get_or_create_thread()
        manager.save_turn("Old message", "Old response")
        
        new_thread = manager.new_conversation()
        
        assert new_thread.is_active is True
        assert new_thread.messages.count() == 0

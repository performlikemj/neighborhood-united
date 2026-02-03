# chefs/services/sous_chef/tests/test_service.py
"""Tests for SousChefService."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestSousChefServiceInit:
    """Test service initialization."""
    
    def test_initializes_with_chef_id(self, test_chef):
        """Service should initialize with chef_id."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        
        assert service.chef_id == test_chef.id
        assert service.channel == "telegram"
    
    def test_initializes_factory(self, test_chef):
        """Service should create factory."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        
        assert service.factory is not None
        assert service.factory.chef_id == test_chef.id
    
    def test_initializes_thread_manager(self, test_chef):
        """Service should create thread manager."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        
        assert service.thread_manager is not None


@pytest.mark.django_db
class TestSendMessage:
    """Test send_message method."""
    
    def test_returns_dict(self, test_chef, mock_groq):
        """send_message should return a dict."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        result = service.send_message("Hello")
        
        assert isinstance(result, dict)
    
    def test_returns_success_status(self, test_chef, mock_groq):
        """send_message should return success status."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        result = service.send_message("Hello")
        
        assert result["status"] == "success"
    
    def test_returns_message_content(self, test_chef, mock_groq):
        """send_message should return message content."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        result = service.send_message("Hello")
        
        assert "message" in result
        assert len(result["message"]) > 0
    
    def test_returns_thread_id(self, test_chef, mock_groq):
        """send_message should return thread_id."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        result = service.send_message("Hello")
        
        assert "thread_id" in result
        assert result["thread_id"] is not None
    
    def test_saves_conversation(self, test_chef, mock_groq):
        """send_message should save conversation to thread."""
        from chefs.services.sous_chef import SousChefService
        from customer_dashboard.models import SousChefMessage
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        result = service.send_message("Test message")
        
        # Check messages were saved
        thread_id = result["thread_id"]
        messages = SousChefMessage.objects.filter(thread_id=thread_id)
        
        assert messages.count() >= 2
        assert messages.filter(role="chef").exists()
        assert messages.filter(role="assistant").exists()
    
    def test_uses_correct_channel(self, test_chef):
        """send_message should use channel-specific tools."""
        from chefs.services.sous_chef import SousChefService
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test"
            mock_response.choices[0].message.tool_calls = None
            mock_groq.chat.completions.create.return_value = mock_response
            
            service = SousChefService(chef_id=test_chef.id, channel="telegram")
            service.send_message("Hello")
            
            # Check that Groq was called
            mock_groq.chat.completions.create.assert_called_once()
            
            # Get the tools passed
            call_args = mock_groq.chat.completions.create.call_args
            tools = call_args.kwargs.get("tools") or call_args[1].get("tools")
            
            if tools:
                tool_names = [
                    t.get("name") or t.get("function", {}).get("name")
                    for t in tools
                ]
                # Navigation tools should not be present
                assert "navigate_to_dashboard_tab" not in tool_names


@pytest.mark.django_db
class TestSendMessageErrorHandling:
    """Test error handling in send_message."""
    
    def test_handles_groq_error(self, test_chef):
        """send_message should handle Groq errors gracefully."""
        from chefs.services.sous_chef import SousChefService
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            mock_groq.chat.completions.create.side_effect = Exception("API Error")
            
            service = SousChefService(chef_id=test_chef.id, channel="telegram")
            result = service.send_message("Hello")
            
            assert result["status"] == "error"
            assert "message" in result
    
    def test_handles_empty_response(self, test_chef):
        """send_message should handle empty responses."""
        from chefs.services.sous_chef import SousChefService
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            mock_response = MagicMock()
            mock_response.choices = []
            mock_groq.chat.completions.create.return_value = mock_response
            
            service = SousChefService(chef_id=test_chef.id, channel="telegram")
            result = service.send_message("Hello")
            
            # Should not crash
            assert "status" in result


@pytest.mark.django_db
class TestToolExecution:
    """Test tool call handling."""
    
    def test_executes_tool_calls(self, test_chef, mock_groq_with_tool_call):
        """send_message should execute tool calls."""
        from chefs.services.sous_chef import SousChefService
        
        with patch("meals.sous_chef_tools.handle_sous_chef_tool_call") as mock_handler:
            mock_handler.return_value = {"orders": []}
            
            service = SousChefService(chef_id=test_chef.id, channel="telegram")
            result = service.send_message("What orders do I have?")
            
            # Tool should have been called
            mock_handler.assert_called()
    
    def test_handles_tool_errors(self, test_chef):
        """send_message should handle tool execution errors."""
        from chefs.services.sous_chef import SousChefService
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            
            # First call returns tool call
            tool_response = MagicMock()
            tool_response.choices = [MagicMock()]
            tool_response.choices[0].message.content = ""
            tool_response.choices[0].message.tool_calls = [MagicMock()]
            tool_response.choices[0].message.tool_calls[0].id = "call_123"
            tool_response.choices[0].message.tool_calls[0].function.name = "get_orders"
            tool_response.choices[0].message.tool_calls[0].function.arguments = "{}"
            
            # Second call returns final response
            final_response = MagicMock()
            final_response.choices = [MagicMock()]
            final_response.choices[0].message.content = "Done"
            final_response.choices[0].message.tool_calls = None
            
            mock_groq.chat.completions.create.side_effect = [tool_response, final_response]
            
            with patch("meals.sous_chef_tools.handle_sous_chef_tool_call") as mock_handler:
                mock_handler.side_effect = Exception("Tool error")
                
                service = SousChefService(chef_id=test_chef.id, channel="telegram")
                result = service.send_message("Get orders")
                
                # Should still return a response (with error handled)
                assert "status" in result


@pytest.mark.django_db
class TestNewConversation:
    """Test new_conversation method."""
    
    def test_returns_new_thread_id(self, test_chef, mock_groq):
        """new_conversation should return new thread info."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        
        # Start a conversation
        service.send_message("Hello")
        old_thread_id = service.thread_manager.thread_id
        
        # Start new conversation
        result = service.new_conversation()
        
        assert result["status"] == "success"
        assert result["thread_id"] != old_thread_id


@pytest.mark.django_db
class TestGetHistory:
    """Test get_history method."""
    
    def test_returns_list(self, test_chef, mock_groq):
        """get_history should return a list."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        service.send_message("Hello")
        
        history = service.get_history()
        
        assert isinstance(history, list)
    
    def test_contains_messages(self, test_chef, mock_groq):
        """get_history should contain sent messages."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        service.send_message("Test message")
        
        history = service.get_history()
        
        assert len(history) >= 2
        contents = [msg["content"] for msg in history]
        assert "Test message" in contents

# chefs/services/sous_chef/tests/test_telegram_integration.py
"""End-to-end tests for Telegram integration."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestProcessChefMessage:
    """Test process_chef_message function."""
    
    def test_returns_string(self, test_chef, mock_groq):
        """process_chef_message should return a string."""
        from chefs.tasks.telegram_tasks import process_chef_message
        
        result = process_chef_message(test_chef, "Hello")
        
        assert isinstance(result, str)
    
    def test_returns_response_content(self, test_chef):
        """process_chef_message should return AI response."""
        from chefs.tasks.telegram_tasks import process_chef_message
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Hello, Chef! I can help you."
            mock_response.choices[0].message.tool_calls = None
            mock_groq.chat.completions.create.return_value = mock_response
            
            result = process_chef_message(test_chef, "Hi")
            
            assert "Hello, Chef!" in result
    
    def test_uses_telegram_channel(self, test_chef):
        """process_chef_message should use telegram channel."""
        from chefs.tasks.telegram_tasks import process_chef_message
        
        with patch("chefs.services.sous_chef.SousChefService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.send_message.return_value = {
                "status": "success",
                "message": "Test response"
            }
            mock_service_class.return_value = mock_service
            
            process_chef_message(test_chef, "Hello")
            
            # Verify channel was set to telegram
            mock_service_class.assert_called_once()
            call_kwargs = mock_service_class.call_args.kwargs
            assert call_kwargs.get("channel") == "telegram"
    
    def test_handles_error_gracefully(self, test_chef):
        """process_chef_message should handle errors."""
        from chefs.tasks.telegram_tasks import process_chef_message
        
        with patch("chefs.services.sous_chef.SousChefService") as mock_service_class:
            mock_service_class.side_effect = Exception("Service error")
            
            result = process_chef_message(test_chef, "Hello")
            
            # Should return error message, not crash
            assert isinstance(result, str)
            assert "sorry" in result.lower() or "wrong" in result.lower()


@pytest.mark.django_db
class TestTelegramToolFiltering:
    """Test that Telegram excludes navigation tools."""
    
    def test_telegram_service_excludes_navigation(self, test_chef):
        """Telegram service should exclude navigation tools."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        tools = service.factory.get_tools()
        
        tool_names = [t.get("name") or t.get("function", {}).get("name") for t in tools]
        
        # Navigation tools should be excluded
        assert "navigate_to_dashboard_tab" not in tool_names
        assert "prefill_form" not in tool_names
        assert "scaffold_meal" not in tool_names
    
    def test_telegram_has_core_tools(self, test_chef):
        """Telegram service should have core tools."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        tools = service.factory.get_tools()
        
        tool_names = [t.get("name") or t.get("function", {}).get("name") for t in tools]
        
        # Core tools should be present
        assert "get_family_dietary_summary" in tool_names
        assert "search_chef_dishes" in tool_names
    
    def test_web_vs_telegram_tool_count(self, test_chef):
        """Web should have more tools than Telegram."""
        from chefs.services.sous_chef import SousChefService
        
        web_service = SousChefService(chef_id=test_chef.id, channel="web")
        telegram_service = SousChefService(chef_id=test_chef.id, channel="telegram")
        
        web_tools = web_service.factory.get_tools()
        telegram_tools = telegram_service.factory.get_tools()
        
        assert len(web_tools) > len(telegram_tools)


@pytest.mark.django_db
class TestTelegramPrompt:
    """Test Telegram-specific prompts."""
    
    def test_telegram_prompt_mentions_constraints(self, test_chef):
        """Telegram prompt should mention navigation constraints."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        prompt = service.factory.build_system_prompt()
        
        prompt_lower = prompt.lower()
        
        # Should mention Telegram
        assert "telegram" in prompt_lower
        
        # Should mention navigation constraints
        assert "cannot" in prompt_lower or "can't" in prompt_lower
    
    def test_telegram_prompt_mentions_security(self, test_chef):
        """Telegram prompt should warn about sensitive data."""
        from chefs.services.sous_chef import SousChefService
        
        service = SousChefService(chef_id=test_chef.id, channel="telegram")
        prompt = service.factory.build_system_prompt()
        
        prompt_lower = prompt.lower()
        
        # Should mention security concerns
        has_security = any(word in prompt_lower for word in [
            "sensitive", "health", "never", "security", "allerg"
        ])
        assert has_security


@pytest.mark.django_db
class TestFullWebhookFlow:
    """Test complete webhook → response flow."""
    
    def test_webhook_processes_message(self, test_chef, telegram_link):
        """Webhook should process message and send response."""
        from chefs.tasks.telegram_tasks import process_telegram_update
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "I can help with that!"
            mock_response.choices[0].message.tool_calls = None
            mock_groq.chat.completions.create.return_value = mock_response
            
            with patch("chefs.tasks.telegram_tasks.send_telegram_message") as mock_send:
                mock_send.return_value = True
                
                # Simulate webhook update
                update = {
                    "update_id": 123,
                    "message": {
                        "message_id": 1,
                        "from": {
                            "id": telegram_link.telegram_user_id,
                            "first_name": "Test"
                        },
                        "chat": {"id": telegram_link.telegram_user_id},
                        "text": "What can you help me with?"
                    }
                }
                
                process_telegram_update(update)
                
                # Verify send_telegram_message was called
                mock_send.assert_called_once()
                call_args = mock_send.call_args[0]
                assert call_args[0] == telegram_link.telegram_user_id  # chat_id
                assert "help" in call_args[1].lower()  # response contains "help"
    
    def test_webhook_handles_unknown_user(self):
        """Webhook should handle unknown Telegram users."""
        from chefs.tasks.telegram_tasks import process_telegram_update
        
        with patch("chefs.tasks.telegram_tasks.send_telegram_message") as mock_send:
            mock_send.return_value = True
            
            # Unknown user
            update = {
                "update_id": 123,
                "message": {
                    "message_id": 1,
                    "from": {"id": 99999, "first_name": "Unknown"},
                    "chat": {"id": 99999},
                    "text": "Hello"
                }
            }
            
            process_telegram_update(update)
            
            # Should send "not recognized" message
            mock_send.assert_called_once()
            response_text = mock_send.call_args[0][1]
            assert "recognize" in response_text.lower() or "connect" in response_text.lower()


@pytest.mark.django_db
class TestConversationPersistence:
    """Test that Telegram conversations are persisted."""
    
    def test_messages_saved_to_thread(self, test_chef, mock_groq):
        """Telegram messages should be saved to thread."""
        from chefs.tasks.telegram_tasks import process_chef_message
        from customer_dashboard.models import SousChefThread, SousChefMessage
        
        process_chef_message(test_chef, "First message")
        process_chef_message(test_chef, "Second message")
        
        # Find the thread
        thread = SousChefThread.objects.filter(
            chef_id=test_chef.id,
            is_active=True
        ).first()
        
        assert thread is not None
        
        # Check messages
        messages = SousChefMessage.objects.filter(thread=thread)
        assert messages.count() >= 4  # 2 user + 2 assistant
    
    def test_conversation_context_maintained(self, test_chef):
        """Conversation context should be maintained across messages."""
        from chefs.tasks.telegram_tasks import process_chef_message
        
        with patch("chefs.services.sous_chef.service.Groq") as mock_groq_class:
            mock_groq = MagicMock()
            mock_groq_class.return_value = mock_groq
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.choices[0].message.tool_calls = None
            mock_groq.chat.completions.create.return_value = mock_response
            
            # Send two messages
            process_chef_message(test_chef, "First message")
            process_chef_message(test_chef, "Second message")
            
            # Check that second call included history
            calls = mock_groq.chat.completions.create.call_args_list
            assert len(calls) >= 2
            
            # Second call should have more messages (includes history)
            second_call_messages = calls[1].kwargs.get("messages") or calls[1][1].get("messages")
            assert len(second_call_messages) > 2  # More than just system + user

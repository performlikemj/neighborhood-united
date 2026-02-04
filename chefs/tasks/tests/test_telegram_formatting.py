# chefs/tasks/tests/test_telegram_formatting.py
"""
Tests for Telegram message formatting.

Ensures markdown-to-HTML conversion works reliably
and doesn't cause Telegram API 400 errors.
"""

import pytest


class TestMarkdownToTelegramHtml:
    """Test markdown_to_telegram_html conversion."""
    
    def test_bold_double_asterisk(self):
        """**bold** converts to <b>bold</b>."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("This is **bold** text")
        assert result == "This is <b>bold</b> text"
    
    def test_bold_single_asterisk(self):
        """*bold* converts to <b>bold</b>."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("This is *bold* text")
        assert result == "This is <b>bold</b> text"
    
    def test_italic_underscore(self):
        """_italic_ converts to <i>italic</i>."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("This is _italic_ text")
        assert result == "This is <i>italic</i> text"
    
    def test_inline_code(self):
        """`code` converts to <code>code</code>."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("Use `print()` function")
        assert result == "Use <code>print()</code> function"
    
    def test_headers_to_bold(self):
        """# Header converts to <b>Header</b>."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("# Main Title\nSome text")
        assert "<b>Main Title</b>" in result
        assert "Some text" in result
    
    def test_h2_headers(self):
        """## Header also converts to bold."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("## Section\nContent")
        assert "<b>Section</b>" in result
    
    def test_special_chars_preserved(self):
        """Special chars like ! . - $ are preserved."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("Price: $10.99! Great deal - buy now.")
        assert "Price: $10.99! Great deal - buy now." == result
    
    def test_html_entities_escaped(self):
        """< > & are escaped to prevent HTML injection."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("Use <script> & 5 > 3")
        assert "&lt;script&gt;" in result
        assert "&amp;" in result
        assert "5 &gt; 3" in result
    
    def test_unbalanced_asterisk_safe(self):
        """Unbalanced * doesn't break output."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        # Should not crash or produce broken HTML
        result = markdown_to_telegram_html("Rating: 4* hotel")
        assert "Rating:" in result
        assert "hotel" in result
    
    def test_mixed_formatting(self):
        """Mixed **bold** and _italic_ work together."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("**Bold** and _italic_ text")
        assert "<b>Bold</b>" in result
        assert "<i>italic</i>" in result
    
    def test_code_block_stripped(self):
        """```code blocks``` are converted to plain text."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("```python\nprint('hi')\n```")
        assert "print('hi')" in result
        assert "```" not in result
    
    def test_empty_string(self):
        """Empty string returns empty string."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("")
        assert result == ""
    
    def test_none_returns_empty(self):
        """None returns empty string."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html(None)
        assert result == ""
    
    def test_table_to_list(self):
        """Markdown tables convert to bullet lists."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        table = """| Day | Meal |
|-----|------|
| Mon | Pasta |
| Tue | Salad |"""
        
        result = markdown_to_telegram_html(table)
        
        # Should have bullet points, not pipes
        assert "|" not in result or "• " in result
        assert "Pasta" in result
        assert "Salad" in result
    
    def test_horizontal_rule_removed(self):
        """--- horizontal rules are removed."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        result = markdown_to_telegram_html("Above\n---\nBelow")
        assert "---" not in result
        assert "Above" in result
        assert "Below" in result
    
    def test_real_sous_chef_response(self):
        """Real-world Sous Chef response converts cleanly."""
        from chefs.tasks.telegram_tasks import markdown_to_telegram_html
        
        response = """**Weekly Meal Plan**

Here are some suggestions for the week:

| Day | Meal |
|-----|------|
| Monday | Grilled Chicken |
| Tuesday | Pasta Primavera |

_Note: Check dietary restrictions!_

Let me know if you'd like changes."""
        
        result = markdown_to_telegram_html(response)
        
        # Should have HTML formatting
        assert "<b>Weekly Meal Plan</b>" in result
        assert "<i>Note: Check dietary restrictions!</i>" in result
        # Table should be converted
        assert "Grilled Chicken" in result
        # No raw markdown leftovers that would break Telegram
        assert "**" not in result
        assert "_Note" not in result  # underscore should be converted


class TestSendTelegramMessage:
    """Test send_telegram_message uses HTML correctly."""
    
    def test_default_parse_mode_is_html(self):
        """send_telegram_message should default to HTML parse mode."""
        from chefs.tasks.telegram_tasks import send_telegram_message
        from unittest.mock import patch, MagicMock
        
        # Create a mock settings object with TELEGRAM_BOT_TOKEN
        mock_settings = MagicMock()
        mock_settings.TELEGRAM_BOT_TOKEN = 'test-token-123'
        
        with patch("chefs.tasks.telegram_tasks.settings", mock_settings):
            with patch("chefs.tasks.telegram_tasks.requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response
                
                send_telegram_message(123, "**test**")
                
                # Check the payload
                mock_post.assert_called_once()
                call_kwargs = mock_post.call_args
                payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
                
                assert payload["parse_mode"] == "HTML"
                assert "<b>test</b>" in payload["text"]

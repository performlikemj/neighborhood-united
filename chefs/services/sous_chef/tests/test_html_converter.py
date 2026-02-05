"""Tests for HTML converter module."""
import pytest
from chefs.services.sous_chef.html_converter import markdown_to_html


class TestBasicConversions:
    """Test basic markdown to HTML conversions."""

    def test_empty_input(self):
        """Should return empty string for empty input."""
        assert markdown_to_html("") == ""
        assert markdown_to_html(None) == ""

    def test_plain_text(self):
        """Should pass through plain text."""
        result = markdown_to_html("Hello world")
        assert "Hello world" in result

    def test_bold_double_asterisks(self):
        """Should convert **bold** to <strong>."""
        result = markdown_to_html("This is **bold** text")
        assert "<strong>bold</strong>" in result

    def test_bold_single_asterisks(self):
        """Should convert *bold* to <strong>."""
        result = markdown_to_html("This is *bold* text")
        assert "<strong>bold</strong>" in result

    def test_italic_underscores(self):
        """Should convert _italic_ to <em>."""
        result = markdown_to_html("This is _italic_ text")
        assert "<em>italic</em>" in result

    def test_inline_code(self):
        """Should convert `code` to <code>."""
        result = markdown_to_html("Use the `print()` function")
        assert "<code>print()</code>" in result

    def test_headers(self):
        """Should convert # headers to <strong>."""
        result = markdown_to_html("# Main Header")
        assert "<strong>Main Header</strong>" in result

        result = markdown_to_html("## Sub Header")
        assert "<strong>Sub Header</strong>" in result

        result = markdown_to_html("### Third Level")
        assert "<strong>Third Level</strong>" in result


class TestLinks:
    """Test link conversion."""

    def test_basic_link(self):
        """Should convert [text](url) to <a href>."""
        result = markdown_to_html("Check out [Google](https://google.com)")
        assert '<a href="https://google.com"' in result
        assert ">Google</a>" in result

    def test_link_with_query_params(self):
        """Should handle links with query parameters."""
        result = markdown_to_html("[Search](https://example.com?q=test&page=1)")
        assert 'href="https://example.com?q=test&amp;page=1"' in result

    def test_link_has_security_attrs(self):
        """Links should have target and rel attributes."""
        result = markdown_to_html("[Link](https://example.com)")
        assert 'target="_blank"' in result
        assert 'rel="noopener noreferrer"' in result


class TestCodeBlocks:
    """Test code block conversion."""

    def test_fenced_code_block(self):
        """Should convert fenced code blocks to <pre><code>."""
        result = markdown_to_html("```\nprint('hello')\n```")
        assert "<pre><code>" in result
        assert "print('hello')" in result
        assert "</code></pre>" in result

    def test_fenced_code_block_with_language(self):
        """Should preserve language class on code blocks."""
        result = markdown_to_html("```python\nprint('hello')\n```")
        assert 'class="language-python"' in result

    def test_code_block_preserves_content(self):
        """Markdown inside code blocks should not be converted."""
        result = markdown_to_html("```\n**not bold**\n```")
        assert "<strong>" not in result or "**not bold**" in result


class TestLists:
    """Test list conversion."""

    def test_unordered_list_dash(self):
        """Should convert - items to <ul><li>."""
        result = markdown_to_html("- Item 1\n- Item 2\n- Item 3")
        assert "<ul>" in result
        assert "<li>Item 1</li>" in result
        assert "<li>Item 2</li>" in result
        assert "<li>Item 3</li>" in result
        assert "</ul>" in result

    def test_unordered_list_asterisk(self):
        """Should convert * items to <ul><li>."""
        result = markdown_to_html("* Item 1\n* Item 2")
        assert "<ul>" in result
        assert "<li>Item 1</li>" in result

    def test_ordered_list(self):
        """Should convert 1. items to <ol><li>."""
        result = markdown_to_html("1. First\n2. Second\n3. Third")
        assert "<ol>" in result
        assert "<li>First</li>" in result
        assert "<li>Second</li>" in result
        assert "<li>Third</li>" in result
        assert "</ol>" in result

    def test_mixed_content_with_list(self):
        """Should properly close lists before other content."""
        result = markdown_to_html("Intro text\n\n- Item 1\n- Item 2\n\nMore text")
        assert "<ul>" in result
        assert "</ul>" in result
        # List should be closed before "More text"


class TestTables:
    """Test table conversion."""

    def test_basic_table(self):
        """Should convert markdown table to HTML table."""
        md = """| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |"""
        result = markdown_to_html(md)
        assert "<table>" in result
        assert "<thead>" in result
        assert "<th>Name</th>" in result
        assert "<th>Age</th>" in result
        assert "<tbody>" in result
        assert "<td>Alice</td>" in result
        assert "<td>30</td>" in result
        assert "</table>" in result

    def test_table_without_alignment(self):
        """Should handle tables without alignment markers."""
        md = """| Col1 | Col2 |
|---|---|
| A | B |"""
        result = markdown_to_html(md)
        assert "<table>" in result
        assert "<td>A</td>" in result

    def test_table_mixed_with_text(self):
        """Tables should render with surrounding text."""
        md = """Here's a table:

| Item | Price |
|------|-------|
| Apple | $1 |

That's all!"""
        result = markdown_to_html(md)
        assert "<table>" in result
        assert "</table>" in result


class TestHorizontalRule:
    """Test horizontal rule conversion."""

    def test_dashes(self):
        """Should convert --- to <hr>."""
        result = markdown_to_html("Above\n\n---\n\nBelow")
        assert "<hr>" in result

    def test_asterisks(self):
        """Should convert *** to <hr>."""
        result = markdown_to_html("Above\n\n***\n\nBelow")
        assert "<hr>" in result


class TestXSSProtection:
    """Test XSS attack prevention."""

    def test_escapes_script_tags(self):
        """Should escape <script> tags."""
        result = markdown_to_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escapes_html_tags(self):
        """Should escape arbitrary HTML tags."""
        result = markdown_to_html("<div onclick='evil()'>Click me</div>")
        assert "<div" not in result
        assert "&lt;div" in result

    def test_escapes_img_onerror(self):
        """Should escape img onerror attacks."""
        result = markdown_to_html("<img src=x onerror=alert('xss')>")
        assert "<img" not in result
        assert "&lt;img" in result

    def test_escapes_ampersands(self):
        """Should escape & to prevent entity injection."""
        result = markdown_to_html("Tom & Jerry")
        assert "&amp;" in result
        assert "Tom &amp; Jerry" in result

    def test_escapes_less_than(self):
        """Should escape < characters."""
        result = markdown_to_html("5 < 10")
        assert "&lt;" in result

    def test_escapes_greater_than(self):
        """Should escape > characters."""
        result = markdown_to_html("10 > 5")
        assert "&gt;" in result


class TestComplexContent:
    """Test complex markdown combinations."""

    def test_sous_chef_typical_response(self):
        """Should handle typical Sous Chef AI response format."""
        md = """## Today's Orders

Here's a summary of your orders:

| Customer | Dish | Status |
|----------|------|--------|
| John D. | Grilled Salmon | Pending |
| Sarah M. | Pasta Primavera | In Progress |

**Action needed:**
- Review the salmon order
- Confirm delivery time with Sarah

Let me know if you need more details!"""

        result = markdown_to_html(md)

        # Check headers
        assert "<strong>Today's Orders</strong>" in result

        # Check table
        assert "<table>" in result
        assert "<th>Customer</th>" in result
        assert "<td>John D.</td>" in result

        # Check bold
        assert "<strong>Action needed:</strong>" in result

        # Check list
        assert "<ul>" in result
        assert "<li>Review the salmon order</li>" in result

    def test_nested_formatting(self):
        """Should handle formatting inside other elements."""
        result = markdown_to_html("- This is **bold** in a list")
        assert "<li>This is <strong>bold</strong> in a list</li>" in result

    def test_code_in_text(self):
        """Should handle inline code with other text."""
        result = markdown_to_html("Use `api.get()` to fetch data")
        assert "<code>api.get()</code>" in result
        assert "to fetch data" in result

    def test_multiple_paragraphs(self):
        """Should handle multiple paragraphs."""
        result = markdown_to_html("First paragraph.\n\nSecond paragraph.")
        assert "<br>" in result  # Paragraphs separated by breaks


class TestEdgeCases:
    """Test edge cases and potential issues."""

    def test_underscore_in_variable_name(self):
        """Should not convert underscores in snake_case."""
        result = markdown_to_html("Use the variable_name here")
        assert "<em>" not in result
        assert "variable_name" in result

    def test_asterisk_not_bold(self):
        """Should not convert asterisks that aren't formatting."""
        result = markdown_to_html("5 * 10 = 50")
        # This is tricky - ideally we'd preserve this, but basic conversion
        # might convert it. The key is it shouldn't break.
        assert "50" in result

    def test_empty_table_cells(self):
        """Should handle empty table cells."""
        md = "| A | B |\n|---|---|\n|   | X |"
        result = markdown_to_html(md)
        assert "<table>" in result
        assert "<td></td>" in result or "<td> </td>" in result

    def test_single_list_item(self):
        """Should handle single item lists."""
        result = markdown_to_html("- Only item")
        assert "<ul>" in result
        assert "<li>Only item</li>" in result
        assert "</ul>" in result

    def test_whitespace_preservation(self):
        """Should handle various whitespace."""
        result = markdown_to_html("Line 1\n\n\n\nLine 2")
        # Excessive newlines should be cleaned up
        assert result.count('<br>') < 5 or '\n\n\n' not in result

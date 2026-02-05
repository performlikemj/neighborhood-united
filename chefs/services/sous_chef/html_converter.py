"""
HTML Converter for Sous Chef AI responses.

Converts markdown output from the LLM to HTML for rendering on all clients
(web, iOS, Android). This approach keeps the LLM outputting markdown (more
reliable) while providing HTML for richer display.

Based on patterns from telegram_tasks.py but outputs full HTML tags instead
of Telegram-specific subset.
"""
import re
from typing import List, Tuple


def markdown_to_html(text: str) -> str:
    """
    Convert GitHub-flavored Markdown to HTML.

    This function:
    - Escapes HTML entities first (XSS protection)
    - Converts **bold** to <strong>bold</strong>
    - Converts _italic_ to <em>italic</em>
    - Converts `code` to <code>code</code>
    - Converts ```code blocks``` to <pre><code>...</code></pre>
    - Converts # Headers to <strong>Header</strong> (keeps inline with chat UI)
    - Converts - items to <ul><li>items</li></ul>
    - Converts 1. items to <ol><li>items</li></ol>
    - Converts [text](url) to <a href="url">text</a>
    - Converts markdown tables to HTML <table>
    - Converts --- to <hr>

    Args:
        text: GitHub-flavored markdown text

    Returns:
        HTML string safe for rendering
    """
    if not text:
        return ""

    result = text

    # Step 1: Escape HTML entities FIRST (before we add our own HTML tags)
    # This prevents XSS attacks from user input that might be echoed back
    result = result.replace('&', '&amp;')
    result = result.replace('<', '&lt;')
    result = result.replace('>', '&gt;')

    # Step 2: Extract and protect code blocks ```code``` BEFORE other processing
    # (to avoid converting markdown inside code blocks)
    code_blocks: List[str] = []

    def extract_code_block(match: re.Match) -> str:
        lang = match.group(1) or ''
        code = match.group(2)
        code_blocks.append((lang, code))
        return f'__CODE_BLOCK_{len(code_blocks) - 1}__'

    result = re.sub(r'```(\w*)\n?(.*?)```', extract_code_block, result, flags=re.DOTALL)

    # Step 3: Convert inline code `code` to <code>code</code>
    result = re.sub(r'`([^`]+)`', r'<code>\1</code>', result)

    # Step 4: Convert headers to bold (# Header -> <strong>Header</strong>)
    # Using strong instead of h1-h6 to keep text inline with chat bubble UI
    result = re.sub(r'^#{1,6}\s+(.+)$', r'<strong>\1</strong>', result, flags=re.MULTILINE)

    # Step 4b: Remove orphaned hash marks (# with nothing after, or just whitespace)
    # These can occur when LLM outputs "# " with trailing space
    result = re.sub(r'^#{1,6}\s*$', '', result, flags=re.MULTILINE)

    # Step 5: Convert bold **text** to <strong>text</strong>
    result = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', result)

    # Step 6: Convert remaining *text* to <strong>text</strong> (but only balanced pairs)
    # Use word boundaries to avoid matching things like "4* hotel"
    result = re.sub(r'(?<!\w)\*([^\*\n]+?)\*(?!\w)', r'<strong>\1</strong>', result)

    # Step 7: Convert _italic_ to <em>italic</em>
    # Be careful with underscores in variable_names
    result = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'<em>\1</em>', result)

    # Step 8: Convert links [text](url) to <a href="url">text</a>
    # URL was already escaped, so we need to unescape &amp; back to & for href
    def convert_link(match: re.Match) -> str:
        link_text = match.group(1)
        url = match.group(2)
        # Unescape the URL (it was escaped in step 1)
        url = url.replace('&amp;', '&')
        # Re-escape just the ampersands for HTML attribute (but keep them functional)
        url_safe = url.replace('&', '&amp;')
        return f'<a href="{url_safe}" target="_blank" rel="noopener noreferrer">{link_text}</a>'

    result = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', convert_link, result)

    # Step 9: Convert markdown tables to HTML tables
    result = _convert_tables(result)

    # Step 10: Convert lists (must happen after tables to avoid conflicts)
    result = _convert_lists(result)

    # Step 11: Convert horizontal rules (--- or ***) to <hr>
    result = re.sub(r'^[\-\*]{3,}$', '<hr>', result, flags=re.MULTILINE)

    # Step 12: Restore code blocks with proper HTML
    for i, (lang, code) in enumerate(code_blocks):
        class_attr = f' class="language-{lang}"' if lang else ''
        replacement = f'<pre><code{class_attr}>{code}</code></pre>'
        result = result.replace(f'__CODE_BLOCK_{i}__', replacement)

    # Step 13: Convert double newlines to paragraph breaks
    # But don't add <p> tags inside tables, lists, or pre blocks
    result = _wrap_paragraphs(result)

    # Step 14: Clean up excessive whitespace
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


def _convert_tables(text: str) -> str:
    """Convert markdown tables to HTML tables."""
    lines = text.split('\n')
    converted_lines = []
    in_table = False
    table_rows: List[Tuple[str, List[str]]] = []  # (row_type, cells)

    for line in lines:
        stripped = line.strip()

        # Check if this is a table separator row (|---|---|)
        # Separator rows contain only pipes, dashes, colons, and spaces
        if stripped.startswith('|') and stripped.endswith('|') and '-' in stripped:
            # Split by | and check if all cells are separator-style (only -:space)
            potential_cells = stripped.split('|')[1:-1]  # exclude empty strings from split
            is_separator = all(
                cell.strip() == '' or re.match(r'^[\s\-:]+$', cell)
                for cell in potential_cells
            ) and any('-' in cell for cell in potential_cells)
            if is_separator:
                in_table = True
                continue

        # Table row
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]

            if not in_table:
                # This is the header row
                table_rows.append(('header', cells))
                in_table = True
            else:
                # Data row
                table_rows.append(('data', cells))
            continue
        else:
            # Not a table row - flush any accumulated table
            if table_rows:
                converted_lines.append(_render_table(table_rows))
                table_rows = []
            in_table = False
            converted_lines.append(line)

    # Flush any remaining table
    if table_rows:
        converted_lines.append(_render_table(table_rows))

    return '\n'.join(converted_lines)


def _render_table(rows: List[Tuple[str, List[str]]]) -> str:
    """Render accumulated table rows as HTML."""
    if not rows:
        return ''

    html_parts = ['<table>']

    # Check if first row is header
    if rows and rows[0][0] == 'header':
        header_cells = rows[0][1]
        html_parts.append('<thead><tr>')
        for cell in header_cells:
            html_parts.append(f'<th>{cell}</th>')
        html_parts.append('</tr></thead>')
        rows = rows[1:]

    # Render body rows
    if rows:
        html_parts.append('<tbody>')
        for row_type, cells in rows:
            html_parts.append('<tr>')
            for cell in cells:
                html_parts.append(f'<td>{cell}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')

    html_parts.append('</table>')
    return ''.join(html_parts)


def _convert_lists(text: str) -> str:
    """Convert markdown lists to HTML lists."""
    lines = text.split('\n')
    converted_lines = []
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        # Check for unordered list item (- item or * item)
        ul_match = re.match(r'^[-*+]\s+(.+)$', stripped)
        # Check for ordered list item (1. item)
        ol_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)

        if ul_match:
            if in_ol:
                converted_lines.append('</ol>')
                in_ol = False
            if not in_ul:
                converted_lines.append('<ul>')
                in_ul = True
            converted_lines.append(f'<li>{ul_match.group(1)}</li>')
        elif ol_match:
            if in_ul:
                converted_lines.append('</ul>')
                in_ul = False
            if not in_ol:
                converted_lines.append('<ol>')
                in_ol = True
            converted_lines.append(f'<li>{ol_match.group(2)}</li>')
        else:
            # Close any open lists
            if in_ul:
                converted_lines.append('</ul>')
                in_ul = False
            if in_ol:
                converted_lines.append('</ol>')
                in_ol = False
            converted_lines.append(line)

    # Close any remaining open lists
    if in_ul:
        converted_lines.append('</ul>')
    if in_ol:
        converted_lines.append('</ol>')

    return '\n'.join(converted_lines)


def _wrap_paragraphs(text: str) -> str:
    """
    Wrap text blocks in <p> tags, but not content already in block elements.

    This is a simplified approach that doesn't fully parse HTML but handles
    common cases for chat messages.
    """
    # For chat messages, we don't need full paragraph wrapping
    # Just convert double newlines to <br><br> for spacing
    # This keeps the output cleaner and works better in chat bubbles

    # Don't modify content inside block elements
    block_elements = ['<table>', '<ul>', '<ol>', '<pre>', '<hr>']

    # Check if text contains block elements - if so, be more careful
    has_blocks = any(elem in text for elem in block_elements)

    if not has_blocks:
        # Simple case: just convert newlines to <br>
        text = text.replace('\n\n', '<br><br>')
        text = text.replace('\n', '<br>')
    else:
        # More complex: preserve block structure
        # Split by block elements and process non-block sections
        lines = text.split('\n')
        in_block = False
        converted = []

        for line in lines:
            # Check if entering/exiting a block
            if any(line.strip().startswith(elem.rstrip('>')) for elem in block_elements):
                in_block = True
            elif any(line.strip().startswith(f'</{elem[1:]}') for elem in block_elements if elem.startswith('<')):
                in_block = False
                converted.append(line)
                continue

            if in_block:
                converted.append(line)
            else:
                # Outside block: convert empty lines to <br>
                if line.strip() == '':
                    converted.append('<br>')
                else:
                    converted.append(line)

        text = '\n'.join(converted)
        # Clean up excessive <br> tags
        text = re.sub(r'(<br>\s*){3,}', '<br><br>', text)

    return text


# Alias for backwards compatibility if needed
convert_markdown_to_html = markdown_to_html

"""
Enhanced Tool-Specific Formatters with Official Instacart Branding Compliance
Uses the official Instacart partner branding specifications.
"""

import re
from typing import Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


def _append_instacart_utm_params(url: str) -> str:
    """Append required UTM parameters to Instacart URLs for affiliate tracking."""
    utm_params = (
        "utm_campaign=instacart-idp&utm_medium=affiliate&utm_source=instacart_idp"
        "&utm_term=partnertype-mediapartner&utm_content=campaignid-20313_partnerid-6356307"
    )
    if "?" in url:
        return f"{url}&{utm_params}"
    return f"{url}?{utm_params}"


def _format_instacart_button(url: str, text: str) -> str:
    """
    Return the Instacart call‑to‑action HTML that meets the latest
    partner‑branding specifications.

    • Height: 46px (div container)
    • Dynamic width: grows with text
    • Padding: 16px vertical × 18px horizontal
    • Logo: 22px tall
    • Border: #E8E9EB solid 0.5px
    • Background: #FFFFFF
    • Text color: #000000, 16px, semi-bold
    
    Button text options:
    • "Get Recipe Ingredients" (for recipe context)
    • "Get Ingredients" (when recipes are not included)
    • "Shop with Instacart" (legal approved)
    • "Order with Instacart" (legal approved)
    """
    # 🔍 DIAGNOSTIC: Log button creation
    logger.info(f"Creating Instacart button: text='{text}', url='{url[:50]}...'")
    
    # Validate button text is one of the approved options
    approved_texts = [
        "Get Recipe Ingredients", 
        "Get Ingredients", 
        "Shop with Instacart", 
        "Order with Instacart"
    ]
    
    if text not in approved_texts:
        # Default to "Shop with Instacart" if not an approved text
        logger.info(f"Button text '{text}' not approved, defaulting to 'Shop with Instacart'")
        text = "Shop with Instacart"
    
    # Append UTM parameters for affiliate tracking
    url_with_utm = _append_instacart_utm_params(url)
    
    button_html = (
        f'<a href="{url_with_utm}" target="_blank" style="text-decoration:none;">'
        f'<div style="height:46px;display:inline-flex;align-items:center;'
        f'padding:16px 18px;background:#FFFFFF;border:0.5px solid #E8E9EB;'
        f'border-radius:8px;">'
        f'<img src="https://live.staticflickr.com/65535/54538897116_fb233f397f_m.jpg" '
        f'alt="Instacart" style="height:22px;width:auto;margin-right:10px;">'
        f'<span style="font-family:Arial,sans-serif;font-size:16px;'
        f'font-weight:500;color:#000000;white-space:nowrap;">{text}</span>'
        f'</div></a>'
    )
    
    logger.info(f"✅ Instacart button created successfully")
    return button_html


@dataclass
class FormattedContent:
    """Container for formatted content sections"""
    main_content: str = ""
    data_content: str = ""
    final_content: str = ""


class BaseFormatter:
    """Base class for all content formatters"""
    
    def __init__(self):
        self.css_classes = {
            'button': 'button',
            'table': 'table-slim',
            'card': 'card',
            'highlight': 'highlight'
        }
    
    def format(self, content: str, context: Dict[str, Any] = None) -> FormattedContent:
        """Format content and return structured sections"""
        raise NotImplementedError


class ShoppingListFormatter(BaseFormatter):
    """Formats shopping lists with proper categorization and Instacart compliance"""
    
    def format(self, content: str, context: Dict[str, Any] = None) -> FormattedContent:
        formatted = FormattedContent()
        
        # Extract and format Instacart links first (API compliance requirement)
        instacart_content, remaining_content = self._extract_and_format_instacart_links(content)
        
        # Process the remaining content
        sections = self._parse_shopping_sections(remaining_content)
        
        if sections:
            # Main content: Introduction and Instacart button
            intro_text = self._extract_intro_text(remaining_content)
            formatted.main_content = f"{intro_text}\n\n{instacart_content}"
            
            # Data content: Shopping list table
            formatted.data_content = self._create_shopping_table(sections)
            
            # Final content: Store locations if present
            store_content = self._extract_store_locations(remaining_content)
            if store_content:
                formatted.final_content = store_content
        else:
            # Fallback: put everything in main with Instacart formatting
            formatted.main_content = f"{instacart_content}\n\n{remaining_content}"
        
        return formatted
    
    def _extract_and_format_instacart_links(self, content: str) -> tuple[str, str]:
        """Extract Instacart links and format them using official branding (API compliance)"""
        
        # 🔍 DIAGNOSTIC: Log Instacart detection
        logger.info(f"=== INSTACART DIAGNOSTIC START ===")
        logger.info(f"Checking content for Instacart links: {repr(content[:200])}")
        
        if 'instacart' not in content.lower():
            logger.info("❌ No 'instacart' found in content")
            logger.info(f"=== INSTACART DIAGNOSTIC END ===")
            return "", content
        
        logger.info("✅ 'instacart' found in content")
        
        # Multiple patterns to catch different Instacart link formats
        instacart_patterns = [
            r'Instacart link:\s*(https://[^\s\n]+)',  # "Instacart link: https://..."
            r'https://[^\s\n]*instacart[^\s\n]+',     # Any URL containing "instacart"
            r'https://customers\.dev\.instacart\.tools[^\s\n]+',  # Specific dev tools URLs
            r'https://[^\s\n]*\.instacart\.com[^\s\n]+',  # Any instacart.com URL
        ]
        
        matches = []
        for pattern in instacart_patterns:
            pattern_matches = re.findall(pattern, content, re.IGNORECASE)
            matches.extend(pattern_matches)
            if pattern_matches:
                logger.info(f"✅ Found {len(pattern_matches)} URLs with pattern: {pattern}")
        
        # Remove duplicates while preserving order
        unique_matches = []
        for match in matches:
            if match not in unique_matches:
                unique_matches.append(match)
        
        if unique_matches:
            logger.info(f"✅ Found {len(unique_matches)} unique Instacart URLs: {unique_matches}")
            
            # Use the first URL found
            url = unique_matches[0]
            
            # Determine appropriate button text based on content context
            button_text = self._determine_instacart_button_text(content)
            logger.info(f"🔘 Creating button with text: '{button_text}' for URL: {url}")
            
            # Format using official Instacart branding
            instacart_html = f'''
<div style="text-align: center; margin: 20px 0;">
    {_format_instacart_button(url, button_text)}
</div>'''
            
            logger.info(f"🔘 Generated button HTML: {repr(instacart_html[:100])}")
            
            # Remove the plain text version from content (handle multiple formats)
            cleaned_content = content
            for pattern in instacart_patterns:
                cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.IGNORECASE)
            
            # Clean up extra whitespace
            cleaned_content = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_content)
            cleaned_content = cleaned_content.strip()
            
            logger.info("✅ Instacart links replaced with buttons")
            logger.info(f"=== INSTACART DIAGNOSTIC END ===")
            return instacart_html, cleaned_content
        else:
            logger.warning("⚠️ 'instacart' found but no valid URLs extracted")
            logger.info(f"=== INSTACART DIAGNOSTIC END ===")
        
        return "", content
    
    def _determine_instacart_button_text(self, content: str) -> str:
        """Determine appropriate button text based on content context"""
        content_lower = content.lower()
        
        # Check for recipe context
        if any(word in content_lower for word in ['recipe', 'ingredient', 'cooking', 'preparation']):
            return "Get Recipe Ingredients"
        
        # Check for shopping list context
        if any(word in content_lower for word in ['shopping list', 'grocery', 'produce']):
            return "Get Ingredients"
        
        # Default to legal approved text
        return "Shop with Instacart"
    
    def _parse_shopping_sections(self, content: str) -> Dict[str, List[str]]:
        """Parse shopping list into categorized sections"""
        sections = {}
        current_section = None
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for section headers (— SECTION NAME —)
            section_match = re.match(r'—\s*([A-Z\s&]+)\s*—', line)
            if section_match:
                current_section = section_match.group(1).strip()
                sections[current_section] = []
                continue
            
            # Add items to current section
            if current_section and line.startswith('•'):
                item = line[1:].strip()  # Remove bullet point
                sections[current_section].append(item)
        
        return sections
    
    def _create_shopping_table(self, sections: Dict[str, List[str]]) -> str:
        """Create a formatted table for shopping list sections"""
        if not sections:
            return ""
        
        table_html = f'<table class="{self.css_classes["table"]}" style="width: 100%; border-collapse: collapse; margin: 20px 0;">\n'
        
        for section_name, items in sections.items():
            if not items:
                continue
                
            # Section header
            table_html += f'''
    <tr style="background-color: #f8f9fa;">
        <td colspan="2" style="padding: 12px; font-weight: bold; 
                           border-bottom: 2px solid #dee2e6; color: #495057;">
            {section_name}
        </td>
    </tr>
'''
            
            # Items in this section
            for item in items:
                table_html += f'''
    <tr>
        <td style="padding: 8px 12px; border-bottom: 1px solid #dee2e6; width: 20px;">
            <span style="color: #28a745;">✓</span>
        </td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #dee2e6;">
            {item}
        </td>
    </tr>
'''
        
        table_html += '</table>'
        return table_html
    
    def _extract_intro_text(self, content: str) -> str:
        """Extract introductory text before the shopping list"""
        lines = content.split('\n')
        intro_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('—') or line.startswith('•'):
                break
            if line and not line.startswith('Instacart'):
                intro_lines.append(line)
        
        return '\n'.join(intro_lines)
    
    def _extract_store_locations(self, content: str) -> str:
        """Extract and format nearby store locations"""
        store_pattern = r'—\s*NEARBY SUPERMARKETS\s*—(.*?)(?=—|\Z)'
        match = re.search(store_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if match:
            store_content = match.group(1).strip()
            # Format as a nice list
            formatted_stores = "<h3>🏪 Nearby Supermarkets</h3>\n<ul>\n"
            
            lines = store_content.split('\n')
            current_store = ""
            
            for line in lines:
                line = line.strip()
                if re.match(r'^\d+\.', line):  # Store number
                    if current_store:
                        formatted_stores += f"<li>{current_store}</li>\n"
                    current_store = line
                elif line and current_store:
                    current_store += f"<br>{line}"
            
            if current_store:
                formatted_stores += f"<li>{current_store}</li>\n"
            
            formatted_stores += "</ul>"
            return formatted_stores
        
        return ""


class MealPlanFormatter(BaseFormatter):
    """Formats meal plans as calendar-style tables"""
    
    def format(self, content: str, context: Dict[str, Any] = None) -> FormattedContent:
        formatted = FormattedContent()
        formatted.main_content = content  # Placeholder implementation
        return formatted


class RecipeFormatter(BaseFormatter):
    """Formats recipes with proper ingredient lists and numbered instructions"""
    
    def format(self, content: str, context: Dict[str, Any] = None) -> FormattedContent:
        formatted = FormattedContent()
        
        # Check for Instacart links in recipe context
        instacart_content, remaining_content = self._extract_and_format_instacart_links(content)
        
        if instacart_content:
            formatted.main_content = f"{remaining_content}\n\n{instacart_content}"
        else:
            formatted.main_content = content
            
        return formatted
    
    def _extract_and_format_instacart_links(self, content: str) -> tuple[str, str]:
        """Extract Instacart links and format them for recipe context"""
        instacart_pattern = r'Instacart link:\s*(https://[^\s\n]+)'
        matches = re.findall(instacart_pattern, content, re.IGNORECASE)
        
        if matches:
            # Use "Get Recipe Ingredients" for recipe context
            instacart_html = f'''
<div style="text-align: center; margin: 20px 0;">
    {_format_instacart_button(matches[0], "Get Recipe Ingredients")}
</div>'''
            
            # Remove the plain text version from content
            cleaned_content = re.sub(r'Instacart link:\s*https://[^\s\n]+\n?', '', content, flags=re.IGNORECASE)
            return instacart_html, cleaned_content
        
        return "", content


class PrepInstructionsFormatter(BaseFormatter):
    """Formats meal prep instructions with sequential numbering"""
    
    def format(self, content: str, context: Dict[str, Any] = None) -> FormattedContent:
        formatted = FormattedContent()
        formatted.main_content = content  # Placeholder implementation
        return formatted


class GeneralFormatter(BaseFormatter):
    """Default formatter for general content"""
    
    def format(self, content: str, context: Dict[str, Any] = None) -> FormattedContent:
        formatted = FormattedContent()
        formatted.main_content = content
        return formatted


class ToolSpecificFormatterManager:
    """Manages different formatters based on detected tools"""
    
    def __init__(self):
        self.formatters = {
            'shopping_list_tool': ShoppingListFormatter(),
            'meal_plan_tool': MealPlanFormatter(),
            'recipe_tool': RecipeFormatter(),
            'prep_instructions_tool': PrepInstructionsFormatter(),
            'general': GeneralFormatter()
        }
    
    def format_content(self, content: str, detected_tools: List[str], 
                      context: Dict[str, Any] = None) -> FormattedContent:
        """Format content based on detected tools"""
        
        # Determine primary formatter based on detected tools
        primary_tool = self._determine_primary_tool(detected_tools)
        formatter = self.formatters.get(primary_tool, self.formatters['general'])
        
        # Format the content
        return formatter.format(content, context)
    
    def _determine_primary_tool(self, detected_tools: List[str]) -> str:
        """Determine which formatter to use based on detected tools"""
        
        # Priority order for formatters
        priority_order = [
            'shopping_list_tool',
            'meal_plan_tool', 
            'recipe_tool',
            'prep_instructions_tool'
        ]
        
        for tool in priority_order:
            if tool in detected_tools:
                return tool
        
        return 'general'


# Test the Instacart compliant formatter
if __name__ == "__main__":
    # Test shopping list with Instacart link
    test_content = """
Here's your shopping list for the week of May 19–25 (3 servings daily) with Jamaican-inspired, cholesterol-lowering meals.

Instacart link:
https://customers.dev.instacart.tools/store/shopping_lists/5827424

— PRODUCE —
• Firm tofu: 1800 g
• Carrots: 450 g
• Bell peppers: 900 g

— CONDIMENTS & SPICES —
• White vinegar: 90 ml
• Allspice powder: 9 g

— NEARBY SUPERMARKETS —
1. Whole Foods Market
214 Prospect Park West, Brooklyn, NY 11215
"""
    
    manager = ToolSpecificFormatterManager()
    result = manager.format_content(test_content, ['shopping_list_tool'])
        
    recipe_content = """
Here's your recipe for Jamaican Jerk Chicken with ingredients.

Instacart link:
https://customers.dev.instacart.tools/store/shopping_lists/5827424

Ingredients:
• Chicken breast: 2 lbs
• Jerk seasoning: 2 tbsp
"""
    
    recipe_result = manager.format_content(recipe_content, ['recipe_tool'])


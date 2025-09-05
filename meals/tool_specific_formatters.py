"""
Tool-Specific Formatters for Email Content

This module implements specialized formatters for different types of tool outputs,
ensuring consistent and beautiful email formatting based on the content type.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime, date
import re

logger = logging.getLogger(__name__)

@dataclass
class FormattedSection:
    """Container for a formatted email section"""
    content: str
    section_type: str  # 'main', 'data', 'final'
    css_classes: List[str]
    priority: int  # For ordering multiple sections
    
class BaseToolFormatter(ABC):
    """Base class for all tool-specific formatters"""
    
    def __init__(self, tool_name: str, tool_output: Dict, user_context: Optional[Dict] = None):
        self.tool_name = tool_name
        self.tool_output = tool_output
        self.user_context = user_context or {}
        self.css_classes = []
    
    @abstractmethod
    def format(self) -> List[FormattedSection]:
        """Format the tool output into email sections"""
        pass
    
    def _safe_get(self, data: Dict, key: str, default: Any = "") -> Any:
        """Safely get a value from a dictionary"""
        return data.get(key, default) if isinstance(data, dict) else default
    
    def _format_date(self, date_str: str) -> str:
        """Format date string for display"""
        try:
            if isinstance(date_str, str):
                # Try different date formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime("%B %d, %Y")
                    except ValueError:
                        continue
            return str(date_str)
        except:
            return str(date_str)
    
    def _create_button(self, text: str, url: str, style: str = "primary") -> str:
        """Create a styled button"""
        return f'<a href="{url}" class="button {style}" style="display: inline-block; padding: 12px 24px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px; margin: 8px 4px;">{text}</a>'
    
    def _create_table_row(self, cells: List[str], is_header: bool = False) -> str:
        """Create a table row"""
        tag = "th" if is_header else "td"
        cells_html = "".join([f"<{tag}>{cell}</{tag}>" for cell in cells])
        class_attr = ' class="header"' if is_header else ''
        return f"<tr{class_attr}>{cells_html}</tr>"

class MealPlanFormatter(BaseToolFormatter):
    """Formatter for meal planning tools"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        if self.tool_name in ["create_meal_plan", "get_meal_plan", "list_user_meal_plans"]:
            sections.extend(self._format_meal_plan())
        elif self.tool_name == "get_meal_plan_meals_info":
            sections.extend(self._format_meal_info())
        elif self.tool_name == "list_upcoming_meals":
            sections.extend(self._format_upcoming_meals())
        
        return sections
    
    def _format_meal_plan(self) -> List[FormattedSection]:
        """Format meal plan data into beautiful weekly calendar"""
        sections = []
        
        # Main section - Introduction
        meal_plan_data = self.tool_output.get('meal_plan', {})
        week_start = self._safe_get(meal_plan_data, 'week_start_date', 'this week')
        week_end = self._safe_get(meal_plan_data, 'week_end_date', '')
        
        main_content = f"""
        <h2>🍽️ Your Meal Plan</h2>
        <p>Here's your personalized meal plan for {self._format_date(week_start)}
        {f" - {self._format_date(week_end)}" if week_end else ""}:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["meal-plan-intro"],
            priority=1
        ))
        
        # Data section - Meal calendar
        meals = self._safe_get(meal_plan_data, 'meals', [])
        if meals:
            calendar_html = self._create_meal_calendar(meals)
            sections.append(FormattedSection(
                content=calendar_html,
                section_type="data",
                css_classes=["meal-plan-calendar"],
                priority=2
            ))
        
        # Final section - Actions
        meal_plan_id = self._safe_get(meal_plan_data, 'id', '')
        actions_html = f"""
        <div class="meal-plan-actions">
            <h3>What's Next?</h3>
            <p>Ready to get started with your meal plan?</p>
            {self._create_button("Generate Shopping List", f"/shopping-list/{meal_plan_id}", "primary")}
            {self._create_button("View Recipe Instructions", f"/recipes/{meal_plan_id}", "secondary")}
        </div>
        """
        
        sections.append(FormattedSection(
            content=actions_html,
            section_type="final",
            css_classes=["meal-plan-actions"],
            priority=3
        ))
        
        return sections
    
    def _create_meal_calendar(self, meals: List[Dict]) -> str:
        """Create a beautiful weekly meal calendar"""
        # Group meals by day and meal type
        calendar_data = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        meal_types = ["Breakfast", "Lunch", "Dinner"]
        
        for meal in meals:
            day = self._safe_get(meal, 'day', 'Monday')
            meal_type = self._safe_get(meal, 'meal_type', 'Dinner')
            if day not in calendar_data:
                calendar_data[day] = {}
            calendar_data[day][meal_type] = meal
        
        # Create table HTML
        html = '<table class="meal-calendar table-slim" style="width: 100%; border-collapse: collapse; margin: 20px 0;">'
        
        # Header row
        header_cells = ["Day"] + meal_types
        html += self._create_table_row(header_cells, is_header=True)
        
        # Day rows
        for day in days:
            day_meals = calendar_data.get(day, {})
            row_cells = [f"<strong>{day}</strong>"]
            
            for meal_type in meal_types:
                meal = day_meals.get(meal_type, {})
                if meal:
                    meal_name = self._safe_get(meal, 'meal_name', 'No meal planned')
                    is_chef_meal = self._safe_get(meal, 'is_chef_meal', False)
                    chef_name = self._safe_get(meal, 'chef_name', '')
                    
                    cell_content = f'<div class="meal-item">'
                    cell_content += f'<div class="meal-name">{meal_name}</div>'
                    
                    if is_chef_meal and chef_name:
                        cell_content += f'<div class="chef-badge">👨‍🍳 Chef {chef_name}</div>'
                    
                    cell_content += '</div>'
                    row_cells.append(cell_content)
                else:
                    row_cells.append('<div class="no-meal">-</div>')
            
            html += self._create_table_row(row_cells)
        
        html += '</table>'
        
        return f"""
        <div class="meal-calendar-container">
            <h3>📅 Weekly Meal Calendar</h3>
            {html}
        </div>
        """
    
    def _format_meal_info(self) -> List[FormattedSection]:
        """Format detailed meal information"""
        sections = []
        
        meals_info = self.tool_output.get('meals_info', [])
        if not meals_info:
            return sections
        
        # Main section
        main_content = f"""
        <h2>🍽️ Meal Details</h2>
        <p>Here are the details for your selected meals:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["meal-details-intro"],
            priority=1
        ))
        
        # Data section - Meal cards
        meals_html = '<div class="meal-details-grid">'
        
        for meal in meals_info:
            meal_name = self._safe_get(meal, 'name', 'Unknown Meal')
            description = self._safe_get(meal, 'description', '')
            dietary_prefs = self._safe_get(meal, 'dietary_preferences', [])
            
            meals_html += f"""
            <div class="meal-card" style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0;">
                <h4>{meal_name}</h4>
                <p>{description}</p>
                {f'<div class="dietary-tags">{", ".join(dietary_prefs)}</div>' if dietary_prefs else ''}
            </div>
            """
        
        meals_html += '</div>'
        
        sections.append(FormattedSection(
            content=meals_html,
            section_type="data",
            css_classes=["meal-details-grid"],
            priority=2
        ))
        
        return sections
    
    def _format_upcoming_meals(self) -> List[FormattedSection]:
        """Format upcoming meals list"""
        sections = []
        
        upcoming_meals = self.tool_output.get('upcoming_meals', [])
        if not upcoming_meals:
            return sections
        
        # Main section
        main_content = f"""
        <h2>🗓️ Upcoming Meals</h2>
        <p>Here are your meals coming up:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["upcoming-meals-intro"],
            priority=1
        ))
        
        # Data section - Upcoming meals list
        meals_html = '<div class="upcoming-meals-list">'
        
        for meal in upcoming_meals[:5]:  # Limit to 5 upcoming meals
            meal_name = self._safe_get(meal, 'meal_name', 'Unknown Meal')
            day = self._safe_get(meal, 'day', '')
            meal_type = self._safe_get(meal, 'meal_type', '')
            
            meals_html += f"""
            <div class="upcoming-meal-item" style="padding: 12px; border-left: 4px solid #007bff; margin: 8px 0; background: #f8f9fa;">
                <strong>{day} {meal_type}</strong><br>
                {meal_name}
            </div>
            """
        
        meals_html += '</div>'
        
        sections.append(FormattedSection(
            content=meals_html,
            section_type="data",
            css_classes=["upcoming-meals-list"],
            priority=2
        ))
        
        return sections

class ShoppingFormatter(BaseToolFormatter):
    """Formatter for shopping and pantry tools"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        if self.tool_name == "generate_shopping_list":
            sections.extend(self._format_shopping_list())
        elif self.tool_name == "generate_instacart_link_tool":
            sections.extend(self._format_instacart_link())
        elif self.tool_name == "find_nearby_supermarkets":
            sections.extend(self._format_nearby_stores())
        elif self.tool_name in ["check_pantry_items", "get_expiring_items"]:
            sections.extend(self._format_pantry_info())
        
        return sections
    
    def _format_shopping_list(self) -> List[FormattedSection]:
        """Format shopping list with categories"""
        sections = []
        
        # Main section
        main_content = f"""
        <h2>🛒 Shopping List</h2>
        <p>Here's everything you need for your meal plan:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["shopping-list-intro"],
            priority=1
        ))
        
        # Data section - Categorized shopping list
        shopping_items = self.tool_output.get('shopping_list', {}).get('items', [])
        if shopping_items:
            categories_html = self._create_categorized_shopping_list(shopping_items)
            sections.append(FormattedSection(
                content=categories_html,
                section_type="data",
                css_classes=["shopping-categories"],
                priority=2
            ))
        
        # Final section - Shopping actions
        instacart_url = self.tool_output.get('instacart_url', '')
        actions_html = f"""
        <div class="shopping-actions">
            <h3>Ready to Shop?</h3>
            <p>Get your ingredients delivered or find a store near you:</p>
            {self._create_button("🛒 Order on Instacart", instacart_url, "primary") if instacart_url else ""}
            {self._create_button("🏪 Find Local Stores", "/find-stores", "secondary")}
        </div>
        """
        
        sections.append(FormattedSection(
            content=actions_html,
            section_type="final",
            css_classes=["shopping-actions"],
            priority=3
        ))
        
        return sections
    
    def _create_categorized_shopping_list(self, items: List[Dict]) -> str:
        """Create categorized shopping list"""
        # Group items by category
        categories = {}
        for item in items:
            category = self._safe_get(item, 'category', 'Miscellaneous')
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        # Create HTML for each category
        html = '<div class="shopping-categories">'
        
        # Define category order and icons
        category_icons = {
            'Produce': '🥬',
            'Dairy': '🥛',
            'Meat': '🥩',
            'Bakery': '🍞',
            'Beverages': '🥤',
            'Frozen': '🧊',
            'Grains': '🌾',
            'Snacks': '🍿',
            'Condiments': '🧂',
            'Miscellaneous': '📦'
        }
        
        for category, category_items in categories.items():
            icon = category_icons.get(category, '📦')
            html += f"""
            <div class="shopping-category" style="margin: 16px 0; padding: 12px; background: #f8f9fa; border-radius: 8px;">
                <h4>{icon} {category}</h4>
                <ul style="list-style: none; padding: 0;">
            """
            
            for item in category_items:
                ingredient = self._safe_get(item, 'ingredient', 'Unknown item')
                quantity = self._safe_get(item, 'quantity', '')
                unit = self._safe_get(item, 'unit', '')
                notes = self._safe_get(item, 'notes', '')
                
                quantity_text = f"{quantity} {unit}".strip() if quantity or unit else ""
                
                html += f"""
                <li style="padding: 4px 0; border-bottom: 1px solid #eee;">
                    <strong>{ingredient}</strong>
                    {f" - {quantity_text}" if quantity_text else ""}
                    {f" <em>({notes})</em>" if notes else ""}
                </li>
                """
            
            html += '</ul></div>'
        
        html += '</div>'
        return html
    
    def _format_instacart_link(self) -> List[FormattedSection]:
        """Format Instacart shopping link"""
        sections = []
        
        instacart_url = self.tool_output.get('instacart_url', '')
        if not instacart_url:
            return sections
        
        # Main section with Instacart branding
        main_content = f"""
        <h2>🛒 Shop with Instacart</h2>
        <p>Your shopping list is ready! Get your ingredients delivered in as little as 1 hour.</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["instacart-intro"],
            priority=1
        ))
        
        # Final section - Instacart button
        actions_html = f"""
        <div class="instacart-actions" style="text-align: center; padding: 20px;">
            {self._create_button("🛒 Shop on Instacart", instacart_url, "primary")}
            <p style="font-size: 12px; color: #666; margin-top: 12px;">
                Delivery available from your favorite local stores
            </p>
        </div>
        """
        
        sections.append(FormattedSection(
            content=actions_html,
            section_type="final",
            css_classes=["instacart-actions"],
            priority=3
        ))
        
        return sections
    
    def _format_nearby_stores(self) -> List[FormattedSection]:
        """Format nearby supermarkets"""
        sections = []
        
        stores = self.tool_output.get('supermarkets', [])
        if not stores:
            return sections
        
        # Main section
        main_content = f"""
        <h2>🏪 Nearby Supermarkets</h2>
        <p>Here are grocery stores in your area:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["stores-intro"],
            priority=1
        ))
        
        # Data section - Store list
        stores_html = '<div class="nearby-stores">'
        
        for store in stores[:5]:  # Limit to 5 stores
            name = self._safe_get(store, 'name', 'Unknown Store')
            address = self._safe_get(store, 'address', '')
            distance = self._safe_get(store, 'distance', '')
            
            stores_html += f"""
            <div class="store-item" style="padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin: 8px 0;">
                <h4>{name}</h4>
                <p>{address}</p>
                {f"<p><small>📍 {distance}</small></p>" if distance else ""}
            </div>
            """
        
        stores_html += '</div>'
        
        sections.append(FormattedSection(
            content=stores_html,
            section_type="data",
            css_classes=["nearby-stores"],
            priority=2
        ))
        
        return sections
    
    def _format_pantry_info(self) -> List[FormattedSection]:
        """Format pantry items information"""
        sections = []
        
        if self.tool_name == "get_expiring_items":
            expiring_items = self.tool_output.get('expiring_items', [])
            if expiring_items:
                # Main section
                main_content = f"""
                <h2>⚠️ Expiring Pantry Items</h2>
                <p>These items in your pantry are expiring soon:</p>
                """
                
                sections.append(FormattedSection(
                    content=main_content,
                    section_type="main",
                    css_classes=["expiring-items-intro"],
                    priority=1
                ))
                
                # Data section - Expiring items list
                items_html = '<div class="expiring-items-list">'
                
                for item in expiring_items:
                    item_name = self._safe_get(item, 'item_name', 'Unknown Item')
                    expiration_date = self._safe_get(item, 'expiration_date', '')
                    quantity = self._safe_get(item, 'quantity', '')
                    
                    items_html += f"""
                    <div class="expiring-item" style="padding: 12px; border-left: 4px solid #ff6b6b; margin: 8px 0; background: #fff5f5;">
                        <strong>{item_name}</strong>
                        {f" ({quantity})" if quantity else ""}
                        <br>
                        <small>Expires: {self._format_date(expiration_date)}</small>
                    </div>
                    """
                
                items_html += '</div>'
                
                sections.append(FormattedSection(
                    content=items_html,
                    section_type="data",
                    css_classes=["expiring-items-list"],
                    priority=2
                ))
        
        return sections

class RecipeFormatter(BaseToolFormatter):
    """Formatter for recipe and instruction tools"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        if self.tool_name in ["email_generate_meal_instructions", "stream_meal_instructions"]:
            sections.extend(self._format_recipe_instructions())
        elif self.tool_name == "get_meal_macro_info":
            sections.extend(self._format_nutrition_info())
        elif self.tool_name == "find_related_youtube_videos":
            sections.extend(self._format_youtube_videos())
        
        return sections
    
    def _format_recipe_instructions(self) -> List[FormattedSection]:
        """Format recipe instructions with proper step numbering"""
        sections = []
        
        # Extract recipe data
        instructions_data = self.tool_output.get('instructions', {})
        meal_name = self.tool_output.get('meal_name', 'Recipe')
        
        # Main section - Recipe header
        main_content = f"""
        <h2>👨‍🍳 {meal_name}</h2>
        <p>Follow these step-by-step instructions to create your delicious meal:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["recipe-intro"],
            priority=1
        ))
        
        # Data section - Instructions
        if isinstance(instructions_data, dict) and 'steps' in instructions_data:
            instructions_html = self._create_recipe_steps(instructions_data['steps'])
            sections.append(FormattedSection(
                content=instructions_html,
                section_type="data",
                css_classes=["recipe-instructions"],
                priority=2
            ))
        
        # Final section - Additional resources
        youtube_videos = self.tool_output.get('youtube_videos', {}).get('videos', [])
        final_html = '<div class="recipe-resources">'
        
        if youtube_videos:
            final_html += '<h3>📺 Helpful Videos</h3>'
            for video in youtube_videos[:2]:  # Limit to 2 videos
                title = self._safe_get(video, 'title', 'Cooking Video')
                url = self._safe_get(video, 'url', '')
                channel = self._safe_get(video, 'channel', '')
                
                if url:
                    final_html += f"""
                    <div class="video-link" style="margin: 8px 0; padding: 8px; background: #f8f9fa; border-radius: 4px;">
                        <a href="{url}" target="_blank" style="text-decoration: none; color: #007bff;">
                            📺 {title}
                        </a>
                        {f"<br><small>by {channel}</small>" if channel else ""}
                    </div>
                    """
        
        final_html += '</div>'
        
        sections.append(FormattedSection(
            content=final_html,
            section_type="final",
            css_classes=["recipe-resources"],
            priority=3
        ))
        
        return sections
    
    def _create_recipe_steps(self, steps: List[Dict]) -> str:
        """Create properly numbered recipe steps"""
        if not steps:
            return "<p>No instructions available.</p>"
        
        html = '<div class="recipe-steps">'
        html += '<h3>🥄 Instructions</h3>'
        html += '<ol class="instruction-list" style="padding-left: 20px;">'
        
        # Filter out empty steps and renumber properly
        valid_steps = [step for step in steps if self._safe_get(step, 'description', '').strip()]
        
        for i, step in enumerate(valid_steps, 1):
            description = self._safe_get(step, 'description', '').strip()
            duration = self._safe_get(step, 'duration', '')
            
            if description:
                html += f"""
                <li style="margin: 12px 0; padding: 8px; background: #f8f9fa; border-radius: 4px;">
                    <div class="step-content">
                        {description}
                        {f'<div class="step-duration" style="font-size: 12px; color: #666; margin-top: 4px;">⏱️ {duration}</div>' if duration and duration != 'N/A' else ''}
                    </div>
                </li>
                """
        
        html += '</ol></div>'
        return html
    
    def _format_nutrition_info(self) -> List[FormattedSection]:
        """Format nutritional information"""
        sections = []
        
        macro_info = self.tool_output.get('macro_info', {})
        if not macro_info:
            return sections
        
        # Main section
        main_content = f"""
        <h2>📊 Nutritional Information</h2>
        <p>Here's the nutritional breakdown for your meal:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["nutrition-intro"],
            priority=1
        ))
        
        # Data section - Nutrition table
        nutrition_html = self._create_nutrition_table(macro_info)
        sections.append(FormattedSection(
            content=nutrition_html,
            section_type="data",
            css_classes=["nutrition-table"],
            priority=2
        ))
        
        return sections
    
    def _create_nutrition_table(self, macro_info: Dict) -> str:
        """Create nutrition information table"""
        html = '<div class="nutrition-info">'
        html += '<table class="nutrition-table table-slim" style="width: 100%; border-collapse: collapse;">'
        
        # Define nutrition fields with labels and units
        nutrition_fields = [
            ('calories', 'Calories', 'kcal'),
            ('protein', 'Protein', 'g'),
            ('carbohydrates', 'Carbohydrates', 'g'),
            ('fat', 'Fat', 'g'),
            ('fiber', 'Fiber', 'g'),
            ('sugar', 'Sugar', 'g'),
            ('sodium', 'Sodium', 'mg')
        ]
        
        for field, label, unit in nutrition_fields:
            value = self._safe_get(macro_info, field, '')
            if value:
                html += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>{label}</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{value} {unit}</td>
                </tr>
                """
        
        serving_size = self._safe_get(macro_info, 'serving_size', '')
        if serving_size:
            html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Serving Size</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{serving_size}</td>
            </tr>
            """
        
        html += '</table></div>'
        return html
    
    def _format_youtube_videos(self) -> List[FormattedSection]:
        """Format YouTube video recommendations"""
        sections = []
        
        videos = self.tool_output.get('videos', [])
        if not videos:
            return sections
        
        # Main section
        main_content = f"""
        <h2>📺 Cooking Videos</h2>
        <p>Watch these helpful cooking tutorials:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["videos-intro"],
            priority=1
        ))
        
        # Data section - Video list
        videos_html = '<div class="youtube-videos">'
        
        for video in videos[:3]:  # Limit to 3 videos
            title = self._safe_get(video, 'title', 'Cooking Video')
            url = self._safe_get(video, 'url', '')
            channel = self._safe_get(video, 'channel', '')
            description = self._safe_get(video, 'description', '')
            duration = self._safe_get(video, 'duration', '')
            
            if url:
                videos_html += f"""
                <div class="video-card" style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0;">
                    <h4><a href="{url}" target="_blank" style="color: #007bff; text-decoration: none;">📺 {title}</a></h4>
                    <p><strong>Channel:</strong> {channel}</p>
                    {f"<p><strong>Duration:</strong> {duration}</p>" if duration else ""}
                    {f"<p>{description}</p>" if description else ""}
                    {self._create_button("Watch Video", url, "primary")}
                </div>
                """
        
        videos_html += '</div>'
        
        sections.append(FormattedSection(
            content=videos_html,
            section_type="data",
            css_classes=["youtube-videos"],
            priority=2
        ))
        
        return sections

class ChefFormatter(BaseToolFormatter):
    """Formatter for chef connection tools"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        if self.tool_name == "find_local_chefs":
            sections.extend(self._format_chef_listings())
        elif self.tool_name == "view_chef_meal_events":
            sections.extend(self._format_chef_events())
        elif self.tool_name == "get_chef_details":
            sections.extend(self._format_chef_profile())
        
        return sections
    
    def _format_chef_listings(self) -> List[FormattedSection]:
        """Format local chef listings"""
        sections = []
        
        chefs = self.tool_output.get('chefs', [])
        if not chefs:
            return sections
        
        # Main section
        main_content = f"""
        <h2>👨‍🍳 Local Chefs</h2>
        <p>Connect with talented chefs in your area for fresh, homemade meals:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["chefs-intro"],
            priority=1
        ))
        
        # Data section - Chef cards
        chefs_html = '<div class="chef-listings">'
        
        for chef in chefs[:3]:  # Limit to 3 chefs
            name = self._safe_get(chef, 'name', 'Unknown Chef')
            bio = self._safe_get(chef, 'bio', '')
            specialties = self._safe_get(chef, 'specialties', [])
            rating = self._safe_get(chef, 'rating', '')
            chef_id = self._safe_get(chef, 'id', '')
            
            chefs_html += f"""
            <div class="chef-card" style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0;">
                <h4>👨‍🍳 {name}</h4>
                {f"<p>{bio}</p>" if bio else ""}
                {f"<p><strong>Specialties:</strong> {', '.join(specialties)}</p>" if specialties else ""}
                {f"<p><strong>Rating:</strong> ⭐ {rating}</p>" if rating else ""}
                {self._create_button("View Chef Details", f"/chef/{chef_id}", "primary") if chef_id else ""}
                {self._create_button("View Meal Events", f"/chef/{chef_id}/events", "secondary") if chef_id else ""}
            </div>
            """
        
        chefs_html += '</div>'
        
        sections.append(FormattedSection(
            content=chefs_html,
            section_type="data",
            css_classes=["chef-listings"],
            priority=2
        ))
        
        return sections
    
    def _format_chef_events(self) -> List[FormattedSection]:
        """Format chef meal events"""
        sections = []
        
        events = self.tool_output.get('events', [])
        chef_name = self.tool_output.get('chef_name', 'Chef')
        
        if not events:
            return sections
        
        # Main section
        main_content = f"""
        <h2>🍽️ {chef_name}'s Meal Events</h2>
        <p>Fresh, chef-prepared meals available for order:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["chef-events-intro"],
            priority=1
        ))
        
        # Data section - Event listings
        events_html = '<div class="chef-events">'
        
        for event in events:
            meal_name = self._safe_get(event, 'meal_name', 'Chef Meal')
            description = self._safe_get(event, 'description', '')
            price = self._safe_get(event, 'price', '')
            event_date = self._safe_get(event, 'event_date', '')
            event_id = self._safe_get(event, 'id', '')
            
            events_html += f"""
            <div class="chef-event" style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 12px 0;">
                <h4>{meal_name}</h4>
                {f"<p>{description}</p>" if description else ""}
                {f"<p><strong>Date:</strong> {self._format_date(event_date)}</p>" if event_date else ""}
                {f"<p><strong>Price:</strong> ${price}</p>" if price else ""}
                {self._create_button("Order This Meal", f"/order/chef-event/{event_id}", "primary") if event_id else ""}
            </div>
            """
        
        events_html += '</div>'
        
        sections.append(FormattedSection(
            content=events_html,
            section_type="data",
            css_classes=["chef-events"],
            priority=2
        ))
        
        return sections
    
    def _format_chef_profile(self) -> List[FormattedSection]:
        """Format detailed chef profile"""
        sections = []
        
        chef = self.tool_output.get('chef', {})
        if not chef:
            return sections
        
        name = self._safe_get(chef, 'name', 'Unknown Chef')
        bio = self._safe_get(chef, 'bio', '')
        specialties = self._safe_get(chef, 'specialties', [])
        rating = self._safe_get(chef, 'rating', '')
        location = self._safe_get(chef, 'location', '')
        
        # Main section - Chef profile
        main_content = f"""
        <h2>👨‍🍳 Meet {name}</h2>
        {f"<p><strong>Location:</strong> {location}</p>" if location else ""}
        {f"<p><strong>Rating:</strong> ⭐ {rating}</p>" if rating else ""}
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["chef-profile-intro"],
            priority=1
        ))
        
        # Data section - Chef details
        profile_html = f"""
        <div class="chef-profile">
            {f"<div class='chef-bio'><h3>About {name}</h3><p>{bio}</p></div>" if bio else ""}
            {f"<div class='chef-specialties'><h3>Specialties</h3><p>{', '.join(specialties)}</p></div>" if specialties else ""}
        </div>
        """
        
        sections.append(FormattedSection(
            content=profile_html,
            section_type="data",
            css_classes=["chef-profile"],
            priority=2
        ))
        
        return sections

class PaymentFormatter(BaseToolFormatter):
    """Formatter for payment and order tools"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        if self.tool_name == "generate_payment_link":
            sections.extend(self._format_payment_link())
        elif self.tool_name == "check_payment_status":
            sections.extend(self._format_payment_status())
        elif self.tool_name == "get_order_details":
            sections.extend(self._format_order_details())
        
        return sections
    
    def _format_payment_link(self) -> List[FormattedSection]:
        """Format payment link with order summary"""
        sections = []
        
        checkout_url = self.tool_output.get('checkout_url', '')
        if not checkout_url:
            return sections
        
        # Main section
        main_content = f"""
        <h2>💳 Complete Your Payment</h2>
        <p>Your order is ready! Complete your payment to confirm your meal order.</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["payment-intro"],
            priority=1
        ))
        
        # Final section - Payment button
        payment_html = f"""
        <div class="payment-actions" style="text-align: center; padding: 20px;">
            {self._create_button("💳 Complete Payment", checkout_url, "primary")}
            <p style="font-size: 12px; color: #666; margin-top: 12px;">
                🔒 Secure payment powered by Stripe
            </p>
        </div>
        """
        
        sections.append(FormattedSection(
            content=payment_html,
            section_type="final",
            css_classes=["payment-actions"],
            priority=3
        ))
        
        return sections
    
    def _format_payment_status(self) -> List[FormattedSection]:
        """Format payment status information"""
        sections = []
        
        status = self._safe_get(self.tool_output, 'status', 'unknown')
        order_id = self._safe_get(self.tool_output, 'order_id', '')
        
        # Main section with status
        status_emoji = {
            'paid': '✅',
            'pending': '⏳',
            'failed': '❌',
            'cancelled': '🚫'
        }.get(status.lower(), '❓')
        
        main_content = f"""
        <h2>{status_emoji} Payment Status</h2>
        <p>Here's the current status of your payment:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["payment-status-intro"],
            priority=1
        ))
        
        # Data section - Status details
        status_html = f"""
        <div class="payment-status-details">
            <table class="status-table table-slim" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Order ID</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{order_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Status</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{status_emoji} {status.title()}</td>
                </tr>
            </table>
        </div>
        """
        
        sections.append(FormattedSection(
            content=status_html,
            section_type="data",
            css_classes=["payment-status-details"],
            priority=2
        ))
        
        return sections
    
    def _format_order_details(self) -> List[FormattedSection]:
        """Format order details"""
        sections = []
        
        order = self.tool_output.get('order', {})
        if not order:
            return sections
        
        order_id = self._safe_get(order, 'id', '')
        total = self._safe_get(order, 'total', '')
        status = self._safe_get(order, 'status', '')
        order_date = self._safe_get(order, 'created_at', '')
        
        # Main section
        main_content = f"""
        <h2>📋 Order Details</h2>
        <p>Here are the details for your order:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["order-details-intro"],
            priority=1
        ))
        
        # Data section - Order summary
        order_html = f"""
        <div class="order-summary">
            <table class="order-table table-slim" style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Order ID</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{order_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Date</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{self._format_date(order_date)}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Status</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{status}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Total</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>${total}</strong></td>
                </tr>
            </table>
        </div>
        """
        
        sections.append(FormattedSection(
            content=order_html,
            section_type="data",
            css_classes=["order-summary"],
            priority=2
        ))
        
        return sections

class DietaryFormatter(BaseToolFormatter):
    """Formatter for dietary preference and compatibility tools"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        if self.tool_name == "check_meal_compatibility":
            sections.extend(self._format_compatibility_check())
        elif self.tool_name == "suggest_alternatives":
            sections.extend(self._format_alternatives())
        elif self.tool_name == "list_dietary_preferences":
            sections.extend(self._format_preferences_list())
        
        return sections
    
    def _format_compatibility_check(self) -> List[FormattedSection]:
        """Format meal compatibility results"""
        sections = []
        
        compatibility = self.tool_output.get('compatibility', {})
        if not compatibility:
            return sections
        
        is_compatible = self._safe_get(compatibility, 'is_compatible', False)
        violations = self._safe_get(compatibility, 'violations', [])
        meal_name = self.tool_output.get('meal_name', 'Meal')
        
        # Main section
        status_emoji = '✅' if is_compatible else '❌'
        main_content = f"""
        <h2>{status_emoji} Dietary Compatibility</h2>
        <p>Here's how "{meal_name}" aligns with your dietary preferences:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["compatibility-intro"],
            priority=1
        ))
        
        # Data section - Compatibility results
        compat_html = f"""
        <div class="compatibility-results">
            <div class="compatibility-status" style="padding: 16px; border-radius: 8px; margin: 12px 0; {'background: #d4edda; border: 1px solid #c3e6cb;' if is_compatible else 'background: #f8d7da; border: 1px solid #f5c6cb;'}">
                <h4>{status_emoji} {'Compatible' if is_compatible else 'Not Compatible'}</h4>
                {f"<p>This meal meets all your dietary requirements!</p>" if is_compatible else ""}
            </div>
        """
        
        if violations:
            compat_html += """
            <div class="violations">
                <h4>⚠️ Dietary Concerns:</h4>
                <ul>
            """
            for violation in violations:
                compat_html += f"<li>{violation}</li>"
            compat_html += "</ul></div>"
        
        compat_html += "</div>"
        
        sections.append(FormattedSection(
            content=compat_html,
            section_type="data",
            css_classes=["compatibility-results"],
            priority=2
        ))
        
        return sections
    
    def _format_alternatives(self) -> List[FormattedSection]:
        """Format alternative meal suggestions"""
        sections = []
        
        alternatives = self.tool_output.get('alternatives', [])
        if not alternatives:
            return sections
        
        # Main section
        main_content = f"""
        <h2>🔄 Alternative Meal Suggestions</h2>
        <p>Here are some meals that better match your dietary preferences:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["alternatives-intro"],
            priority=1
        ))
        
        # Data section - Alternative meals
        alts_html = '<div class="alternative-meals">'
        
        for alt in alternatives:
            meal_name = self._safe_get(alt, 'name', 'Alternative Meal')
            description = self._safe_get(alt, 'description', '')
            dietary_prefs = self._safe_get(alt, 'dietary_preferences', [])
            meal_id = self._safe_get(alt, 'id', '')
            
            alts_html += f"""
            <div class="alternative-meal" style="border: 1px solid #28a745; border-radius: 8px; padding: 16px; margin: 12px 0; background: #f8fff9;">
                <h4>✅ {meal_name}</h4>
                {f"<p>{description}</p>" if description else ""}
                {f"<div class='dietary-tags' style='margin: 8px 0;'><strong>Dietary:</strong> {', '.join(dietary_prefs)}</div>" if dietary_prefs else ""}
                {self._create_button("Select This Meal", f"/replace-meal/{meal_id}", "primary") if meal_id else ""}
            </div>
            """
        
        alts_html += '</div>'
        
        sections.append(FormattedSection(
            content=alts_html,
            section_type="data",
            css_classes=["alternative-meals"],
            priority=2
        ))
        
        return sections
    
    def _format_preferences_list(self) -> List[FormattedSection]:
        """Format dietary preferences list"""
        sections = []
        
        preferences = self.tool_output.get('preferences', [])
        if not preferences:
            return sections
        
        # Main section
        main_content = f"""
        <h2>🥗 Your Dietary Preferences</h2>
        <p>Here are your current dietary preferences and restrictions:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["preferences-intro"],
            priority=1
        ))
        
        # Data section - Preferences list
        prefs_html = '<div class="dietary-preferences">'
        
        for pref in preferences:
            pref_name = self._safe_get(pref, 'name', 'Dietary Preference')
            description = self._safe_get(pref, 'description', '')
            
            prefs_html += f"""
            <div class="dietary-preference" style="padding: 12px; border-left: 4px solid #007bff; margin: 8px 0; background: #f8f9fa;">
                <h4>{pref_name}</h4>
                {f"<p>{description}</p>" if description else ""}
            </div>
            """
        
        prefs_html += '</div>'
        
        sections.append(FormattedSection(
            content=prefs_html,
            section_type="data",
            css_classes=["dietary-preferences"],
            priority=2
        ))
        
        return sections

class GeneralFormatter(BaseToolFormatter):
    """Formatter for general tools and fallback formatting"""
    
    def format(self) -> List[FormattedSection]:
        sections = []
        
        # Generic formatting for any tool output
        tool_output_str = json.dumps(self.tool_output, indent=2) if self.tool_output else "No output available"
        
        main_content = f"""
        <h2>ℹ️ Information</h2>
        <p>Here's the information you requested:</p>
        """
        
        sections.append(FormattedSection(
            content=main_content,
            section_type="main",
            css_classes=["general-info"],
            priority=1
        ))
        
        # Data section - Tool output
        data_html = f"""
        <div class="tool-output">
            <pre style="background: #f8f9fa; padding: 12px; border-radius: 4px; overflow-x: auto;">
{tool_output_str}
            </pre>
        </div>
        """
        
        sections.append(FormattedSection(
            content=data_html,
            section_type="data",
            css_classes=["tool-output"],
            priority=2
        ))
        
        return sections

# Formatter registry and selection logic
TOOL_FORMATTER_MAP = {
    # Meal Planning
    "create_meal_plan": MealPlanFormatter,
    "get_meal_plan": MealPlanFormatter,
    "list_user_meal_plans": MealPlanFormatter,
    "modify_meal_plan": MealPlanFormatter,
    "get_meal_plan_meals_info": MealPlanFormatter,
    "list_upcoming_meals": MealPlanFormatter,
    
    # Shopping & Pantry
    "generate_shopping_list": ShoppingFormatter,
    "generate_instacart_link_tool": ShoppingFormatter,
    "find_nearby_supermarkets": ShoppingFormatter,
    "check_pantry_items": ShoppingFormatter,
    "get_expiring_items": ShoppingFormatter,
    "add_pantry_item": ShoppingFormatter,
    
    # Recipes & Instructions
    "email_generate_meal_instructions": RecipeFormatter,
    "stream_meal_instructions": RecipeFormatter,
    "stream_bulk_prep_instructions": RecipeFormatter,
    "get_meal_macro_info": RecipeFormatter,
    "find_related_youtube_videos": RecipeFormatter,
    
    # Chef Connection
    "find_local_chefs": ChefFormatter,
    "get_chef_details": ChefFormatter,
    "view_chef_meal_events": ChefFormatter,
    "place_chef_meal_event_order": ChefFormatter,
    "replace_meal_plan_meal": ChefFormatter,
    
    # Payment & Orders
    "generate_payment_link": PaymentFormatter,
    "check_payment_status": PaymentFormatter,
    "get_order_details": PaymentFormatter,
    "cancel_order": PaymentFormatter,
    "process_refund": PaymentFormatter,
    
    # Dietary & Health
    "check_meal_compatibility": DietaryFormatter,
    "suggest_alternatives": DietaryFormatter,
    "list_dietary_preferences": DietaryFormatter,
    "manage_dietary_preferences": DietaryFormatter,
    "check_allergy_alert": DietaryFormatter,
}

def get_formatter_for_tool(tool_name: str, tool_output: Dict, user_context: Optional[Dict] = None) -> BaseToolFormatter:
    """
    Get the appropriate formatter for a tool
    
    Args:
        tool_name: Name of the tool
        tool_output: Output from the tool
        user_context: Optional user context
        
    Returns:
        Formatter instance
    """
    formatter_class = TOOL_FORMATTER_MAP.get(tool_name, GeneralFormatter)
    return formatter_class(tool_name, tool_output, user_context)

def format_tool_outputs(tool_outputs: List[Dict], user_context: Optional[Dict] = None) -> List[FormattedSection]:
    """
    Format multiple tool outputs
    
    Args:
        tool_outputs: List of tool outputs with tool names
        user_context: Optional user context
        
    Returns:
        List of formatted sections
    """
    all_sections = []
    
    for tool_data in tool_outputs:
        tool_name = tool_data.get('tool_name', 'unknown')
        tool_output = tool_data.get('output', {})
        
        formatter = get_formatter_for_tool(tool_name, tool_output, user_context)
        sections = formatter.format()
        all_sections.extend(sections)
    
    # Sort sections by priority
    all_sections.sort(key=lambda x: x.priority)
    
    return all_sections

# Example usage and testing
if __name__ == "__main__":
    # Test meal plan formatting
    test_meal_plan_output = {
        'meal_plan': {
            'id': 123,
            'week_start_date': '2024-01-15',
            'week_end_date': '2024-01-21',
            'meals': [
                {
                    'day': 'Monday',
                    'meal_type': 'Breakfast',
                    'meal_name': 'Oatmeal with Berries',
                    'is_chef_meal': False,
                    'chef_name': None
                },
                {
                    'day': 'Monday',
                    'meal_type': 'Lunch',
                    'meal_name': 'Grilled Chicken Salad',
                    'is_chef_meal': True,
                    'chef_name': 'Chef Maria'
                }
            ]
        }
    }
    
    formatter = MealPlanFormatter('get_meal_plan', test_meal_plan_output)
    sections = formatter.format()
    
    print("=== Test Meal Plan Formatting ===")
    for section in sections:
        print(f"\n--- {section.section_type.upper()} SECTION ---")
        print(section.content)
    
    # Test shopping list formatting
    test_shopping_output = {
        'shopping_list': {
            'items': [
                {
                    'ingredient': 'Chicken Breast',
                    'quantity': '2',
                    'unit': 'lbs',
                    'category': 'Meat',
                    'notes': 'Organic preferred'
                },
                {
                    'ingredient': 'Spinach',
                    'quantity': '1',
                    'unit': 'bag',
                    'category': 'Produce',
                    'notes': ''
                }
            ]
        },
        'instacart_url': 'https://instacart.com/example'
    }
    
    formatter = ShoppingFormatter('generate_shopping_list', test_shopping_output)
    sections = formatter.format()
    
    print("\n\n=== Test Shopping List Formatting ===")
    for section in sections:
        print(f"\n--- {section.section_type.upper()} SECTION ---")
        print(section.content)

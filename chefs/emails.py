"""
Chef email notifications.

Handles sending transactional emails to chefs for onboarding events.
"""

import logging
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_chef_approved_email(chef, dashboard_url: Optional[str] = None) -> bool:
    """
    Send approval notification email to a newly approved chef.
    
    Args:
        chef: Chef model instance
        dashboard_url: URL to the chef dashboard (defaults to settings or constructed)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        user = chef.user
        
        # Get chef's name
        chef_name = user.first_name or user.username
        
        # Get recipient email
        recipient_email = user.email
        if not recipient_email:
            logger.warning(f"Chef {chef.id} has no email address, cannot send approval email")
            return False
        
        # Construct dashboard URL
        if not dashboard_url:
            base_url = getattr(settings, 'FRONTEND_URL', 'https://sautai.com')
            dashboard_url = f"{base_url}/chef-hub"
        
        # Render the email template
        context = {
            'chef_name': chef_name,
            'dashboard_url': dashboard_url,
            'current_year': datetime.now().year,
        }
        
        html_content = render_to_string('chefs/emails/chef_approved.html', context)
        text_content = strip_tags(html_content)  # Fallback plain text
        
        # Create email
        subject = "🎉 Welcome to Sautai — You're Approved!"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'hello@sautai.com')
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient_email],
            reply_to=[getattr(settings, 'SUPPORT_EMAIL', 'support@sautai.com')],
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send it
        email.send(fail_silently=False)
        
        logger.info(f"Sent approval email to chef {chef.id} ({recipient_email})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send approval email to chef {chef.id}: {str(e)}")
        return False


def send_chef_stripe_reminder_email(chef, dashboard_url: Optional[str] = None) -> bool:
    """
    Send a reminder to complete Stripe setup.
    
    TODO: Implement when needed
    """
    # Placeholder for future implementation
    pass

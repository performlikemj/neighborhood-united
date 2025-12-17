"""
Email utility module for sending HTML emails via Django's email framework.
Replaces n8n webhook-based email sending with direct SMTP.
"""
import logging
from typing import List, Optional, Union

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def send_html_email(
    subject: str,
    html_content: str,
    recipient_email: Union[str, List[str]],
    from_email: Optional[str] = None,
    reply_to: Optional[List[str]] = None,
    fail_silently: bool = False,
) -> bool:
    """
    Send an HTML email with automatic plain-text fallback.
    
    Args:
        subject: Email subject line
        html_content: HTML content of the email
        recipient_email: Single email address or list of addresses
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        reply_to: Optional list of reply-to addresses
        fail_silently: If True, don't raise exceptions on failure
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Use default from email if not provided
        sender = from_email or settings.DEFAULT_FROM_EMAIL
        
        # Generate plain-text version from HTML
        plain_text = BeautifulSoup(html_content, 'html.parser').get_text(separator='\n')
        # Clean up excessive whitespace in plain text
        plain_text = '\n'.join(line.strip() for line in plain_text.split('\n') if line.strip())
        
        # Ensure recipient is a list
        if isinstance(recipient_email, str):
            recipients = [recipient_email]
        else:
            recipients = list(recipient_email)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=sender,
            to=recipients,
            reply_to=reply_to,
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=fail_silently)
        
        logger.info(f"Email sent successfully to {recipients} with subject: {subject[:50]}...")
        return True
        
    except Exception as e:
        logger.exception(f"Failed to send email to {recipient_email}: {e}")
        if not fail_silently:
            raise
        return False


def send_activation_email(
    to_email: str,
    username: str,
    activation_link: str,
    from_email: Optional[str] = None,
) -> bool:
    """
    Send account activation email.
    
    Args:
        to_email: Recipient email address
        username: User's username
        activation_link: URL for account activation
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        
    Returns:
        bool: True if email was sent successfully
    """
    subject = "Activate Your sautai Account"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2c5282;">Welcome to sautai!</h1>
            <p>Hi {username},</p>
            <p>Thank you for signing up! Please click the button below to activate your account:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{activation_link}" 
                   style="background-color: #4299e1; color: white; padding: 12px 30px; 
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Activate Account
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #4299e1;">{activation_link}</p>
            <p>This link will expire in 24 hours.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
            <p style="color: #718096; font-size: 14px;">
                If you didn't create an account with sautai, please ignore this email.
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_html_email(
        subject=subject,
        html_content=html_content,
        recipient_email=to_email,
        from_email=from_email or 'support@sautai.com',
    )


def send_password_reset_email(
    to_email: str,
    reset_link: str,
    from_email: Optional[str] = None,
) -> bool:
    """
    Send password reset email.
    
    Args:
        to_email: Recipient email address
        reset_link: URL for password reset
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        
    Returns:
        bool: True if email was sent successfully
    """
    subject = "Reset Your sautai Password"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2c5282;">Password Reset Request</h1>
            <p>You requested to reset your password for your sautai account.</p>
            <p>Click the button below to set a new password:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" 
                   style="background-color: #4299e1; color: white; padding: 12px 30px; 
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Reset Password
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #4299e1;">{reset_link}</p>
            <p>This link will expire in 1 hour.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
            <p style="color: #718096; font-size: 14px;">
                If you didn't request a password reset, please ignore this email. 
                Your password will remain unchanged.
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_html_email(
        subject=subject,
        html_content=html_content,
        recipient_email=to_email,
        from_email=from_email or 'support@sautai.com',
    )


def send_profile_update_email(
    to_email: str,
    username: str,
    activation_link: str,
    from_email: Optional[str] = None,
) -> bool:
    """
    Send profile update confirmation email (email change verification).
    
    Args:
        to_email: New email address to verify
        username: User's username
        activation_link: URL to confirm the email change
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        
    Returns:
        bool: True if email was sent successfully
    """
    subject = "Confirm Your Email Change - sautai"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2c5282;">Confirm Your Email Change</h1>
            <p>Hi {username},</p>
            <p>You requested to change your email address to this one. Please click the button below to confirm:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{activation_link}" 
                   style="background-color: #4299e1; color: white; padding: 12px 30px; 
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Confirm Email Change
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #4299e1;">{activation_link}</p>
            <p>This link will expire in 24 hours.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
            <p style="color: #718096; font-size: 14px;">
                If you didn't request this change, please ignore this email and your 
                email address will remain unchanged.
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_html_email(
        subject=subject,
        html_content=html_content,
        recipient_email=to_email,
        from_email=from_email or 'support@sautai.com',
    )

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .tokens import account_activation_token
from django.contrib.sites.shortcuts import get_current_site
from .models import CustomUser
from django.utils import timezone

def send_email_change_confirmation(request, user, new_email):
    # generate token with user id and new email
    token = account_activation_token.make_token(user)

    # store the new email and token creation time
    user.new_email = new_email
    user.token_created_at = timezone.now()
    user.save()

    current_site = get_current_site(request)
    mail_subject = 'Confirm your email change'
    message = render_to_string('custom_auth/email_change_confirm.html', {
        'user': user,
        'new_email': new_email,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': token,
    })
    email = EmailMessage(
        mail_subject, 
        message, 
        from_email='mj@igobymj.com',
        to=[new_email]
    )
    email.send()

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from .tokens import account_activation_token
from .models import CustomUser, Address, UserRole
from chefs.models import ChefRequest
from .forms import RegistrationForm, UserProfileForm, EmailChangeForm, AddressForm
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from datetime import timedelta
from .utils import send_email_change_confirmation
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from .serializers import CustomUserSerializer, AddressSerializer, PostalCodeSerializer
from local_chefs.models import PostalCode
import os
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.http import JsonResponse
import json
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.permissions import IsAuthenticated
import logging
import requests
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.hashers import check_password


logger = logging.getLogger(__name__)

# Load configuration from config.json
with open('/etc/config.json') as config_file:
    config = json.load(config_file)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')

    # Check if current password is correct
    if not check_password(current_password, request.user.password):
        return Response({'status': 'error', 'message': 'Current password is incorrect.'}, status=400)

    # Check if new password and confirmation match
    if new_password != confirm_password:
        return Response({'status': 'error', 'message': 'New password and confirmation do not match.'}, status=400)

    # Change the password
    try:
        request.user.set_password(new_password)
        request.user.save()
        return Response({'status': 'success', 'message': 'Password changed successfully.'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=500)

@api_view(['POST'])
def password_reset_request(request):
    try:
        email = request.data['email']
        user = CustomUser.objects.get(email=email)
        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{config['STREAMLIT_URL']}/activate?uid={uid}&token={token}&action=password_reset"

        mail_subject = "Password Reset Request"
        message = f"Hi {user.username},\n\nPlease click on the link below to reset your password:\n{reset_link}\n\nIf you did not request an email change, please ignore this email."

        # Send data to Zapier
        zapier_webhook_url = config['ZAP_PW_RESET_URL']
        email_data = {
            'subject': mail_subject,
            'message': message,
            'to': email,
            'from': 'support@sautai.com'
        }
        try:
            requests.post(zapier_webhook_url, json=email_data)
            logger.info(f"Password reset email data sent to Zapier for: {email}")
        except Exception as e:
            logger.error(f"Error sending password reset email data to Zapier for: {email}, error: {str(e)}")

        return Response({'status': 'success', 'message': 'Password reset email sent.'})
    except CustomUser.DoesNotExist:
        logger.warning(f"Password reset attempted for non-existent email: {email}")
        return Response({'status': 'success', 'message': 'Password reset email sent'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})

@api_view(['POST'])
def reset_password(request):
    uidb64 = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(id=uid)

        if not PasswordResetTokenGenerator().check_token(user, token):
            return Response({'status': 'error', 'message': 'Token is invalid.'})

        # Check if new password and confirmation match
        if new_password != confirm_password:
            return Response({'status': 'error', 'message': 'New password and confirmation do not match.'}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({'status': 'success', 'message': 'Password reset successfully.'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_details_view(request):
    # Serialize the request user's data
    serializer = CustomUserSerializer(request.user)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def address_details_view(request):
    serializer = AddressSerializer(request.user.address)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_api(request):
    user = request.user
    # Deserialize and update user data
    user_serializer = CustomUserSerializer(user, data=request.data, partial=True)
    if user_serializer.is_valid():
        print(f"Validated data: {user_serializer.validated_data}")  # Debug print

        # Check if email is updated
        if 'email' in user_serializer.validated_data:
            user.email_confirmed = False
            user.new_email = user_serializer.validated_data['email']
            user.save()

            # Send activation email
            mail_subject = 'Verify your email to resume access.'
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{config['STREAMLIT_URL']}/activate?uid={uid}&token={token}"
            message = f"Hi {user.username},\n\nYou've recently updated your email!\n\n" \
                    f"Please click the link below to verify the change:\n\n{activation_link}\n\n" \
                    f"If you have any issues, please contact us at {config['STREAMLIT_SUPPORT_EMAIL']}.\n\n" \
                    "Thanks,\nYour SautAI Support Team"

            to_email = user_serializer.validated_data.get('email')
            email = EmailMessage(mail_subject, message, from_email='support@sautai.com', to=[to_email])
            email.send()
        if 'dietary_preference' in user_serializer.validated_data:
            user.dietary_preference = user_serializer.validated_data['dietary_preference']

        if 'allergies' in user_serializer.validated_data:
            user.allergies = user_serializer.validated_data['allergies']
        user_serializer.save()

    else:
        print(f"Serializer errors: {user_serializer.errors}")  # Debug print
        return Response({'status': 'failure', 'message': user_serializer.errors}, status=400)

    # Update or create address data
    address_fields = [field.name for field in Address._meta.get_fields()]
    address_data = {key: value for key, value in request.data.items() if key in address_fields}
    if address_data:
        try:
            address = Address.objects.get(user=user)
        except Address.DoesNotExist:
            address = None

        address_serializer = AddressSerializer(instance=address, data=address_data, partial=True)
        if address_serializer.is_valid():
            address = address_serializer.save(user=user)
            is_served = address.is_postalcode_served()

            return Response({'status': 'success', 'message': 'Profile updated successfully', 'is_served': is_served})
        else:
            return Response({'status': 'failure', 'message': address_serializer.errors}, status=400)
    else:
        return Response({'status': 'failure', 'message': 'Address data not provided'}, status=400)



@api_view(['POST'])
def login_api_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data['username']
        password = data['password']
        user = authenticate(username=username, password=password)
        if user:
            # Create the token for the user
            refresh = RefreshToken.for_user(user)
            print(f'User {user.username} logged in successfully')
            print(f'Refresh token: {refresh}')
            print(f'Access token: {refresh.access_token}')
            return JsonResponse({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id,  # Include the user_id in the response
                'email_confirmed': user.email_confirmed,
                'status': 'success',
                'message': 'Logged in successfully'
            }, status=200)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid username or password'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST method allowed'}, status=405)


@api_view(['POST'])
@login_required
def logout_api_view(request):
    try:
        refresh_token = request.data.get('refresh')
        token = RefreshToken(refresh_token)
        token.blacklist()
        logout(request)
        return JsonResponse({'status': 'success', 'message': 'Logged out successfully'}, status=200)
    except (TokenError, InvalidToken):
        return JsonResponse({'status': 'error', 'message': 'Invalid token'}, status=400)

@api_view(['POST'])
def register_api_view(request):
    user_serializer = CustomUserSerializer(data=request.data.get('user'))

    if not user_serializer.is_valid():
        return Response({'errors': user_serializer.errors})

    try:
        with transaction.atomic():
            user = user_serializer.save()
            UserRole.objects.create(user=user, current_role='customer')
            address_data = request.data.get('address')
            address_data['user'] = user.id

            address_serializer = AddressSerializer(data=address_data)
            if not address_serializer.is_valid():
                return Response({'errors': address_serializer.errors})

            address_serializer.save()

            # Prepare activation email data
            mail_subject = 'Activate your account.'
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{config['STREAMLIT_URL']}/activate?uid={uid}&token={token}&action=activate"        
            message = f"Hi {user.username},\n\nThank you for signing up for our website!\n\n" \
                    f"Please click the link below to activate your account:\n\n{activation_link}\n\n" \
                    "If you have any issues, please contact us at support@sautAI.com.\n\n" \
                    "Thanks,\nYour SautAI Support Team"

            to_email = user_serializer.validated_data.get('email')

            # Send data to Zapier
            zapier_webhook_url = config['ZAP_REGISTER_URL']
            email_data = {
                'subject': mail_subject,
                'message': message,
                'to': to_email,
                'from': 'mj@sautai.com',
                'username': user.username,
                'activation_link': activation_link,
            }
            try:
                requests.post(zapier_webhook_url, json=email_data)
                logger.info(f"Activation email data sent to Zapier for: {to_email}")
            except Exception as e:
                logger.error(f"Error sending activation email data to Zapier for: {to_email}, error: {str(e)}")

        # After successful registration
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'status': 'User registered',
            'navigate_to': 'Assistant'
        })
    except IntegrityError as e:
        return Response({'errors': {'username': ['This username is already taken.']}})
    
@api_view(['POST'])
def activate_account_api_view(request):
    uidb64 = request.data.get('uid')
    token = request.data.get('token')
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)
        if user and account_activation_token.check_token(user, token):
            user.email_confirmed = True
            user.initial_email_confirmed = True
            user.save()
            return Response({'status': 'success', 'message': 'Account activated successfully.'})
        else:
            return Response({'status': 'failure', 'message': 'Activation link is invalid.'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})

def email_confirmed_required(function):
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.email_confirmed:
            return function(request, *args, **kwargs)
        else:
            messages.info(request, "Please confirm your email address.")
            return redirect('custom_auth:register') 
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def is_customer(user):
    return user.initial_email_confirmed

def is_correct_user(user, customuser_username):
    return user.username == customuser_username


@login_required
def profile(request):
    if not is_customer(request.user):
        messages.info(request, "Please confirm your email.")
        return redirect('custom_auth:register')  

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('custom_auth:profile'), 'name': 'Profile'},
    ]

    pending_email_change = request.user.new_email is not None 

    address = Address.objects.get(user=request.user)  # Add this line

    try:
        user_role = UserRole.objects.get(user=request.user)
    except UserRole.DoesNotExist:
        user_role = None

    return render(request, 'custom_auth/profile.html', {
        'customuser': request.user,
        'breadcrumbs': breadcrumbs,
        'pending_email_change': pending_email_change,
        'address': address,  # Pass the variable to the template
        'user_role': user_role,  # Pass UserRole to the template
    })


@login_required
@user_passes_test(lambda u: is_correct_user(u, u.username), login_url='chefs:chef_list', redirect_field_name=None)
def update_profile(request):
    # Fetch or create the user role
    user_role, created = UserRole.objects.get_or_create(user=request.user, defaults={'current_role': 'customer'})
    if created:
        messages.info(request, "Your user role has been set to 'customer' by default.")

    # Define forms
    form = UserProfileForm(request.POST or None, instance=request.user, request=request)
    address_form_instance = None  # Initialize as None

    # Determine the correct address form based on the user's role
    address_form_class = AddressForm
    try:
        address_instance = Address.objects.get(user=request.user)
        address_form_instance = address_form_class(request.POST or None, instance=address_instance)
    except (Address.DoesNotExist):
        address_form_instance = address_form_class(request.POST or None)  # No instance if address doesn't exist

    # Handle form submission
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            if address_form_instance and address_form_instance.is_valid():
                address_form_instance.save()
                messages.success(request, 'Address updated successfully.')
            elif not address_instance:
                messages.info(request, 'Please add an address to your profile.')
            return redirect('custom_auth:profile')

    # Prepare context
    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('custom_auth:profile'), 'name': 'Profile'},
        {'url': reverse('custom_auth:update_profile'), 'name': 'Update Profile'},
    ]
    context = {
        'form': form,
        'address_form': address_form_instance,
        'breadcrumbs': breadcrumbs
    }

    return render(request, 'custom_auth/update_profile.html', context)


@login_required
@user_passes_test(lambda u: is_correct_user(u, u.username), login_url='chefs:chef_list', redirect_field_name=None)
def switch_roles(request):
    # Get the user's role, or create a new one with 'customer' as the default
    user_role, created = UserRole.objects.get_or_create(user=request.user, defaults={'current_role': 'customer'})

    if request.method == 'POST':  # Only switch roles for POST requests
        if user_role.current_role == 'chef':
            user_role.current_role = 'customer'
            user_role.save()
            messages.success(request, 'You have switched to the Customer role.')
        elif user_role.current_role == 'customer':
            # Check if there's a chef request and it is approved
            chef_request = ChefRequest.objects.filter(user=request.user, is_approved=True).first()
            if chef_request:
                user_role.current_role = 'chef'
                user_role.save()
                messages.success(request, 'You have switched to the Chef role.')
            else:
                messages.error(request, 'You are not approved to become a chef.')
        else:
            messages.error(request, 'Invalid role.')

    return redirect('custom_auth:profile')  # Always redirect to the profile page after the operation


# register view
def register_view(request):
    user_group = None
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        address_form = AddressForm(request.POST)
        if request.user.is_authenticated:
            user_group = request.user.groups.values_list('name', flat=True).first()
        if form.is_valid() and address_form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()

            # Save the Address
            address = address_form.save(commit=False)
            address.user = user
            address.save()

            current_site = get_current_site(request)
            mail_subject = 'Activate your account.'
            message = render_to_string('custom_auth/acc_active_email.html', {
                'user': user,
                'domain': 'https://www.sautai.com',
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(
                mail_subject, 
                message, 
                from_email=config['STREAMLIT_SUPPORT_EMAIL'],  # Use a different From address
                to=[to_email]
            )
          # Prepare data for Zapier
            #zapier_data = {
            #    'email': to_email,
            #    'username': user.username,
            #    'domain': current_site.domain,
            #    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            #    'token': account_activation_token.make_token(user),
            #}
            #requests.post('https://hooks.zapier.com/hooks/catch/17732876/3qbqiob/', json=zapier_data)
            email.send()
            return redirect('custom_auth:verify_email')
    else:
        form = RegistrationForm()
        address_form = AddressForm()
        if request.user.is_authenticated:
            user_group = request.user.groups.values_list('name', flat=True).first()

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('custom_auth:register'), 'name': 'Register'},
    ]
    return render(request, 'custom_auth/register.html', {'form': form, 'address_form': address_form, 'user_group': user_group, 'breadcrumbs': breadcrumbs})

# activate view for clicking the link in the email
def activate_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
        if account_activation_token.check_token(user, token):
            user.email_confirmed = True  # Change is_active to email_confirmed
            user.initial_email_confirmed = True   
            user.save()
            login(request, user)
            return render(request, 'custom_auth/activate_success.html')
        else:
            return render(request, 'custom_auth/activate_failure.html')
    except(TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
        return render(request, 'custom_auth/activate_failure.html')

# login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('custom_auth:profile')
        else:
            messages.error(request, 'Invalid username or password')
    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('custom_auth:login'), 'name': 'Login'},
    ]
    return render(request, 'custom_auth/login.html', {'breadcrumbs' : breadcrumbs})

# logout view
@login_required
def logout_view(request):
    logout(request)
    return redirect('custom_auth:login')

# email verification view
def verify_email_view(request):
    show_login_message = False
    show_email_verification_message = False
    if not request.user.is_authenticated:
        show_login_message = True
    elif not request.user.is_active:
        show_email_verification_message = True

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('custom_auth:verify_email'), 'name': 'Verify Email'},
    ]
    return render(request, 'custom_auth/verify_email.html', {
        'show_login_message': show_login_message,
        'show_email_verification_message': show_email_verification_message,
        'breadcrumbs' : breadcrumbs
    })


def confirm_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
        if account_activation_token.check_token(user, token):
            # check if the token is not expired
            token_lifetime = timedelta(hours=48)  # 48 hours
            if timezone.now() > user.token_created_at + token_lifetime:
                messages.error(request, 'The confirmation token has expired.')
            else:
                user.email = user.new_email
                user.new_email = None
                user.token_created_at = None
                user.email_confirmed = True
                user.save()
                return render(request, 'custom_auth/confirm_email_success.html')
        else:
            return render(request, 'custom_auth/confirm_email_failure.html')
    except(TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
        return render(request, 'custom_auth/confirm_email_failure.html')


@login_required
def re_request_email_change(request):
    if request.method == 'POST':
        form = EmailChangeForm(request.user, request.POST)
        if form.is_valid():
            new_email = form.cleaned_data.get('new_email')
            if CustomUser.objects.filter(email=new_email).exclude(username=request.user.username).exists():
                messages.error(request, "This email is already in use.")
            else:
                send_email_change_confirmation(request, request.user, new_email)
                return redirect('custom_auth:profile')
    else:
        form = EmailChangeForm(request.user)

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('custom_auth:profile'), 'name': 'Profile'},
        {'url': reverse('custom_auth:re_request_email_change'), 'name': 'Re-request Email Change'},
    ]

    return render(request, 'custom_auth/re_request_email_change.html', {'form': form, 'breadcrumbs': breadcrumbs})


class EmailChangeView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = EmailChangeForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data.get('email')
            if CustomUser.objects.filter(email=new_email).exclude(username=request.user.username).exists():
                messages.error(request, "This email is already in use.")
            else:
                send_email_change_confirmation(request, request.user, new_email)
                return redirect('custom_auth:profile')
        else:
            messages.error(request, "Please correct the error below.")
        return render(request, 'custom_auth/change_email.html', {'form': form})


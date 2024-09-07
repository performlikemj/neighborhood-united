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
from customer_dashboard.models import GoalTracking
from chefs.models import ChefRequest
from .forms import RegistrationForm, UserProfileForm, EmailChangeForm, AddressForm
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django_countries import countries
from datetime import timedelta
from .utils import send_email_change_confirmation
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from .serializers import CustomUserSerializer, AddressSerializer, PostalCodeSerializer, UserRoleSerializer
from rest_framework import serializers
import requests
from local_chefs.models import PostalCode
import os
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.http import JsonResponse
import json
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.tokens import PasswordResetTokenGenerator
import logging
from django.contrib.auth.hashers import check_password
from dotenv import load_dotenv
from django.db import IntegrityError
from meals.tasks import create_meal_plan_for_new_user, generate_user_summary
from django.core.mail import send_mail

load_dotenv("dev.env")

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_role_api(request):
    # Get the user's role, or create a new one with 'customer' as the default
    user_role, _ = UserRole.objects.get_or_create(user=request.user, defaults={'current_role': 'customer'})
    print(f"User role: {user_role.current_role}")  # Debug print
    new_role = 'chef' if user_role.current_role == 'customer' and user_role.is_chef else 'customer'

    print(f"User {request.user.username} is trying to switch role to {new_role}.")

    # Check if the user can switch to chef
    if new_role == 'chef' and not user_role.is_chef:
        print(f"User {request.user.username} tried to switch to chef role but is not a chef.")
        return Response({'error': 'You are not a chef.'}, status=400)

    # Update the user role
    user_role.current_role = new_role
    user_role.save()

    print(f"User {request.user.username} switched role to {new_role}.")

    # Serialize and return the new user role
    serializer = UserRoleSerializer(user_role)
    return Response(serializer.data)

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
        reset_link = f"{os.getenv('STREAMLIT_URL')}/account?uid={uid}&token={token}&action=password_reset"

        mail_subject = "Password Reset Request"
        message = f"""
        <html>
        <body>
            <div style="text-align: center;">
                <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
            </div>
            <h2 style="color: #333;">Password Reset Request</h2>
            <p>Hi {user.username},</p>
            <p>We received a request to reset your password. Please click the button below to proceed:</p>
            <div style="text-align: center; margin: 20px 0;">
                <a href="{reset_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Your Password</a>
            </div>
            <p>If the button above doesn't work, you can copy and paste the following link into your web browser:</p>
            <p><a href="{reset_link}" style="color: #4CAF50;">{reset_link}</a></p>
            <p>If you did not request a password reset, please ignore this email or contact us at <a href="mailto:support@sautai.com">support@sautai.com</a>.</p>
            <p>Thanks,<br>The SautAI Support Team</p>
        </body>
        </html>
        """

        # Send data to Zapier
        zapier_webhook_url = os.getenv('ZAP_PW_RESET_URL')
        email_data = {
            'subject': mail_subject,
            'message': message,
            'to': email,
            'from': 'support@sautai.com',
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
    try:
        address = request.user.address
    except Address.DoesNotExist:
        return Response({"detail": "Address not found for this user."})
    
    serializer = AddressSerializer(address)
    return Response(serializer.data)

@api_view(['GET'])
def get_countries(request):
    country_list = [{"code": code, "name": name} for code, name in list(countries)]
    return JsonResponse(country_list, safe=False)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_api(request):
    print(f"Request data: {request.data}")  # Debug print

    user = request.user
    user_serializer = CustomUserSerializer(user, data=request.data, partial=True)

    if user_serializer.is_valid():
        print(f"Validated data: {user_serializer.validated_data}")  # Debug print

        if 'email' in user_serializer.validated_data and user_serializer.validated_data['email'] != user.email:
            new_email = user_serializer.validated_data['email']
            if not new_email:
                return Response({'status': 'failure', 'message': 'Email cannot be empty'}, status=400)

            user.email_confirmed = False
            user.new_email = new_email
            user.save()

            # Prepare data for Zapier webhook
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{os.getenv('STREAMLIT_URL')}/account?uid={uid}&token={token}"
            # HTML email content
            email_content = f"""
            <html>
            <body>
                <div style="text-align: center;">
                    <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
                </div>
                <h2 style="color: #333;">Email Verification Required, {user.username}</h2>
                <p>We noticed that you've updated your email address. To continue accessing your account, please verify your new email address by clicking the button below:</p>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{activation_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Your Email</a>
                </div>
                <p>If the button above doesn't work, you can copy and paste the following link into your web browser:</p>
                <p><a href="{activation_link}" style="color: #4CAF50;">{activation_link}</a></p>
                <p>If you did not request this change, please contact our support team at <a href="mailto:support@sautai.com">support@sautai.com</a> immediately.</p>
                <p>Thanks,<br>The SautAI Support Team</p>
            </body>
            </html>
            """

            zapier_data = {
                'recipient_email': user_serializer.validated_data.get('email'),
                'subject': 'Verify your email to resume access.',
                'message': email_content,
                'username': user.username,
                'activation_link': activation_link,
                'html': True  # Indicate that the message is in HTML format
            }
            # Send data to Zapier
            requests.post(os.getenv("ZAP_UPDATE_PROFILE_URL"), json=zapier_data)

        if 'username' in user_serializer.validated_data and user_serializer.validated_data['username'] != user.username:
            user.username = user_serializer.validated_data['username']
            user.save()

        if 'dietary_preference' in user_serializer.validated_data:
            user.dietary_preference = user_serializer.validated_data['dietary_preference']

        if 'custom_dietary_preference' in user_serializer.validated_data:
            user.custom_dietary_preference = user_serializer.validated_data['custom_dietary_preference']

        if 'allergies' in user_serializer.validated_data:
            user.allergies = user_serializer.validated_data['allergies']
        
        if 'custom_allergies' in user_serializer.validated_data:
            user.custom_allergies = user_serializer.validated_data['custom_allergies']

        if 'timezone' in user_serializer.validated_data:
            user.timezone = user_serializer.validated_data['timezone']

        if 'preferred_language' in user_serializer.validated_data:
            user.preferred_language = user_serializer.validated_data['preferred_language']

        if 'email_daily_instructions' in user_serializer.validated_data:
            user.email_daily_instructions = user_serializer.validated_data['email_daily_instructions']
        
        if 'email_meal_plan_saved' in user_serializer.validated_data:
            user.email_meal_plan_saved = user_serializer.validated_data['email_meal_plan_saved']
        
        if 'email_instruction_generation' in user_serializer.validated_data:
            user.email_instruction_generation = user_serializer.validated_data['email_instruction_generation']

        user_serializer.save()

    else:
        print(f"Serializer errors: {user_serializer.errors}")  # Debug print
        return Response({'status': 'failure', 'message': user_serializer.errors}, status=400)

    # Update or create address data
    address_data = request.data.get('address')
    if address_data:
        print(f'Address data: {address_data}')  # Debug print
        
        # Convert full country name to country code
        country_name = address_data.get('country')
        if country_name:
            country_code = get_country_code(country_name)  # Use the new function to get the country code
            print(f"Country name: {country_name}, Country code: {country_code}")  # Debugging print
            if not country_code:
                return Response({'status': 'failure', 'message': f'Invalid country name: {country_name}'}, status=400)
            address_data['country'] = country_code

        try:
            address = Address.objects.get(user=user)
        except Address.DoesNotExist:
            address = None

        # Correct field name and handle possible missing data
        address_data['input_postalcode'] = address_data.pop('postalcode', '')
        address_serializer = AddressSerializer(instance=address, data=address_data, partial=True)
        print(f"Address serializer data: {address_serializer.initial_data}")  # Debug print
        if address_serializer.is_valid():
            address = address_serializer.save(user=user)
            is_served = address.is_postalcode_served()

            return Response({'status': 'success', 'message': 'Profile updated successfully', 'is_served': is_served})
        else:
            print(f"Address serializer errors: {address_serializer.errors}")  # Debug print
            return Response({'status': 'failure', 'message': address_serializer.errors}, status=400)
    else:
        return Response({'status': 'success', 'message': 'Profile updated successfully without address data'})

def get_country_code(country_name):
    # Search through the country dictionary and find the corresponding country code
    for code, name in countries:
        if name.lower() == country_name.lower():  # Match ignoring case
            return code
    return None  # Return None if the country is not found

@api_view(['POST'])
def login_api_view(request):
    # Ensure method is POST
    print(f'Login request: {request}')
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)

    # Extract username and password
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return JsonResponse({'status': 'error', 'message': 'Username and password are required'}, status=400)

    # Authenticate user
    user = authenticate(username=username, password=password)
    if not user:
        return JsonResponse({'status': 'error', 'message': 'Invalid username or password'}, status=400)

    # Successful authentication
    try:
        refresh = RefreshToken.for_user(user)
        user_role = user.userrole  # Assuming a OneToOne relationship for simplicity

        # Fetch user goals
        goal = GoalTracking.objects.filter(user=user).first()
        goal_name = goal.goal_name if goal else ""
        goal_description = goal.goal_description if goal else ""
        # Convert the country to a string
        country = str(user.address.country) if hasattr(user, 'address') and user.address.country else None

        response_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user_id': user.id,
            'email_confirmed': user.email_confirmed,
            'timezone': user.timezone,
            'preferred_language': user.preferred_language,
            'allergies': user.allergies,
            'custom_allergies': user.custom_allergies,
            'dietary_preference': user.dietary_preference,
            'custom_dietary_preference': user.custom_dietary_preference,
            'is_chef': user_role.is_chef,
            'current_role': user_role.current_role,
            'goal_name': goal_name,
            'goal_description': goal_description,
            'country': country,
            'status': 'success',
            'message': 'Logged in successfully'
        }

        return JsonResponse(response_data, status=200)

    except Exception as e:
        # Log the exception details to debug it
        print(f"Error during user authentication: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred during authentication'}, status=500)

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
    user_data = request.data.get('user')
    if not user_data:
        return Response({'errors': 'User data is required'}, status=400)

    user_serializer = CustomUserSerializer(data=user_data)
    if not user_serializer.is_valid():
        logger.error(f"User serializer errors: {user_serializer.errors}")
        return Response({'errors': f"We've experienced an issue when updating your user information: {user_serializer.errors}"}, status=400)

    try:
        with transaction.atomic():
            user = user_serializer.save()
            UserRole.objects.create(user=user, current_role='customer')

            address_data = request.data.get('address')
            # Check if any significant address data is provided
            if address_data and any(value.strip() for value in address_data.values()):
                address_data['user'] = user.id
                address_serializer = AddressSerializer(data=address_data)
                if not address_serializer.is_valid():
                    logger.error(f"Address serializer errors: {address_serializer.errors}")
                    raise serializers.ValidationError(f"We've experienced an issue when updating your address information: {address_serializer.errors}")
                address_serializer.save()

            # Handle goal data
            goal_data = request.data.get('goal')
            if goal_data:
                GoalTracking.objects.create(
                    user=user,
                    goal_name=goal_data.get('goal_name', ''),
                    goal_description=goal_data.get('goal_description', '')
                )


            # Prepare and send activation email
            mail_subject = 'Activate your account.'
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = account_activation_token.make_token(user)
            activation_link = f"{os.getenv('STREAMLIT_URL')}/account?uid={uid}&token={token}&action=activate"        
            message = f"""
            <html>
            <body>
                <div style="text-align: center;">
                    <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
                </div>
                <h2 style="color: #333;">Welcome to SautAI, {user.username}!</h2>
                <p>Thank you for signing up! We’re excited to have you on board.</p>
                <p>To get started, please confirm your email address by clicking the button below:</p>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{activation_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Activate Your Account</a>
                </div>
                <p>If the button above doesn't work, you can copy and paste the following link into your web browser:</p>
                <p><a href="{activation_link}" style="color: #4CAF50;">{activation_link}</a></p>
                <p>If you have any issues, feel free to reach out to us at <a href="mailto:support@sautAI.com">support@sautAI.com</a>.</p>
                <p>Thanks,<br>The SautAI Support Team</p>
            </body>
            </html>
            """

            to_email = user_serializer.validated_data.get('email')
            email_data = {
                'subject': mail_subject,
                'message': message,
                'to': to_email,
                'from': 'support@sautai.com',
                'username': user.username,
                'activation_link': activation_link,
                'html': True  # Indicate that the message is in HTML format
            }
            try:
                # requests.post(os.getenv('ZAP_REGISTER_URL'), json=email_data)
                logger.info(f"Activation email data sent to Zapier for: {to_email}")
                print(f"Email data: {email_data}")
            except Exception as e:
                logger.error(f"Error sending activation email data to Zapier for: {to_email}, error: {str(e)}")
                raise 
        # After successful registration
        refresh = RefreshToken.for_user(user)  # Assuming you have RefreshToken defined or imported
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'status': 'User registered',
            'navigate_to': 'Assistant'
        })
    except serializers.ValidationError as ve:
        logger.error(f"Validation Error during user registration: {str(ve)}")
        return Response({'errors': ve.detail}, status=400)
    except IntegrityError as e:
        logger.error(f"Integrity Error during user registration: {str(e)}")
        return Response({'errors': 'Error occurred while registering. Support team has been notified.'}, status=400)
    except Exception as e:
        logger.error(f"Exception Error during user registration: {str(e)}")
        return Response({'errors': str(e)}, status=500)
    
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
            
            # Trigger the Celery tasks to create the meal plan and generate the user summary
            transaction.on_commit(lambda: create_meal_plan_for_new_user.delay(user.id))
            transaction.on_commit(lambda: generate_user_summary.delay(user.id))
            
            return Response({'status': 'success', 'message': 'Account activated successfully.'})
        else:
            return Response({'status': 'failure', 'message': 'Activation link is invalid.'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)})

@api_view(['POST'])
def resend_activation_link(request):
    try:
        print(f"Request data: {request.data}")
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({'status': 'error', 'message': 'User ID is required.'}, status=400)
        
        user = CustomUser.objects.get(pk=user_id)
        
        if user.email_confirmed:
            return Response({'status': 'error', 'message': 'This email is already verified.'}, status=400)
        
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        activation_link = f"{os.getenv('STREAMLIT_URL')}/account?uid={uid}&token={token}&action=activate"
        
        mail_subject = 'Resend Activation Link'
        message = f"""
        <html>
        <body>
            <div style="text-align: center;">
                <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
            </div>
            <h2 style="color: #333;">Welcome back to SautAI, {user.username}!</h2>
            <p>You requested a new activation link. Please confirm your email address by clicking the button below:</p>
            <div style="text-align: center; margin: 20px 0;">
                <a href="{activation_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Activate Your Account</a>
            </div>
            <p>If the button above doesn't work, you can copy and paste the following link into your web browser:</p>
            <p><a href="{activation_link}" style="color: #4CAF50;">{activation_link}</a></p>
            <p>If you have any issues, feel free to reach out to us at <a href="mailto:support@sautAI.com">support@sautAI.com</a>.</p>
            <p>Thanks,<br>The SautAI Support Team</p>
        </body>
        </html>
        """
        
        to_email = user.email
        email_data = {
            'subject': mail_subject,
            'message': message,
            'to': to_email,
            'from': 'support@sautai.com',
            'username': user.username,
            'activation_link': activation_link,
            'html': True  # Indicate that the message is in HTML format
        }
        try:
            requests.post(os.getenv('ZAP_RESEND_URL'), json=email_data)
            logger.info(f"Activation email data sent to Zapier for: {to_email}")
        except Exception as e:
            logger.error(f"Error sending activation email data to Zapier for: {to_email}, error: {str(e)}")
        
        return Response({'status': 'success', 'message': 'A new activation link has been sent to your email.'})
    
    except CustomUser.DoesNotExist:
        return Response({'status': 'error', 'message': 'User not found.'}, status=400)
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=500)

    
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


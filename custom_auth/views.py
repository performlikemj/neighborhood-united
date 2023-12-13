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
from .models import CustomUser, Address, UserRole, ChefAddress
from chefs.models import ChefRequest
from .forms import RegistrationForm, UserProfileForm, EmailChangeForm, AddressForm, ChefAddressForm
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from datetime import timedelta
from .utils import send_email_change_confirmation
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

def is_customer(user):
    return user.initial_email_confirmed

def is_correct_user(user, customuser_username):
    return user.username == customuser_username


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
    address_form_class = ChefAddressForm if user_role.current_role == 'chef' else AddressForm
    try:
        address_instance = ChefAddress.objects.get(user=request.user) if user_role.current_role == 'chef' else Address.objects.get(user=request.user)
        address_form_instance = address_form_class(request.POST or None, instance=address_instance)
    except (ChefAddress.DoesNotExist, Address.DoesNotExist):
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
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(
                mail_subject, 
                message, 
                from_email='mj@igobymj.com',  # Use a different From address
                to=[to_email]
            )
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


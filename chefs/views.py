from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseBadRequest, JsonResponse
from django.contrib.auth.decorators import login_required
from .forms import ChefProfileForm
from .models import Chef, ChefRequest
from meals.models import Dish, Meal
from .forms import MealForm
from .decorators import chef_required
from meals.forms import IngredientForm 
from custom_auth.models import UserRole
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

def chef_list(request):
    search_query = request.GET.get('search', '')

    chefs = Chef.objects.all()

    # Filtering by search query
    if search_query:
        chefs = chefs.filter(user__username__icontains=search_query)

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('chefs:chef_list'), 'name': 'Chefs'},
    ]

    context = {
        'chefs': chefs,
        'search': search_query,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'chef_list.html', context)


def chef_detail(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)
    featured_dishes = chef.featured_dishes
    summary = chef.review_summary

    print("Chef Image URL:", chef.profile_pic.url)
    print("MEDIA_ROOT:", settings.MEDIA_ROOT)
    print("MEDIA_URL:", settings.MEDIA_URL)

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('chefs:chef_list'), 'name': 'Chefs'},
        {'url': reverse('chefs:chef_detail', args=[chef_id]), 'name': chef.user.username},
    ]

    context = {
        'chef': chef,
        'chef_image': chef.profile_pic.url,
        'featured_dishes': featured_dishes,
        'summary': summary,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'chef_detail.html', context)


@login_required
def chef_request(request):
    try:
        user_role = UserRole.objects.get(user=request.user)
    except UserRole.DoesNotExist:
        return HttpResponseBadRequest('You aren\'t a chef or a customer.')

    if user_role.is_chef:
        return HttpResponseBadRequest('You are already a chef.')
    
    if request.method == 'POST':
        form = ChefProfileForm(request.POST, request.FILES)
        if form.is_valid():
            chef_request = ChefRequest.objects.create(
                user=request.user,
                experience=form.cleaned_data['experience'],
                bio=form.cleaned_data['bio'],
                profile_pic=form.cleaned_data['profile_pic'],
            )
            chef_request.requested_postalcodes.set(form.cleaned_data['serving_postalcodes'])
            return redirect('custom_auth:profile')
    else:
        form = ChefProfileForm()

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('chefs:chef_list'), 'name': 'Chefs'},
        {'url': reverse('chefs:chef_request'), 'name': 'Chef Request'},
    ]

    return render(request, 'chef_request.html', {'form': form, 'breadcrumbs': breadcrumbs})


@login_required
@chef_required
def chef_view(request):
    dishes = Dish.objects.filter(chef=request.user.chef)
    meals = Meal.objects.filter(chef=request.user.chef)
    ingredient_form = IngredientForm()  # instantiate the IngredientForm
    if request.method == 'POST':
        form = MealForm(request.POST)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.chef = request.user.chef
            meal.save()
            form.save_m2m()
            return redirect('chef_view')
    else:
        form = MealForm()

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('chefs:chef_view'), 'name': 'My Dishes'},
    ]

    return render(request, 'chef_view.html', {
        'dishes': dishes, 
        'meals': meals, 
        'form': form,
        'ingredient_form': ingredient_form, 
        'breadcrumbs': breadcrumbs,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_chef_status(request):
    """
    Check if a user is a chef or has a pending chef request
    """
    user = request.user
    
    # Check if user is a chef
    is_chef = Chef.objects.filter(user=user).exists()
    
    # Check if user has a pending chef request
    has_pending_request = ChefRequest.objects.filter(
        user=user, 
        is_approved=False
    ).exists()
    
    return JsonResponse({
        'is_chef': is_chef,
        'has_pending_request': has_pending_request
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_chef_request(request):
    """
    Submit a new chef request or update an existing one
    """
    try:
        # Log incoming request data
        print("Request Data:", request.data)
        print("POST Data:", request.POST)
        print("Files:", request.FILES)
        if 'profile_pic' in request.FILES:
            print("Profile pic details:", {
                'name': request.FILES['profile_pic'].name,
                'size': request.FILES['profile_pic'].size,
                'content_type': request.FILES['profile_pic'].content_type
            })

        # Validate required fields
        required_fields = ['user_id', 'experience', 'bio']
        missing_fields = [field for field in required_fields if not request.data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'required_fields': required_fields,
                'received_data': {
                    'data': dict(request.data),
                    'post': dict(request.POST),
                    'files': bool(request.FILES)
                }
            }, status=400)

        user_id = request.data.get('user_id')
        
        try:
            from custom_auth.models import CustomUser
            user = CustomUser.objects.get(id=user_id)
            print(f"Found user: {user.username} (ID: {user.id})")
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'error': f'User with ID {user_id} not found',
                'received_user_id': user_id
            }, status=404)
        
        # Check if user is already a chef
        if Chef.objects.filter(user=user).exists():
            return JsonResponse({
                'error': 'User is already a chef',
                'user_id': user_id
            }, status=400)
        
        # Check if user already has a pending request
        existing_request = ChefRequest.objects.filter(user=user).first()
        print(f"Existing request: {existing_request}")
        if existing_request:
            if not existing_request.is_approved:
                return JsonResponse({
                    'error': 'User already has a pending chef request',
                    'request_id': existing_request.id,
                    'user_id': user_id
                }, status=409)
            else:
                chef_request = existing_request
                print(f"Updating existing request for user {user.username}")
        else:
            chef_request = ChefRequest(user=user)
            print(f"Creating new request for user {user.username}")
        
        # Update chef request with new data
        try:
            chef_request.experience = request.data.get('experience', '')
            chef_request.bio = request.data.get('bio', '')
            
            # Handle profile pic if provided
            if 'profile_pic' in request.FILES:
                try:
                    profile_pic = request.FILES['profile_pic']
                    print(f"Processing profile pic: {profile_pic.name}")
                    
                    # Get file extension
                    import os
                    file_ext = os.path.splitext(profile_pic.name)[1].lower()
                    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
                    
                    # Check either content type or file extension
                    allowed_types = ['image/jpeg', 'image/png', 'image/gif']
                    is_valid_type = (profile_pic.content_type in allowed_types) or (file_ext in allowed_extensions)
                    print(f"Is valid type: {is_valid_type}")
                    if not is_valid_type:
                        return JsonResponse({
                            'error': 'Invalid file type',
                            'details': f'File must be a valid image (jpg, jpeg, png, or gif)',
                            'received_type': profile_pic.content_type,
                            'file_extension': file_ext
                        }, status=400)
                    
                    # Validate file size (max 5MB)
                    if profile_pic.size > 5 * 1024 * 1024:
                        return JsonResponse({
                            'error': 'File too large',
                            'details': 'Profile picture must be less than 5MB',
                            'received_size': profile_pic.size
                        }, status=400)
                    
                    chef_request.profile_pic = profile_pic
                    print("Profile pic assigned successfully")
                except Exception as e:
                    print(f"Error processing profile pic: {str(e)}")
                    return JsonResponse({
                        'error': 'Failed to process profile picture',
                        'details': str(e)
                    }, status=400)
            
            chef_request.save()
            print(f"Saved chef request for user {user.username}")
            
        except Exception as e:
            print(f"Error saving chef request: {str(e)}")
            return JsonResponse({
                'error': 'Failed to save chef request',
                'details': str(e)
            }, status=500)
        
        # Handle postal codes
        postal_codes = request.data.get('postal_codes', [])
        # Ensure postal_codes is a list
        if not isinstance(postal_codes, list):
            postal_codes = [postal_codes] if postal_codes else []
        if postal_codes:
            try:
                from local_chefs.models import PostalCode
                # Clear existing postal codes
                chef_request.requested_postalcodes.clear()
                
                processed_codes = []
                failed_codes = []
                
                # Add new postal codes
                for code in postal_codes:
                    try:
                        # First try to get existing postal code
                        postal_code = PostalCode.objects.filter(code=code).first()
                        if not postal_code:
                            # If it doesn't exist, create a new one
                            postal_code = PostalCode.objects.create(code=code)
                        chef_request.requested_postalcodes.add(postal_code)
                        processed_codes.append(code)
                    except Exception as e:
                        print(f"Error processing postal code {code}: {str(e)}")
                        failed_codes.append({'code': code, 'error': str(e)})
                
                if failed_codes:
                    print(f"Some postal codes failed: {failed_codes}")
                
            except Exception as e:
                print(f"Error handling postal codes: {str(e)}")
                return JsonResponse({
                    'error': 'Failed to process postal codes',
                    'details': str(e),
                    'processed_codes': processed_codes,
                    'failed_codes': failed_codes
                }, status=500)
        
        return JsonResponse({
            'success': True,
            'message': 'Chef request submitted successfully',
            'request_id': chef_request.id,
            'user_id': user_id,
            'processed_postal_codes': processed_codes if postal_codes else [],
            'profile_pic_saved': 'profile_pic' in request.FILES
        })
        
    except Exception as e:
        print(f"Unexpected error in submit_chef_request: {str(e)}")
        return JsonResponse({
            'error': 'An unexpected error occurred',
            'details': str(e),
            'request_data': dict(request.data)
        }, status=500)

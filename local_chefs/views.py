from django.http import JsonResponse
from .models import ChefPostalCode, PostalCode
from chefs.models import Chef
from rest_framework.response import Response
from custom_auth.models import Address, CustomUser

def chef_service_areas(request, query):
    # Normalize the query to match chef's name or identifier
    normalized_query = query.strip().lower()

    # Fetch all chefs whose username contains the normalized query
    chefs = Chef.objects.filter(user__username__icontains=normalized_query)

    if not chefs.exists():
        return JsonResponse({'error': 'No chefs found based on the query provided'})

    auth_chef_result = []

    for chef in chefs:
        # Fetch postal codes served by the chef
        postal_codes_served = ChefPostalCode.objects.filter(chef=chef).values_list('postal_code__code', flat=True)

        # Add chef information and service areas
        chef_info = {
            "chef_id": chef.id,
            "name": chef.user.username,
            "experience": chef.experience,
            "bio": chef.bio,
            "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
            'service_postal_codes': list(postal_codes_served),
        }
        auth_chef_result.append(chef_info)
    return {
        "auth_chef_result": auth_chef_result
    }

def service_area_chefs(request):
    user_id = request.data.get('user_id')
    user = CustomUser.objects.get(id=user_id)
    address = Address.objects.get(user=user)
    # Get the user's input postal code
    user_input_postalcode = address.input_postalcode

    try:
        # Get the PostalCode instance for the user's input postal code
        user_postalcode = PostalCode.objects.get(code=user_input_postalcode)

        # Filter chefs whose serving_postalcodes include the user's input postal code
        chefs = Chef.objects.filter(serving_postalcodes=user_postalcode)

        chef_result = []
        for chef in chefs:
            # Fetch postal codes served by the chef
            postal_codes_served = ChefPostalCode.objects.filter(chef=chef).values_list('postal_code__code', flat=True)

            # Add chef information and service areas
            chef_info = {
                "chef_id": chef.id,
                "name": chef.user.username,
                "experience": chef.experience,
                "bio": chef.bio,
                "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
                'service_postal_codes': list(postal_codes_served),
            }
            chef_result.append(chef_info)

        return {'chefs': chef_result}
    except PostalCode.DoesNotExist:
        return {'message': 'We do not serve your area yet. Please check back later.'}
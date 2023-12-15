from django.http import JsonResponse
from .models import ChefPostalCode, PostalCode
from chefs.models import Chef

def chef_service_areas(request, query):
    # Normalize the query to match chef's name or identifier
    normalized_query = query.strip().lower()
    print(f'Using chef_service_areas with query: {normalized_query}')

    # Fetch all chefs whose username contains the normalized query
    chefs = Chef.objects.filter(user__username__icontains=normalized_query)

    print(f'chefs: {chefs}')
    if not chefs.exists():
        return JsonResponse({'error': 'No chefs found based on the query provided'}, status=404)

    auth_chef_result = []

    for chef in chefs:
        # Fetch postal codes served by the chef
        postal_codes_served = ChefPostalCode.objects.filter(chef=chef).values_list('postal_code__code', flat=True)

        print(f'chef: {chef.user.username} - postal_codes_served: {postal_codes_served}')
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
        print(f'auth_chef_result: {auth_chef_result}')
    return {
        "auth_chef_result": auth_chef_result
    }

def service_area_chefs(request, query):
    # Normalize the query to match the postal code format
    print(f'using service_area_chefs with query: {query}')
    normalized_query = query.strip()

    try:
        # Find the postal code based on the query
        postal_code = PostalCode.objects.get(code=normalized_query)

        # Find chefs serving the queried postal code
        chefs_serving = ChefPostalCode.objects.filter(postal_code=postal_code).select_related('chef')

        if not chefs_serving:
            return JsonResponse({'message': 'No chefs are currently serving this area.'}, status=200)

        chef_info = [{
            'chef_id': chef_serve.chef.id,
            'chef_name': chef_serve.chef.user.username,  # Adjust based on your user model relation
            # Add more chef details as needed
        } for chef_serve in chefs_serving]

        response_data = {
            "postal_code": postal_code.code,
            "chefs": chef_info,
        }

        return {
            "response_data": response_data
        }

    except PostalCode.DoesNotExist:
        return JsonResponse({'error': 'Postal code not found'}, status=404)
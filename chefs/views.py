from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from .forms import ChefProfileForm
from .models import Chef, ChefRequest
from meals.models import Dish, Meal
from .forms import MealForm
from .decorators import chef_required
from meals.forms import IngredientForm 
from custom_auth.models import UserRole
from django.conf import settings

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

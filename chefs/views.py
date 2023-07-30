from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from .forms import ChefProfileForm
from .models import Chef
from menus.models import Dish, Menu
from .forms import MenuForm
from .decorators import chef_required
from menus.forms import IngredientForm 

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
    reviews = chef.reviews

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('chefs:chef_list'), 'name': 'Chefs'},
        {'url': reverse('chefs:chef_detail', args=[chef_id]), 'name': chef.user.username},
    ]

    context = {
        'chef': chef,
        'featured_dishes': featured_dishes,
        'reviews': reviews,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'chef_detail.html', context)



@login_required
def chef_request(request):
    if request.user.is_chef:
        return HttpResponseBadRequest('You are already a chef.')

    if request.method == 'POST':
        form = ChefProfileForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            user.chef_request = True
            user.chef_request_experience = form.cleaned_data['experience']
            user.chef_request_bio = form.cleaned_data['bio']
            user.chef_request_profile_pic = form.cleaned_data['profile_pic']
            user.save()

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
    menus = Menu.objects.filter(chef=request.user.chef)
    ingredient_form = IngredientForm()  # instantiate the IngredientForm
    if request.method == 'POST':
        form = MenuForm(request.POST)
        if form.is_valid():
            menu = form.save(commit=False)
            menu.chef = request.user.chef
            menu.save()
            form.save_m2m()
            return redirect('chef_view')
    else:
        form = MenuForm()

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('chefs:chef_view'), 'name': 'My Dishes'},
    ]

    return render(request, 'chef_view.html', {
        'dishes': dishes, 
        'menus': menus, 
        'form': form,
        'ingredient_form': ingredient_form, 
        'breadcrumbs': breadcrumbs,
    })

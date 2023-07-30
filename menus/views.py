from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from datetime import date, timedelta
from .forms import DishForm, IngredientForm, MenuForm
from .models import Menu, Cart, Dish, Ingredient, MealType
from chefs.models import Chef
from django.conf import settings
import requests
from django.http import JsonResponse
from django.urls import reverse
from django.http import HttpResponseBadRequest

def is_chef(user):
    return user.is_authenticated and hasattr(user, 'chef')

def api_search_ingredients(request):
    query = request.GET.get('query', '')
    results = search_ingredients(query)
    return JsonResponse(results)


def search_ingredients(query, number=20, apiKey=settings.SPOONACULAR_API_KEY):
    search_url = "https://api.spoonacular.com/food/ingredients/search"
    search_params = {
        "query": query,
        "number": number,
        "apiKey": apiKey,
    }
    response = requests.get(search_url, params=search_params)
    response.raise_for_status()  # Raises an HTTPError if the response status isn't 200
    return response.json()


@csrf_exempt
@user_passes_test(is_chef, login_url='custom_auth:login')
def api_create_ingredient(request):
    if request.method == 'POST':
        chef = request.user.chef
        name = request.POST.get('name')
        spoonacular_id = request.POST.get('spoonacular_id')

        if chef.ingredients.filter(spoonacular_id=spoonacular_id).exists():
            # Ingredient already exists, no need to add it again
            return JsonResponse({"message": "Ingredient already added"}, status=400)
        
        ingredient = Ingredient.objects.create(name=name, spoonacular_id=spoonacular_id, chef_id=chef.id)

        return JsonResponse({
            'name': ingredient.name,
            'spoonacular_id': ingredient.spoonacular_id,
            'message': "Ingredient created successfully"
        })

@login_required
def add_to_cart(request, menu_id):
    menu = get_object_or_404(Menu, pk=menu_id)

    if not request.user.email_confirmed:
        return redirect('shared/verify_email')

    if menu.end_date < date.today():
        return HttpResponseBadRequest('This menu is no longer available.')

    cart, created = Cart.objects.get_or_create(customer=request.user)
    cart.menus.add(menu)
    cart.save()

    return redirect('cart_view')


@login_required
def cart_view(request):
    cart = get_object_or_404(Cart, customer=request.user)
    total_price = sum(menu.price for menu in cart.menus.all())

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('menus:cart_view'), 'name': 'Cart'},
    ]

    context = {
        'cart': cart,
        'total_price': total_price,
        'breadcrumbs': breadcrumbs,
    }

    return render(request, 'menus/cart_view.html', context)

def dish_list(request):
    chefs = Chef.objects.all()
    # Here you are getting all the dishes, not just the ones associated with the chefs
    dishes = Dish.objects.all()
    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('menus:dish_list'), 'name': 'Dishes'},
    ]

    context = {
        'chefs': chefs,
        'dishes': dishes,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'menus/dish_list.html', context)


def dish_detail(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id)

    breadcrumbs = [
        {'url': reverse('qa_app:home'), 'name': 'Home'},
        {'url': reverse('menus:dish_list'), 'name': 'Dishes'},
        {'url': reverse('menus:dish_detail', args=[dish_id]), 'name': dish.name},
    ]

    context = {
        'dish': dish,
        'chef': dish.chef,  
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'menus/dish_detail.html', context)


@user_passes_test(is_chef, login_url='custom_auth:login')
def create_dish(request):
    if request.method == 'POST':
        form = DishForm(request.POST)
        if form.is_valid():
            dish = form.save(commit=False)
            dish.chef = request.user.chef
            dish.save()
            form.save_m2m()
            return redirect('menus:dish_detail', dish_id=dish.id)

    else:
        form = DishForm()
    context = {'form': form}
    return render(request, 'menus/create_dish.html', context)

@user_passes_test(is_chef, login_url='custom_auth:login')
def update_dish(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id)

    # Ensure the dish belongs to the authenticated chef
    if dish.chef != request.user.chef:
        return redirect('error_page')

    if request.method == 'POST':
        form = DishForm(request.POST, instance=dish)
        if form.is_valid():
            form.save()
            return redirect('menus:dish_detail', dish_id=dish.id)
    else:
        form = DishForm(instance=dish)

    context = {'form': form, 'dish': dish}
    return render(request, 'menus/update_dish.html', context)



@user_passes_test(is_chef, login_url='custom_auth:login')
def create_ingredient(request):
    if request.method == 'POST':
        # I don't believe this does anything except add to template, because functionality is in api_create_ingredient
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save(commit=False)
            spoonacular_id = form.cleaned_data.get('spoonacular_id')
            if spoonacular_id:
                # Check if ingredient already exists for this chef
                chef = request.user.chef
                if chef.ingredients.filter(spoonacular_id=spoonacular_id).exists():
                    # Ingredient already exists, no need to add it again
                    return JsonResponse({"message": "Ingredient already added"}, status=400)

                ingredient.spoonacular_id = spoonacular_id
                ingredient.chef = chef
                try:
                    ingredient.save()
                except Exception as e:
                    return JsonResponse({"message": str(e)}, status=400)
                return JsonResponse({"message": "Ingredient created successfully"}, status=200)
            else:
                return JsonResponse({"message": "No Spoonacular ID found"}, status=400)
    else:
        form = IngredientForm()
    ingredients = Ingredient.objects.filter(chef=request.user.chef)
    context = {'form': form, 'ingredients': ingredients}
    return render(request, 'menus/create_ingredient.html', context)


@user_passes_test(is_chef, login_url='custom_auth:login')
def create_menu(request):
    if request.method == 'POST':
        form = MenuForm(request.POST)
        if form.is_valid():
            menu = form.save(commit=False)
            menu.chef = request.user.chef
            menu.save()
            form.save_m2m()
            return redirect('menus:menu_detail', menu_id=menu.id)

    form = MenuForm()
    context = {'form': form}
    return render(request, 'menus/create_menu.html', context)

def chef_weekly_menu(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)
    today = date.today()
    menus = chef.menus.filter(start_date__gte=today).order_by('start_date')

    context = {
        'chef': chef,
        'menus': menus,
    }
    return render(request, 'menus/chef_weekly_menu.html', context)

def menu_detail(request, menu_id):
    menu = get_object_or_404(Menu, id=menu_id)

    context = {
        'menu': menu,
    }
    return render(request, 'menus/menu_detail.html', context)

def menu_list(request):
    menus = Menu.objects.all()

    context = {
        'menus': menus,
    }
    return render(request, 'menus/menu_list.html', context)


def menus_with_dish(request, dish_id):
    menus = Menu.objects.filter(dishes__id=dish_id)

    context = {
        'menus': menus,
    }
    return render(request, 'menus/menus_with_dish.html', context)


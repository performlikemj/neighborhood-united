import os
import json
from django.shortcuts import render, redirect
from .models import FoodQA
from meals.models import Dish, MealType, Meal
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.core.paginator import Paginator
from chefs.models import Chef
from custom_auth.models import Address
from datetime import date, timedelta
from django.db.models import Q
from reviews.models import Review
from django.contrib.contenttypes.models import ContentType
from random import sample
from collections import defaultdict
from datetime import datetime
from shared.utils import auth_get_meal_plan, auth_search_chefs, auth_search_dishes, guest_get_meal_plan, guest_search_chefs, guest_search_dishes, generate_review_summary, sanitize_query
from random import sample



# TODO: Create a completion that categorizes a meal based on what i have in the meal model

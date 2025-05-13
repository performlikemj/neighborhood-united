from django import template
from itertools import groupby

register = template.Library()

@register.filter
def groupby_day(queryset, day):
    """Group a queryset of meal_plan_meals by the day."""
    key = lambda meal_plan_meal: getattr(meal_plan_meal, day)
    return {day: list(meals) for day, meals in groupby(queryset, key)}

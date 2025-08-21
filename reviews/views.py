from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import CreateView, ListView
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.contrib.contenttypes.models import ContentType
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer
from chefs.models import Chef
from meals.models import Meal, Order, MealPlan
from events.models import Event
from custom_auth.models import UserRole
from django.views.generic.edit import UpdateView, DeleteView
from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver
from qa_app.views import generate_review_summary

# from django.core.cache import cache  # For rate limiting
# from django.core.mail import send_mail  # For sending email notifications

class ReviewCreateView(CreateView):
    model = Review
    fields = ['content', 'rating']
    template_name = 'review_create.html'

    def form_valid(self, form):
        user_role = UserRole.objects.get(user=self.request.user).current_role  # Fetch UserRole object

        if user_role == 'chef':
            return HttpResponseForbidden("Chefs cannot submit reviews.")

        content_type = ContentType.objects.get_for_model(self.model)
        object_id = self.kwargs.get('object_id')

        # TODO: Rate Limiting - Implement some sort of rate limiting to prevent spam reviews.
        # Example: Use Django's cache to store the last time a user submitted a review.
        
        existing_review = Review.objects.filter(
            content_type=content_type,
            object_id=object_id,
            user=self.request.user
        ).exists()

        if existing_review:
            return HttpResponseForbidden("You have already reviewed this. You can edit or delete your existing review.")

        if content_type == ContentType.objects.get_for_model(Chef):
            if not Order.objects.filter(meal__chef__id=object_id, customer_name=self.request.user.username).exists():
                return HttpResponseForbidden("You haven't ordered from this chef yet. Cannot write a review.")
        elif content_type == ContentType.objects.get_for_model(Meal):
            if not Order.objects.filter(meal__id=object_id, customer_name=self.request.user.username).exists():
                return HttpResponseForbidden("You haven't ordered this meal yet. Cannot write a review.")
        
        form.instance.user = self.request.user
        form.instance.content_type = content_type
        form.instance.object_id = object_id

        # TODO: User Notifications - Notify chefs when a new review is posted about them or their dishes.
        # Example: Use Django's email sending functionality here.
        # send_mail(
        #     'New Review Posted',
        #     'A new review has been posted about you or your dish.',
        #     'from@example.com',
        #     ['chef@example.com'],
        #     fail_silently=False,
        # )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('reviews:review_list')


# TODO: Pagination - Add pagination for large number of reviews.
# TODO: Search and Filter - Add features for users to search reviews by keyword or filter by rating.
# TODO: Analytics Dashboard - A dashboard for chefs to see an overview of their reviews, ratings, etc.

class ReviewListView(ListView):
    model = Review
    template_name = 'review_list.html'
    context_object_name = 'reviews'

    def get_queryset(self):
        user_role = UserRole.objects.get(user=self.request.user).current_role  # Fetch UserRole object

        if user_role == 'customer':
            return Review.objects.filter(user=self.request.user)
        elif user_role == 'chef':
            chef_reviews = Review.objects.filter(content_type=ContentType.objects.get_for_model(Chef), object_id=self.request.user.id)
            meal_reviews = Review.objects.filter(content_type=ContentType.objects.get_for_model(Meal), object_id__in=self.request.user.meals.values_list('id', flat=True))
            return chef_reviews | meal_reviews
        else:
            return Review.objects.none()


class ReviewUpdateView(UpdateView):
    model = Review
    fields = ['content', 'rating']
    template_name = 'review_edit.html'
    
    def get_success_url(self):
        return reverse_lazy('reviews:review_list')
    

class ReviewDeleteView(DeleteView):
    model = Review
    template_name = 'review_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('reviews:review_list')
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_meal_review(request, meal_id):
    user = request.user
    rating = request.data.get('rating')
    comment = request.data.get('comment', '')
    meal_plan_id = request.data.get('meal_plan_id')
    if not meal_plan_id:
        return Response({"error": "meal_plan_id is required to review a meal."}, status=400)

    meal = get_object_or_404(Meal, id=meal_id)
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)

    if not meal_plan.mealplanmeal_set.filter(meal=meal).exists():
        return Response({"error": "This meal is not part of the specified meal plan."}, status=400)

    if not meal_plan.is_approved:
        return Response({"error": "Cannot review a meal from an unapproved meal plan."}, status=403)

    # Try fetching an existing review
    existing_review = Review.objects.filter(
        user=user,
        content_type=ContentType.objects.get_for_model(Meal),
        object_id=meal.id
    ).first()

    if existing_review:
        # Update the existing review
        existing_review.rating = rating
        existing_review.comment = comment
        existing_review.save()
        serializer = ReviewSerializer(existing_review)
        return Response(serializer.data, status=200)  # or 202 Accepted
    else:
        # Create a new review
        review = Review.objects.create(
            user=user,
            content_type=ContentType.objects.get_for_model(Meal),
            object_id=meal.id,
            rating=rating,
            comment=comment
        )
        serializer = ReviewSerializer(review)
        return Response(serializer.data, status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_meal_plan_review(request, meal_plan_id):
    user = request.user
    rating = request.data.get('rating')
    comment = request.data.get('comment', '')

    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)

    # Check if the meal plan is approved
    if not meal_plan.is_approved:
        return Response({"error": "Meal plan is not approved. Reviews can only be submitted for approved meal plans."}, status=403)

    review = Review.objects.create(
        user=user,
        content_object=meal_plan,
        rating=rating,
        comment=comment
    )
    serializer = ReviewSerializer(review)
    return Response(serializer.data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_meal_plan_reviews(request, meal_plan_id):
    user = request.user
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
    reviews = meal_plan.reviews.all().order_by('-created_at')
    serializer = ReviewSerializer(reviews, many=True)
    return Response(serializer.data, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_meal_reviews(request, meal_id):
    # Make sure the meal exists
    meal = get_object_or_404(Meal, id=meal_id)

    # Filter reviews for this meal
    reviews = Review.objects.filter(
        content_type=ContentType.objects.get_for_model(Meal),
        object_id=meal.id
    ).order_by('-created_at')

    serializer = ReviewSerializer(reviews, many=True)
    return Response(serializer.data, status=200)
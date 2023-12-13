from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import CreateView, ListView
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.contrib.contenttypes.models import ContentType
from .models import Review
from chefs.models import Chef
from meals.models import Meal, Order
from events.models import Event
from custom_auth.models import UserRole
from django.views.generic.edit import UpdateView, DeleteView
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
    

@receiver(post_save, sender=Review)
def update_review_summary(sender, instance, **kwargs):
    generate_review_summary(instance.object_id, instance.content_type.model)

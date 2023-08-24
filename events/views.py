from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, DetailView, CreateView
from .models import Event
from .forms import EventForm
from django.urls import reverse
from django.utils.dateparse import parse_date


def check_admin(user):
   return user.is_superuser

class EventListView(ListView):
    model = Event
    template_name = 'event_list.html'
    context_object_name = 'events'

    def get_queryset(self):
        queryset = super().get_queryset()

        # Category filter
        category = self.request.GET.get('category')
        if category and category in dict(Event.CATEGORIES):
            queryset = queryset.filter(category=category)

        # Status filter
        status = self.request.GET.get('status')
        if status and status in dict(Event.STATUS_CHOICES):
            queryset = queryset.filter(status=status)

        # Date filter
        date_from = self.request.GET.get('date_from')
        if date_from:
            parsed_date = parse_date(date_from)
            if parsed_date:
                queryset = queryset.filter(date__gte=parsed_date)

        return queryset


class EventDetailView(DetailView):
    model = Event
    template_name = 'event_detail.html'
    context_object_name = 'event'

user_passes_test(check_admin, login_url='custom_auth:profile')
class EventCreateView(CreateView):
    model = Event
    template_name = 'event_form.html'
    form_class = EventForm

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('events:event_detail', kwargs={'pk': self.object.pk})
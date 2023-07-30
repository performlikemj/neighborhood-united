from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView
from .models import Event

class EventListView(ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'

    def get_queryset(self):
        queryset = super().get_queryset()
        # Implement filtering logic here
        return queryset


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'


class EventCreateView(CreateView):
    model = Event
    template_name = 'events/event_form.html'
    fields = ['title', 'description', 'date', 'location', 'category']

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        return super().form_valid(form)

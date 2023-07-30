from django.shortcuts import render, get_object_or_404
from django.views.generic import CreateView, ListView
from .models import Chef
from menus.models import Menu
from reviews.models import Review
from events.models import Event

class ReviewCreateView(CreateView):
    model = Review
    fields = ['title', 'text', 'rating']
    template_name = 'review_create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        chef_id = self.kwargs.get('chef_id')
        menu_id = self.kwargs.get('menu_id')
        event_id = self.kwargs.get('event_id')
        if chef_id:
            form.instance.chef = get_object_or_404(Chef, pk=chef_id)
        elif menu_id:
            form.instance.menu = get_object_or_404(Menu, pk=menu_id)
        elif event_id:
            form.instance.event = get_object_or_404(Event, pk=event_id)
        return super().form_valid(form)

class ReviewListView(ListView):
    model = Review
    template_name = 'review_list.html'
    context_object_name = 'reviews'

    def get_queryset(self):
        chef_id = self.kwargs.get('chef_id')
        menu_id = self.kwargs.get('menu_id')
        event_id = self.kwargs.get('event_id')
        if chef_id:
            chef = get_object_or_404(Chef, pk=chef_id)
            return chef.reviews.all()
        elif menu_id:
            menu = get_object_or_404(Menu, pk=menu_id)
            return menu.reviews.all()
        elif event_id:
            event = get_object_or_404(Event, pk=event_id)
            return event.reviews.all()
        else:
            return super().get_queryset()

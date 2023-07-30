from django.db import models
from chefs.models import Chef
from menus.models import Menu
from events.models import Event
from custom_auth.models import CustomUser

class Review(models.Model):
    title = models.CharField(max_length=100)
    text = models.TextField(blank=True)
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='chef_reviews')
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True) 
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reviews')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title}'

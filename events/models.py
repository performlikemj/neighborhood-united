from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Event(models.Model):
    CATEGORIES = (
        ('WS', 'Workshop'),
        ('SE', 'Seminar'),
        ('ME', 'Meetup'),
        # add more categories as needed
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=200)
    category = models.CharField(max_length=2, choices=CATEGORIES)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

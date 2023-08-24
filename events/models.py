from django.db import models
from django.conf import settings

class Event(models.Model):
    CATEGORIES = (
        ('WS', 'Workshop'),
        ('SE', 'Seminar'),
        ('ME', 'Meetup'),
        ('CO', 'Conference'),
        ('WE', 'Webinar'),
        ('FE', 'Festival'),
        ('EX', 'Exhibition'),
        ('FU', 'Fundraiser'),
        ('CO', 'Competition'),
    )
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('past', 'Past'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True, null=True)
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    youtube_video_url = models.URLField(blank=True, null=True)
    category = models.CharField(max_length=2, choices=CATEGORIES, default='ME')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organized_events', default=1)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.title

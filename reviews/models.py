from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator

class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    content = models.TextField(default="NBHD United", validators=[MinValueValidator(10), MaxValueValidator(1000)])
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    date_posted = models.DateTimeField(auto_now_add=True, null=True)
    
    # Limit the choices for content_type
    def limit_content_type_choices():
        return models.Q(app_label='chefs', model='chef') | models.Q(app_label='meals', model='meal')

    # Generic Foreign Key setup
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        limit_choices_to=limit_content_type_choices
    )
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f'Review by {self.user} - {self.rating}/5'

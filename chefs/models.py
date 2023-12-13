from django.conf import settings
from django.db import models
from local_chefs.models import PostalCode, ChefPostalCode

class Chef(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    experience = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    serving_postalcodes = models.ManyToManyField(
        PostalCode,
        through=ChefPostalCode,
        related_name='serving_chefs'
    )
    profile_pic = models.ImageField(upload_to='chefs/profile_pics/', blank=True)
    chef_request = models.BooleanField(default=False)
    chef_request_experience = models.TextField(blank=True, null=True)
    chef_request_bio = models.TextField(blank=True, null=True)
    chef_request_profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    review_summary = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.user.username

    @property
    def featured_dishes(self):
        return self.dishes.filter(featured=True)

    @property
    def reviews(self):
        return self.chef_reviews.all()

    class Meta:
        app_label = 'chefs'


class ChefRequest(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    experience = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    requested_postalcodes = models.ManyToManyField(PostalCode, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Chef Request for {self.user.username}"

from django.conf import settings
from django.db import models
from local_chefs.models import PostalCode, ChefPostalCode
from pgvector.django import VectorField

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
    chef_embedding = VectorField(dimensions=1536, null=True, blank=True)  # Embedding field


    def __str__(self):
        # Combine chef's information into one string
        postal_codes = ', '.join([postal_code.code for postal_code in self.serving_postalcodes.all()])
        info_parts = [
            f"Username: {self.user.username}",
            f"Experience: {self.experience}",
            f"Bio: {self.bio}",
            f"Serving Postal Codes: {postal_codes}",
            f"Review Summary: {self.review_summary}"
        ]
        # Filter out None or empty strings before joining
        filtered_info = [part for part in info_parts if part]
        return '. '.join(filtered_info) + '.'
    
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

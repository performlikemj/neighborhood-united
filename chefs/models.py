from django.conf import settings
from django.db import models
from local_chefs.models import PostalCode, ChefPostalCode
from pgvector.django import VectorField
from django.utils import timezone

class Chef(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    experience = models.CharField(max_length=500, blank=True)
    bio = models.TextField(blank=True)
    # Simple availability flag: when True, the chef is temporarily not accepting orders
    is_on_break = models.BooleanField(default=False, help_text="Temporarily not accepting orders")
    # Verification & compliance
    is_verified = models.BooleanField(default=False, help_text="Admin approval for platform listing")
    background_checked = models.BooleanField(default=False)
    insured = models.BooleanField(default=False)
    insurance_expiry = models.DateField(blank=True, null=True)
    food_handlers_cert = models.BooleanField(default=False)
    serving_postalcodes = models.ManyToManyField(
        PostalCode,
        through=ChefPostalCode,
        related_name='serving_chefs'
    )
    profile_pic = models.ImageField(upload_to='chefs/profile_pics/', blank=True)
    banner_image = models.ImageField(upload_to='chefs/banners/', blank=True, null=True)
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


class ChefPhoto(models.Model):
    """Gallery photo uploaded by an approved chef to showcase their food."""
    CATEGORY_CHOICES = [
        ('appetizer', 'Appetizer'),
        ('main', 'Main Course'),
        ('dessert', 'Dessert'),
        ('beverage', 'Beverage'),
        ('side', 'Side Dish'),
        ('other', 'Other'),
    ]
    
    chef = models.ForeignKey('Chef', on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='chefs/photos/')
    thumbnail = models.ImageField(upload_to='chefs/photos/thumbnails/', blank=True, null=True)
    
    # Text fields
    title = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    description = models.TextField(blank=True)
    
    # Relationships
    dish = models.ForeignKey('meals.Dish', on_delete=models.SET_NULL, null=True, blank=True, related_name='photos')
    meal = models.ForeignKey('meals.Meal', on_delete=models.SET_NULL, null=True, blank=True, related_name='photos')
    
    # Organization
    tags = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, null=True)
    
    # Metadata
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    file_size = models.IntegerField(blank=True, null=True)
    
    # Features
    is_featured = models.BooleanField(default=False)
    is_public = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['chef', '-created_at']),
            models.Index(fields=['chef', 'category']),
            models.Index(fields=['chef', 'is_public']),
        ]

    def __str__(self):
        base = self.title or 'Chef Photo'
        return f"{base} (chef_id={self.chef_id})"
    
    def save(self, *args, **kwargs):
        """Extract image dimensions and file size on save."""
        if self.image and hasattr(self.image, 'file'):
            try:
                from PIL import Image
                image = Image.open(self.image.file)
                self.width, self.height = image.size
                
                # Get file size
                self.image.file.seek(0, 2)  # Seek to end
                self.file_size = self.image.file.tell()
                self.image.file.seek(0)  # Reset to beginning
            except Exception:
                pass  # Silently fail if we can't extract metadata
        
        super().save(*args, **kwargs)


class ChefDefaultBanner(models.Model):
    """Site-wide default banner that applies when a Chef has no custom banner_image."""
    image = models.ImageField(upload_to='chefs/banners/defaults/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return f"ChefDefaultBanner(id={self.id})"


class ChefVerificationDocument(models.Model):
    """Documents uploaded by chef for verification: insurance, background, certifications."""
    DOC_TYPES = [
        ('insurance', 'Insurance'),
        ('background', 'Background Check'),
        ('food_handlers', 'Food Handler Certificate'),
        ('other', 'Other'),
    ]
    chef = models.ForeignKey('Chef', on_delete=models.CASCADE, related_name='verification_docs')
    doc_type = models.CharField(max_length=32, choices=DOC_TYPES)
    file = models.FileField(upload_to='chefs/verification_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)
    rejected_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"VerificationDoc(type={self.doc_type}, chef_id={self.chef_id}, approved={self.is_approved})"

# Waitlist feature models
class ChefWaitlistConfig(models.Model):
    """Global toggle and config for chef waitlist notifications."""
    enabled = models.BooleanField(default=False, help_text="Enable chef waitlist feature globally")
    cooldown_hours = models.PositiveIntegerField(default=24, help_text="Minimum hours a chef must be inactive before a new activation triggers notifications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'chefs'
        verbose_name = 'Chef Waitlist Config'
        verbose_name_plural = 'Chef Waitlist Config'

    def __str__(self):
        return f"Waitlist {'ENABLED' if self.enabled else 'DISABLED'} (cooldown={self.cooldown_hours}h)"

    @classmethod
    def get_config(cls):
        return cls.objects.order_by('-updated_at', '-id').first()

    @classmethod
    def get_enabled(cls) -> bool:
        cfg = cls.get_config()
        return bool(getattr(cfg, 'enabled', False))

    @classmethod
    def get_cooldown_hours(cls) -> int:
        cfg = cls.get_config()
        return int(getattr(cfg, 'cooldown_hours', 24) or 24)


class ChefAvailabilityState(models.Model):
    """Tracks a chef's availability state for orderable events and notification epochs."""
    chef = models.OneToOneField('Chef', on_delete=models.CASCADE, related_name='availability')
    is_active = models.BooleanField(default=False)
    activation_epoch = models.PositiveIntegerField(default=0, help_text="Increments each time the chef becomes active after a cooldown")
    last_activated_at = models.DateTimeField(null=True, blank=True)
    last_deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'chefs'
        verbose_name = 'Chef Availability State'
        verbose_name_plural = 'Chef Availability States'

    def __str__(self):
        return f"ChefAvailability(chef_id={self.chef_id}, active={self.is_active}, epoch={self.activation_epoch})"


class ChefWaitlistSubscription(models.Model):
    """Per-user subscription to be notified when a chef becomes active again."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chef_waitlist_subscriptions')
    chef = models.ForeignKey('Chef', on_delete=models.CASCADE, related_name='waitlist_subscriptions')
    active = models.BooleanField(default=True)
    last_notified_epoch = models.PositiveIntegerField(null=True, blank=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'chefs'
        unique_together = (('user', 'chef', 'active'),)
        indexes = [
            models.Index(fields=['chef', 'active']),
            models.Index(fields=['user', 'active']),
        ]

    def __str__(self):
        status = 'active' if self.active else 'inactive'
        return f"Waitlist({self.user_id} -> chef {self.chef_id}, {status}, last_epoch={self.last_notified_epoch})"

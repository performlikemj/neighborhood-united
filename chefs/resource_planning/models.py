"""
Chef Resource Planning Models

These models support the chef resource optimization system, providing:
- Structured recipe ingredients with quantities
- Aggregated prep plans across upcoming commitments
- Smart shopping lists with shelf-life awareness
"""
from django.db import models
from django.utils import timezone


class RecipeIngredient(models.Model):
    """
    Structured ingredient with quantity for a dish.
    
    This model provides a more detailed representation than the basic
    Dish.ingredients M2M, including precise quantities and storage information
    for resource planning calculations.
    """
    STORAGE_TYPE_CHOICES = [
        ('refrigerated', 'Refrigerated'),
        ('frozen', 'Frozen'),
        ('pantry', 'Pantry/Dry'),
        ('counter', 'Counter'),
    ]

    dish = models.ForeignKey(
        'meals.Dish',
        on_delete=models.CASCADE,
        related_name='recipe_ingredients'
    )
    name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=50)  # grams, cups, pieces, etc.
    notes = models.TextField(blank=True)
    
    # Cached shelf life from Groq (refreshed periodically)
    shelf_life_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated shelf life in days, determined by AI"
    )
    storage_type = models.CharField(
        max_length=20,
        choices=STORAGE_TYPE_CHOICES,
        default='refrigerated'
    )
    shelf_life_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When shelf life was last determined/refreshed"
    )

    class Meta:
        app_label = 'chefs'
        indexes = [
            models.Index(fields=['dish', 'name']),
            models.Index(fields=['name']),
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.name} (dish_id={self.dish_id})"

    def needs_shelf_life_refresh(self, max_age_days: int = 30) -> bool:
        """Check if shelf life data needs to be refreshed."""
        if self.shelf_life_days is None or self.shelf_life_updated_at is None:
            return True
        age = timezone.now() - self.shelf_life_updated_at
        return age.days > max_age_days


class ChefPrepPlan(models.Model):
    """
    Aggregated planning view for a chef's upcoming service window.
    
    A prep plan consolidates all upcoming meal events and service orders
    for a chef within a date range, providing an optimized shopping list
    and batch cooking suggestions.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='prep_plans'
    )
    plan_start_date = models.DateField()
    plan_end_date = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Aggregated data stored as JSON for quick retrieval
    shopping_list = models.JSONField(
        null=True,
        blank=True,
        help_text="Aggregated shopping list with timing suggestions"
    )
    batch_suggestions = models.JSONField(
        null=True,
        blank=True,
        help_text="AI-generated batch cooking recommendations"
    )
    
    # Summary statistics
    total_meals = models.PositiveIntegerField(default=0)
    total_servings = models.PositiveIntegerField(default=0)
    unique_ingredients = models.PositiveIntegerField(default=0)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    notes = models.TextField(blank=True)

    class Meta:
        app_label = 'chefs'
        indexes = [
            models.Index(fields=['chef', '-plan_start_date']),
            models.Index(fields=['chef', 'status']),
        ]
        ordering = ['-plan_start_date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(plan_end_date__gte=models.F('plan_start_date')),
                name='prep_plan_end_after_start'
            ),
        ]

    def __str__(self):
        return f"PrepPlan(chef_id={self.chef_id}, {self.plan_start_date} to {self.plan_end_date})"

    @property
    def duration_days(self) -> int:
        """Number of days covered by this plan."""
        return (self.plan_end_date - self.plan_start_date).days + 1


class ChefPrepPlanItem(models.Model):
    """
    Individual shopping item within a prep plan.
    
    Each item represents an aggregated ingredient need across all meals
    in the plan window, with smart timing suggestions based on shelf life.
    """
    STORAGE_TYPE_CHOICES = [
        ('refrigerated', 'Refrigerated'),
        ('frozen', 'Frozen'),
        ('pantry', 'Pantry/Dry'),
        ('counter', 'Counter'),
    ]
    
    TIMING_STATUS_CHOICES = [
        ('optimal', 'Optimal'),      # Plenty of time
        ('tight', 'Tight'),          # Less than ideal but workable
        ('problematic', 'Problematic'),  # May need to split purchase
        ('impossible', 'Impossible'),    # Shelf life too short for date range
    ]

    prep_plan = models.ForeignKey(
        ChefPrepPlan,
        on_delete=models.CASCADE,
        related_name='items'
    )
    ingredient_name = models.CharField(max_length=200)
    total_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50)
    
    # Shelf life information
    shelf_life_days = models.PositiveIntegerField(
        help_text="Estimated shelf life in days"
    )
    storage_type = models.CharField(
        max_length=20,
        choices=STORAGE_TYPE_CHOICES,
        default='refrigerated'
    )
    
    # Timing calculations
    earliest_use_date = models.DateField(
        help_text="First meal needing this ingredient"
    )
    latest_use_date = models.DateField(
        help_text="Last meal needing this ingredient"
    )
    suggested_purchase_date = models.DateField(
        help_text="Calculated optimal purchase date based on shelf life"
    )
    timing_status = models.CharField(
        max_length=20,
        choices=TIMING_STATUS_CHOICES,
        default='optimal'
    )
    timing_notes = models.TextField(
        blank=True,
        help_text="Explanation of timing considerations"
    )
    
    # Meal tracking
    meals_using = models.JSONField(
        help_text="List of meal names and dates using this ingredient"
    )
    
    # Purchase tracking
    is_purchased = models.BooleanField(default=False)
    purchased_date = models.DateField(null=True, blank=True)
    purchased_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    class Meta:
        app_label = 'chefs'
        indexes = [
            models.Index(fields=['prep_plan', 'ingredient_name']),
            models.Index(fields=['prep_plan', 'suggested_purchase_date']),
            models.Index(fields=['prep_plan', 'timing_status']),
        ]
        ordering = ['suggested_purchase_date', 'ingredient_name']

    def __str__(self):
        return f"{self.total_quantity} {self.unit} {self.ingredient_name} (plan_id={self.prep_plan_id})"

    def calculate_timing_status(self) -> str:
        """
        Determine the timing status based on shelf life and usage dates.
        
        Returns the timing status and updates the field.
        """
        use_span = (self.latest_use_date - self.earliest_use_date).days
        
        if self.shelf_life_days >= use_span + 2:
            # Plenty of buffer
            self.timing_status = 'optimal'
            self.timing_notes = f"Shelf life ({self.shelf_life_days} days) comfortably covers usage span ({use_span} days)."
        elif self.shelf_life_days >= use_span:
            # Workable but tight
            self.timing_status = 'tight'
            self.timing_notes = f"Shelf life ({self.shelf_life_days} days) just covers usage span ({use_span} days). Buy close to first use date."
        elif self.shelf_life_days >= use_span // 2:
            # May need to split purchase
            self.timing_status = 'problematic'
            self.timing_notes = f"Shelf life ({self.shelf_life_days} days) doesn't cover full usage span ({use_span} days). Consider splitting purchase or using frozen."
        else:
            # Impossible without multiple purchases
            self.timing_status = 'impossible'
            self.timing_notes = f"Shelf life ({self.shelf_life_days} days) is much shorter than usage span ({use_span} days). Must purchase multiple times or freeze."
        
        return self.timing_status


class ChefPrepPlanCommitment(models.Model):
    """
    Links a prep plan to specific meal commitments.
    
    This through-model tracks which commitments are included in a plan,
    allowing for easy updates when orders change.
    
    Supports three types of commitments:
    - client_meal_plan: Meals from ChefMealPlan (primary workflow)
    - meal_event: Public meal events with customer orders
    - service_order: Booked service appointments
    """
    COMMITMENT_TYPE_CHOICES = [
        ('client_meal_plan', 'Client Meal Plan'),
        ('meal_event', 'Meal Event'),
        ('service_order', 'Service Order'),
    ]

    prep_plan = models.ForeignKey(
        ChefPrepPlan,
        on_delete=models.CASCADE,
        related_name='commitments'
    )
    commitment_type = models.CharField(
        max_length=20,
        choices=COMMITMENT_TYPE_CHOICES
    )
    
    # References to source objects (all optional, depends on commitment_type)
    chef_meal_plan = models.ForeignKey(
        'meals.ChefMealPlan',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prep_plan_links'
    )
    meal_event = models.ForeignKey(
        'meals.ChefMealEvent',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prep_plan_links'
    )
    service_order = models.ForeignKey(
        'chef_services.ChefServiceOrder',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='prep_plan_links'
    )
    
    # Denormalized for quick access
    service_date = models.DateField()
    servings = models.PositiveIntegerField(default=1)
    meal_name = models.CharField(max_length=200, blank=True)
    customer_name = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = 'chefs'
        indexes = [
            models.Index(fields=['prep_plan', 'service_date']),
            models.Index(fields=['prep_plan', 'commitment_type']),
        ]
        ordering = ['service_date', 'meal_name']

    def __str__(self):
        label = f"{self.meal_name}"
        if self.customer_name:
            label += f" for {self.customer_name}"
        return f"{self.commitment_type}: {label} on {self.service_date}"




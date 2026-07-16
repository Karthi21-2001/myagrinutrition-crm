from django.db import models
from django.conf import settings

class Farm(models.Model):
    """
    Tracks foundational details of the farm, owner structural data, 
    geographical breakdown matrices, and livestock inventory telemetry.
    """
    BUSINESS_TYPE_CHOICES = [
        ('Poultry', 'Poultry Sector'),
        ('Aqua', 'Aqua Sector'),
        ('General', 'General Agriculture'),
    ]

    executive = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_farms',
        help_text="The field executive assigned to manage this farm account."
    )
    farm_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    
    business_type = models.CharField(
        max_length=50, 
        choices=BUSINESS_TYPE_CHOICES, 
        default='General'
    )
    sub_segment = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Specific operational sub-classification or industry segment."
    )  # <-- Added Field
    
    # 🐥 Poultry Shed Population Inventory Tracking Metrics
    chicks_count = models.IntegerField(default=0, verbose_name="Chicks Population")
    grower_count = models.IntegerField(default=0, verbose_name="Grower Population")
    layer_count = models.IntegerField(default=0, verbose_name="Layer Population")
    culling_bird_count = models.IntegerField(default=0, verbose_name="Culling Bird Population")
    
    # Hierarchical Regional Parameters for Dashboard Analytics
    country = models.CharField(max_length=100, default="India")
    state = models.CharField(max_length=100, default="State")
    district = models.CharField(max_length=100, blank=True, default='')
    area = models.CharField(max_length=255, blank=True, default='', help_text="Block or Assigned Area")
    
    # Geolocation mapping coordinates mapped to FloatField for backend processing alignment
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Unified tracking timestamp field name across tables
    visit_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Farm Profile"
        verbose_name_plural = "Farm Profiles"
        ordering = ['-created_at']

    @property
    def visiting_count(self):
        """Calculates total historical visit reports logged for this profile."""
        return self.visits.count()

    @property
    def total_birds(self):
        """Calculates total capacity across all sheds dynamically."""
        return self.chicks_count + self.grower_count + self.layer_count + self.culling_bird_count

    def __str__(self):
        return f"{self.farm_name} - {self.owner_name} ({self.get_business_type_display()})"


class FarmVisitReport(models.Model):
    """
    Logs each specific field visit activity event instance. Serves as the 
    parent record grouping the ordered products together.
    """
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='visits'
    )
    executive = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='filed_visit_reports'
    )
    farm_problem = models.TextField(blank=True, null=True)
    
    # Aligned with the exact field lookup criteria filtering dashboard telemetry
    visit_date = models.DateTimeField(auto_now_add=True, help_text="Date the visit occurred.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Field Visit Report"
        verbose_name_plural = "Field Visit Reports"
        ordering = ['-created_at']

    def __str__(self):
        return f"Visit to {self.farm.farm_name} on {self.visit_date.strftime('%Y-%m-%d') if self.visit_date else ''}"


class VisitedProductDetail(models.Model):
    """
    Holds individual product items booked or tracked during field visits, 
    including advanced conversion percentage and line-item revenue records.
    """
    PROCESS_CHOICES = [
        ('Cold', '❄️ Cold'),
        ('Warm', '🔥 Warm'),
        ('Hot', '💥 Hot'),
    ]

    # Explicit related_name='products' definition securely resolves backward field resolution issues
    visit = models.ForeignKey(
        FarmVisitReport, 
        on_delete=models.CASCADE, 
        related_name='products'
    )
    product_name = models.CharField(max_length=255)
    
    # Live Input Tracking Attributes
    potential_quantity = models.IntegerField(default=0, blank=True)
    target_quantity = models.IntegerField(default=0, blank=True)
    sale_quantity = models.IntegerField(default=0)
    unit_type = models.CharField(max_length=50, default='KG', help_text="Bags, Liters, KG etc.")
    
    # Financial data structures supporting custom pipeline metrics
    primary_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    revenue_generated = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Pipeline conversion components
    process_status = models.CharField(max_length=50, choices=PROCESS_CHOICES, default='Warm')
    conversion_percentage = models.IntegerField(default=0)  # Value between 0 and 100

    class Meta:
        verbose_name = "Visited Product Detail"
        verbose_name_plural = "Visited Product Details"

    def save(self, *args, **kwargs):
        """Automatically updates line item metrics if price and quantity match up."""
        if self.primary_price and self.sale_quantity:
            self.revenue_generated = self.primary_price * self.sale_quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.sale_quantity} {self.unit_type}) - Visit #{self.visit.id}"

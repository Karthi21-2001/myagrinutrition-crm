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

    # NEW: Distributor supplying/servicing this farm account. Treated as
    # a farm-level attribute (like owner_name) rather than a per-visit
    # field, since the distributor tied to a farm doesn't usually change
    # visit-to-visit.
    distributor_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Distributor associated with this farm account."
    )

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
    )
    
    # Poultry Shed Population Inventory Tracking Metrics
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
    STATUS_CHOICES = [
        ('Completed', 'Completed'),
        ('Follow-up Required', 'Follow-up Required'),
        ('No Response', 'No Response'),
    ]

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

    visit_status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='Completed',
        help_text="Outcome status of this visit."
    )

    # FIX: this field was missing entirely, which is why
    # save_farm_visit()'s next_visit_date=... create() call always hit
    # its TypeError fallback and silently dropped the value, and why
    # the Excel export column ("Next Visit Date") was always blank.
    next_visit_date = models.DateField(
        null=True,
        blank=True,
        help_text="Planned follow-up date captured on the visit-logging form."
    )

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

    # Explicit related_name='visited_products' matches prefetch_related lookups
    visit = models.ForeignKey(
        FarmVisitReport, 
        on_delete=models.CASCADE, 
        related_name='visited_products'
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


class WhatsAppGroup(models.Model):
    """A WhatsApp group the CRM can send notifications to."""
    name = models.CharField(max_length=100, unique=True)           # internal label
    whatsapp_group_title = models.CharField(max_length=150)        # EXACT title as shown in WhatsApp
    area = models.CharField(max_length=100, blank=True, null=True)
    team = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "WhatsApp Group"
        verbose_name_plural = "WhatsApp Groups"

    def __str__(self):
        return f"{self.name} ({self.whatsapp_group_title})"


class SalesExecutiveProfile(models.Model):
    """
    Extends the existing User model with CRM-specific identity fields
    (employee ID, area, team, WhatsApp routing) instead of duplicating
    the executive record that Farm/FarmVisitReport already point to.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_profile"
    )
    employee_id = models.CharField(max_length=50, unique=True)  # e.g. MurugesanMYA070
    area = models.CharField(max_length=100, blank=True, null=True)
    team = models.CharField(max_length=100, blank=True, null=True)
    whatsapp_group = models.ForeignKey(
        WhatsAppGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="executives"
    )

    class Meta:
        verbose_name = "Sales Executive Profile"
        verbose_name_plural = "Sales Executive Profiles"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"

# crm/models/customer.py
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from tenancy.models import TenantBaseModel

class Customer(TenantBaseModel):
    class Status(models.TextChoices):
        LEAD = 'LEAD', _('Lead')
        ACTIVE = 'ACTIVE', _('Active')
        INACTIVE = 'INACTIVE', _('Inactive')
        BLOCKED = 'BLOCKED', _('Blocked')

    class CustomerType(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', _('Individual')
        BUSINESS = 'BUSINESS', _('Business')

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    type = models.CharField(max_length=10, choices=CustomerType.choices, db_index=True)
    display_name = models.CharField(max_length=200, help_text=_("Full name for individuals or trading/common name for businesses."))
    email = models.EmailField(db_index=True)
    phone = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[\d\s\-\(\)]{7,20}$",
                message=_("Enter a valid phone number."),
            )
        ]
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Customer')
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(type__in=['INDIVIDUAL', 'BUSINESS']),
                name='customer_valid_type'
            ),
            models.UniqueConstraint(
                fields=('workspace', 'email'),
                name='unique_customer_email_per_workspace'
            )
        ]

    def __str__(self):
        return f"{self.display_name} ({self.type})"
    
    def clean(self):
        super().clean()
        if self.type == self.CustomerType.INDIVIDUAL and hasattr(self, 'business_profile'):
            raise ValidationError({"type": _("An individual customer cannot have a business profile.")})
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Address(TenantBaseModel):
    class Purpose(models.TextChoices):
        BILLING = "billing", _("Billing")
        SHIPPING = "shipping", _("Shipping")
        HEADQUARTERS = "headquarters", _("Headquarters")
        WAREHOUSE = "warehouse", _("Warehouse")
        OTHER = "other", _("Other")

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    purpose = models.CharField(max_length=12, choices=Purpose.choices, db_index=True)
    label = models.CharField(max_length=100, blank=True, null=True)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2)
    is_primary = models.BooleanField(default=False,)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['"-is_primary", "purpose", "created_at"']
        constraints = [
            # Only one primary address per purpose per customer
            models.UniqueConstraint(
                fields=["customer", "purpose"],
                condition=models.Q(is_primary=True),
                name="unique_primary_address_per_purpose",
            ),
        ]

    def __str__(self) -> str:
        parts = [self.line1, self.city, self.country]
        label = f" ({self.label})" if self.label else ""
        return f"{self.purpose}{label}: {', '.join(filter(None, parts))}"
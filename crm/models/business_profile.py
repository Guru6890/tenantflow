# crm/models/business_profile.py
import uuid
from django.db import models
from django.core.exceptions import ValidationError

from tenancy.models import TenantBaseModel
from crm.models.customer import Customer
from crm.models.lead import Lead

class BusinessProfile(TenantBaseModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='business_profile', null=True, blank=True)
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE, related_name='business_profile', null=True, blank=True)
    legal_name = models.CharField(max_length=250)
    tax_identifier = models.CharField(max_length=100, null=True, blank=True)
    website = models.URLField(blank=True, null=True)
    industry = models.CharField(max_length=128, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                condition=(
                    models.Q(customer__isnull=False, lead__isnull=True)
                    | models.Q(customer__isnull=True, lead__isnull=False)
                ),
                name='business_profile_xor_customer_lead'
            )
        ]
    def __str__(self):
        return self.legal_name
    
    def clean(self):
        if self.customer and self.lead:
            raise ValidationError('Same business profile cannot belong to both a customer and a lead.')
        if not self.customer and not self.lead:
            raise ValidationError('Business profile must belong to either a customer or a lead.')
        if self.customer and self.customer.type != Customer.CustomerType.BUSINESS:
            raise ValidationError("Business profile can only be attached to a business customer.")
        if self.lead and self.lead.type != Lead.LeadType.BUSINESS:
            raise ValidationError("Business profile can only be attached to a business customer.")
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
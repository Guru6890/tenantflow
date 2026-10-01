# crm/models/deal.py
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings

from decimal import Decimal

from tenancy.models import TenantBaseModel
from crm.models.customer import Customer
from crm.models.pipeline import Pipeline, PipelineStage

class Deal(TenantBaseModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='deals')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name='deals')
    stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name='deals')
    title = models.CharField(max_length=100)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0.00)])
    expected_close_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_deals',
        null=True,
        blank=True
    )

    won_at = models.DateTimeField(null=True, blank=True)
    lost_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} (${self.value})"
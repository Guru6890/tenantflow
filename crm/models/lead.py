# crm/models/lead.py
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator

from tenancy.models import TenantBaseModel

class Lead(TenantBaseModel):
    class LeadType(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', 'Individual'
        BUSINESS = 'BUSINESS', 'Business'

    class ContactMethod(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        PHONE = 'PHONE', 'Phone'
        WHATSAPP = 'WHATSAPP', 'Whatsapp'
        SMS = 'SMS', 'SMS'

    class Status(models.TextChoices):
        NEW = 'NEW', 'New'
        ATTEMPTED_CONTACT = 'ATTEMPTED_CONTACT', 'Attempted Contact'
        CONTACTED = 'CONTACTED', 'Contacted'
        QUALIFIED = 'QUALIFIED', 'Qualified'
        UNQUALIFIED = 'UNQUALIFIED', 'Unqualified'
        CONVERTED = 'CONVERTED', 'Converted'

    class Source(models.TextChoices):
        WEBSITE = 'WEBSITE', 'Website'
        INBOUND_CALL = 'INBOUND_CALL', 'Inbound Call'
        REFERRAL = 'REFERRAL', 'Referral'
        CAMPAIGN = 'CAMPAIGN', 'Campaign'
        WALK_IN = 'WALK_IN', 'Walk In'
        OUTBOUND = 'OUTBOUND', 'Outbound'

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    type = models.CharField(max_length=10, choices=LeadType.choices, db_index=True)
    display_name = models.CharField(max_length=200)
    email = models.EmailField(db_index=True)
    phone = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[\d\s\-\(\)]{7,20}$",
                message="Enter a valid phone number."
            )
        ]
    )
    preferred_contact_method = models.CharField(max_length=8, choices=ContactMethod.choices, default=ContactMethod.EMAIL)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.NEW)
    source = models.CharField(max_length=13, choices=Source.choices)
    address = models.TextField(null=True, blank=True)
    assigned_to_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    notes = models.TextField(null=True, blank=True)

    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by_user_id = models.UUIDField(null=True, blank=True)

    qualification_score = models.PositiveSmallIntegerField(null=True, blank=True,
                                                           validators=[MaxValueValidator(0), MaxValueValidator(100)])
    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.display_name} ({self.get_status_display()})"
    
    def mark_converted(self, user_id=None):
        """Helper you can call from a service layer."""
        from django.utils import timezone
        self.status = self.Status.CONVERTED
        self.converted_at = timezone.now()
        self.converted_by_user_id = user_id
        self.save(update_fields=["status", "converted_at", "converted_by_user_id", "updated_at"])
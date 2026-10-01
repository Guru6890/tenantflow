# crm/models/contact.py
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from crm.models.customer import Customer
from tenancy.models import TenantBaseModel

class Contact(TenantBaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=50)
    email = models.EmailField()
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
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace","customer"],
                condition=models.Q(is_primary=True),
                name="unique_primary_contact_per_customer",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.customer.display_name})"
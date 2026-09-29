from django.db import models
import uuid

from tenancy.models import TenantBaseModel
# Create your models here.

class Warehouse(TenantBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'code'],
                name='unique_warehouse_code_per_workspace'
            )
        ]

    def __str__(self):
        return self.name
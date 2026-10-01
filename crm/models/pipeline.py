# crm/models/pipeline.py
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from tenancy.models import TenantBaseModel

class Pipeline(TenantBaseModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class PipelineStage(TenantBaseModel):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(help_text='Visual ordering priority e.x (1, 2, 3)')
    probability = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=10,
        help_text='Win probability percentage (0-100)'
    )
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(
                fields = ['workspace', 'pipeline', 'name'],
                name = 'unique_name_for_pipeline'
            )
        ]

    def __str__(self) -> str:
        return f'{self.pipeline.name} -> {self.name}'
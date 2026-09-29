# tenancy/models.py
import uuid
from django.db import models
from django.utils import timezone

class Workspace(models.Model):
    class BusinessTypes(models.TextChoices):
        GYM = 'gym', 'Gym / Fitness Studio'
        PHARMACY = 'pharmacy', 'Medical Shop / Pharmacy'
        MANUFACTURING = 'manufacturing', 'Manufacturing / Production'
        FOOD = 'food', 'Food Products'
        RETAIL = 'retail', 'Supermarket / General Retail'
        SERVICE = 'service', 'Service Business'
        OTHER = 'other', 'Other'

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    business_type = models.CharField(max_length=30, choices=BusinessTypes.choices)
    settings = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class WorkspaceMembership(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    
    user = models.ForeignKey(
        'identity.User', 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    workspace = models.ForeignKey(
        Workspace, 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    role = models.ForeignKey(
        'authorization.Role', 
        on_delete=models.PROTECT, 
        related_name='memberships'
    )

    invited_by = models.ForeignKey(
        'identity.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_invitations'
    )
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"],
                name="unique_user_workspace"
            )
        ]   # One user per workspace
        
        ordering = ['-joined_at']

# ====================== Tenant Isolation ======================

from django.db import models
from django.utils import timezone

from .utils import get_current_workspace

class TenantQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)
    
    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)
    
    def delete(self):
        """Bulk soft-deletion across a QuerySet."""
        return self.update(is_deleted=True, deleted_at=timezone.now())
    
    def hard_delete(self):
        """Bulk physical database deletion."""
        return super().delete()
    
    def restore(self):
        return self.update(is_deleted=False, deleted_at=None)

class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Unified manager capable of handling workspace context 
    and soft-delete state filtering simultaneously.
    """
    def __init__(self, include_deleted=False, include_all_workspaces=False, *args, **kwargs):
        self.include_deleted = include_deleted
        self.include_all_workspaces = include_all_workspaces
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        # We start with our robust custom QuerySet base
        queryset = super().get_queryset()
        
        # 1. Apply Soft Delete filter unless explicitly bypassed
        if not self.include_deleted:
            queryset = queryset.filter(is_deleted=False)
            
        # 2. Apply Tenant/Workspace isolation filter unless explicitly bypassed
        if not self.include_all_workspaces:
            current_workspace = get_current_workspace()
            if current_workspace is None:
                raise RuntimeError('No active workspace context')
            queryset = queryset.filter(workspace=current_workspace)
                
        return queryset

class TenantBaseModel(models.Model):
    """
    The universal foundation for the SaaS IMS application. 
    Handles identity, tenant isolation, auditing, and soft deletes.
    """
    workspace = models.ForeignKey(
        'tenancy.Workspace', 
        on_delete=models.CASCADE, 
        related_name="%(class)ss"
    )
    
    # Audit timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    # --- Unified Manager Strategy ---
    # Default: Shows active records for the current workspace only
    objects = TenantManager() 
    
    # Shows active + soft-deleted records for the current workspace
    all_objects = TenantManager(include_deleted=True)
    
    # Global escape hatch: Across all workspaces, including soft-deleted items (for background tasks/global admins)
    global_objects = TenantManager(include_deleted=True, include_all_workspaces=True)

    class Meta:
        abstract = True

    def delete(self, using=None):
        """Safe Instance-level soft delete inside a transaction boundary."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=['is_deleted', 'deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """Bypass soft deletion to permanently purge the row from disk."""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """Revert a soft-deletion state cleanly."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

# ====================== Custom Field Configuration for business models ======================

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

class CustomFieldDefinition(TenantBaseModel):
    FIELD_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('boolean', 'Checkbox'),
        ('date', 'Date'),
        ('select', 'Dropdown')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    name = models.CharField(max_length=50)
    label = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    is_required = models.BooleanField(default=False)
    choices = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'content_type', 'name'],
                name='unique_field_per_workspace_per_model'
            )
        ]

    def __str__(self):
        return f"{self.content_type.model} -> {self.label}"
    
def validate_custom_payload(workspace, model_class, custom_data):
    if not isinstance(custom_data, dict):
        raise ValidationError({'custom_data': 'Must be a valid JSON object.'})
    
    ctype = CustomFieldDefinition.objects.get_for_model(model_class)

    definitions = CustomFieldDefinition.objects.filter(workspace=workspace, content_type=ctype)
    sanitized_data = {}
    
    for definition in definitions:
        key = definition.name
        value = custom_data.get(key)

        if definition.is_required and value in [None, '']:
            raise ValidationError({'key': f'The field {definition.label} is required.'})
        if value in [None, '']:
            continue
        try:
            if definition.field_type == 'number':
                sanitized_data['key'] = float(value) if '.' in str(value) else int
            elif definition.field_type == 'boolean':
                sanitized_data['key'] = bool(value)
            elif definition.field_type == 'select':
                if value not in definition.choices:
                    raise ValidationError({'key': f'Invalid selection. Choose from: {definition.choices}'})
                sanitized_data['key'] = value
            else:
                sanitized_data['key'] = str(value).strip()
        except (ValueError, TypeError):
            raise ValidationError({key: f"Invalid format for field type '{definition.field_type}'."})

    return sanitized_data
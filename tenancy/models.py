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
        db_table = 'workspaces'
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
        db_table = 'workspace_memberships'
        
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"],
                name="unique_user_workspace"
            )
        ]   # One user per workspace
        
        ordering = ['-joined_at']


# ====================== Tenant Isolation ======================

from .utils import get_current_workspace

class TenantManager(models.Manager):
    """Manager that automatically filters by current workspace"""
    def get_queryset(self):
        
        queryset = super().get_queryset()
        current_workspace = get_current_workspace()
        
        if current_workspace:
            return queryset.filter(workspace=current_workspace)
        return queryset


class TenantBaseModel(models.Model):
    """Base model for all tenant-specific data"""
    workspace = models.ForeignKey(
        Workspace, 
        on_delete=models.CASCADE, 
        related_name="%(class)ss"   # e.g. products, customers
    )

    objects = TenantManager()              # Filtered by workspace
    all_objects = models.Manager()         # Unfiltered access (for admin)

    class Meta:
        abstract = True
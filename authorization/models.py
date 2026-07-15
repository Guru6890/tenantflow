# authorization/models.py
from django.db import models

import uuid

from django.utils.translation import gettext_lazy as _

class Permission(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    module = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'permissions'
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')

    def __str__(self):
        return f'{self.name}-{self.codename}'
    
class Role(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    workspace = models.ForeignKey('tenancy.Workspace', on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'name'],
                name='unique_roles_in_workspaces'
            )
        ]
        ordering = ['name']

    def __str__(self):
        return f'{self.name} (workspace: {self.workspace_id})'

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = 'role_permissions'
        constraints = [
            models.UniqueConstraint(fields=['role', 'permission'], name='unique_role_permission')
        ]
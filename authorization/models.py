# authorization/models.py
from django.db import models

import uuid

from django.utils.translation import gettext_lazy as _

class Module(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_core = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
    
class WorkspaceModule(models.Model):
    workspace = models.ForeignKey('tenancy.Workspace', on_delete=models.CASCADE, related_name='modules')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='workspaces')
    is_active = models.BooleanField(default=True)
    activated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'module'],
                name='unique_module_per_workspace'
            )
        ]
        
class Permission(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='permissions')
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['module', 'codename'],
                name='unique_permission_per_module'
            )
        ]
        ordering = ['module__name', 'codename']

    def __str__(self):
        return f'{self.module.name}-{self.codename}'
    
class Role(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    workspace = models.ForeignKey('tenancy.Workspace', on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
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
        constraints = [
            models.UniqueConstraint(fields=['role', 'permission'], name='unique_role_permission')
        ]
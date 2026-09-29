# authorization/services.py
from __future__ import annotations
from uuid import UUID
from typing import Optional, Set
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import PermissionDenied

from.models import RolePermission
from tenancy.models import Workspace, WorkspaceMembership

class AuthorizationService:
    @staticmethod
    def get_user_permissions(user: AbstractUser, workspace_id: UUID) -> Set[str]:
        """Fetches all permission codenames for a user in a workspace once per request."""
        cache_attr = f"_workspace_perms_{workspace_id}"

        # 1. Check if permissions are already loaded on the user instance
        if not hasattr(user, cache_attr):
            # 2. Single query to fetch role + active workspace status
            membership = WorkspaceMembership.objects.filter(
                user_id=user.pk,
                workspace_id=workspace_id
            ).select_related('role').first()

            if not membership or not membership.role:
                perms = set()
            elif getattr(membership.role, 'is_system', False) and membership.role.name == 'Owner':
                # Bypass DB join for workspace owner if designated by system role
                perms = {"*"}
            else:
                # 3. Pull all permission codenames into a flat Python set in ONE query
                perms = set(
                    RolePermission.objects.filter(role_id=membership.role_id)
                    .values_list('permission__codename', flat=True)
                )

            # 4. Attach to the user instance in memory
            setattr(user, cache_attr, perms)

        return getattr(user, cache_attr)

    @classmethod
    def has_permission(
        cls, 
        user: Optional[AbstractUser], 
        workspace: Optional[Workspace], 
        permission_codename: str
    ) -> bool:
        if not user or not user.is_authenticated or not workspace:
            return False

        if user.is_superuser:
            return True

        # Retrieve permissions from cache or populate cache on first access
        user_permissions = cls.get_user_permissions(user, workspace.pk)

        if "*" in user_permissions:
            return True

        return permission_codename in user_permissions
    
    @classmethod
    def require_permission(
        cls,
        user: Optional[AbstractUser],
        workspace: Optional[Workspace],
        permission_codename: str,
    ) -> None:
        if not cls.has_permission(
            user,
            workspace,
            permission_codename,
        ):
            raise PermissionDenied
        
    @staticmethod
    def clear_cached_permissions(user: AbstractUser, workspace_id: str | int) -> None:
        """Forcefully clears the in-memory permission cache for a specific workspace."""
        cache_attr = f"_workspace_perms_{workspace_id}"
        if hasattr(user, cache_attr):
            delattr(user, cache_attr)  # Deletes the dynamic attribute from the object

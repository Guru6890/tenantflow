# tenancy/services.py
from django.shortcuts import redirect
from django.contrib import messages

from .models import Workspace, WorkspaceMembership
from .utils import initialize_workspace_modules
from authorization.models import Role


class WorkspaceService:
    """Service layer for Workspace related business logic"""

    @staticmethod
    def create_workspace(request, form):
        """
        Complete workspace creation flow for new users.
        Returns redirect response.
        """
        if not form.is_valid():
            return None

        # 1. Create Workspace
        workspace = form.save()

        # 2. Initialize default modules & settings
        initialize_workspace_modules(workspace)

        # 3. Create Owner Role
        owner_role = Role.objects.create(
            workspace=workspace,
            name="OWNER",
            is_system=True,
            description="Full access - Owner of the workspace"
        )

        # 4. Create Owner Membership
        membership = WorkspaceMembership.objects.create(
            user=request.user,
            workspace=workspace,
            role=owner_role,
            invited_by=request.user
        )

        # 5. Set current workspace in session
        request.session['current_workspace_id'] = str(workspace.id)
        request.session.save()

        messages.success(request, f"Workspace '{workspace.name}' created successfully!")


    @staticmethod
    def switch_workspace(request, workspace_id):
        """Switch between workspaces"""
        try:
            membership = WorkspaceMembership.objects.select_related('workspace').get(
                user=request.user,
                workspace_id=workspace_id
            )
            
            request.session['current_workspace_id'] = str(workspace_id)
            request.session.save()
            
            messages.info(request, f"Switched to workspace: {membership.workspace.name}")
            return True
            
        except WorkspaceMembership.DoesNotExist:
            messages.error(request, "You don't have access to this workspace.")
            return False
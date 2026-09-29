#authorization.mixins.py
from django.contrib import messages
from django.shortcuts import redirect

from .services import AuthorizationService

class WorkspacePermissionMixin:
    required_permission = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_permission is None:
            raise ValueError(
                f'{self.__class__.__name__} must define "required_permission".'
            )
        
        if AuthorizationService.has_permission(
            user = request.user,
            workspace=request.workspace,
            permission_codename=self.required_permission
        ):
            return super().dispatch(request, *args, **kwargs)
        
        messages.error(
            request,
            'You do not have permission to perform this action.'
        )
        return redirect('tenancy:dashboard')
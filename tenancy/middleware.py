# tenancy/middleware.py
from .models import WorkspaceMembership
from tenancy.utils import set_current_workspace

class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None
        request.membership = None
        request.role = None

        if request.user.is_authenticated:
            workspace_id = request.session.get('current_workspace_id')

            # Fallback: Find latest membership if session key is missing
            if not workspace_id:
                fallback_membership = WorkspaceMembership.objects.filter(
                    user=request.user
                ).order_by('-joined_at').first()
                
                if fallback_membership:
                    workspace_id = fallback_membership.workspace_id
                    # CRITICAL: Cast UUID to string to avoid JSON session serialization errors
                    request.session['current_workspace_id'] = str(workspace_id)

            if workspace_id:
                try:
                    membership = WorkspaceMembership.objects.select_related('workspace', 'role').get(
                        user=request.user,
                        workspace_id=workspace_id
                    )
                    request.workspace = membership.workspace
                    request.membership = membership
                except WorkspaceMembership.DoesNotExist:
                    request.session.pop('current_workspace_id', None)

        # Set the global thread-local tenant workspace context before the view runs
        set_current_workspace(request.workspace)

        try:
            response = self.get_response(request)
        finally:
            # ALWAYS clear the thread-local state after the request cycle completes
            set_current_workspace(None)

        return response
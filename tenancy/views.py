from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from .forms import WorkspaceCreationForm
from .services import WorkspaceService

@login_required
def dashboard_router_view(request):
    if request.workspace:
        return render(request, 'dashboard.html', {'workspace': request.workspace, 'role': request.role})

    return redirect('tenancy:create_workspace')

@login_required
def create_workspace_view(request):
    if request.workspace:
        return redirect('tenancy:dashboard')
    
    if request.method == 'POST':
        form = WorkspaceCreationForm(request.POST)
        WorkspaceService.create_workspace(request, form)
        return redirect('tenancy:dashboard')
    else:
        form = WorkspaceCreationForm()

    return render(request, 'create_workspace.html', {'form': form})
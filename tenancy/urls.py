from django.urls import path

from .views import dashboard_router_view, create_workspace_view

app_name = 'tenancy'

urlpatterns = [
    path('dashboard/', dashboard_router_view, name='dashboard'),
    path('workspace/new/', create_workspace_view, name='create_workspace'),
]
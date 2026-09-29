# tenancy/utils.py
import contextvars

from authorization.models import Module, WorkspaceModule

_current_workspace_var = contextvars.ContextVar('current_workspace', default=None)

def get_current_workspace():
    return _current_workspace_var.get()

def set_current_workspace(workspace):
    _current_workspace_var.set(workspace)

def clear_current_workspace():
    """Useful in background tasks"""
    _current_workspace_var.set(None)

# tenancy/utils/business.py
DEFAULT_MODULES_BY_TYPE = {
    'gym': ['inventory', 'crm', 'subscriptions', 'billing'],
    'pharmacy': ['inventory', 'crm', 'billing', 'suppliers'],
    'manufacturing': ['inventory', 'production', 'billing'],
    'food': ['inventory', 'production', 'billing', 'expiry_tracking'],
    'retail': ['inventory', 'crm', 'billing', 'pos'],
    'service': ['crm', 'billing', 'subscriptions'],
    'other': ['crm', 'billing'],
}

def get_default_modules(business_type: str):
    return DEFAULT_MODULES_BY_TYPE.get(business_type, 'other')


def initialize_workspace_modules(workspace):
    """Call this after workspace creation"""
    default_modules = get_default_modules(workspace.business_type)
    for module_name in default_modules:
        module = Module.objects.get(name=module_name)
        WorkspaceModule.objects.create(workspace=workspace, module=module)
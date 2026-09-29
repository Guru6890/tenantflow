# Multi-Tenant SaaS Portfolio Project — Technical Context

## 1. Project Goal

I am building a production-oriented **multi-tenant SaaS platform** as a Django portfolio project.

The goal is NOT to build only an Inventory Management System (IMS). The platform is intended to support different types of businesses through modular business applications.

Initial business types include:

* Retail / Supermarket
* Medical Shop / Pharmacy
* Gym / Fitness Studio
* Food Products / Snacks Manufacturing
* General Manufacturing
* Service Business
* Other

A workspace selects a business type and receives a set of appropriate modules.

The project is intended to demonstrate:

* Multi-tenancy
* Strict workspace/data isolation
* Authentication and user management
* Role-based access control (RBAC)
* Modular permissions
* Workspace membership
* Soft deletion
* Service-layer architecture
* Django ORM proficiency
* Transactions and row locking
* Business rules and validation
* Extensible SaaS architecture
* PostgreSQL features such as JSONField/JSONB
* Professional CRUD workflows
* Dashboard/reporting capabilities

The project is being built carefully rather than as a tutorial CRUD application.

---

# 2. High-Level Architecture

The conceptual architecture is:

User
↓
Identity
↓
Workspace / Tenancy
↓
Authorization
↓
Business Modules
↓
Module-specific applications/models/services

The major platform components are:

```text
identity/
tenancy/
authorization/
core/
```

Business functionality is implemented as modular applications such as:

```text
inventory/
crm/
billing/
production/
...
```

The current implementation focus is the **Inventory module**.

---

# 3. Identity

Django uses a custom user model.

Current model concept:

```python
class User(AbstractUser):
    username = None
    id = models.UUIDField(...)
    email = models.EmailField(unique=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
```

Important characteristics:

* UUID primary key
* Email-based authentication
* Username removed
* Custom `UserManager`
* `AUTH_USER_MODEL` configured to use this model

The identity app is responsible for:

* User identity
* Authentication
* Registration/login
* Password management
* User profile-related functionality

Identity should NOT contain workspace-specific authorization logic.

---

# 4. Tenancy

The core tenant is a `Workspace`.

Current `Workspace` concept:

```text
Workspace
├── id (UUID)
├── name
├── slug
├── business_type
├── settings
├── is_active
├── created_at
└── updated_at
```

Business types currently include:

```text
gym
pharmacy
manufacturing
food
retail
service
other
```

A user can belong to multiple workspaces through:

```text
WorkspaceMembership
```

Membership contains:

```text
user
workspace
role
invited_by
joined_at
```

There is a uniqueness constraint on:

```text
(user, workspace)
```

so a user can have only one membership per workspace.

---

# 5. Current Workspace / Tenant Context

The active workspace is stored in the session:

```text
current_workspace_id
```

`WorkspaceMiddleware`:

1. Checks whether the user is authenticated.
2. Reads the current workspace ID from the session.
3. Falls back to the user's latest membership if necessary.
4. Retrieves the corresponding `WorkspaceMembership`.
5. Sets:

```text
request.workspace
request.membership
request.role
```

6. Establishes the current workspace in a `contextvars.ContextVar`.

Current utility concept:

```python
_current_workspace_var = contextvars.ContextVar(
    "current_workspace",
    default=None
)

get_current_workspace()
set_current_workspace(workspace)
clear_current_workspace()
```

The context is cleared after the request finishes.

This allows service/query/model layers to determine the active tenant without passing `workspace` through every method.

---

# 6. Tenant Isolation + Soft Delete

There is a reusable abstract model:

```text
TenantBaseModel
```

It contains:

```text
workspace FK
created_at
updated_at

is_deleted
deleted_at
```

It also provides tenant-aware managers.

Current conceptual managers:

```text
objects
    → active records
    → current workspace only

all_objects
    → active + soft-deleted records
    → current workspace only

global_objects
    → all records
    → all workspaces
    → including deleted
```

The custom `TenantQuerySet` supports:

```text
active()
deleted()
for_workspace()
delete()
hard_delete()
restore()
```

The default manager obtains the current workspace through:

```python
get_current_workspace()
```

and filters automatically by workspace.

If no workspace context exists, the tenant manager raises an error rather than accidentally returning cross-tenant data.

This is an intentional security measure.

---

# 7. Authorization Architecture

Authorization is RBAC-based.

Current models:

```text
Module
Permission
Role
RolePermission
WorkspaceMembership
```

The conceptual relationship is:

```text
Workspace
    │
    ├── WorkspaceModule ── Module
    │
    └── Role
          │
          └── RolePermission ── Permission
                                   │
                                   └── Module
```

A user receives a role through:

```text
WorkspaceMembership.role
```

Therefore:

```text
User
 ↓
WorkspaceMembership
 ↓
Role
 ↓
RolePermission
 ↓
Permission
 ↓
Module
```

---

# 8. Permission Model

Permission has approximately:

```text
id
codename
name
description
module
```

The permission codename convention is:

```text
<module>.<resource>.<action>
```

Examples:

```text
inventory.category.view
inventory.category.create
inventory.category.update
inventory.category.delete

inventory.product.view
inventory.product.create
inventory.product.update
inventory.product.delete

inventory.stock.view
inventory.stock.adjust
```

Permissions are global definitions.

They are not created separately for every workspace.

A workspace gets access to the functionality through its enabled modules.

---

# 9. Module Architecture

A major architectural decision was made:

The SaaS is **modular**, not just an IMS.

There is a `Module` model and a `WorkspaceModule` connector model.

Conceptually:

```text
Module
├── name
├── description
├── is_core
└── is_active

WorkspaceModule
├── workspace
├── module
└── ...
```

A workspace can therefore enable modules such as:

```text
Inventory
CRM
Billing
Subscriptions
POS
Production
Suppliers
Expiry Tracking
```

The previous idea of storing enabled modules only inside:

```text
Workspace.settings["modules"]
```

has been replaced by the proper `WorkspaceModule` relationship.

The `settings` JSONField may still be useful for workspace-specific configuration, but it is no longer the source of truth for enabled modules.

---

# 10. Business Type → Default Modules

The original concept was:

```python
DEFAULT_MODULES_BY_TYPE = {
    "gym": [
        "inventory",
        "crm",
        "subscriptions",
        "billing",
    ],

    "pharmacy": [
        "inventory",
        "crm",
        "billing",
        "suppliers",
    ],

    "manufacturing": [
        "inventory",
        "production",
        "billing",
    ],

    "food": [
        "inventory",
        "production",
        "billing",
        "expiry_tracking",
    ],

    "retail": [
        "inventory",
        "crm",
        "billing",
        "pos",
    ],

    "service": [
        "crm",
        "billing",
        "subscriptions",
    ],

    "other": [
        "crm",
        "billing",
    ],
}
```

This is now being used conceptually to initialize `WorkspaceModule` records rather than merely storing module names in JSON.

---

# 11. Module + Permission Seeding

There is a management command:

```text
authorization/
    management/
        commands/
            seed_permissions.py
```

The command is responsible for seeding:

1. Modules
2. Permissions belonging to modules

It is idempotent and uses `get_or_create()`.

Current module definitions include:

```text
inventory
crm
billing
subscriptions
pos
production
suppliers
expiry_tracking
```

The permission matrix currently looks conceptually like:

```python
{
    "inventory": {
        "category": "crud",
        "product": "crud",
        "supplier": "crud",
        "stock": ["view", "adjust"],
    },

    "crm": {
        "customer": "crud",
        "lead": "crud",
    },

    "billing": {
        "invoice": "cru",
        "payment": ["view", "create"],
    },

    "subscriptions": {
        "plan": "crud",
        "subscription": "cru",
    },

    "pos": {
        "sale": ["view", "create", "refund"],
    },

    "production": {
        "order": "cru",
    },

    "expiry_tracking": {
        "item": ["view", "manage"],
    },
}
```

`crud` is expanded into:

```text
c → create
r → view
u → update
d → delete
```

Custom actions such as:

```text
adjust
refund
manage
```

are also supported.

This permission matrix is intended to become reusable metadata rather than duplicated inside services.

---

# 12. AuthorizationService

Current service:

```python
class AuthorizationService:

    @staticmethod
    def user_has_permission(
        user,
        workspace,
        permissions_codename: str
    ) -> bool:

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        if not workspace:
            return False

        return WorkspaceMembership.objects.filter(
            user=user,
            workspace=workspace,
            role__permissions__permission__codename=permissions_codename
        ).exists()
```

This is the low-level authorization checker.

The next layer is a reusable:

```text
WorkspacePermissionMixin
```

which should allow class-based views to declare required permissions without repeating authorization queries.

---

# 13. Roles — Current Design Decision

The project has reached the point where roles are the remaining part of the authorization architecture that needs to be implemented.

Important design decision:

**Modules define permissions and recommended role templates.**

Modules should NOT own actual workspace roles.

A real `Role` belongs to a workspace because the workspace may customize it.

Therefore:

```text
Role Template
    ↓
creates
    ↓
Workspace Role
```

A role template is a blueprint/configuration, not necessarily a database model.

Example:

```text
Inventory Manager
    category → crud
    product  → crud
    supplier → crud
    stock    → view + adjust
```

The actual role becomes:

```text
Role
+
RolePermission rows
```

inside a specific workspace.

---

# 14. Plugin Architecture for Business Modules

The Inventory module is being treated as a plugin/module boundary.

Conceptually:

```text
inventory/
├── apps.py
├── security.py
├── navigation.py
├── dashboard.py
│
├── catalogue/
├── locations/
├── stock/
└── reports/
```

The important idea is that:

```text
inventory/security.py
```

is the Inventory module's security declaration.

It can contain:

```text
PERMISSIONS
ROLE_TEMPLATES
```

The Inventory module therefore tells the platform:

> These are the permissions I provide, and these are recommended role templates for those permissions.

Authorization does not need to know that the Inventory module contains `catalogue`, `locations`, or `stock` apps internally.

This creates a plugin-like architecture.

---

# 15. Inventory Module Structure

Current Inventory module is split internally.

Conceptually:

```text
inventory/
│
├── security.py
│
├── navigation.py
├── dashboard.py
│
├── catalogue/
│   ├── models.py
│   ├── forms.py
│   ├── services.py
│   ├── views.py
│   ├── urls.py
│   └── templates/
│
├── locations/
│   ├── models.py
│   ├── forms.py
│   ├── services.py
│   ├── views.py
│   └── urls.py
│
├── stock/
│   ├── models.py
│   ├── forms.py
│   ├── services.py
│   ├── views.py
│   └── urls.py
│
└── reports/
```

The module boundary is `inventory/`.

The internal Django apps are implementation details.

---

# 16. Inventory Models Already Implemented

Current Inventory catalogue contains:

```text
Supplier
Category
Product
```

All inherit from:

```text
TenantBaseModel
```

### Supplier

Contains business information such as:

```text
name
contact_person
email
phone
tax_id
address
is_active
```

Supplier is tenant-specific.

### Category

Currently very simple:

```text
name
```

with a workspace-specific uniqueness constraint.

### Product

Contains:

```text
sku
name
category
unit
min_stock_level
max_stock_level
barcode
expiry_days
description
weight
purchase_price
selling_price
is_active
supplier
custom_data
```

`custom_data` is a JSONField intended to support future tenant-specific/custom product fields.

SKU is normalized to uppercase in `save()`.

Product deletion is prevented if physical inventory still exists.

---

# 17. Inventory Stock Architecture

Stock-related work has already been designed around business rules.

Important concepts include:

```text
Stock
StockAdjustment
StockLedger
```

The Stock model has concepts such as:

```text
physical_qty
allocated_qty
```

with the business rule:

```text
allocated_qty <= physical_qty
```

This is enforced at the model/database level.

Stock operations use:

```python
transaction.atomic()
```

and:

```python
select_for_update()
```

where concurrent modifications could cause race conditions.

Services already considered/designed include:

```text
TransferStock
AdjustStock
AllocationService
```

The design deliberately keeps complex business logic in services rather than bloating views/models.

---

# 18. Inventory Catalogue Service Layer

Category currently has:

```text
CategoryService
```

with methods conceptually:

```text
create()
update()
delete()
list()
get_by_id()
```

The service:

* obtains current workspace
* creates tenant-owned objects
* calls `full_clean()`
* handles domain validation
* uses the tenant-aware manager

Example flow:

```text
CategoryCreateView
    ↓
CategoryForm
    ↓
CategoryService.create()
    ↓
Category
    ↓
Database
```

---

# 19. Generic Service-Based Views

There is a reusable `core.views` layer.

Current generic views include:

```text
ServiceListView
ServiceCreateView
ServiceUpdateView
ServiceDeleteView
```

Their purpose is to reduce repetitive CRUD view code.

Example:

```python
class CategoryListView(LoginRequiredMixin, ServiceListView):
    service = CategoryService
    ...
```

The view delegates business operations to the service.

This is an intentional architecture decision:

```text
View
    → Form
    → Service
    → Model/Database
```

rather than putting business logic directly into views.

---

# 20. Category CRUD — Current State

Category is being used as the first complete CRUD workflow because it is simple.

Current pieces exist:

```text
Category model
CategoryForm
CategoryService
CategoryListView
CategoryCreateView
CategoryUpdateView
CategoryDeleteView
```

The generic service views exist.

The remaining pieces are mainly:

```text
URL configuration
success URLs / redirects
templates
permission enforcement
final CRUD workflow testing
```

The exact URL design has not yet been finalized.

---

# 21. Important Architecture Rules

When continuing development, preserve these principles.

### Tenant isolation

Business data must always belong to a workspace.

Never trust a workspace ID supplied directly by the client.

Use the current authenticated membership/workspace context.

### Authorization

Permission checking should happen before business operations.

Example:

```text
User
↓
WorkspaceMembership
↓
Role
↓
Permission
```

### Services

Use services for business operations and domain workflows.

Do not turn services into giant utility classes.

### Models

Models should contain:

* schema
* constraints
* basic invariants
* model-level behavior

Complex workflows belong in services.

### Views

Views should primarily coordinate:

```text
request
→ form
→ permission
→ service
→ response
```

### Modules

Modules should be self-contained.

Inventory owns its own:

```text
security
navigation
dashboard
business apps
```

Authorization should not contain Inventory-specific knowledge.

---

# 22. Intended Final Architecture

The simplified target structure is:

```text
project/
│
├── identity/
│   ├── models.py
│   ├── managers.py
│   ├── forms.py
│   ├── services.py
│   ├── views.py
│   └── urls.py
│
├── tenancy/
│   ├── models.py
│   ├── middleware.py
│   ├── utils.py
│   ├── services.py
│   ├── forms.py
│   ├── views.py
│   └── urls.py
│
├── authorization/
│   ├── models.py
│   ├── services.py
│   ├── mixins.py
│   ├── decorators.py
│   ├── utils.py
│   │
│   └── management/
│       └── commands/
│           ├── seed_modules.py
│           ├── seed_permissions.py
│           └── ...
│
├── core/
│   └── views.py
│
└── inventory/
    ├── apps.py
    ├── security.py
    ├── navigation.py
    ├── dashboard.py
    │
    ├── catalogue/
    │   ├── models.py
    │   ├── forms.py
    │   ├── services.py
    │   ├── views.py
    │   ├── urls.py
    │   └── templates/
    │
    ├── locations/
    │   ├── models.py
    │   ├── forms.py
    │   ├── services.py
    │   └── views.py
    │
    ├── stock/
    │   ├── models.py
    │   ├── forms.py
    │   ├── services.py
    │   └── views.py
    │
    └── reports/
```

---

# 23. Current Project Status

### Completed / largely completed

* Custom User model
* Email authentication foundation
* Workspace model
* Workspace membership
* Workspace switching
* Workspace middleware
* Current-workspace context
* Tenant-aware managers/querysets
* Soft deletion
* Tenant base model
* Module model
* WorkspaceModule connector
* Business-type → default-module concept
* Permission model
* Role model
* RolePermission model
* Permission/module seeding command
* AuthorizationService foundation
* Inventory module foundation
* Inventory catalogue models
* Stock architecture
* Service-layer architecture
* Generic service-based CRUD views
* Category CRUD foundation

### Currently being implemented

* Role initialization
* Role templates
* RoleService
* MembershipService
* WorkspacePermissionMixin
* Module-owned security metadata
* Category's complete permission-protected CRUD workflow

### Later

* Complete Inventory CRUD
* Warehouse/location workflows
* Stock workflows
* Inventory dashboards/reports
* Other business modules
* Module-specific navigation
* Subscription/billing functionality
* More advanced SaaS features

---

# 24. Current Architectural Direction

The most important design decision going forward is:

```text
MODULE
    │
    ├── Permissions
    ├── Role Templates
    ├── Navigation
    ├── Dashboard
    └── Business Applications
```

while:

```text
AUTHORIZATION
    │
    ├── Permission
    ├── Role
    ├── RolePermission
    ├── AuthorizationService
    └── Permission enforcement
```

The module defines **what it provides**.

Authorization defines **how access control works**.

Tenancy defines **which workspace owns the data**.

Identity defines **who the user is**.

This separation is the central architectural principle of the project.

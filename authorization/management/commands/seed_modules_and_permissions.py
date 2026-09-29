#authorization.management.commands.seed_modules_and_permissions.py
from django.core.management.base import BaseCommand
from django.db import transaction

from authorization.models import Module, Permission

from authorization.permissions import permission_matrix, action_labels

class Command(BaseCommand):
    help = "Seed all Modules and their Permissions (idempotent)"

    def handle(self, *args, **options):
        with transaction.atomic():
            self._seed_modules()
            self._seed_permissions()
            self.stdout.write(self.style.SUCCESS("Successfully seeded modules and permissions"))

    def _seed_modules(self):
        modules = [
            {"name": "inventory", "description": "Product, category, stock and supplier management", "is_core": True},
            {"name": "crm", "description": "Customer and lead management", "is_core": True},
            {"name": "billing", "description": "Invoices, payments and basic billing", "is_core": True},
            {"name": "subscriptions", "description": "Membership plans and recurring billing", "is_core": False},
            {"name": "pos", "description": "Retail point of sale", "is_core": False},
            {"name": "production", "description": "Manufacturing and production management", "is_core": False},
            {"name": "suppliers", "description": "Supplier management", "is_core": False},
            {"name": "expiry_tracking", "description": "Track product expiry dates", "is_core": False},
        ]

        for data in modules:
            Module.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "is_core": data["is_core"],
                    "is_active": True,
                }
            )
        self.stdout.write(f"  → Modules: {len(modules)}")

    def _seed_permissions(self):
        # Mapping of resources to their allowed actions
        # Actions can be shortcuts like 'crud', 'cru', or custom lists

        created_count = 0

        for module_name, resources in permission_matrix.items():
            module = Module.objects.get(name=module_name)

            for resource, actions in resources.items():
            # If actions is a string shortcut like 'crud', expand it
                if isinstance(actions, str):
                    action_list = [action_labels[char] for char in actions]
                else:
                # For custom action lists like ['view', 'adjust']
                    action_list = []
                    for action in actions:
                        label = "Can view" if action == "view" else f"Can {action}"
                        action_list.append((action, label))

            # Database execution
                for action_code, action_label in action_list:
                    codename = f"{module_name}.{resource}.{action_code}"
                    name = f"{action_label} {resource}" # e.g., "Can view categories" (handles pluralization if needed)

                    _, created = Permission.objects.get_or_create(
                        module=module,
                        codename=codename,
                        defaults={"name": name}
                    )
                    if created:
                        created_count += 1

        self.stdout.write(f" → Permissions created: {created_count}")
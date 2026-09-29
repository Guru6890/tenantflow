#authorization.permissions.py
permission_matrix = {
            "inventory": {
                "category": "crud",
                "product": "crud",
                "supplier": "crud",
                "stock": ["view", "receive", "allocate", "adjust"],
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

        # Map characters to human-readable labels
action_labels = {
            "c": ("create", "Can create"),
            "r": ("view", "Can view"),
            "u": ("update", "Can update"),
            "d": ("delete", "Can delete"),
        }
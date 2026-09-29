#authorization.role_templates.py
pharmacy_roles = {
    'admin': {
        'name': 'Clinic Administrator',
        'description': 'Manages patient flow, compliance tracking and overall',
        'is_default': False,
        "capabilities": {
            "appointments": {"calendar": "crud", "booking": "crud"},
            "billing": {"invoice": "crud", "payment": ["view", "create"], "audit": "r"},
            "inventory": {"product": "crud", "supplier": "crud", "purchase_order": "cru"},
            "crm": {"customer": "crud"},
        },
    },
    'receptionist': {
        'name': 'Medical Receptionist',
        'description': 'Manages patient intake, schedules visits, and handles ',
        'is_default': True,
        "capabilities": {
                "appointments": {"calendar": "r", "booking": "cru"},
                "billing": {"invoice": "c", "payment": ["create"]},
                "crm": {"customer": "cru"},
            },
    },
    'pharmacist': {
        'name': 'Pharmacist/Inventory Custodian',
        'description': 'Safely manages drug dispensaries, expiration dates, ',
        'is_default': False,
        "capabilities": {
                "inventory": {"category": "cru", "product": "crud", "supplier": "cru", "stock": ["view", "adjust"], "batch": "crud"},
                "billing": {"invoice": "r", "payment": ["view"]},
            },
    },
}

manufacturing = {
    'manager': {
        'name': 'Plant Manager',
        'description': 'Oversees factory floors, shifts, output levels and ',
        'is_default': False,
        "capabilities": {
                "inventory": {"raw_material": "crud", "finished_goods": "crud", "stock": ["view", "adjust"]},
                "hr_payroll": {"shift": "crud", "timesheet": "cru", "labor_cost": "r"},
                "billing": {"invoice": "r", "purchase_order": "cru"},
            },
    },
    'inventory_clerk': {
        'name': 'Procurement and Inventory Clerk',
        'description': 'Tracks incoming materials, reconciles vendor shipments',
        'is_default': True,
        "capabilities": {
                "inventory": {"raw_material": "ru", "finished_goods": "r", "stock": ["view", "adjust"], "transfer": "cru"},
                "billing": {"purchase_order": "r"},
            },
    },
    'accountant': {
        'name': 'B2B Accounts Specialist',
        'description': 'Manages corporate billing accounts, commercial clients',
        'is_default': False,
        "capabilities": {
                "billing": {"invoice": "crud", "payment": ["view", "create"], "accounts_receivable": "ru"},
                "crm": {"customer": "crud", "corporate_record": "cru"},
            },
    },
}

food_service = {
    'general_manager': {
        'name': 'General Manager',
        'description': 'Responsible for day-to-day profit, labor percentages, ',
        'is_default': False,
        "capabilities": {
                "billing": {"invoice": "crud", "payment": ["view", "create", "refund"], "menu_pricing": "u"},
                "inventory": {"product": "cru", "stock": ["view", "adjust"], "waste_log": "cru"},
                "hr_payroll": {"shift": "cru", "timesheet": "cru", "clock_in_override": "cru"},
            },
    },
    'staff': {
        'name': 'Floor server/Cashier',
        'descriptions': 'Takes guest orders, apply modifiers, fires items to ',
        'is_default': True,
        "capabilities": {
                "billing": {"invoice": "c", "payment": ["create"], "pos_order": "cru"},
            },
    },
    'kitchen_manager': {
        'name': 'Kitchen Manager / Head Chef',
        'description': 'Controles food cost, inventory intake, menu prep list ',
        'is_default': False,
        "capabilities": {
                "inventory": {"product": "r", "stock": ["view", "adjust"], "waste_log": "cru", "supplier_delivery": "cru"},
                "hr_payroll": {"shift": "r", "timesheet": "r"},
            },
    }
}

gym = {
    'manager': {
        'name': 'Club Manager',
        'description': 'Full access to member pipelines, schedule management',
        'is_default': False,
        "capabilities": {
                "subscriptions": {"plan": "crud", "subscription": "crud"},
                "appointments": {"calendar": "crud", "booking": "crud", "staff_schedule": "crud"},
                "crm": {"customer": "crud", "lead": "crud", "analytics": "r"},
                "billing": {"invoice": "crud", "payment": ["view", "create", "refund"], "discount": "manage"},
            },
    },
    'fron_desk': {
        'name': 'Front Desk Representative',
        'description': 'Greets guests, validates memberships, sells walk-in',
        'is_default': True,
        "capabilities": {
                "subscriptions": {"subscription": "ru"},
                "appointments": {"calendar": "r", "booking": "cru"},
                "billing": {"invoice": "c", "payment": ["create"]},
                "crm": {"customer": "cru", "notes": "cru"},
            },
    },
    'trainer': {
        'name': 'Personal Trainer / Coach',
        'description': 'Conducts training sessions, tracks client progress, ',
        'is_default': False,
        "capabilities": {
                "appointments": {"calendar": "r", "booking": "ru", "my_schedule": "cru"},
                "crm": {"customer": "r", "health_notes": "cru"},
            }
    }
}

retail = {
    'manager':{
        'name': 'Store Manager',
        'description': 'Oversees floor staff, monitors sales targets, and ',
        'is_default': False,
        "capabilities": {
                "billing": {"invoice": "crud", "payment": ["view", "create", "refund"], "discount": "manage"},
                "inventory": {"category": "crud", "product": "crud", "supplier": "crud", "stock": ["view", "adjust"]},
                "crm": {"customer": "crud", "analytics": "r"},
            },
    },
    'associate': {
        'name': 'Retail Associate',
        'description': 'Ring up customers on the floor, look up stock variants',
        'is_default': True,
        "capabilities": {
                "billing": {"invoice": "c", "payment": ["create"], "pos_sale": "cru"},
                "inventory": {"product": "r", "stock": ["view"]},
                "crm": {"customer": "cru"},
            },
    },
    'order_packager': {
        'name': 'E-Commerce Fulfillment Agent',
        'description': 'Packs online orders, prints shipping lables, and upd',
        'is_default': False,
        "capabilities": {
                "inventory": {"product": "r", "stock": ["view", "adjust"], "fulfillment": "u"},
                "crm": {"customer": "r", "shipping_address": "r"},
            },
    }
}

services = {
    'dispatcher': {
        'name': 'Service Dispatcher',
        'description': 'Organize team logistics, answers inbound client, cal',
        'is_default': False,
        "capabilities": {
                "appointments": {"calendar": "crud", "booking": "crud", "dispatch_board": "cru"},
                "crm": {"customer": "crud", "history": "cru"},
            },
    },
    'service_provider': {
        'name': 'Field Technician / Consultant',
        'description': 'Performs work on-site, logs job notes, and invoices clients upon job completion.',
        'is_default': True,
        "capabilities": {
                "appointments": {"my_schedule": "ru", "booking_status": "u"},
                "billing": {"invoice": "c", "payment": ["create"], "estimate": "cru"},
                "crm": {"customer": "r", "job_notes": "cru"},
            },
    }
}

renting = {
    'manager': {
        'name': 'Rental Operations Manager',
        'description': 'Maximizes asset utilization rates, handles insurance',
        'is_default': False,
        "capabilities": {
                "inventory": {"asset": "crud", "stock": ["view", "adjust"], "pricing_tier": "u"},
                "billing": {"invoice": "crud", "payment": ["view", "create"], "damage_claim": "cru"},
                "crm": {"customer": "crud", "contract_log": "cru"},
            },
    },
    'desk_associate': {
        'name': 'Rental Desk Associate',
        'description': 'Processes pick-ups and returns, verifies customer identity',
        'is_default': True,
        "capabilities": {
                "inventory": {"asset": "r", "stock": ["view"], "inspection_log": "cru"},
                "billing": {"invoice": "c", "payment": ["create"], "deposit_hold": "cru"},
                "crm": {"customer": "cru", "verification_upload": "c"},
            },
    }
}

coworking = {
    'manager': {
        'name': 'Community Manager',
        'description': 'Drives building membership occupancy, schedules tour',
        'is_default': False,
        "capabilities": {
                "subscriptions": {"plan": "crud", "subscription": "crud", "agreement": "cru"},
                "appointments": {"calendar": "crud", "room_booking": "crud"},
                "crm": {"customer": "crud", "lead": "crud"},
                "billing": {"invoice": "crud", "payment": ["view", "create"], "ad_hoc_fee": "c"},
            }
    },
    'coordinator': {
        'name': 'Front Desk Coordinator',
        'description': 'Handles guest arrivals, verifies active desk memberships and books meeting room requests',
        'is_default': True,
        "capabilities": {
                "subscriptions": {"subscription": "r", "check_in": "c"},
                "appointments": {"calendar": "r", "room_booking": "cru"},
                "billing": {"invoice": "c", "payment": ["create"]},
        }
    }
}

agency = {
    'director': {
        'name': 'Account director',
        'description': 'Owns client retention strategy, manages sales pipelines, and reviews project revenue loops',
        'is_default': False,
        "capabilities": {
            "crm": {"customer": "crud", "pipeline": "crud", "deal": "crud"},
            "subscriptions": {"retainer_package": "crud", "subscription": "cru"},
            "billing": {"invoice": "crud", "payment": ["view", "create"], "milestone_billing": "cru"},
        }
    },
    'executive': {
        'name': 'Project Executive / Sales Rep',
        'description': 'Works leads, books initial strategy pitches, and tracks personal client touchpoints.',
        'is_default': True,
        "capabilities": {
            "crm": {"customer": "cru", "lead": "cru", "pipeline_stage": "u"},
            "appointments": {"calendar": "r", "pitch_meeting": "cru"},
        }
    }
}
# inventory>services>catalogue_service.py
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from django.db import transaction

from django.core.exceptions import ValidationError

from inventory.catalogue.models import (
    Product, 
    ProductVariant, 
    ProductSupplier, 
    Supplier, 
    Category, 
    UnitOfMeasure, 
    AttributeValue, 
    VariantAttributeValue,
    ItemType, 
    TrackingType
)
from inventory.stocks.models import Stock, StockLedger
from inventory.services.exceptions import (
    WorkspaceMismatchError, 
    ImmutableFieldError, 
    ProductHasStockError,
    ProductPermissionDenied,
    ProductValidationError,
    DuplicateSKUError,
    DuplicateBarcodeError,
    ProductHasStockError,
    ProductNotFound,
)
from inventory.selectors.catalogue_selectors import product_exists

from authorization.services import AuthorizationService
from tenancy.models import validate_custom_payload

class catalogue_permissions(str, Enum):
    PRODUCT_CREATE = 'inventory.product.create'
    PRODUCT_UPDATE = 'inventory.product.update'
    PRODUCT_DELETE = 'inventory.product.delete'

class CatalogueService:
    """
    Domain service for managing Product, Variant, and ProductSupplier lifecycles.
    Enforces business invariants, workspace isolation, and inventory protection rules.
    """
    @staticmethod
    def _validate_prices(purchase_price: Decimal, selling_price: Decimal) -> None:
        if purchase_price < 0:
            raise ProductValidationError("Purchase price cannot be negative", field="cost_price")
        if selling_price < 0:
            raise ProductValidationError("Selling price cannot be negative", field="selling_price")
    
    @staticmethod
    def _validate_stock_levels(min_level: Decimal, max_level: Decimal | None) -> None:
        if min_level < 0:
            raise ProductValidationError("Min stock level cannot be negative", field="min_stock_level")
        if max_level is not None and max_level < min_level:
            raise ProductValidationError(
                "Max stock level must be greater than or equal to min stock level",
                field="max_stock_level",
            )
    @staticmethod
    def _validate_workspace_ownership(workspace, **entities) -> None:
        """Asserts all provided entities belong to the active workspace."""
        for name, entity in entities.items():
            if entity and entity.workspace_id != workspace.id:
                raise WorkspaceMismatchError(
                    f"The provided {name} ({getattr(entity, 'id', entity)}) does not belong to workspace {workspace.id}."
                )
    
    @staticmethod
    def _has_inventory_history(product) -> bool:
        """Checks if a product has active physical stock or recorded ledger history."""
        has_stock = Stock.objects.filter(
            product = product,
            physical_qty__gt = Decimal(0.000)
        ).exists()

        if has_stock:
            return True
        return StockLedger.objects.filter(
            workspace=product.workspace, 
            product=product
        ).exists()
    
    @classmethod
    @transaction.atomic
    def create_product(
        cls,
        *,
        workspace,
        user,
        name,
        category: Optional[Category] = None,
        supplier: Optional[Supplier] = None,
        uom: UnitOfMeasure,
        item_type: str = ItemType.STANDARD,
        tracking_type: str = TrackingType.BASIC,
        sku: Optional[str] = None,
        barcode: Optional[str] = None,
        description: str = "",
        cost_price: Decimal = Decimal('0.00'),
        selling_price: Decimal = Decimal('0.00'),
        custom_data: Optional[Dict[str, Any]] = None,
        variants_data: Optional[List[Dict[str, Any]]] = None
    ) -> Product:
        """
        Creates a Product and handles its initial variant setup.
        - STANDARD items auto-generate a single synthetic ProductVariant.
        - VARIANT_PARENT items require variants_data.
        - SERVICE items cannot have variants and default to BASIC tracking.
        """
        AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_CREATE)
        cls._validate_workspace_ownership(
            workspace, 
            category=category, 
            supplier=supplier, 
            uom=uom
        )
        if item_type == ItemType.SERVICE:
            if tracking_type != TrackingType.BASIC:
                raise ValidationError("SERVICE products must use BASIC tracking type.")
            if variants_data:
                raise ValidationError("SERVICE products cannot have variants.")
        
        cls._validate_prices(cost_price, selling_price)
        
        if not name or not name.strip():
            raise ProductValidationError("Name is required", field="name")
        if not sku or not sku.strip():
            raise ProductValidationError("SKU is required", field="sku")
        if sku:
            sku = sku.strip().upper()
        if barcode:
            barcode = barcode.strip()

        sanitized_custom_data = validate_custom_payload(
        workspace=workspace, 
        model_class=Product, 
        custom_data=custom_data or {}
        )
        
        product = Product(
            workspace=workspace,
            name=name,
            item_type=item_type,
            tracking_type=tracking_type,
            sku=sku,
            barcode=barcode,
            category=category,
            supplier=supplier,
            uom=uom,
            description=description,
            custom_data=sanitized_custom_data or {},
        )
        product.full_clean()
        product.save()

        if item_type == ItemType.STANDARD:
            variant_sku =sku or f'{product.id.hex[:8].upper()}-DEF'
            default_variant = ProductVariant(
                workspace=workspace,
                product=product,
                sku=variant_sku,
                barcode=barcode,
                variant_name='Default',
                cost_price=cost_price,
                selling_price=selling_price,
            )
            default_variant.full_clean()
            default_variant.save()
        elif item_type == ItemType.VARIANT_PARENT:
            if not variants_data:
                raise ValidationError('VARIANT_PARENT products require at least one variant configuration.')
            for v_data in variants_data:
                cls.create_variant(
                    workspace=workspace,
                    user=user,
                    product=product,
                    sku=v_data["sku"],
                    barcode=v_data.get("barcode"),
                    variant_name=v_data.get("variant_name", ""),
                    cost_price=v_data.get("cost_price", Decimal("0.00")),
                    selling_price=v_data.get("selling_price", Decimal("0.00")),
                    attribute_value_ids=v_data.get("attribute_value_ids", []),
                )
        if supplier:
            cls.link_supplier(
                workspace=workspace,
                product=product,
                supplier=supplier,
                purchase_price=cost_price,
                is_preferred=True
            )
        return product
    
    @classmethod
    @transaction.atomic
    def create_variant(
        cls,
        *,
        workspace,
        user,
        product: Product,
        sku: str,
        variant_name: str,
        barcode: Optional[str] = None,
        cost_price: Decimal = Decimal("0.00"),
        selling_price: Decimal = Decimal("0.00"),
        min_stock_level: Decimal = Decimal("0.000"),
        max_stock_level: Optional[Decimal] = None,
        weight_kg: Optional[Decimal] = None,
        attribute_value_ids: Optional[List[str]] = None,
    ) -> ProductVariant:
        AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_CREATE)
        if product.item_type != ItemType.VARIANT_PARENT:
            raise ValidationError('Variants can only be added to VARIANT_PARENT products.')
        cls._validate_workspace_ownership(workspace, product=product)
        cls._validate_prices(cost_price, selling_price)
        cls._validate_stock_levels(min_stock_level, max_stock_level)
        
        variant = ProductVariant(
            workspace=workspace,
            product=product,
            sku=sku,
            barcode=barcode,
            variant_name=variant_name,
            cost_price=cost_price,
            selling_price=selling_price,
            min_stock_level=min_stock_level,
            max_stock_level=max_stock_level,
            weight_kg=weight_kg,
        )
        variant.full_clean()
        variant.save()
        if attribute_value_ids:
            attr_values = AttributeValue.objects.filter(id__in=attribute_value_ids)
            if len(attr_values) != len(attribute_value_ids):
                raise WorkspaceMismatchError('One or more AttributeValues were invalid or belong to another workspace.')
            junctions = [
                VariantAttributeValue(workspace=workspace, variant=variant, attribute_value=av) for av in attr_values
            ]
            VariantAttributeValue.objects.bulk_create(junctions)
        return variant
    
    @classmethod
    @transaction.atomic
    def update_product(
        cls,
        *,
        workspace,
        user,
        product: Product,
        **updated_fields
    ) -> Product:
        AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_UPDATE)
        cls._validate_workspace_ownership(workspace, product=product)

        if "tracking_type" in updated_fields and updated_fields["tracking_type"] != product.tracking_type:
            raise ImmutableFieldError("tracking_type cannot be modified after product creation.")

        if "item_type" in updated_fields and updated_fields["item_type"] != product.item_type:
            raise ImmutableFieldError("item_type cannot be modified after product creation.")
            
        for field, value in updated_fields.items():
            if hasattr(product, field):
                setattr(product, field, value)
        product.full_clean()
        product.save()

        if product.item_type == ItemType.STANDARD and ("sku" in updated_fields):
            default_variant = product.variants.first()
            if default_variant:
                if "sku" in updated_fields and updated_fields["sku"]:
                    default_variant.sku = updated_fields["sku"]
                default_variant.save()

        return product
    
    @classmethod
    @transaction.atomic
    def link_supplier(
        cls,
        *,
        workspace,
        product: Product,
        supplier: Supplier,
        variant: Optional[ProductVariant] = None,
        supplier_sku: str = '',
        purchase_price: Decimal,
        min_order_qty: Decimal = Decimal("1.000"),
        lead_time_days: int = 0,
        is_preferred: bool = False,
    ) -> ProductSupplier:
        if variant and variant.product_id != product.id:
            raise ValidationError('Variant does not belong to the specified product.')
        if is_preferred:
            ProductSupplier.objects.filter(
                product=product,
                variant=variant,
                is_preferred=True
            ).update(is_preferred=False)

        link, created = ProductSupplier.objects.update_or_create(
            workspace=workspace,
            product=product,
            supplier=supplier,
            variant=variant,
            defaults={
                "supplier_sku": supplier_sku,
                "purchase_price": purchase_price,
                "min_order_qty": min_order_qty,
                "lead_time_days": lead_time_days,
                "is_preferred": is_preferred,
            }
        )
        return link
    
    @classmethod
    @transaction.atomic
    def archive_product(
        cls,
        *,
        workspace,
        user,
        product
    ) -> Product:
        AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_DELETE)

        product.is_active = False
        product.save()
        product.variants.all().update(is_active=False)
        return product

    @classmethod
    @transaction.atomic
    def delete_product(cls, *, workspace, user, product: Product) -> None:
        """Performs safe hard deletion of a product if no stock history exists."""
        cls._validate_workspace_ownership(workspace, product=product)

        if cls._has_inventory_history(product):
            raise ProductHasStockError()
        # Deletion cascades to variants and junctions per model definitions
        product.delete()
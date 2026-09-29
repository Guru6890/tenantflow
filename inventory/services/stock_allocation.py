# inventory>services>stock_allocation.py
import logging
from decimal import Decimal
from typing import List, Optional, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AbstractUser

from tenancy.models import Workspace
from inventory.catalogue.models import Product, ProductVariant, ItemType, TrackingType
from inventory.locations.models import Warehouse
from inventory.stocks.models import Stock, StockLedger, SerialItem
from inventory.services.exceptions import WorkspaceMismatchError
from authorization.services import AuthorizationService

logger = logging.getLogger(__name__)

ALLOCATE_PERMISSION = 'inventory.stock.allocate'
RELEASE_PERMISSION = 'inventory.stock.release'

def _validate_inputs(
        product: Product,
        variant: Optional[ProductVariant],
        quantity: Decimal,
        serial_numbers: Optional[List[str]] = None
    ):
        if quantity <= 0:
            raise ValidationError({'quantity': 'Quantity to be allocated must be greater than zero.'})
        if product.item_type == ItemType.SERVICE:
            raise ValidationError({'product': 'Services do not carry physical stock to allocate.'})
        if product.tracking_type == TrackingType.SERIAL:
            if not serial_numbers:
                raise ValidationError({'serial_numbers': 'Serial numbers must be specified for serialized allocations.'})
            if quantity % Decimal('1') != Decimal('0'):
                raise ValidationError({'quantity': 'Serialized products cannot have fractional allocation quantities.'})
        if variant and variant.product_id != product.id:
            raise ValidationError({'variant': 'Selected variant does not belong to the provided product.'})
        
def _validate_workspace_ownership(workspace: Workspace, **entities) -> None:
        """Asserts all provided entities belong to the active workspace."""
        for name, entity in entities.items():
            if entity and entity.workspace_id != workspace.id:
                raise WorkspaceMismatchError(
                    f"The provided {name} ({getattr(entity, 'id', entity)}) does not belong to workspace {workspace.id}."
                )

class AllocateStockService:
    @classmethod
    @transaction.atomic
    def allocate(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        warehouse: Warehouse,
        product: Product,
        quantity: Decimal,
        variant: Optional[ProductVariant] = None,
        serial_numbers: Optional[List[str]] = None,
        origin_document: Optional[Any] = None,
        notes: Optional[str] = None
    ) -> StockLedger:
        AuthorizationService.require_permission(user, workspace, ALLOCATE_PERMISSION)
        if product.item_type == ItemType.STANDARD:
            variant = variant or product.variants.first()
            if not variant:
                raise ValidationError({'product': f'Standard product {product.id} lacks a default variant.'})
        _validate_workspace_ownership(workspace, warehouse=warehouse, product=product,)
        _validate_inputs(product, variant, quantity, serial_numbers)

        try:
            stock = Stock.objects.select_for_update().get(
                warehouse=warehouse,
                product=product,
                variant=variant
            )
        except Stock.DoesNotExist:
            raise ValidationError({'stock': f'No stock record found for product in warehouse {warehouse.name}.'})
        
        if stock.available_qty < quantity:
            raise ValidationError({
                'quantity': f'Insufficient available stock. Requested: {quantity}, Available: {stock.available_qty}'
            })
        
        if product.tracking_type == TrackingType.SERIAL and serial_numbers:
            cleaned_serials = [number.strip().upper() for number in serial_numbers]
            if len(cleaned_serials) != len(set(cleaned_serials)):
                raise ValidationError('There are duplicate serial numbers in the list.')
            if len(cleaned_serials) != int(quantity):
                raise ValidationError({
                    'serial_numbers': f'Expected {int(quantity)} serial numbers, got {len(cleaned_serials)}.'
                })
            available_serials = SerialItem.objects.select_for_update().filter(
                warehouse=warehouse,
                variant=variant,
                serial_number__in=cleaned_serials,
                status=SerialItem.Status.IN_STOCK
            )
            if len(available_serials) != len(set(cleaned_serials)):
                found_serials = set(available_serials.values_list('serial_number', flat=True))
                missing_serials = set(cleaned_serials) - found_serials
                raise ValidationError({
                    'serial_numbers': f'The following serial numbers are not available for allocation: {", ".join(missing_serials)}'
                })
            
            available_serials.update(status=SerialItem.Status.ALLOCATED)

        stock.allocated_qty += quantity
        stock.full_clean()
        stock.save()

        content_type = ContentType.objects.get_for_model(origin_document) if origin_document else None
        object_id = origin_document.id if origin_document else None

        ledger_entry = StockLedger.objects.create(
            workspace=workspace,
            stock=stock,
            product=product,
            transaction_type=StockLedger.TRANSACTIONS.ALLOCATE,
            quantity_change=quantity,
            content_type=content_type,
            object_id=object_id,
            notes=notes or f"Allocated {quantity} units in {warehouse.name}"
        )

        logger.info(
            f"User {user.id} allocated {quantity} units of Variant {variant.id} "
            f"in Warehouse {warehouse.id}."
        )

        return ledger_entry
    
class ReleaseStockService:
    @staticmethod
    @transaction.atomic
    def release(
        user: AbstractUser,
        workspace: Workspace,
        warehouse: Warehouse,
        product: Product,
        quantity: Decimal,
        variant: Optional[ProductVariant] = None,
        serial_numbers: Optional[List[str]] = None,
        origin_document: Optional[Any] = None,
        notes: Optional[str] = None
    ) -> StockLedger:
        AuthorizationService.require_permission(user, workspace, RELEASE_PERMISSION)
        if product.item_type == ItemType.STANDARD:
            variant = variant or product.variants.first()
            if not variant:
                raise ValidationError({'product': f'Standard product {product.id} lacks a default variant.'})
        _validate_workspace_ownership(workspace, warehouse=warehouse, product=product)
        _validate_inputs(product, variant, quantity, serial_numbers)

        try:
            stock = Stock.objects.select_for_update().get(
                product=product,
                variant=variant,
                warehouse=warehouse
            )
        except Stock.DoesNotExist:
            raise ValidationError({'stock': 'Stock record does not exist.'})
        if stock.allocated_qty < quantity:
            raise ValidationError({'quantity': f'Cannot release {quantity} units. Only {stock.allocated_qty} units are allocated.'})
        
        if product.tracking_type == TrackingType.SERIAL and serial_numbers:
            cleaned_serials = [number.strip().upper() for number in serial_numbers]
            if len(cleaned_serials) != len(set(cleaned_serials)):
                raise ValidationError('There are duplicate serial numbers in the list.')
            if len(cleaned_serials) != int(quantity):
                raise ValidationError({
                    'serial_numbers': f'Expected {int(quantity)} serial numbers, got {len(cleaned_serials)}.'
                })
            allocated_serials = SerialItem.objects.select_for_update().filter(
                variant=variant,
                serial_number__in=cleaned_serials,
                status=SerialItem.Status.ALLOCATED
            )
            if len(allocated_serials) != len(set(cleaned_serials)):
                raise ValidationError({
                    'serial_numbers':
                    f'Expected {len(set(cleaned_serials))} allocated serial numbers, '
                    f'but found {len(allocated_serials)}.'
                })
            allocated_serials.update(status=SerialItem.Status.IN_STOCK)

        stock.allocated_qty -= quantity
        stock.full_clean()
        stock.save()

        content_type = ContentType.objects.get_for_model(origin_document) if origin_document else None
        object_id = origin_document.id if origin_document else None

        ledger_entry = StockLedger.objects.create(
            workspace=workspace,
            stock=stock,
            product=product,
            transaction_type=StockLedger.TRANSACTIONS.RELEASE,
            quantity_change=quantity,
            content_type=content_type,
            object_id=object_id,
            notes=notes or f"Released {quantity} allocated units in {warehouse.name}"
        )

        return ledger_entry
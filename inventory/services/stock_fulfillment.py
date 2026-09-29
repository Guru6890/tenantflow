# inventory>services>stock_fulfillment.py
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AbstractUser

from tenancy.models import Workspace
from inventory.catalogue.models import Product, ProductVariant, ItemType, TrackingType
from inventory.locations.models import Warehouse
from inventory.stocks.models import Stock, StockLedger, SerialItem, Batch
from inventory.services.exceptions import WorkspaceMismatchError
from authorization.services import AuthorizationService

logger = logging.getLogger(__name__)

FULFILL_PERMISSION = 'inventory.stock.fulfill'

@dataclass(frozen=True)
class BatchPickDTO:
    """Explicit batch picking instruction when overriding FEFO."""
    batch_number: str
    quantity: Decimal

def _validate_inputs(
        product: Product,
        quantity: Decimal,
        variant: Optional[ProductVariant],
        serial_numbers: Optional[List[str]] = None,
        batch_picks: Optional[List[BatchPickDTO]] = None,
):
    if quantity <= Decimal('0.000'):
        raise ValidationError({'quantity': 'Quantity to fulfill must be greater than zero.'})
    if product.item_type == ItemType.SERVICE:
        raise ValidationError({'product': 'Services do not carry physical stock to fulfill.'})
    if product.item_type == ItemType.VARIANT_PARENT and not variant:
        raise ValidationError({'variant': 'Variant can not be empty for products with variants.'})
    if product.tracking_type == TrackingType.SERIAL:
        if not serial_numbers:
            raise ValidationError({'serial_numbers': 'Serial numbers must be specified for serialized fulfillment.'})
        if quantity % Decimal('1') != Decimal('0'):
            raise ValidationError({'quantity': 'Serialized products cannot have fractional fulfillment quantities.'})
    if product.tracking_type == TrackingType.BATCH and batch_picks:
        cleaned_batch_numbers = [pick.batch_number.strip().upper() for pick in batch_picks]
        if len(cleaned_batch_numbers) != len(set(cleaned_batche_numbers)):
            raise ValidationError({'batch_picks': 'Duplicate batch numbers found in fulfillment input.'})
        for pick in batch_picks:
            if pick.quantity <= Decimal('0.000'):
                raise ValidationError({
                    'batch_picks': f'Picked quantity for batch {pick.batch_number} must be greater than zero.'
                })
        total_picked = sum(pick.quantity for pick in batch_picks)
        if total_picked != quantity:
            raise ValidationError({
                    'batch_picks': f'Total batch picked quantity ({total_picked}) does not match fulfillment quantity ({quantity}).'
                })
        
    if variant and variant.product_id != product.id:
        raise ValidationError({'variant': 'Selected variant does not belong to the provided product.'})
    
def _validate_workspace_ownership(workspace: Workspace, **entities) -> None:
    for name, entity in entities.items():
        if entity and entity.workspace_id != workspace.id:
            raise WorkspaceMismatchError(
                f"The provided {name} ({getattr(entity, 'id', entity)}) does not belong to workspace {workspace.id}."
            )
        
def normalize_serials(serial_numbers: List[str], quantity: Decimal) -> List[str]:
    cleaned_serials = [sn.strip().upper() for sn in serial_numbers]
    if len(cleaned_serials) != len(set(cleaned_serials)):
        raise ValidationError({'serial_numbers': 'Duplicate serial numbers found in input.'})
    if len(cleaned_serials) != int(quantity):
        raise ValidationError({
            'serial_numbers': f'Expected {int(quantity)} serial numbers, got {len(cleaned_serials)}.'
        })
    return cleaned_serials
        
class FulfillStockService:
    @staticmethod
    @transaction.atomic
    def fulfill(
        user: AbstractUser,
        workspace: Workspace,
        warehouse: Warehouse,
        product: Product,
        quantity: Decimal,
        variant: Optional[ProductVariant] = None,
        serial_numbers: Optional[List[str]] = None,
        batch_picks: Optional[List[BatchPickDTO]] = None,
        origin_document: Optional[Any] = None,
        notes: Optional[str] = None
    ) -> StockLedger:
        AuthorizationService.require_permission(user, workspace, FULFILL_PERMISSION)
        if product.item_type == ItemType.STANDARD:
            variant = variant or product.variants.first()
        _validate_workspace_ownership(
            workspace,
            warehouse=warehouse,
            product=product,
            variant=variant
        )
        _validate_inputs(product, quantity, variant, serial_numbers, batch_picks)

        try:
            stock = Stock.objects.select_for_update().get(
                warehouse=warehouse,
                product=product,
                variant=variant
            )
        except Stock.DoesNotExist:
            raise ValidationError({'stock': f'No stock record found for product in warehouse {warehouse.name}.'})
        
        if stock.allocated_qty < quantity:
            raise ValidationError({
                'quantity': f'Cannot fulfill {quantity} units. Only {stock.allocated_qty} units are allocated.'
            })
        
        if product.tracking_type == TrackingType.SERIAL and serial_numbers:
            cleaned_serials = normalize_serials(serial_numbers, quantity)
            allocated_serials = SerialItem.objects.select_for_update().filter(
                warehouse=warehouse,
                variant=variant,
                serial_number__in=cleaned_serials,
                status=SerialItem.Status.ALLOCATED
            )
            if len(allocated_serials) != len(cleaned_serials):
                found_serials = set(allocated_serials.values_list('serial_number', flat=True))
                missing_serials = set(cleaned_serials) - found_serials
                raise ValidationError({
                    'serial_numbers': f'The following serial numbers are not in ALLOCATED status: {", ".join(missing_serials)}'
                })
            allocated_serials.update(
                status=SerialItem.Status.SOLD,
                warehouse=None
            )

        if product.tracking_type == TrackingType.BATCH:
            if batch_picks:
                for pick in batch_picks:
                    try:
                        batch = Batch.objects.select_for_update().get(
                            warehouse=warehouse,
                            variant=variant,
                            batch_number=pick.batch_number.strip().upper()
                        )
                    except Batch.DoesNotExist:
                        raise ValidationError({
                            'batch_picks': f'Batch {pick.batch_number} does not exist in this warehouse.'
                        })
                    if batch.quantity < pick.quantity:
                        raise ValidationError({
                            'batch_picks': f'Batch {batch.batch_number} has insufficient quantity ({batch.quantity}) for pick ({pick.quantity}).'
                        })
                    batch.quantity -= pick.quantity
                    batch.save()

            else:
                remaining_to_fulfill = quantity
                batches = Batch.objects.select_for_update().filter(
                    warehouse=warehouse,
                    variant=variant,
                    quantity__gt=Decimal('0.000')
                ).order_by('expiry_date', 'manufactured_date')

                total_batch_qty = sum(b.quantity for b in batches)
                if total_batch_qty < quantity:
                    raise ValidationError({
                        'batch_picks': f'Insufficient total batch quantity across available batches. Required: {quantity}, Available: {total_batch_qty}'
                    })
                
                for batch in batches:
                    if remaining_to_fulfill <= 0:
                        break
                    deduct_qty = min(batch.quantity, remaining_to_fulfill)
                    batch.quantity -= deduct_qty
                    batch.save()
                    remaining_to_fulfill -= deduct_qty

        stock.physical_qty -= quantity
        stock.allocated_qty -= quantity
        stock.full_clean()
        stock.save()
                
        content_type = ContentType.objects.get_for_model(origin_document) if origin_document else None
        object_id = origin_document.id if origin_document else None

        ledger_entry = StockLedger.objects.create(
            workspace=workspace,
            stock=stock,
            product=product,
            transaction_type=StockLedger.TRANSACTIONS.SALE,
            quantity_change=-quantity,  # Negative value represents outward stock movement
            content_type=content_type,
            object_id=object_id,
            notes=notes or f"Fulfilled {quantity} units from {warehouse.name}"
        )

        logger.info(
            f"User {user.id} fulfilled {quantity} units of Variant {variant.id} "
            f"from Warehouse {warehouse.id}. Stock Ledger ID: {ledger_entry.id}"
        )

        return ledger_entry
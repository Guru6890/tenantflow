# inventory/services/stock_adjustment.py
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AbstractUser

from tenancy.models import Workspace
from inventory.catalogue.models import Product, ProductVariant, ItemType, TrackingType
from inventory.locations.models import Warehouse
from inventory.stocks.models import Stock, StockLedger, SerialItem, Batch, StockAdjustment
from inventory.services.exceptions import WorkspaceMismatchError
from authorization.services import AuthorizationService

logger = logging.getLogger(__name__)

ADJUSTMENT_PERMISSION = 'inventory.stock.adjust'

@dataclass
class BatchAdjustmentDTO:
    batch_number: str
    quantity_change: Decimal

def _validate_workspace_ownership(workspace: Workspace, **entities) -> None:
    for name, entity in entities.items():
        if entity and entity.workspace_id != workspace.id:
            raise ValidationError(
                f"The provided {name} ({getattr(entity, 'id', entity)}) does not belong to workspace {workspace.id}."
            )

def _validate_inputs(
    product: Product,
    quantity_change: Decimal,
    variant: Optional[ProductVariant],
    serial_numbers: Optional[List[str]] = None,
    batch_adjustments: Optional[List[BatchAdjustmentDTO]] = None
):
    if quantity_change == Decimal('0.000'):
        raise ValidationError({'quantity_change': 'Quantity change cannot be zero.'})
    if product.item_type == ItemType.SERVICE:
        raise ValidationError({'product': 'Services do not carry physical stock to adjust.'})
    if product.item_type == ItemType.VARIANT_PARENT and not variant:
        raise ValidationError({'variant': 'Variant cannot be empty for products with variants.'})
    if product.tracking_type == TrackingType.SERIAL:
        if not serial_numbers:
            raise ValidationError({'serial_numbers': 'Serial numbers must be provided for serialized stock adjustment.'})
        if quantity_change % Decimal('1') != Decimal('0'):
            raise ValidationError({'quantity_change': 'Serialized products cannot have fractional adjustment quantities.'})
    if product.tracking_type == TrackingType.BATCH:
        if not batch_adjustments:
            raise ValidationError({'batch_adjustments': 'Products tracked in batches require batch information.'})
        total_batch_change = sum(adj.quantity_change for adj in batch_adjustments)
        if quantity_change != total_batch_change:
            raise ValidationError({
                'batch_adjustments': f'Sum of batch changes ({total_batch_change}) does not match total quantity change ({quantity_change}).'
            })
    if variant and variant.product_id != product.id:
        raise ValidationError({'variant': 'Selected variant does not belong to the provided product.'})
    
class AdjustStockService:
    @staticmethod
    @transaction.atomic
    def adjust(
        user: AbstractUser,
        workspace: Workspace,
        warehouse: Warehouse,
        product: Product,
        quantity_change: Decimal,
        reason: str,
        variant: Optional[ProductVariant],
        serial_numbers: Optional[List[str]] = None,
        batch_adjustments: Optional[List[BatchAdjustmentDTO]] = None,
        target_serial_status: Optional[str] = SerialItem.Status.DEFECTIVE,
        notes: Optional[str] = None
    ) -> Tuple[StockAdjustment, StockLedger]:
        AuthorizationService.require_permission(user, workspace, ADJUSTMENT_PERMISSION)
        valid_reasons = [choice[0] for choice in StockAdjustment.REASON.choices]
        if reason not in valid_reasons:
            raise ValidationError({
                'reason': f"Invalid reason '{reason}'. Must be one of: {', '.join(valid_reasons)}"
            })
        if product.item_type == ItemType.STANDARD:
            variant = variant or product.variants.first()

        _validate_workspace_ownership(
            workspace,
            product=product,
            warehouse=warehouse
        )
        _validate_inputs(product, quantity_change, variant, serial_numbers, batch_adjustments)

        try:
            stock = Stock.objects.select_for_update().get(
                workspace=workspace,
                warehouse=warehouse,
                product=product,
                variant=variant
            )
        except Stock.DoesNotExist:
            if quantity_change < 0:
                raise ValidationError({'stock': f'No stock record found in warehouse {warehouse.name} to reduce.'})
            stock = Stock.objects.create(
                workspace=workspace,
                warehouse=warehouse,
                product=product,
                variant=variant,
                physical_qty=Decimal('0.000'),
                allocated_qty=Decimal('0.000')
            )
        old_qty = stock.physical_qty
        new_physical_qty = stock.physical_qty + quantity_change
        difference = quantity_change
        if new_physical_qty < Decimal('0.000'):
            raise ValidationError({
                'quantity_change': f'Cannot decrease physical stock below zero. Current physical stock: {stock.physical_qty}'
            })
        if new_physical_qty < stock.allocated_qty:
            raise ValidationError(
                "Physical quantity cannot be reduced below allocated quantity. "
                "Resolve affected allocations first."
            )
        
        if product.tracking_type == TrackingType.SERIAL and serial_numbers:
            cleaned_serials = [sn.strip().upper() for sn in serial_numbers]
            if len(cleaned_serials) != len(set(cleaned_serials)):
                raise ValidationError({'serial_numbers': 'Duplicate serial numbers found in input.'})
            
            if len(cleaned_serials) != abs(quantity_change):
                raise ValidationError({
                    'serial_numbers': f'Expected {abs(int(quantity_change))} serial numbers for adjustment, got {len(cleaned_serials)}.'
                })
            
            if quantity_change < Decimal('0.000'):
                serials_qs = SerialItem.objects.select_for_update().filter(
                    workspace=workspace,
                    warehouse=warehouse,
                    variant=variant,
                    serial_number__in=cleaned_serials,
                    status=SerialItem.Status.IN_STOCK
                )
                if len(serials_qs) != len(cleaned_serials):
                    found_serials = set(serials_qs.values_list('serial_number', flat=True))
                    missing_serials = set(cleaned_serials) - found_serials
                    raise ValidationError({
                        'serial_numbers': f'The following serials are not available to adjust out: {", ".join(missing_serials)}'
                    })
                serials_qs.update(status=target_serial_status)
            else:
                existing_serials = SerialItem.objects.filter(
                    workspace=workspace,
                    warehouse=warehouse,
                    variant=variant,
                    serial_number__in=cleaned_serials
                )
                if existing_serials.exists():
                    existing_list = list(existing_serials.values_list('serial_number', flat=True))
                    raise ValidationError({
                        'serial_numbers': f'The following serial number(s) already exist in the system: {", ".join(existing_list)}'
                    })
                new_serial_objs = [
                    SerialItem(
                        workspace=workspace,
                        warehouse=warehouse,
                        variant=variant,
                        serial_number=sn,
                        status=SerialItem.Status.IN_STOCK
                    )
                    for sn in cleaned_serials
                ]
                SerialItem.objects.bulk_create(new_serial_objs)
        if product.tracking_type == TrackingType.BATCH and batch_adjustments:
            for adj in batch_adjustments:
                cleaned_batch_num = adj.batch_number.strip().upper()
                try:
                    batch = Batch.objects.select_for_update().get(
                        workspace=workspace,
                        warehouse=warehouse,
                        variant=variant,
                        batch_number=cleaned_batch_num
                    )
                except Batch.DoesNotExist:
                    raise ValidationError({'batch_adjustments': f'Batch {cleaned_batch_num} does not exist.'})

                new_batch_qty = batch.quantity + adj.quantity_change
                if new_batch_qty < Decimal('0.000'):
                    raise ValidationError({
                        'batch_adjustments': f'Cannot reduce batch {batch.batch_number} below 0. Current: {batch.quantity}'
                    })

                batch.quantity = new_batch_qty
                batch.save()

        # 5. Apply Updates to Stock
        stock.physical_qty = new_physical_qty
        stock.full_clean()
        stock.save()

        adjustment_record = StockAdjustment.objects.create(
            workspace=workspace,
            stock=stock,
            old_qty=old_qty,
            new_qty=new_physical_qty,
            difference=difference,
            reason=reason,
            notes=notes or ''
        )

        content_type = ContentType.objects.get_for_model(StockAdjustment)
        
        ledger_entry = StockLedger.objects.create(
            workspace=workspace,
            stock=stock,
            product=product,
            transaction_type=StockLedger.TRANSACTIONS.ADJUSTMENT,
            quantity_change=difference,
            content_type=content_type,
            object_id=adjustment_record.id,
            notes=f"Adjustment ({reason}): {difference:+f} | {notes}"
        )

        logger.info(
            f"StockAdjustment #{adjustment_record.id} created by User #{user.id}. "
            f"Stock #{stock.id} adjusted from {old_qty} to {new_physical_qty} ({difference:+f})."
        )

        return adjustment_record, ledger_entry
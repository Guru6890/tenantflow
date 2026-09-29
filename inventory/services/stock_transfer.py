# inventory/services/stock_transfer.py
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List, Dict, Tuple
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone

from tenancy.models import Workspace
from inventory.catalogue.models import Product, ProductVariant, ItemType, TrackingType
from inventory.locations.models import Warehouse
from inventory.stocks.models import (
    Stock, StockLedger, SerialItem, Batch, WarehouseTransfer, TransferItem
)
from authorization.services import AuthorizationService

logger = logging.getLogger(__name__)

TRANSFER_PERMISSION = 'inventory.stock.transfer'

@dataclass
class TransferItemInputDTO:
    product: Product
    variant: ProductVariant
    quantity: Decimal
    
@dataclass
class DispatchItemAssignmentDTO:
    transfer_item_id: int
    serial_numbers: Optional[List[str]] = None
    batch_number: Optional[str] = None

@dataclass
class ReceiveItemAssignmentDTO:
    transfer_item_id: int
    serial_numbers: Optional[List[str]] = None
    batch_number: Optional[str] = None

class TransferStockService:
    @classmethod
    @transaction.atomic
    def create_transfer(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        from_warehouse: Warehouse,
        to_warehouse: Warehouse,
        items: List[TransferItemInputDTO],
        notes: Optional[str] = ''
    ) -> WarehouseTransfer:
        AuthorizationService.require_permission(user, workspace, TRANSFER_PERMISSION)
        
        if from_warehouse == to_warehouse:
            raise ValidationError({'to_warehouse': 'Origin and destination warehouses cannot be identical.'})
        
        cls._validate_workspace_ownership(workspace, from_warehouse=from_warehouse, to_warehouse=to_warehouse)

        if not items:
            raise ValidationError({'items': 'At least one item must be included in the transfer.'})
        
        transfer = WarehouseTransfer.objects.create(
            workspace=workspace,
            from_warehouse=from_warehouse,
            to_warehouse=to_warehouse,
            status=WarehouseTransfer.STATUS.PENDING,
            notes=notes or ''
        )

        for item_dto in items:
            product = item_dto.product
            variant = item_dto.variant or (product.variants.first() if product.item_type == ItemType.STANDARD else None)
            qty = item_dto.quantity

            cls._validate_workspace_ownership(workspace, product=product)
            cls._validate_item_inputs(product, variant, qty)

            TransferItem.objects.create(
                workspace=workspace,
                transfer=transfer,
                product=product,
                variant=variant,
                quantity=qty
            )

            try:
                origin_stock = Stock.objects.select_for_update().get(
                    workspace=workspace,
                    warehouse=from_warehouse,
                    product=product,
                    variant=variant
                )
            except Stock.DoesNotExist:
                raise ValidationError({'items': f'Stock record for {product.name} does not exist in {from_warehouse.name}.'})

            if origin_stock.available_qty < qty:
                raise ValidationError({
                    'items': (
                        f"Cannot transfer {qty} units of {product.name}. "
                        f"Physical: {origin_stock.physical_qty}, Allocated: {origin_stock.allocated_qty}, "
                        f"Available: {origin_stock.available_qty}."
                    )
                })
            origin_stock.reserved_qty += qty
            origin_stock.full_clean()
            origin_stock.save()

        logger.info(f"Transfer #{transfer.id} created in PENDING status by User #{user.id}.")
        return transfer
    
    @classmethod
    @transaction.atomic
    def dispatch_transfer(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        transfer: WarehouseTransfer,
        dispatch_assignments: List[DispatchItemAssignmentDTO]
    ) -> Tuple[WarehouseTransfer, List[StockLedger]]:
        AuthorizationService.require_permission(user, workspace, TRANSFER_PERMISSION)
        if transfer.status != WarehouseTransfer.STATUS.PENDING:
            raise ValidationError("Only pending transfers can be dispatched.")
        cls._validate_workspace_ownership(workspace, transfer=transfer)
        
        ledger_entries: List[StockLedger] = []

        assignment_map = {assignment.transfer_item_id: assignment for assignment in dispatch_assignments}

        for transfer_item in transfer.transfer_items.select_related('product', 'variant'):
            product = transfer_item.product
            variant = transfer_item.variant
            qty = transfer_item.quantity
            assignment = assignment_map.get(transfer_item.id)

            origin_stock = Stock.objects.select_for_update().get(
                workspace=workspace,
                warehouse=transfer.from_warehouse,
                product=product,
                variant=variant
            )

            if product.tracking_type == TrackingType.SERIAL:
                if not assignment or not assignment.serial_numbers:
                    raise ValidationError({'serial_numbers': f'Serial numbers required to dispatch item #{transfer_item.id}.'})
                cleaned_serials = cls.process_serial_numbers(assignment.serial_numbers, qty)
                serials_qs = SerialItem.objects.select_for_update().filter(
                    workspace=workspace,
                    warehouse=transfer.from_warehouse,
                    variant=variant,
                    serial_number__in=cleaned_serials,
                    status=SerialItem.Status.IN_STOCK
                )
                if len(serials_qs) != len(cleaned_serials):
                    found_serials = set(serials_qs.values_list('serial_number', flat=True))
                    missing_serials = set(cleaned_serials) - found_serials
                    raise ValidationError({
                        'serial_numbers': f"Serials not available IN_STOCK at {transfer.from_warehouse.name}: {', '.join(missing_serials)}"
                    })
                
                serials_qs.update(
                    status=SerialItem.Status.IN_TRANSIT
                )

            if product.tracking_type == TrackingType.BATCH:
                if not assignment or not assignment.batch_number:
                    raise ValidationError({'batch_number': f'Batch number required to dispatch item #{transfer_item.id}.'})
                cleaned_batch_num = assignment.batch_number.strip().upper()
                try:
                    origin_batch = Batch.objects.select_for_update().get(
                        workspace=workspace,
                        warehouse=transfer.from_warehouse,
                        variant=variant,
                        batch_number=cleaned_batch_num
                    )
                except Batch.DoesNotExist:
                    raise ValidationError({'batch_number': f"Batch {cleaned_batch_num} does not exist at {transfer.from_warehouse.name}."})
                if origin_batch.quantity < qty:
                    raise ValidationError({'batch_number': f"Insufficient batch balance in {cleaned_batch_num}. Available: {origin_batch.quantity}"})
                origin_batch.quantity -= qty
                origin_batch.save()

            origin_stock.physical_qty -= qty
            origin_stock.reserved_qty += qty
            origin_stock.full_clean()
            origin_stock.save()

            content_type = ContentType.objects.get_for_model(WarehouseTransfer)
            ledger_entry = StockLedger.objects.create(
                workspace=workspace,
                stock=origin_stock,
                product=product,
                transaction_type=StockLedger.TRANSACTIONS.TRANSFER_OUT,
                quantity_change=-qty,
                content_type=content_type,
                object_id=transfer.id,
                notes=f"Dispatched via Transfer #{transfer.id} to {transfer.to_warehouse.name}"
            )
            ledger_entries.append(ledger_entry)

        # Update Transfer Document Status
        transfer.mark_as_dispatched()

        logger.info(f"Transfer #{transfer.id} dispatched from Warehouse #{transfer.from_warehouse.id} by User #{user.id}.")
        return transfer, ledger_entries
    
    @classmethod
    @transaction.atomic
    def receive_transfer(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        transfer: WarehouseTransfer,
        receive_assignment: List[ReceiveItemAssignmentDTO]
    ) -> Tuple[WarehouseTransfer, List[StockLedger]]:
        AuthorizationService.require_permission(user, workspace, TRANSFER_PERMISSION)

        if transfer.status != WarehouseTransfer.STATUS.IN_TRANSIT:
            raise ValidationError({'transfer': 'Only IN_TRANSIT transfers can be received.'})
        
        cls._validate_workspace_ownership(workspace, transfer=transfer)

        assignment_map = {assignment.transfer_item_id: assignment for assignment in receive_assignment}
        ledger_entries: List[StockLedger] = []

        for transfer_item in transfer.transfer_items.select_related('product', 'variant'):
            product = transfer_item.product
            variant = transfer_item.variant
            qty = transfer_item.quantity
            to_warehouse = transfer.to_warehouse
            assignment = assignment_map.get(transfer_item.id)

            dest_stock, _ = Stock.objects.select_for_update().get_or_create(
                workspace=workspace,
                warehouse=to_warehouse,
                product=product,
                variant=variant,
                defaults={
                    'physical_qty': Decimal('0.000'),
                    'allocated_qty': Decimal('0.000')
                }
            )

            if product.tracking_type == TrackingType.SERIAL:
                if not assignment or not assignment.serial_numbers:
                    raise ValidationError({'serial_numbers': f'Serial numbers required to receive item #{transfer_item.id}.'})
                cleaned_serials = cls.process_serial_numbers(assignment.serial_numbers, qty)
                serials_qs = SerialItem.objects.select_for_update().filter(
                    workspace=workspace,
                    variant=variant,
                    serial_number__in=cleaned_serials,
                    status=SerialItem.Status.IN_TRANSIT
                )
                if len(serials_qs) != len(cleaned_serials):
                    raise ValidationError({'serial_numbers': f'One or more serial numbers are not in IN_TRANSIT status.'})
                serials_qs.update(
                    status=SerialItem.Status.IN_STOCK,
                    warehouse=to_warehouse
                )

            if product.tracking_type == TrackingType.BATCH:
                if not assignment or not assignment.batch_number:
                    raise ValidationError({'batch_number': f'Batch number required to receive item #{transfer_item.id}.'})
                cleaned_batch_num = assignment.batch_number.strip().upper()

                origin_batch = Batch.objects.filter(
                    workspace=workspace,
                    warehouse=transfer.from_warehouse,
                    variant=variant,
                    batch_number=cleaned_batch_num
                ).first()
                
                dest_batch, _ = Batch.objects.select_for_update().get_or_create(
                    workspace=workspace,
                    warehouse=to_warehouse,
                    variant=variant,
                    batch_number=cleaned_batch_num,
                    defaults={
                        'quantity': Decimal('0.000'),
                        'expiry_date': origin_batch.expiry_date if origin_batch else None,
                        'manufactured_date': origin_batch.manufactured_date if origin_batch else None,
                    }
                )
                dest_batch.quantity += qty
                dest_batch.save()

            dest_stock.physical_qty += qty
            dest_stock.full_clean()
            dest_stock.save()

            content_type = ContentType.objects.get_for_model(WarehouseTransfer)
            ledger_entry = StockLedger.objects.create(
                workspace=workspace,
                stock=dest_stock,
                product=product,
                transaction_type=StockLedger.TRANSACTIONS.TRANSFER_IN,
                quantity_change=qty,
                content_type=content_type,
                object_id=transfer.id,
                notes=f"Received via Transfer #{transfer.id} from {transfer.from_warehouse.name}"
            )
            ledger_entries.append(ledger_entry)

        # Update Transfer Document Status
        transfer.status = WarehouseTransfer.STATUS.RECEIVED
        transfer.received_at = timezone.now()
        transfer.save()

        logger.info(f"Transfer #{transfer.id} received at Warehouse #{transfer.to_warehouse.id} by User #{user.id}.")
        return transfer, ledger_entries

    @staticmethod
    def _validate_workspace_ownership(workspace: Workspace, **entities) -> None:
        for name, entity in entities.items():
            if entity and getattr(entity, 'workspace_id', None) != workspace.id:
                raise ValidationError(
                    f"The provided {name} ({getattr(entity, 'id', entity)}) does not belong to workspace {workspace.id}."
                )

    @staticmethod
    def _validate_item_inputs(
        product: Product,
        variant: Optional[ProductVariant],
        quantity: Decimal,
    ) -> None:
        if quantity <= Decimal('0.000'):
            raise ValidationError({'quantity': 'Transfer quantity must be greater than zero.'})

        if product.item_type == ItemType.SERVICE:
            raise ValidationError({'product': 'Services cannot be physically transferred between warehouses.'})

        if product.item_type == ItemType.VARIANT_PARENT and not variant:
            raise ValidationError({'variant': 'Variant must be provided for variant parent products.'})

        if variant and variant.product_id != product.id:
            raise ValidationError({'variant': 'Selected variant does not belong to the provided product.'})

    @staticmethod
    def process_serial_numbers(serial_numbers:List[str], quantity: Decimal) -> List[str]:
        if quantity % Decimal('1') != Decimal('0'):
            raise ValidationError({'quantity': 'Serialized products can not have fractional quantities.'})
        
        cleaned_serials = [sn.strip().upper() for sn in serial_numbers]
        if len(cleaned_serials) != len(set(cleaned_serials)):
            raise ValidationError({'serial_numbers': 'Duplicate serial numbers found in input.'})
        if len(cleaned_serials) != int(quantity):
            raise ValidationError({'serial_numbers': f'Expected {int(quantity)} serials, got {len(cleaned_serials)}.'})
        
        return cleaned_serials
    

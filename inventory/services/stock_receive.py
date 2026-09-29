#inventory>services>stock_receive.py
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import AbstractUser

from tenancy.models import Workspace
from inventory.catalogue.models import Product, ProductVariant, ItemType, TrackingType
from inventory.locations.models import Warehouse
from inventory.stocks.models import Stock, StockLedger, Batch, SerialItem
from inventory.services.exceptions import WorkspaceMismatchError
from authorization.services import AuthorizationService

logger = logging.getLogger(__name__)

RECEIVE_PERMISSION = 'inventory.stock.receive'

@dataclass(frozen=True)
class BatchInputDTO:
    batch_number: str
    manufactured_date: Optional[date] = None
    expiry_date: Optional[date] = None

    def __post_init__(self):
        if not self.batch_number or not self.batch_number.strip():
            raise ValidationError({'batch_info': 'Batch number can not be empty.'})

class ReceiveStockService:
    @staticmethod
    def _validate_inputs(
        product: Product,
        variant: Optional[ProductVariant],
        quantity: Decimal,
        batch_info: Optional[Dict[str, Any]] = None,
        serial_numbers: Optional[List[str]] = None,
    ):
        if quantity <= Decimal('0.000'):
            raise ValidationError({'quantity': 'Quantity to receive must be greater than zero.'})
        if product.item_type == ItemType.VARIANT_PARENT and not variant:
            raise ValidationError({'variant': 'Variant must be specified for multi-variant products.'})
        if product.item_type == ItemType.SERVICE:
            raise ValidationError({'product': 'Services can not be in physical product inventories.'})
        if product.tracking_type == TrackingType.BASIC and (batch_info is not None or serial_numbers is not None):
            raise ValidationError('Basic products can not have batch or serial number informations.')
        if product.tracking_type == TrackingType.BATCH and batch_info is None:
            raise ValidationError({'batch_info': 'Products with batch tracking should have batch informations.'})
        if product.tracking_type == TrackingType.SERIAL:
            if not serial_numbers:
                raise ValidationError({'serial_numbers': 'Products with serial number tracking should have serial numbers.'})
            if quantity % Decimal('1') != Decimal('0'):
                raise ValidationError({'quantity': 'Serialized products can not have fractional quantities.'})
        if variant and variant.product_id != product.id:
            raise ValidationError({'variant': 'Selected variant does not belong to the provided product.'})
        
    @staticmethod
    def _validate_workspace_ownership(workspace, **entities) -> None:
        """Asserts all provided entities belong to the active workspace."""
        for name, entity in entities.items():
            if entity and entity.workspace_id != workspace.id:
                raise WorkspaceMismatchError(
                    f"The provided {name} ({getattr(entity, 'id', entity)}) does not belong to workspace {workspace.id}."
                )
    
    @classmethod
    @transaction.atomic
    def receive(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        warehouse: Warehouse,
        product: Product,
        quantity: Decimal,
        variant: Optional[ProductVariant],
        origin_document: Optional[Any] = None,
        notes: Optional[str] = None,
        batch_info: Optional[BatchInputDTO] = None,
        serial_numbers: Optional[List[str]] = None
    ) -> StockLedger:
        AuthorizationService.require_permission(user, workspace, RECEIVE_PERMISSION)
        if product.item_type == ItemType.STANDARD:
            variant = product.variants.first()
            if not variant:
                raise ValidationError({'product': f'Standard product {product.id} lacks a default variant.'})
        cls._validate_workspace_ownership(
            workspace,
            warehouse=warehouse,
            product=product,
            variant=variant
        )
        cls._validate_inputs(product, variant, quantity, batch_info, serial_numbers)
        
        stock, _ = Stock.objects.select_for_update().get_or_create(
            workspace=workspace,
            product=product,
            variant=variant,
            warehouse=warehouse,
            defaults={'physical_qty': Decimal('0.000'), 'allocated_qty': Decimal('0.000')}
        )
        stock.physical_qty += quantity
        stock.full_clean()
        stock.save()

        if product.tracking_type == TrackingType.BATCH and batch_info:
            clean_batch_num = batch_info.batch_number.strip().upper()
            batch, batch_created = Batch.objects.select_for_update().get_or_create(
                workspace=workspace,
                warehouse=warehouse,
                variant=variant,
                batch_number=clean_batch_num,
                defaults={
                    'manufactured_date': batch_info.manufactured_date,
                    'expiry_date': batch_info.expiry_date,
                    'quantity': quantity
                }
            )
            if not batch_created:
                batch.quantity += quantity
                batch.save()

        if product.tracking_type == TrackingType.SERIAL and serial_numbers:
            cleaned_serials = [number.strip().upper() for number in serial_numbers]
            if len(cleaned_serials) != len(set(cleaned_serials)):
                raise ValidationError('There are duplicate serial numbers in the list.')
            if len(serial_numbers) != int(quantity):
                raise ValidationError({'serial_numbers': f'Expected {int(quantity)} serial numbers got {len(serial_numbers)}.'})
            existing_serials = set(
                SerialItem.objects.filter(
                    variant=variant,
                    warehouse=warehouse,
                    serial_number__in=cleaned_serials
                ).values_list('serial_number', flat=True)
            )
            if existing_serials:
                duplicates_str = ", ".join(existing_serials)
                raise ValidationError({
                    'serial_numbers': f'The following serial numbers already exist in the system: {duplicates_str}'
                })
            serials_to_create = [
                SerialItem(
                    workspace=workspace,
                    variant=variant,
                    warehouse=warehouse,
                    serial_number=sn,
                    status=SerialItem.Status.IN_STOCK
                )
                for sn in cleaned_serials
            ]
            SerialItem.objects.bulk_create(serials_to_create)

        content_type = ContentType.objects.get_for_model(origin_document) if origin_document else None
        object_id = origin_document.id if origin_document else None

        ledger_entry = StockLedger.objects.create(
            workspace=workspace,
            stock=stock,
            product=product,
            transaction_type=StockLedger.TRANSACTIONS.PURCHASE,
            quantity_change=quantity,
            content_type=content_type,
            object_id=object_id,
            notes=notes or f"Received {quantity} units into {warehouse.name}"
        )

        logger.info(
            f"User {user.id} received {quantity} units of Variant {variant.id} "
            f"in Warehouse {warehouse.id}. Stock ID: {stock.id}"
        )

        return ledger_entry
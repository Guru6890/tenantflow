# inventory.stocks.models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.core.exceptions import ValidationError

import uuid
from decimal import Decimal

from inventory.catalogue.models import Product, ProductVariant, ItemType
from inventory.locations.models import Warehouse
from tenancy.models import TenantBaseModel

from .managers import StockTenantManager

# Create your models here.

User = settings.AUTH_USER_MODEL

class Stock(TenantBaseModel):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='stocks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='stocks')

    physical_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(0.000))
    allocated_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(0.000))
    reorder_point = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(0.000))
    reserved_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(0.000))

    last_stock_take = models.DateField(blank=True, null=True)

    objects = StockTenantManager()

    @property
    def available_qty(self):
        annotated_qty = getattr(self, '_available_qty', None)
        if annotated_qty is not None:
            return annotated_qty
        return self.physical_qty - (self.allocated_qty + self.reserved_qty)

    def clean(self):
        super().clean()
        if self.allocated_qty > self.physical_qty:
            raise ValidationError('Allocated quantity can not exceed physical quantity.')
        if not self.variant:
            raise ValidationError({'variant': 'Stock must have a variant.'})
        if self.variant.product_id != self.product_id:
            raise ValidationError({'variant': 'Variant does not belong to the selected product.'})
        if self.product.item_type == ItemType.SERVICE:
            raise ValidationError({'product': 'Services cannot have physical stock.'})
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'variant', 'warehouse'],
                condition=models.Q(is_deleted=False),
                name='unique_variant_per_warehouse'
            ),

            models.CheckConstraint(
                condition=models.Q(allocated_qty__lte=models.F('physical_qty')),
                name='allocated_not_greater_than_physical'
            ),

            models.CheckConstraint(
                condition=models.Q(physical_qty__gte=0),
                name='physical_qty_non_negative'
            )
        ]

    def __str__(self):
        return f'{self.product} ({self.physical_qty}) in {self.warehouse}'
    
class Batch(TenantBaseModel):
    """
    Food, Pharma, Chemical & Cosmetics extension.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='batches')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='batches')
    batch_number = models.CharField(max_length=100)
    
    manufactured_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(0.000))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'variant', 'warehouse', 'batch_number'],
                condition=models.Q(is_deleted=False),
                name='unique_batch_per_variant_warehouse'
            ),
            
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name='batch_quantity_non_negative',
            )
        ]

class SerialItem(TenantBaseModel):
    """
    High-value electronics, machinery, and serialized asset extension.
    """
    class Status(models.TextChoices):
        IN_STOCK = 'IN_STOCK', 'In Stock'
        ALLOCATED = 'ALLOCATED', 'Allocated'
        RESERVED = 'RESERVED', 'Reserved'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        SOLD = 'SOLD', 'Sold'
        DEFECTIVE = 'DEFECTIVE', 'Defective'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='serials')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, related_name='serials')
    
    serial_number = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_STOCK)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'variant', 'serial_number'],
                condition=models.Q(is_deleted=False),
                name='unique_serial_per_variant'
            )
        ]
    
class StockLedger(TenantBaseModel):
    class TRANSACTIONS(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase'
        ALLOCATE = 'allocate', 'Allocate'
        RELEASE = 'release', 'Release'
        SALE = 'sale', 'Sale'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        RETURN = 'return', 'Return'
        DAMAGE = 'damage', 'Damage'
        TRANSFER_IN = 'transfer_in', 'Transfer In'
        TRANSFER_OUT = 'transfer_out', 'Transfer Out'
    
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT, null=True, related_name='ledgers_entries')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='ledger_entries')
    variant = models.ForeignKey(ProductVariant,on_delete=models.PROTECT, related_name='ledger_entries')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='ledger_entries')
    transaction_type = models.CharField(max_length=12, choices=TRANSACTIONS.choices)
    quantity_change = models.DecimalField(max_digits=12, decimal_places=3)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    origin_document = GenericForeignKey('content_type', 'object_id')

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class WarehouseTransfer(TenantBaseModel):
    class STATUS(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_TRANSIT = 'in_transit', 'In Transit'
        RECEIVED = 'received', 'Received'
        CANCELLED = 'cancelled', 'Cancelled'

    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_out')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='transfers_in')
    status = models.CharField(max_length=10, choices=STATUS.choices, default=STATUS.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def mark_as_dispatched(self):
        """Service method called when goods actually leave the origin warehouse."""
        if self.status != self.STATUS.PENDING:
            raise ValidationError("Only pending transfers can be dispatched.")
        
        self.dispatched_at = timezone.now()
        self.status = self.STATUS.IN_TRANSIT
        self.save()

    def clean(self):
        super().clean()
        if hasattr(self, 'from_warehouse') and hasattr(self, 'to_warehouse'):
            if self.from_warehouse == self.to_warehouse:
                raise ValidationError({'to_warehouse': 'The destination warehouse cannot be the same as the origin warehouse.'})
        
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(to_warehouse=models.F('from_warehouse')),
                name='prevent_self_transfer'
            )
        ]

class TransferItem(TenantBaseModel):
    transfer = models.ForeignKey(WarehouseTransfer, on_delete=models.CASCADE, related_name='transfer_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transfer_items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='transfer_items')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=Decimal('0.000')),
                name='transfer_item_quantity_non_negative'
            )
        ]

class StockAdjustment(TenantBaseModel):

    class REASON(models.TextChoices):
        CYCLE_COUNT = 'cycle_count', 'Cycle Count'
        DAMAGE = 'damage', 'Damage'
        THEFT = 'theft', 'Theft'
        EXPIRED = 'expired', 'Expired'
        DATA_CORRECTION = 'data_correction', 'Data Correction'
        OTHER = 'other', 'Other'

    stock = models.ForeignKey(
        Stock,
        on_delete=models.PROTECT,
        related_name='adjustments'
    )

    old_qty = models.DecimalField(max_digits=12, decimal_places=3)
    new_qty = models.DecimalField(max_digits=12, decimal_places=3)
    difference = models.DecimalField(max_digits=12, decimal_places=3)
    
    reason = models.CharField(max_length=20, choices=REASON.choices)
    notes = models.TextField(blank=True)
    adjusted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-adjusted_at']
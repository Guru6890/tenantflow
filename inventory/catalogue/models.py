#inventory/catalogue/models.py
from django.db import models
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError

from tenancy.models import TenantBaseModel
# Create your models here.

class ItemType(models.TextChoices):
    STANDARD = 'STANDARD', 'Standard Physical Goods'
    VARIANT_PARENT = 'VARIANT_PARANT', 'Parant with variants (Apparel/Size/Color)'
    SERVICE = 'SERVICE', 'Service/Digital Item (Non-Inventory)'

class TrackingType(models.TextChoices):
    BASIC = 'BASIC', 'Basic Inventory Count'
    BATCH = 'BATCH', 'Batch / Lot & Expiry Tracked (F&B, Pharma)'
    SERIAL = 'SERIAL', 'Serial Number / IMEI Tracked (Electronics)'

class Supplier(TenantBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255,)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    tax_id = models.CharField(max_length=10, blank=True, null=True, verbose_name='GST/VAT/Tax ID')
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'name'],
                condition=models.Q(is_deleted=False),
                name='unique_supplier_name_per_workspace'
            )
        ]

    def __str__(self):
        return self.name

class Category(TenantBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'name'],
                name='unique_category_name_per_workspace'
            )
        ]

    def __str__(self):
        return self.name
    
class UnitOfMeasure(TenantBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)  # Box, Kilogram, Piece
    code = models.CharField(max_length=10)   # BOX, KG, PCS

    def __str__(self):
        return f"{self.name} ({self.code})"

class Product(TenantBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.STANDARD)
    tracking_type = models.CharField(max_length=20, choices=TrackingType.choices, default=TrackingType.BASIC)

    sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    barcode = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, related_name='products')
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='products')

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    custom_data = models.JSONField(default=dict, blank=True)

    class Meta:

        ordering = ['name',]

    def delete(self, using=None, keep_parents=False):
        total_stocks = self.stocks.aggregate(total=models.Sum('physical_qty'))['total'] or 0
        if total_stocks > 0:
            raise ValidationError('Cannot delete product with active physical inventory stock.')
        super().delete(using=using, keep_parents=keep_parents)

    def __str__(self):
        return self.name
    
class ProductVariant(TenantBaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')

    sku = models.CharField(max_length=64, db_index=True)
    barcode = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    variant_name = models.CharField(max_length=255, blank=True)

    supplier_sku = models.CharField(max_length=64, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal(0.00))
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal(0.00))

    min_stock_level = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(0.000))
    max_stock_level = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'sku'],
                condition=models.Q(is_deleted=False),
                name='unique_sku_per_workspace'
            ),
            models.UniqueConstraint(
                fields=['workspace', 'barcode'],
                condition=models.Q(is_deleted=False, barcode__isnull=False),
                name='unique_barcode_per_workspace'
            ),
        ]

    def save(self, *args, **kwargs):
        if self.sku:
            self.sku = self.sku.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} ({self.variant_name})" if self.variant_name else f"{self.product.name} [{self.sku}]"

class Attribute(TenantBaseModel):
    """e.g., Color, Size, Storage Capacity, Material"""
    name = models.CharField(max_length=50) # e.g. "Color"

class AttributeValue(TenantBaseModel):
    """e.g., Red, Blue, XL, XXL, 128GB"""
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=50) # e.g. "Red"

class VariantAttributeValue(TenantBaseModel):
    """Junction model mapping variants to their specific attribute values."""
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='attribute_values')
    attribute_value = models.ForeignKey(AttributeValue, on_delete=models.CASCADE, related_name='variant_links')

class ProductSupplier(TenantBaseModel):
    """
    Junction table connecting products/variants to multiple suppliers.
    Handles vendor-specific catalog codes, lead times, and tier pricing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey('Supplier', on_delete=models.CASCADE, related_name='supplied_products')
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='supplier_links')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name='supplier_links')
    
    supplier_sku = models.CharField(max_length=64, blank=True)  # Vendor's internal part number
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    min_order_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal(1.000))
    lead_time_days = models.PositiveIntegerField(default=0)
    is_preferred = models.BooleanField(default=False)  # Primary vendor flag

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'supplier', 'product', 'variant'],
                condition=models.Q(is_deleted=False),
                name='unique_supplier_product_variant'
            )
        ]
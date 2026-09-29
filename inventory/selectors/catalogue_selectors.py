from __future__ import annotations
from typing import Optional, Union, Dict, Any
from decimal import Decimal
from uuid import UUID
from enum import Enum

from django.db.models import Q, Sum, QuerySet, F, DecimalField, Value
from django.db.models.functions import Coalesce
from django.contrib.auth.models import AbstractUser


from tenancy.models import Workspace
from authorization.services import AuthorizationService
from inventory.catalogue.models import Product, ProductVariant, ItemType, TrackingType
from inventory.services.exceptions import ProductPermissionDenied, ProductNotFound

class catalogue_permissions(str, Enum):
    PRODUCT_VIEW = 'inventory.product.view'

def list_product(
    *,
    workspace: Workspace,
    user: AbstractUser,
    category_id: Optional[Union[UUID, str]] = None,
    supplier_id: Optional[Union[UUID, str]] = None,
    item_type: Optional[str] = None,
    tracking_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    search_query: Optional[str] = None,
    include_stock_aggregates: bool = False,
) -> QuerySet[Product]:
    
    AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_VIEW)

    qs = Product.objects.filter(workspace=workspace).select_related('category', 'supplier')

    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if item_type:
        qs = qs.filter(item_type=item_type)
    if tracking_type:
        qs = qs.filter(tracking_type=tracking_type)
    if search_query:
        query = search_query.strip()
        qs = qs.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query) |
            Q(variants__sku__icontains=query) |
            Q(variants__barcode__icontains=query)
        ).distinct()
    if include_stock_aggregates:
        qs = qs.annotate(
            total_pyhsical_stock=Coalesce(
                Sum('stocks__physical_qty'),
                Decimal(0.000),
                output_field=DecimalField()
            ),
            total_allocated_stock=Coalesce(
                Sum('stocks__allocated_qty'),
                Decimal(0.000),
                output_field=DecimalField()
            )
        )
    return qs.order_by('name')

def get_product_by_id(
        *,
        workspace: Workspace,
        user: AbstractUser,
        product_id: Union[UUID, str],
        prefetch_relations: bool = True
) -> Optional[Product]:
    
    AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_VIEW)

    try:
        qs = Product.objects.filter(id=product_id)
        if prefetch_relations:
            qs = qs.select_related('category', 'supplier', 'uom').prefetch_related(
                'variants',
                "variants__attribute_values__attribute_value__attribute",
                "supplier_links__supplier",
            )
    except Product.DoesNotExist:
        raise ProductNotFound(f'Product {product_id} not found')
    return qs.first()
    
def product_exists(
    *,
    product_id: Optional[Union[UUID, str]] = None,
    sku: Optional[str] = None,
    barcode: Optional[str] = None
) -> bool:
    if not any([product_id, sku, barcode]):
        return False
    if product_id:
        q_object = Q(id=product_id)
    if sku:
        q_object = Q(sku__iexact=sku)
    if barcode:
        q_object = Q(barcode=barcode)
    return Product.objects.filter(q_object).exists()

# ==================== Variants Selectors ==================== #

def get_variant_by_id(
    *,
    workspace: Workspace,
    user: AbstractUser,
    variant_id: Union[UUID, str],
    prefetch_attributes: bool = True,
) -> Optional[ProductVariant]:
    AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_VIEW)
    try:
        qs = ProductVariant.objects.filter(id=variant_id).select_related('product', 'product__uom')
        if prefetch_attributes:
            qs = qs.prefetch_related('attribute_values__attribute_value__attribute')
    except ProductVariant.DoesNotExist:
        raise # have to fill appropriate error
    return qs.first()

def get_variant_by_sku(
    *,
    workspace: Workspace,
    user: AbstractUser,
    sku: str,
) -> Optional[ProductVariant]:
    AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_VIEW)
    try:
        qs = ProductVariant.objects.filter(sku__iexact=sku.strip()).select_related('product').first()
    except ProductVariant.DoesNotExist:
        raise
    return qs

def variant_exists(*, sku: str, exclude_id: Optional[UUID]=None) -> bool:
    try:
        qs = ProductVariant.objects.filter(sku__iexact=sku.strip())
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
    except ProductVariant.DoesNotExist:
        raise
    return qs.exists()

def list_variant_for_product(*, workspace: Workspace, user: AbstractUser, product_id: Union[UUID, str], is_active: Optional[bool]=True) -> QuerySet[ProductVariant]:
    
    AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_VIEW)

    qs = ProductVariant.objects.filter(product_id=product_id).prefetch_related('attributes_values__attribute_value__attribute')

    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs.order_by('sku')

def list_variant_by_attribute(
    *,
    workspace: Workspace,
    user: AbstractUser,
    attribute_value_ids: list[Union[UUID, str]],
    product_id: Optional[Union[UUID, str]] = None
) -> QuerySet[ProductVariant]:
    AuthorizationService.require_permission(user, workspace, catalogue_permissions.PRODUCT_VIEW)
    if product_id:
        qs = ProductVariant.objects.filter(product_id=product_id)
    for value_id in attribute_value_ids:
        queryset = qs.filter(attribute_values__attribute_value_id=value_id)

    return queryset.distinct().select_related("product")

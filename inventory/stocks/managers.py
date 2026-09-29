from django.db.models import F

from tenancy.models import TenantQuerySet, TenantManager

class StockQuerySet(TenantQuerySet):
    def with_available_qty(self):
        return self.annotate(
            _available_qty = F('physical_qty') - (F('allocated_qty') + F('reserved_qty'))
        )
    
class StockTenantManager(TenantManager.from_queryset(StockQuerySet)):
    pass
class InventoryDomainError(Exception):
    """Base exception for inventory domain errors."""
    pass

class WorkspaceMismatchError(InventoryDomainError):
    """Raised when an entity belongs to a different workspace."""
    pass

class ImmutableFieldError(InventoryDomainError):
    """Raised when attempting to modify a field locked by inventory history."""
    pass

#class ProductHasStockError(InventoryDomainError):
#    """Raised when attempting destructive operations on products with active stock/history."""
#    pass

# inventory/exceptions.py
class ProductError(Exception):
    """Base domain error."""

class ProductNotFound(ProductError):
    pass

class ProductPermissionDenied(ProductError):
    pass

class ProductValidationError(ProductError):
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)

class DuplicateSKUError(ProductValidationError):
    def __init__(self, sku: str):
        super().__init__(f"SKU '{sku}' already exists in this workspace.", field="sku")

class DuplicateBarcodeError(ProductValidationError):
    def __init__(self, barcode: str):
        super().__init__(f"Barcode '{barcode}' already exists in this workspace.", field="barcode")

class ProductHasStockError(ProductValidationError):
    def __init__(self):
        super().__init__("Cannot delete product with active physical inventory stock.")
# inventory.catelogue.exceptions.py
class ProductError(Exception):
    """Base for product domain errors."""

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
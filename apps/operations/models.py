from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import BaseModel


class Supplier(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVIEW = "review", "In Review"
        PAUSED = "paused", "Paused"

    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    lead_time_days = models.PositiveIntegerField(default=7)
    payment_terms = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["workspace", "name"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return self.name


class Customer(BaseModel):
    name = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["workspace", "name"]),
        ]

    def __str__(self):
        return self.name


class Product(BaseModel):
    sku = models.CharField(max_length=60)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=80)
    unit = models.CharField(max_length=30, default="unit")
    description = models.TextField(blank=True)
    reorder_level = models.PositiveIntegerField(default=10)
    stock_on_hand = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0, help_text="Stock reserved for sales orders")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_quality_control_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "sku"], name="uniq_product_sku_per_workspace"),
            models.CheckConstraint(check=models.Q(stock_on_hand__gte=0), name="product_stock_non_negative"),
            models.CheckConstraint(check=models.Q(reserved_quantity__gte=0), name="product_reserved_non_negative"),
        ]
        indexes = [
            models.Index(fields=["workspace", "sku"]),
            models.Index(fields=["workspace", "name"]),
            models.Index(fields=["workspace", "category"]),
            models.Index(fields=["workspace", "stock_on_hand"]),
        ]

    def __str__(self):
        return f"{self.sku} · {self.name}"

    @property
    def available_stock(self):
        """Calculate available stock after accounting for reservations."""
        return max(0, self.stock_on_hand - self.reserved_quantity)



class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        PARTIALLY_RECEIVED = "partially_received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    code = models.CharField(max_length=40)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    ordered_on = models.DateField(null=True, blank=True)
    expected_on = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "code"], name="uniq_purchase_order_code_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "code"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return self.code


class PurchaseOrderLine(BaseModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_order_lines")
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag for line items (edit mode only)")

    class Meta:
        ordering = ["purchase_order__code", "product__name"]

    def save(self, *args, **kwargs):
        self.line_total = Decimal(self.quantity_ordered) * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.purchase_order.code} · {self.product.name}"


class GoodsReceipt(BaseModel):
    class Status(models.TextChoices):
        PENDING_QC = "pending_qc", "Pending QC"
        COMPLETED = "completed", "Completed"

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="receipts")
    code = models.CharField(max_length=40)
    received_on = models.DateField()
    reference_number = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_QC)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "code"], name="uniq_goods_receipt_code_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "code"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return self.code


class GoodsReceiptLine(BaseModel):
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="receipt_lines")
    quantity_received = models.PositiveIntegerField()
    accepted_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.goods_receipt.code} · {self.product.name}"


class InventoryLot(BaseModel):
    class Status(models.TextChoices):
        PENDING_QC = "pending_qc", "Pending QC"
        AVAILABLE = "available", "Available"
        REJECTED = "rejected", "Rejected"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="lots")
    goods_receipt_line = models.OneToOneField(
        GoodsReceiptLine,
        on_delete=models.CASCADE,
        related_name="inventory_lot",
    )
    lot_code = models.CharField(max_length=40)
    quantity_received = models.PositiveIntegerField()
    quantity_available = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_QC)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "lot_code"], name="uniq_lot_code_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "lot_code"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return self.lot_code


class QualityInspection(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        PARTIAL = "partial", "Partial"
        REJECTED = "rejected", "Rejected"

    inventory_lot = models.OneToOneField(
        InventoryLot,
        on_delete=models.CASCADE,
        related_name="inspection",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    accepted_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quality_checks_completed",
    )
    inspected_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return f"{self.inventory_lot.lot_code} · {self.get_status_display()}"


class InventoryMovement(BaseModel):
    class Type(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"
        ADJUSTMENT = "adjustment", "Adjustment"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="inventory_movements")
    inventory_lot = models.ForeignKey(
        InventoryLot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_movements",
    )
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    quantity = models.IntegerField()
    reference_code = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "movement_type"]),
            models.Index(fields=["workspace", "reference_code"]),
        ]

    def __str__(self):
        return f"{self.product.name} · {self.movement_type}"


class SalesOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        AWAITING_STOCK = "awaiting_stock", "Awaiting Stock"
        READY_FOR_DISPATCH = "ready_for_dispatch", "Ready for Dispatch"
        DISPATCHED = "dispatched", "Dispatched"
        COMPLETED = "completed", "Completed"

    code = models.CharField(max_length=40)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    ordered_on = models.DateField(null=True, blank=True)
    promised_on = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "code"], name="uniq_sales_order_code_per_workspace"),
        ]
        indexes = [
            models.Index(fields=["workspace", "code"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self):
        return self.code


class SalesOrderLine(BaseModel):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sales_order_lines")
    quantity_ordered = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag for line items (edit mode only)")

    class Meta:
        ordering = ["sales_order__code", "product__name"]

    def save(self, *args, **kwargs):
        self.line_total = Decimal(self.quantity_ordered) * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sales_order.code} · {self.product.name}"


class Shipment(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_TRANSIT = "in_transit", "In Transit"
        DELIVERED = "delivered", "Delivered"

    sales_order = models.OneToOneField(SalesOrder, on_delete=models.CASCADE, related_name="shipment")
    shipment_code = models.CharField(max_length=40)
    carrier = models.CharField(max_length=120)
    tracking_number = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "shipment_code"], name="uniq_shipment_code_per_workspace"),
        ]

    def __str__(self):
        return self.shipment_code


class Invoice(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    sales_order = models.OneToOneField(SalesOrder, on_delete=models.CASCADE, related_name="invoice")
    invoice_number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issued_at = models.DateField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "invoice_number"], name="uniq_invoice_number_per_workspace"),
        ]

    def __str__(self):
        return self.invoice_number


class ActivityEvent(BaseModel):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_events",
    )
    event_type = models.CharField(max_length=80)
    message = models.CharField(max_length=255)
    target_model = models.CharField(max_length=80, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    link = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "event_type"]),
            models.Index(fields=["workspace", "created_at"]),
        ]

    def __str__(self):
        return self.message


class StockReservation(BaseModel):
    """Track stock reservations for sales orders to prevent overselling."""
    sales_order = models.OneToOneField(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="stock_reservation",
        help_text="Sales order this reservation is for",
    )
    reserved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "sales_order"]),
        ]

    def __str__(self):
        return f"Reservation for {self.sales_order.code}"


class StockReservationLine(BaseModel):
    """Individual reserved quantities per product."""
    reservation = models.ForeignKey(
        StockReservation,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_reserved = models.PositiveIntegerField()

    class Meta:
        ordering = ["product__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["reservation", "product"],
                name="uniq_reserv_product_per_order"
            ),
        ]

    def __str__(self):
        return f"{self.product.sku} - {self.quantity_reserved} reserved"


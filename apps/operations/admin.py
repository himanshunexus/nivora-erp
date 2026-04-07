from django.contrib import admin

from apps.operations.models import (
    ActivityEvent,
    Customer,
    GoodsReceipt,
    InventoryLot,
    InventoryMovement,
    Invoice,
    Product,
    PurchaseOrder,
    QualityInspection,
    SalesOrder,
    Shipment,
    Supplier,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "lead_time_days", "email", "phone")
    search_fields = ("name", "email", "phone")
    list_filter = ("status",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "email", "phone")
    search_fields = ("name", "company", "email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "stock_on_hand", "reorder_level", "unit_price")
    search_fields = ("sku", "name", "category")
    list_filter = ("category", "is_quality_control_required")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("code", "supplier", "status", "ordered_on", "expected_on", "total_amount")
    search_fields = ("code", "supplier__name")
    list_filter = ("status",)


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("code", "purchase_order", "received_on", "status")
    search_fields = ("code", "purchase_order__code")
    list_filter = ("status",)


@admin.register(InventoryLot)
class InventoryLotAdmin(admin.ModelAdmin):
    list_display = ("lot_code", "product", "quantity_received", "quantity_available", "status")
    search_fields = ("lot_code", "product__name", "product__sku")
    list_filter = ("status",)


@admin.register(QualityInspection)
class QualityInspectionAdmin(admin.ModelAdmin):
    list_display = ("inventory_lot", "status", "accepted_quantity", "rejected_quantity", "inspected_at")
    list_filter = ("status",)
    search_fields = ("inventory_lot__lot_code", "inventory_lot__product__name")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("product", "movement_type", "quantity", "reference_code", "created_at")
    list_filter = ("movement_type",)
    search_fields = ("product__name", "reference_code")


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("code", "customer", "status", "ordered_on", "promised_on", "total_amount")
    search_fields = ("code", "customer__name")
    list_filter = ("status",)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("shipment_code", "sales_order", "carrier", "tracking_number", "status")
    list_filter = ("status",)
    search_fields = ("shipment_code", "sales_order__code", "tracking_number")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "sales_order", "status", "issued_at", "total_amount")
    list_filter = ("status",)
    search_fields = ("invoice_number", "sales_order__code")


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ("message", "event_type", "actor", "created_at")
    search_fields = ("message", "event_type")

# Register your models here.

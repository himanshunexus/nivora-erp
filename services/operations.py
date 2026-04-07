from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Sum, Q
from django.urls import reverse
from django.utils import timezone

from apps.operations.models import (
    ActivityEvent,
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryLot,
    InventoryMovement,
    Invoice,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    QualityInspection,
    SalesOrder,
    SalesOrderLine,
    Shipment,
    StockReservation,
    StockReservationLine,
)
from core.permissions import ROLE_ADMIN, ROLE_OPERATOR
from services.notifications import notify_roles


class OperationsServiceError(Exception):
    pass


def _next_code(prefix, model, workspace, field_name="code"):
    today_key = timezone.now().strftime("%Y%m")
    prefix_value = f"{prefix}-{today_key}"
    latest = (
        model.objects.filter(workspace=workspace, **{f"{field_name}__startswith": prefix_value})
        .order_by(f"-{field_name}")
        .first()
    )
    sequence = 1
    if latest:
        value = getattr(latest, field_name)
        try:
            sequence = int(value.split("-")[-1]) + 1
        except (TypeError, ValueError):
            sequence = 1
    return f"{prefix_value}-{sequence:04d}"


def log_activity(*, workspace, actor, event_type, message, link="", target_model="", target_id=None, metadata=None):
    activity = ActivityEvent(
        workspace=workspace,
        actor=actor,
        event_type=event_type,
        message=message,
        link=link,
        target_model=target_model,
        target_id=target_id,
        metadata=metadata or {},
    )
    activity.stamp(user=actor, workspace=workspace)
    activity.save()
    return activity


@transaction.atomic
def create_purchase_order(*, workspace, actor, supplier, expected_on, notes, line_items):
    if not line_items:
        raise OperationsServiceError("At least one purchase order line is required.")

    purchase_order = PurchaseOrder(
        workspace=workspace,
        supplier=supplier,
        code=_next_code("PO", PurchaseOrder, workspace),
        ordered_on=timezone.now().date(),
        expected_on=expected_on,
        status=PurchaseOrder.Status.SUBMITTED,
        notes=notes,
    )
    purchase_order.stamp(user=actor, workspace=workspace)
    purchase_order.save()

    subtotal = Decimal("0.00")
    for item in line_items:
        product = item["product"]
        quantity = int(item["quantity_ordered"])
        unit_cost = Decimal(item["unit_cost"])
        if quantity <= 0:
            continue
        line = PurchaseOrderLine(
            workspace=workspace,
            purchase_order=purchase_order,
            product=product,
            quantity_ordered=quantity,
            unit_cost=unit_cost,
        )
        line.stamp(user=actor, workspace=workspace)
        line.save()
        subtotal += line.line_total

    purchase_order.subtotal = subtotal
    purchase_order.total_amount = subtotal
    purchase_order.save(update_fields=["subtotal", "total_amount", "updated_at"])

    detail_link = reverse("operations:purchase_order_detail", args=[purchase_order.pk])
    log_activity(
        workspace=workspace,
        actor=actor,
        event_type="purchase_order.created",
        message=f"{purchase_order.code} created for {supplier.name}.",
        link=detail_link,
        target_model="PurchaseOrder",
        target_id=purchase_order.pk,
    )
    notify_roles(
        workspace=workspace,
        roles=[ROLE_ADMIN, ROLE_OPERATOR],
        title="Purchase order created",
        message=f"{purchase_order.code} is ready for receiving.",
        link=detail_link,
        actor=actor,
    )
    return purchase_order


@transaction.atomic
def receive_purchase_order(*, workspace, actor, purchase_order, received_on, reference_number, lines):
    if purchase_order.status == PurchaseOrder.Status.CANCELLED:
        raise OperationsServiceError("Cancelled purchase orders cannot be received.")

    goods_receipt = GoodsReceipt(
        workspace=workspace,
        purchase_order=purchase_order,
        code=_next_code("GRN", GoodsReceipt, workspace),
        received_on=received_on,
        reference_number=reference_number,
        status=GoodsReceipt.Status.PENDING_QC,
    )
    goods_receipt.stamp(user=actor, workspace=workspace)
    goods_receipt.save()

    for item in lines:
        purchase_order_line = item["purchase_order_line"]
        quantity_received = int(item["quantity_received"])
        if quantity_received <= 0:
            continue

        remaining = purchase_order_line.quantity_ordered - purchase_order_line.quantity_received
        if quantity_received > remaining:
            raise OperationsServiceError(
                f"Received quantity for {purchase_order_line.product.name} exceeds the remaining open quantity."
            )

        receipt_line = GoodsReceiptLine(
            workspace=workspace,
            goods_receipt=goods_receipt,
            purchase_order_line=purchase_order_line,
            product=purchase_order_line.product,
            quantity_received=quantity_received,
            unit_cost=purchase_order_line.unit_cost,
        )
        receipt_line.stamp(user=actor, workspace=workspace)
        receipt_line.save()

        purchase_order_line.quantity_received += quantity_received
        purchase_order_line.save(update_fields=["quantity_received", "updated_at"])

        lot = InventoryLot(
            workspace=workspace,
            product=purchase_order_line.product,
            goods_receipt_line=receipt_line,
            lot_code=_next_code("LOT", InventoryLot, workspace, field_name="lot_code"),
            quantity_received=quantity_received,
            quantity_available=0,
            status=InventoryLot.Status.PENDING_QC,
        )
        lot.stamp(user=actor, workspace=workspace)
        lot.save()

        inspection = QualityInspection(
            workspace=workspace,
            inventory_lot=lot,
            status=QualityInspection.Status.PENDING,
        )
        inspection.stamp(user=actor, workspace=workspace)
        inspection.save()

    total_ordered = purchase_order.lines.aggregate(total=Sum("quantity_ordered"))["total"] or 0
    total_received = purchase_order.lines.aggregate(total=Sum("quantity_received"))["total"] or 0
    purchase_order.status = (
        PurchaseOrder.Status.RECEIVED if total_received >= total_ordered else PurchaseOrder.Status.PARTIALLY_RECEIVED
    )
    purchase_order.save(update_fields=["status", "updated_at"])

    detail_link = reverse("operations:purchase_order_detail", args=[purchase_order.pk])
    log_activity(
        workspace=workspace,
        actor=actor,
        event_type="goods_receipt.created",
        message=f"{goods_receipt.code} recorded against {purchase_order.code}.",
        link=detail_link,
        target_model="GoodsReceipt",
        target_id=goods_receipt.pk,
    )
    notify_roles(
        workspace=workspace,
        roles=[ROLE_ADMIN, ROLE_OPERATOR],
        title="Goods receipt pending QC",
        message=f"{goods_receipt.code} is waiting for inspection.",
        link=detail_link,
        actor=actor,
    )
    return goods_receipt


def _calculate_avco_cost(product, incoming_qty, incoming_cost):
    """
    Calculate Weighted Average Cost (AVCO).
    Formula: new_avg_cost = ((old_qty * old_cost) + (incoming_qty * incoming_cost)) / (old_qty + incoming_qty)
    """
    if not product or incoming_qty <= 0:
        return product.cost_price if product else Decimal("0.00")

    old_qty = product.stock_on_hand
    old_cost = product.cost_price

    total_value = (Decimal(old_qty) * old_cost) + (Decimal(incoming_qty) * incoming_cost)
    total_qty = Decimal(old_qty + incoming_qty)

    if total_qty == 0:
        return old_cost

    new_cost = (total_value / total_qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return new_cost


@transaction.atomic
def decide_quality(*, workspace, actor, inspection, accepted_quantity, rejected_quantity, notes):
    """
    Approve quality inspection with AVCO cost calculation.
    Ensures: accepted + rejected == received
    """
    lot = inspection.inventory_lot
    total = accepted_quantity + rejected_quantity
    if total != lot.quantity_received:
        raise OperationsServiceError("Accepted and rejected quantity must equal the received quantity.")

    inspection.accepted_quantity = accepted_quantity
    inspection.rejected_quantity = rejected_quantity
    inspection.notes = notes
    inspection.inspected_by = actor
    inspection.inspected_at = timezone.now()

    if accepted_quantity == 0:
        inspection.status = QualityInspection.Status.REJECTED
        lot.status = InventoryLot.Status.REJECTED
        lot.quantity_available = 0
    elif rejected_quantity == 0:
        inspection.status = QualityInspection.Status.APPROVED
        lot.status = InventoryLot.Status.AVAILABLE
        lot.quantity_available = accepted_quantity
    else:
        inspection.status = QualityInspection.Status.PARTIAL
        lot.status = InventoryLot.Status.AVAILABLE
        lot.quantity_available = accepted_quantity

    inspection.save(
        update_fields=[
            "accepted_quantity",
            "rejected_quantity",
            "notes",
            "inspected_by",
            "inspected_at",
            "status",
            "updated_at",
        ]
    )
    lot.save(update_fields=["quantity_available", "status", "updated_at"])

    receipt_line = lot.goods_receipt_line
    receipt_line.accepted_quantity = accepted_quantity
    receipt_line.rejected_quantity = rejected_quantity
    receipt_line.save(update_fields=["accepted_quantity", "rejected_quantity", "updated_at"])

    # AVCO: Calculate weighted average cost and update stock atomically
    if accepted_quantity > 0:
        product = lot.product

        # Lock product row to prevent race condition
        product = Product.objects.select_for_update().get(pk=product.pk)

        # Calculate new average cost based on AVCO formula
        new_cost = _calculate_avco_cost(product, accepted_quantity, receipt_line.unit_cost)

        # Update stock and cost atomically
        product.stock_on_hand += accepted_quantity
        product.cost_price = new_cost
        product.save(update_fields=["stock_on_hand", "cost_price", "updated_at"])

        movement = InventoryMovement(
            workspace=workspace,
            product=product,
            inventory_lot=lot,
            movement_type=InventoryMovement.Type.INBOUND,
            quantity=accepted_quantity,
            reference_code=receipt_line.goods_receipt.code,
            notes=f"QC released {accepted_quantity} units @ cost {new_cost}.",
        )
        movement.stamp(user=actor, workspace=workspace)
        movement.save()

    goods_receipt = receipt_line.goods_receipt
    pending = QualityInspection.objects.filter(
        workspace=workspace,
        inventory_lot__goods_receipt_line__goods_receipt=goods_receipt,
        status=QualityInspection.Status.PENDING,
    ).exists()
    goods_receipt.status = GoodsReceipt.Status.PENDING_QC if pending else GoodsReceipt.Status.COMPLETED
    goods_receipt.save(update_fields=["status", "updated_at"])

    detail_link = reverse("operations:purchase_order_detail", args=[goods_receipt.purchase_order_id])
    log_activity(
        workspace=workspace,
        actor=actor,
        event_type="quality.completed",
        message=f"{lot.lot_code} inspection completed with status {inspection.get_status_display().lower()}.",
        link=detail_link,
        target_model="QualityInspection",
        target_id=inspection.pk,
    )
    return inspection


@transaction.atomic
def create_sales_order(*, workspace, actor, customer, promised_on, notes, line_items):
    """
    Create sales order with stock reservation.
    Prevents overselling between order creation and dispatch.
    """
    if not line_items:
        raise OperationsServiceError("At least one sales order line is required.")

    sales_order = SalesOrder(
        workspace=workspace,
        customer=customer,
        code=_next_code("SO", SalesOrder, workspace),
        ordered_on=timezone.now().date(),
        promised_on=promised_on,
        notes=notes,
        status=SalesOrder.Status.CONFIRMED,
    )
    sales_order.stamp(user=actor, workspace=workspace)
    sales_order.save()

    subtotal = Decimal("0.00")
    ready_for_dispatch = True
    reservation_lines = []

    for item in line_items:
        product = item["product"]
        quantity = int(item["quantity_ordered"])
        unit_price = Decimal(item["unit_price"])
        if quantity <= 0:
            continue

        line = SalesOrderLine(
            workspace=workspace,
            sales_order=sales_order,
            product=product,
            quantity_ordered=quantity,
            unit_price=unit_price,
        )
        line.stamp(user=actor, workspace=workspace)
        line.save()
        subtotal += line.line_total

        # Check if stock is available after accounting for existing reservations
        if product.available_stock < quantity:
            ready_for_dispatch = False

        reservation_lines.append({
            "product": product,
            "quantity": quantity
        })

    sales_order.subtotal = subtotal
    sales_order.total_amount = subtotal
    sales_order.status = (
        SalesOrder.Status.READY_FOR_DISPATCH if ready_for_dispatch else SalesOrder.Status.AWAITING_STOCK
    )
    sales_order.save(update_fields=["subtotal", "total_amount", "status", "updated_at"])

    # Create stock reservation atomically
    reservation = StockReservation(
        workspace=workspace,
        sales_order=sales_order,
    )
    reservation.stamp(user=actor, workspace=workspace)
    reservation.save()

    for res_line in reservation_lines:
        product = res_line["product"]
        quantity = res_line["quantity"]

        # Lock product row and update reserved quantity
        product = Product.objects.select_for_update().get(pk=product.pk)
        product.reserved_quantity = F("reserved_quantity") + quantity
        product.save(update_fields=["reserved_quantity", "updated_at"])

        StockReservationLine.objects.create(
            workspace=workspace,
            reservation=reservation,
            product=product,
            quantity_reserved=quantity,
        )

    detail_link = reverse("operations:sales_order_detail", args=[sales_order.pk])
    log_activity(
        workspace=workspace,
        actor=actor,
        event_type="sales_order.created",
        message=f"{sales_order.code} created for {customer.name} with stock reservation.",
        link=detail_link,
        target_model="SalesOrder",
        target_id=sales_order.pk,
    )
    return sales_order


@transaction.atomic
def dispatch_sales_order(*, workspace, actor, sales_order, carrier, tracking_number, notes):
    """
    Dispatch sales order with row-level locking to prevent race conditions.
    Uses select_for_update() to lock stock rows before decrement.
    """
    if sales_order.status == SalesOrder.Status.DISPATCHED:
        raise OperationsServiceError("This order has already been dispatched.")

    lines = list(sales_order.lines.select_related("product"))

    # CRITICAL: Lock all product rows first, re-check stock after locking
    product_ids = [line.product.pk for line in lines]
    products_locked = {
        p.pk: p for p in Product.objects.select_for_update().filter(
            pk__in=product_ids,
            workspace=workspace
        )
    }

    # Re-validate stock after locking (prevents lost updates)
    for line in lines:
        product = products_locked.get(line.product.pk)
        if not product:
            raise OperationsServiceError(f"Product {line.product.name} not found.")

        if product.available_stock < line.quantity_ordered:
            raise OperationsServiceError(
                f"Insufficient stock for {product.name}. Required: {line.quantity_ordered}, "
                f"Available: {product.available_stock}"
            )

    # Decrement stock and update reservations atomically
    for line in lines:
        product = products_locked[line.product.pk]

        # Decrement actual stock
        product.stock_on_hand -= line.quantity_ordered

        # Release reservation
        product.reserved_quantity = F("reserved_quantity") - line.quantity_ordered

        # Ensure DB constraints prevent negative stock
        if product.stock_on_hand < 0:
            raise OperationsServiceError(
                f"Fatal: Stock would go negative for {product.name}. "
                f"This should not happen with proper locking."
            )

        product.save(update_fields=["stock_on_hand", "reserved_quantity", "updated_at"])

        movement = InventoryMovement(
            workspace=workspace,
            product=product,
            movement_type=InventoryMovement.Type.OUTBOUND,
            quantity=line.quantity_ordered,
            reference_code=sales_order.code,
            notes=f"Dispatched {line.quantity_ordered} units against {sales_order.code}.",
        )
        movement.stamp(user=actor, workspace=workspace)
        movement.save()

    # Release stock reservation
    try:
        stock_reservation = sales_order.stock_reservation
        stock_reservation.is_active = False
        stock_reservation.save(update_fields=["is_active", "updated_at"])
    except StockReservation.DoesNotExist:
        pass  # No reservation found (legacy orders)

    # Create/update shipment
    shipment, created = Shipment.objects.get_or_create(
        workspace=workspace,
        sales_order=sales_order,
        defaults={
            "shipment_code": _next_code("SHP", Shipment, workspace, field_name="shipment_code"),
            "carrier": carrier,
            "tracking_number": tracking_number,
            "status": Shipment.Status.IN_TRANSIT,
            "dispatched_at": timezone.now(),
            "notes": notes,
        }
    )
    if not created:
        shipment.carrier = carrier
        shipment.tracking_number = tracking_number
        shipment.status = Shipment.Status.IN_TRANSIT
        shipment.dispatched_at = timezone.now()
        shipment.notes = notes
        shipment.save(update_fields=["carrier", "tracking_number", "status", "dispatched_at", "notes", "updated_at"])

    sales_order.status = SalesOrder.Status.DISPATCHED
    sales_order.save(update_fields=["status", "updated_at"])

    detail_link = reverse("operations:sales_order_detail", args=[sales_order.pk])
    log_activity(
        workspace=workspace,
        actor=actor,
        event_type="sales_order.dispatched",
        message=f"{sales_order.code} dispatched via {carrier}.",
        link=detail_link,
        target_model="SalesOrder",
        target_id=sales_order.pk,
    )
    notify_roles(
        workspace=workspace,
        roles=[ROLE_ADMIN, ROLE_OPERATOR],
        title="Order dispatched",
        message=f"{sales_order.code} is on the way.",
        link=detail_link,
        actor=actor,
    )
    return shipment


# API payloads (existing functions remain unchanged)
def api_product_payload(product):
    return {
        "id": product.pk,
        "sku": product.sku,
        "name": product.name,
        "category": product.category,
        "reorder_level": product.reorder_level,
        "stock_on_hand": product.stock_on_hand,
        "reserved_quantity": product.reserved_quantity,
        "available_stock": product.available_stock,
        "cost_price": str(product.cost_price),
        "unit_price": str(product.unit_price),
    }


def api_purchase_order_payload(purchase_order):
    return {
        "id": purchase_order.pk,
        "code": purchase_order.code,
        "supplier_id": purchase_order.supplier_id,
        "supplier_name": purchase_order.supplier.name,
        "status": purchase_order.status,
        "ordered_on": purchase_order.ordered_on.isoformat() if purchase_order.ordered_on else None,
        "expected_on": purchase_order.expected_on.isoformat() if purchase_order.expected_on else None,
        "subtotal": str(purchase_order.subtotal),
        "total_amount": str(purchase_order.total_amount),
    }


def api_sales_order_payload(sales_order):
    return {
        "id": sales_order.pk,
        "code": sales_order.code,
        "customer_id": sales_order.customer_id,
        "customer_name": sales_order.customer.name,
        "status": sales_order.status,
        "ordered_on": sales_order.ordered_on.isoformat() if sales_order.ordered_on else None,
        "promised_on": sales_order.promised_on.isoformat() if sales_order.promised_on else None,
        "subtotal": str(sales_order.subtotal),
        "total_amount": str(sales_order.total_amount),
    }

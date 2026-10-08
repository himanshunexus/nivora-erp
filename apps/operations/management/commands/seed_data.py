import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Workspace, WorkspaceMembership
from apps.notifications.models import Notification
from apps.operations.models import (
    ActivityEvent,
    Customer,
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
    Supplier,
)

User = get_user_model()
SEED_FILE = Path(__file__).resolve().parents[4] / "data" / "seed_data.json"
SEED_EMAIL = "admin@acme.example"


class Command(BaseCommand):
    help = "Create the durable demo workspace and realistic operational data once."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run without an interactive prompt.")

    @transaction.atomic
    def handle(self, *args, **options):
        if Workspace.objects.filter(slug="acme-operations").exists():
            self.stdout.write("Seed workspace already exists; leaving existing data untouched.")
            return

        with SEED_FILE.open(encoding="utf-8") as seed_file:
            seed = json.load(seed_file)

        now = timezone.now()
        today = now.date()
        user, _ = User.objects.get_or_create(
            email=SEED_EMAIL,
            defaults={
                "full_name": "Avery Morgan",
                "job_title": "Operations Administrator",
                "avatar_url": "https://i.pravatar.cc/160?img=12",
                "is_staff": True,
                "is_active": True,
            },
        )
        user.set_password("ChangeMe-2026!")
        user.save(update_fields=["password", "full_name", "job_title", "is_staff", "is_active"])

        workspace = Workspace.objects.create(
            **seed["workspace"],
            created_by=user,
            updated_by=user,
        )
        user.default_workspace = workspace
        user.save(update_fields=["default_workspace"])
        WorkspaceMembership.objects.create(
            workspace=workspace, user=user, role="owner", title="Operations Administrator", is_default=True
        )

        operators = []
        for index in range(1, 6):
            operator, _ = User.objects.get_or_create(
                email=f"operator{index}@acme.example",
                defaults={
                    "full_name": f"Operations Specialist {index}",
                    "job_title": "Warehouse Operator",
                    "avatar_url": f"https://i.pravatar.cc/160?img={20 + index}",
                },
            )
            operator.set_password("ChangeMe-2026!")
            operator.default_workspace = workspace
            operator.save(update_fields=["password", "default_workspace"])
            WorkspaceMembership.objects.create(
                workspace=workspace, user=operator, role="operator", title="Warehouse Operator"
            )
            operators.append(operator)

        stamp = {"workspace": workspace, "created_by": user, "updated_by": user}
        suppliers = [
            Supplier.objects.create(
                name=name,
                email=f"vendor{index:02d}@suppliers.example",
                phone=f"+1 555 010 {index:04d}",
                lead_time_days=4 + index % 14,
                payment_terms=["Net 15", "Net 30", "Net 45"][index % 3],
                status=["active", "active", "review", "paused"][index % 4],
                **stamp,
            )
            for index, name in enumerate(seed["suppliers"], 1)
        ]
        customers = [
            Customer.objects.create(
                name=name,
                company=name,
                email=f"buyer{index:02d}@customers.example",
                phone=f"+1 555 020 {index:04d}",
                billing_address=f"{100 + index} Market Street, Portland, OR",
                shipping_address=f"{100 + index} Distribution Way, Portland, OR",
                **stamp,
            )
            for index, name in enumerate(seed["customers"], 1)
        ]
        products = []
        for index, definition in enumerate(seed["products"], 1):
            products.append(
                Product.objects.create(
                    **definition,
                    description=f"Production-ready {definition['name'].lower()} for the Acme operations catalog.",
                    reorder_level=10 + index % 20,
                    stock_on_hand=35 + (index * 17) % 240,
                    reserved_quantity=index % 7,
                    cost_price=Decimal(str(8 + (index * 13) % 92)),
                    unit_price=Decimal(str(18 + (index * 29) % 260)),
                    is_quality_control_required=index % 5 != 0,
                    **stamp,
                )
            )

        purchase_orders = []
        sales_orders = []
        for index in range(1, 31):
            supplier = suppliers[(index - 1) % len(suppliers)]
            product = products[(index * 3) % len(products)]
            ordered_on = today - timedelta(days=45 - index)
            status = ["received", "received", "partially_received", "submitted", "draft"][index % 5]
            quantity = 20 + (index * 7) % 90
            unit_cost = product.cost_price
            total = unit_cost * quantity
            purchase_order = PurchaseOrder.objects.create(
                code=f"PO-2026-{index:03d}",
                supplier=supplier,
                status=status,
                ordered_on=ordered_on,
                expected_on=ordered_on + timedelta(days=supplier.lead_time_days),
                subtotal=total,
                total_amount=total,
                notes="Seeded planning order" if index % 4 == 0 else "",
                **stamp,
            )
            received = quantity if status == "received" else quantity // 2 if status == "partially_received" else 0
            po_line = PurchaseOrderLine.objects.create(
                purchase_order=purchase_order,
                product=product,
                quantity_ordered=quantity,
                quantity_received=received,
                unit_cost=unit_cost,
                **stamp,
            )
            purchase_orders.append((purchase_order, po_line, received))

            customer = customers[(index * 5) % len(customers)]
            sales_product = products[(index * 7) % len(products)]
            sales_quantity = 2 + index % 8
            sales_total = sales_product.unit_price * sales_quantity
            sales_status = ["completed", "dispatched", "ready_for_dispatch", "confirmed", "awaiting_stock"][index % 5]
            sales_order = SalesOrder.objects.create(
                code=f"SO-2026-{index:03d}",
                customer=customer,
                status=sales_status,
                ordered_on=today - timedelta(days=index % 21),
                promised_on=today + timedelta(days=index % 14),
                subtotal=sales_total,
                total_amount=sales_total,
                **stamp,
            )
            SalesOrderLine.objects.create(
                sales_order=sales_order,
                product=sales_product,
                quantity_ordered=sales_quantity,
                unit_price=sales_product.unit_price,
                **stamp,
            )
            sales_orders.append((sales_order, sales_product, sales_quantity, sales_total))

        for index, (purchase_order, po_line, received) in enumerate(purchase_orders, 1):
            if not received:
                continue
            receipt = GoodsReceipt.objects.create(
                code=f"GR-2026-{index:03d}",
                purchase_order=purchase_order,
                received_on=purchase_order.ordered_on + timedelta(days=7),
                reference_number=f"ASN-ACME-{index:05d}",
                status="completed" if index % 4 else "pending_qc",
                **stamp,
            )
            receipt_line = GoodsReceiptLine.objects.create(
                goods_receipt=receipt,
                purchase_order_line=po_line,
                product=po_line.product,
                quantity_received=received,
                accepted_quantity=received if index % 4 else received // 2,
                rejected_quantity=0 if index % 4 else received - received // 2,
                unit_cost=po_line.unit_cost,
                **stamp,
            )
            lot_status = "available" if index % 4 else "pending_qc"
            lot = InventoryLot.objects.create(
                product=po_line.product,
                goods_receipt_line=receipt_line,
                lot_code=f"LOT-2026-{index:03d}",
                quantity_received=received,
                quantity_available=received if lot_status == "available" else received // 2,
                status=lot_status,
                **stamp,
            )
            inspection_status = "approved" if index % 4 else "pending"
            QualityInspection.objects.create(
                inventory_lot=lot,
                status=inspection_status,
                accepted_quantity=received if inspection_status == "approved" else received // 2,
                rejected_quantity=0 if inspection_status == "approved" else received - received // 2,
                inspected_by=user if inspection_status == "approved" else None,
                inspected_at=now - timedelta(days=index) if inspection_status == "approved" else None,
                notes="Sampling inspection completed." if inspection_status == "approved" else "Awaiting warehouse review.",
                **stamp,
            )
            InventoryMovement.objects.create(
                product=po_line.product,
                inventory_lot=lot,
                movement_type="inbound",
                quantity=received,
                reference_code=lot.lot_code,
                **stamp,
            )

        for index, (sales_order, product, quantity, total) in enumerate(sales_orders, 1):
            if sales_order.status not in {"dispatched", "completed"}:
                continue
            Shipment.objects.create(
                sales_order=sales_order,
                shipment_code=f"SH-2026-{index:03d}",
                carrier=["FedEx", "UPS", "DHL", "USPS"][index % 4],
                tracking_number=f"ACME{index:018d}",
                status="delivered" if sales_order.status == "completed" else "in_transit",
                dispatched_at=now - timedelta(days=index % 12),
                **stamp,
            )
            Invoice.objects.create(
                sales_order=sales_order,
                invoice_number=f"INV-2026-{index:03d}",
                status="paid" if sales_order.status == "completed" else "issued",
                issued_at=today - timedelta(days=index % 12),
                due_on=today + timedelta(days=30 - index % 10),
                total_amount=total,
                **stamp,
            )
            InventoryMovement.objects.create(
                product=product,
                movement_type="outbound",
                quantity=-quantity,
                reference_code=sales_order.code,
                **stamp,
            )

        for index, (sales_order, product, quantity, _,) in enumerate(sales_orders, 1):
            if sales_order.status in {"confirmed", "ready_for_dispatch", "awaiting_stock"}:
                reservation = StockReservation.objects.create(sales_order=sales_order, **stamp)
                StockReservationLine.objects.create(
                    reservation=reservation,
                    product=product,
                    quantity_reserved=quantity,
                    **stamp,
                )

        for index in range(1, 41):
            actor = operators[index % len(operators)]
            Notification.objects.create(
                recipient=actor,
                title=["Receipt ready for QC", "Low stock review", "Dispatch update", "New purchase order"][index % 4],
                message=f"Workflow update {index}: review the latest operational activity in Acme Operations.",
                level=["info", "success", "warning", "info"][index % 4],
                category=["receiving", "inventory", "fulfillment", "procurement"][index % 4],
                is_read=index % 5 == 0,
                **stamp,
            )
            ActivityEvent.objects.create(
                actor=actor,
                event_type=["purchase_order.created", "receipt.logged", "quality.updated", "shipment.dispatched"][index % 4],
                message=f"{actor.full_name} completed workflow event {index}.",
                target_model="PurchaseOrder" if index % 2 else "SalesOrder",
                target_id=(index % 30) + 1,
                metadata={"seeded": True, "sequence": index},
                **stamp,
            )

        self.stdout.write(self.style.SUCCESS("Seeded 30 suppliers, 30 customers, 30 products, 30 purchase orders, 30 sales orders, and related workflow records."))

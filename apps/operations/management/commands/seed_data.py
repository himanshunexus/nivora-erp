import random
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.conf import settings

from apps.accounts.models import Workspace, WorkspaceMembership
from apps.operations.models import (
    Supplier, Customer, Product, PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine, InventoryLot, QualityInspection,
    InventoryMovement, SalesOrder, SalesOrderLine, Shipment, Invoice, ActivityEvent
)
from apps.notifications.models import Notification

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed logical data into the system (Development only)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force seed data generation without confirmation (DEVELOPMENT ONLY)',
        )

    def handle(self, *args, **kwargs):
        # Safety check: only allow in DEBUG mode
        if not settings.DEBUG:
            raise CommandError(
                "❌ seed_data command is only available in DEBUG mode. "
                "This command is for development/testing only."
            )

        force = kwargs.get('force', False)
        if not force:
            confirm = input(
                "⚠️  This command will create test data. Continue? (yes/no): "
            )
            if confirm.lower() != 'yes':
                self.stdout.write("Cancelled.")
                return

        self.stdout.write("Starting data generation...")
        
        # 1. Accounts
        user, _ = User.objects.get_or_create(email="admin@acme.corp", defaults={
            "full_name": "Admin Operator", "is_superuser": True, "is_staff": True
        })
        user.set_password("admin123")
        user.save()

        workspace, _ = Workspace.objects.get_or_create(
            slug="acme-corp", 
            defaults={"name": "Acme Corp", "created_by": user, "updated_by": user}
        )
        
        user.default_workspace = workspace
        user.save()

        WorkspaceMembership.objects.get_or_create(
            user=user, workspace=workspace, defaults={"role": "owner", "is_default": True}
        )
        
        for i in range(1, 4):
            u, _ = User.objects.get_or_create(email=f"operator{i}@acme.corp", defaults={"full_name": f"Operator {i}"})
            u.set_password("operator123")
            u.save()
            WorkspaceMembership.objects.get_or_create(user=u, workspace=workspace, defaults={"role": "operator"})

        def stamp():
            return {"workspace": workspace, "created_by": user, "updated_by": user}

        self.stdout.write("Created Workspace & Users.")

        # 2. Suppliers
        suppliers = []
        for name in ["Global Supplies Inc", "TechParts Co", "MetalWorks Ltd", "Prime Plastics"]:
            sup, _ = Supplier.objects.get_or_create(name=name, defaults=stamp())
            suppliers.append(sup)
            
        # 3. Customers
        customers = []
        for name in ["Apex Innovations", "Beta Distributions", "Gamma Retails", "Delta Machines"]:
            cust, _ = Customer.objects.get_or_create(name=name, defaults=stamp())
            customers.append(cust)

        self.stdout.write("Created Suppliers & Customers.")

        # 4. Products
        products = []
        product_names = [
            ("Raw Aluminum", "RAW-001", "Raw Materials"),
            ("Steel Bolts", "HW-012", "Hardware"),
            ("Circuit Board RevA", "PCB-001", "Electronics"),
            ("Plastic Housing", "PL-050", "Casing"),
            ("Finished Device A", "FG-001", "Finished Goods"),
            ("Finished Device B", "FG-002", "Finished Goods"),
        ]
        
        for name, sku, cat in product_names:
            p, _ = Product.objects.get_or_create(
                workspace=workspace,
                sku=sku,
                defaults={
                    "name": name,
                    "category": cat,
                    "cost_price": Decimal(random.randint(5, 50)),
                    "unit_price": Decimal(random.randint(60, 200)),
                    "stock_on_hand": random.randint(50, 200),
                    "created_by": user,
                    "updated_by": user
                }
            )
            products.append(p)
            
        self.stdout.write(f"Created {len(products)} products.")

        # 5. Purchase Orders
        po = PurchaseOrder.objects.create(
            workspace=workspace,
            code="PO-2026-001",
            supplier=suppliers[0],
            status=PurchaseOrder.Status.RECEIVED,
            ordered_on=timezone.now().date() - timedelta(days=10),
            expected_on=timezone.now().date() - timedelta(days=2),
            subtotal=Decimal("5000"),
            total_amount=Decimal("5000"),
            created_by=user, updated_by=user
        )
        
        pol = PurchaseOrderLine.objects.create(
            workspace=workspace,
            purchase_order=po,
            product=products[0],
            quantity_ordered=100,
            quantity_received=100,
            unit_cost=Decimal("50"),
            line_total=Decimal("5000"),
            created_by=user, updated_by=user
        )

        gr = GoodsReceipt.objects.create(
            workspace=workspace,
            code="GR-2026-001",
            purchase_order=po,
            received_on=timezone.now().date() - timedelta(days=1),
            status=GoodsReceipt.Status.COMPLETED,
            created_by=user, updated_by=user
        )
        
        grl = GoodsReceiptLine.objects.create(
            workspace=workspace,
            goods_receipt=gr,
            purchase_order_line=pol,
            product=products[0],
            quantity_received=100,
            accepted_quantity=100,
            unit_cost=Decimal("50"),
            created_by=user, updated_by=user
        )
        
        lot = InventoryLot.objects.create(
            workspace=workspace,
            product=products[0],
            goods_receipt_line=grl,
            lot_code="LOT-2026-A1",
            quantity_received=100,
            quantity_available=100,
            status=InventoryLot.Status.AVAILABLE,
            created_by=user, updated_by=user
        )

        QualityInspection.objects.create(
            workspace=workspace,
            inventory_lot=lot,
            status=QualityInspection.Status.APPROVED,
            accepted_quantity=100,
            inspected_by=user,
            inspected_at=timezone.now(),
            created_by=user, updated_by=user
        )
        
        InventoryMovement.objects.create(
            workspace=workspace,
            product=products[0],
            inventory_lot=lot,
            movement_type=InventoryMovement.Type.INBOUND,
            quantity=100,
            reference_code=lot.lot_code,
            created_by=user, updated_by=user
        )

        self.stdout.write("Simulated Full Inbound Workflow.")

        # 6. Sales Orders
        so = SalesOrder.objects.create(
            workspace=workspace,
            code="SO-2026-001",
            customer=customers[0],
            status=SalesOrder.Status.COMPLETED,
            ordered_on=timezone.now().date(),
            subtotal=Decimal("1500"),
            total_amount=Decimal("1500"),
            created_by=user, updated_by=user
        )
        
        SalesOrderLine.objects.create(
            workspace=workspace,
            sales_order=so,
            product=products[-1],
            quantity_ordered=5,
            unit_price=Decimal("300"),
            line_total=Decimal("1500"),
            created_by=user, updated_by=user
        )
        
        shipment = Shipment.objects.create(
            workspace=workspace,
            sales_order=so,
            shipment_code="SH-2026-001",
            carrier="FedEx",
            tracking_number="1Z9999W99999999999",
            status=Shipment.Status.DELIVERED,
            dispatched_at=timezone.now(),
            created_by=user, updated_by=user
        )
        
        inv = Invoice.objects.create(
            workspace=workspace,
            sales_order=so,
            invoice_number="INV-2026-001",
            status=Invoice.Status.ISSUED,
            issued_at=timezone.now().date(),
            due_on=timezone.now().date() + timedelta(days=30),
            total_amount=Decimal("1500"),
            created_by=user, updated_by=user
        )
        
        InventoryMovement.objects.create(
            workspace=workspace,
            product=products[-1],
            movement_type=InventoryMovement.Type.OUTBOUND,
            quantity=-5,
            reference_code=so.code,
            created_by=user, updated_by=user
        )
        
        self.stdout.write("Simulated Full Outbound Workflow.")
        
        # 7. Notifications
        Notification.objects.create(
            workspace=workspace,
            recipient=user,
            title="System Seed",
            message="Data seeded successfully in workspace.",
            level=Notification.Level.SUCCESS,
            created_by=user, updated_by=user
        )
        
        # 8. Activity Events
        ActivityEvent.objects.create(
            workspace=workspace,
            actor=user,
            event_type="app.seeded",
            message=f"{user.full_name} seeded full demo data.",
            created_by=user, updated_by=user
        )
        
        self.stdout.write(self.style.SUCCESS("All logical data seeded successfully!"))
        self.stdout.write(self.style.WARNING("⚠️  Test credentials created - DO NOT USE IN PRODUCTION"))


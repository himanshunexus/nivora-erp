from datetime import date, timedelta

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User, Workspace, WorkspaceMembership
from apps.operations.models import Customer, Product, QualityInspection, Supplier
from core.permissions import ROLE_OWNER
from services.operations import (
    create_purchase_order,
    create_sales_order,
    decide_quality,
    dispatch_sales_order,
    receive_purchase_order,
)


class OperationsWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@nivora.test",
            full_name="Owner User",
            is_active=True,
        )
        self.workspace = Workspace.objects.create(name="Acme Ops", slug="acme-ops")
        WorkspaceMembership.objects.create(
            user=self.user,
            workspace=self.workspace,
            role=ROLE_OWNER,
            is_default=True,
            title="Owner",
        )
        self.user.default_workspace = self.workspace
        self.user.save(update_fields=["default_workspace"])

        self.supplier = Supplier.objects.create(
            workspace=self.workspace,
            name="Acme Metals",
            email="supply@acme.test",
            status="active",
        )
        self.customer = Customer.objects.create(
            workspace=self.workspace,
            name="Northwind Retail",
            company="Northwind",
            email="buy@northwind.test",
        )
        self.product = Product.objects.create(
            workspace=self.workspace,
            sku="SKU-001",
            name="Industrial Sensor",
            category="Sensors",
            unit="unit",
            cost_price="125.00",
            unit_price="225.00",
            reorder_level=5,
        )

        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.pk
        session.save()

    def test_end_to_end_workflow_updates_stock_and_documents(self):
        purchase_order = create_purchase_order(
            workspace=self.workspace,
            actor=self.user,
            supplier=self.supplier,
            expected_on=date.today() + timedelta(days=5),
            notes="Test PO",
            line_items=[{"product": self.product, "quantity_ordered": 10, "unit_cost": "125.00"}],
        )
        receipt = receive_purchase_order(
            workspace=self.workspace,
            actor=self.user,
            purchase_order=purchase_order,
            received_on=date.today(),
            reference_number="GRN-001",
            lines=[{"purchase_order_line": purchase_order.lines.first(), "quantity_received": 10}],
        )
        inspection = QualityInspection.objects.get(
            workspace=self.workspace,
            inventory_lot__goods_receipt_line__goods_receipt=receipt,
        )
        decide_quality(
            workspace=self.workspace,
            actor=self.user,
            inspection=inspection,
            accepted_quantity=10,
            rejected_quantity=0,
            notes="Approved",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 10)

        sales_order = create_sales_order(
            workspace=self.workspace,
            actor=self.user,
            customer=self.customer,
            promised_on=date.today() + timedelta(days=2),
            notes="Test SO",
            line_items=[{"product": self.product, "quantity_ordered": 4, "unit_price": "225.00"}],
        )
        shipment, invoice = dispatch_sales_order(
            workspace=self.workspace,
            actor=self.user,
            sales_order=sales_order,
            carrier="BlueDart",
            tracking_number="TRK-001",
            notes="Dispatch test",
        )

        self.product.refresh_from_db()
        sales_order.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 6)
        self.assertEqual(sales_order.status, "dispatched")
        self.assertEqual(shipment.tracking_number, "TRK-001")
        self.assertEqual(invoice.status, "issued")

    def test_workspace_pages_and_api_endpoints_render(self):
        response_map = {
            "dashboard": self.client.get(reverse("dashboard:home")),
            "hub": self.client.get(reverse("operations:hub")),
            "products": self.client.get(reverse("operations:product_list")),
            "notifications": self.client.get(reverse("notifications:center")),
            "api_dashboard": self.client.get(reverse("api_dashboard_summary")),
            "api_products": self.client.get(reverse("api_products")),
        }
        for response in response_map.values():
            self.assertEqual(response.status_code, 200)

    def test_superuser_without_membership_uses_first_workspace(self):
        admin = User.objects.create_superuser(email="admin@nivora.test", password="admin123")
        client = Client()
        client.force_login(admin)

        response = client.get(reverse("dashboard:home"))

        admin.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(admin.default_workspace, self.workspace)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                user=admin,
                workspace=self.workspace,
            ).exists()
        )

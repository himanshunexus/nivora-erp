from django.db import connection
from django.db.models import Q
from django.urls import reverse

from apps.operations.models import Customer, Product, PurchaseOrder, SalesOrder, Supplier


def command_search(workspace, query, *, limit=8):
    query = (query or "").strip()
    if len(query) < 2 or workspace is None:
        return []

    results = []
    if connection.vendor == "postgresql":
        products = Product.objects.filter(workspace=workspace, name__icontains=query)[:limit]
    else:
        products = Product.objects.filter(workspace=workspace).filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(category__icontains=query)
        )[:limit]

    suppliers = Supplier.objects.filter(workspace=workspace).filter(
        Q(name__icontains=query) | Q(email__icontains=query)
    )[:limit]
    customers = Customer.objects.filter(workspace=workspace).filter(
        Q(name__icontains=query) | Q(email__icontains=query) | Q(company__icontains=query)
    )[:limit]
    purchase_orders = PurchaseOrder.objects.filter(workspace=workspace).filter(
        Q(code__icontains=query) | Q(supplier__name__icontains=query)
    )[:limit]
    sales_orders = SalesOrder.objects.filter(workspace=workspace).filter(
        Q(code__icontains=query) | Q(customer__name__icontains=query)
    )[:limit]

    for product in products:
        results.append(
            {
                "title": product.name,
                "subtitle": f"{product.sku} · {product.stock_on_hand} on hand",
                "type": "Product",
                "status": product.category,
                "url": reverse("operations:product_detail", args=[product.pk]),
            }
        )
    for supplier in suppliers:
        results.append(
            {
                "title": supplier.name,
                "subtitle": supplier.email or supplier.phone,
                "type": "Supplier",
                "status": supplier.status,
                "url": reverse("operations:hub"),
            }
        )
    for customer in customers:
        results.append(
            {
                "title": customer.name,
                "subtitle": customer.company or customer.email,
                "type": "Customer",
                "status": "account",
                "url": reverse("operations:hub"),
            }
        )
    for purchase_order in purchase_orders:
        results.append(
            {
                "title": purchase_order.code,
                "subtitle": purchase_order.supplier.name,
                "type": "Purchase Order",
                "status": purchase_order.status,
                "url": reverse("operations:purchase_order_detail", args=[purchase_order.pk]),
            }
        )
    for sales_order in sales_orders:
        results.append(
            {
                "title": sales_order.code,
                "subtitle": sales_order.customer.name,
                "type": "Sales Order",
                "status": sales_order.status,
                "url": reverse("operations:sales_order_detail", args=[sales_order.pk]),
            }
        )
    return results[:limit]

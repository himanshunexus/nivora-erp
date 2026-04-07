from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.notifications.models import Notification
from apps.operations.models import ActivityEvent, Product, PurchaseOrder, SalesOrder


def dashboard_snapshot(workspace):
    cache_key = f"dashboard:snapshot:{workspace.pk}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    products = Product.objects.filter(workspace=workspace, is_active=True)
    purchase_orders = PurchaseOrder.objects.filter(workspace=workspace, is_active=True)
    sales_orders = SalesOrder.objects.filter(workspace=workspace, is_active=True)

    metrics = {
        "catalog_count": products.count(),
        "stock_units": products.aggregate(total=Sum("stock_on_hand")).get("total") or 0,
        "stock_value": float(
            sum((product.stock_on_hand or 0) * float(product.cost_price or 0) for product in products)
        ),
        "open_purchase_orders": purchase_orders.exclude(status__in=["received", "cancelled"]).count(),
        "ready_shipments": sales_orders.filter(status="ready_for_dispatch").count(),
        "awaiting_stock": sales_orders.filter(status="awaiting_stock").count(),
        "unread_notifications": Notification.objects.filter(
            workspace=workspace,
            is_active=True,
            is_read=False,
        ).count(),
    }

    since = timezone.now() - timedelta(days=6)
    po_trend = (
        purchase_orders.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )
    so_trend = (
        sales_orders.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    trend_map = {}
    for offset in range(7):
        day = (since + timedelta(days=offset)).date()
        trend_map[day.isoformat()] = {"purchase_orders": 0, "sales_orders": 0}
    for row in po_trend:
        trend_map[row["day"].isoformat()]["purchase_orders"] = row["total"]
    for row in so_trend:
        trend_map[row["day"].isoformat()]["sales_orders"] = row["total"]

    low_stock = list(
        products.filter(stock_on_hand__lte=0).values("name", "sku")[:5]
    ) + list(
        products.filter(stock_on_hand__lte=1, stock_on_hand__gt=0).values("name", "sku")[:5]
    )

    activity = ActivityEvent.objects.filter(workspace=workspace).select_related("actor")[:10]
    payload = {
        "metrics": metrics,
        "trend": trend_map,
        "low_stock": low_stock[:5],
        "activity": list(activity),
    }
    cache.set(cache_key, payload, timeout=60)
    return payload

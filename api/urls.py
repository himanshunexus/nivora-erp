from django.urls import path

from apps.accounts import views as account_views
from apps.dashboard import views as dashboard_views
from apps.notifications import views as notification_views
from apps.operations import views as operations_views
from apps.search import views as search_views

urlpatterns = [
    path("auth/logout/", account_views.logout_view, name="api_logout"),
    path("dashboard/summary/", dashboard_views.summary_api_view, name="api_dashboard_summary"),
    path("search/command/", search_views.command_search_api_view, name="api_command_search"),
    path("notifications/poll/", notification_views.poll_api_view, name="api_notifications_poll"),
    path("notifications/<int:pk>/read/", notification_views.mark_read_api_view, name="api_mark_notification_read"),
    path("products/", operations_views.api_products_view, name="api_products"),
    path("products/<int:pk>/", operations_views.api_product_detail_view, name="api_product_detail"),
    path("purchase-orders/", operations_views.api_purchase_orders_view, name="api_purchase_orders"),
    path("purchase-orders/<int:pk>/", operations_views.api_purchase_order_detail_view, name="api_purchase_order_detail"),
    path(
        "purchase-orders/<int:pk>/receive/",
        operations_views.api_receive_purchase_order_view,
        name="api_receive_purchase_order",
    ),
    path("quality-inspections/", operations_views.api_quality_inspections_view, name="api_quality_inspections"),
    path(
        "quality-inspections/<int:pk>/decision/",
        operations_views.api_quality_decision_view,
        name="api_quality_decision",
    ),
    path("sales-orders/", operations_views.api_sales_orders_view, name="api_sales_orders"),
    path("sales-orders/<int:pk>/", operations_views.api_sales_order_detail_view, name="api_sales_order_detail"),
    path(
        "sales-orders/<int:pk>/dispatch/",
        operations_views.api_sales_order_dispatch_view,
        name="api_sales_order_dispatch",
    ),
]

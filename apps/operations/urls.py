from django.urls import path

from apps.operations import views

app_name = "operations"

urlpatterns = [
    path("", views.hub, name="hub"),
    path("suppliers/create/", views.supplier_create, name="supplier_create"),
    path("customers/create/", views.customer_create, name="customer_create"),
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("purchase-orders/", views.purchase_order_list, name="purchase_order_list"),
    path("purchase-orders/new/", views.purchase_order_create_view, name="purchase_order_create"),
    path("purchase-orders/<int:pk>/", views.purchase_order_detail, name="purchase_order_detail"),
    path("purchase-orders/<int:pk>/receive/", views.purchase_order_receive_view, name="purchase_order_receive"),
    path("quality/", views.quality_queue, name="quality_queue"),
    path("quality/<int:pk>/", views.quality_inspection_detail, name="quality_detail"),
    path("sales-orders/", views.sales_order_list, name="sales_order_list"),
    path("sales-orders/new/", views.sales_order_create_view, name="sales_order_create"),
    path("sales-orders/<int:pk>/", views.sales_order_detail, name="sales_order_detail"),
    path("sales-orders/<int:pk>/dispatch/", views.sales_order_dispatch_view, name="sales_order_dispatch"),
]

from datetime import date, timedelta
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

logger = logging.getLogger(__name__)

from apps.notifications.models import Notification
from apps.operations.forms import (
    CustomerForm,
    DispatchForm,
    ProductForm,
    PurchaseOrderForm,
    PurchaseOrderLineFormSet,
    QualityDecisionForm,
    SalesOrderForm,
    SalesOrderLineFormSet,
    SupplierForm,
)
from apps.operations.models import Customer, Product, PurchaseOrder, QualityInspection, SalesOrder, Supplier
from core.api_auth import api_auth_required
from core.permissions import require_workspace_permission
from services.operations import (
    OperationsServiceError,
    api_product_payload,
    api_purchase_order_payload,
    api_sales_order_payload,
    create_purchase_order,
    create_sales_order,
    decide_quality,
    dispatch_sales_order,
    receive_purchase_order,
)
from utils.api import json_error, json_success, pagination_meta, parse_request_data


def _require_workspace(request):
    if not getattr(request, "workspace", None):
        raise Http404("No active workspace found.")
    return request.workspace


def _bind_workspace_to_formset(formset, workspace):
    for form in formset.forms:
        if "product" in form.fields:
            form.fields["product"].queryset = Product.objects.filter(workspace=workspace, is_active=True)


def _parse_iso_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


@login_required
@require_workspace_permission("inventory.manage")
def hub(request):
    workspace = _require_workspace(request)
    context = {
        "suppliers": Supplier.objects.filter(workspace=workspace, is_active=True)[:6],
        "customers": Customer.objects.filter(workspace=workspace, is_active=True)[:6],
        "supplier_form": SupplierForm(),
        "customer_form": CustomerForm(),
        "pending_quality_count": QualityInspection.objects.filter(workspace=workspace, status="pending").count(),
        "unread_count": Notification.objects.filter(
            workspace=workspace,
            recipient=request.user,
            is_read=False,
            is_active=True,
        ).count(),
    }
    return render(request, "operations/hub.html", context)


@login_required
@require_workspace_permission("suppliers.manage")
@require_POST
def supplier_create(request):
    workspace = _require_workspace(request)
    form = SupplierForm(request.POST)
    if form.is_valid():
        supplier = form.save(commit=False)
        supplier.stamp(user=request.user, workspace=workspace)
        supplier.save()
        logger.info(f"Supplier created: {supplier.name} by {request.user.email}")
        messages.success(request, f"{supplier.name} added to the supplier network.")
    else:
        messages.error(request, "Unable to save supplier. Please review the form.")
    return redirect("operations:hub")


@login_required
@require_workspace_permission("orders.manage")
@require_POST
def customer_create(request):
    workspace = _require_workspace(request)
    form = CustomerForm(request.POST)
    if form.is_valid():
        customer = form.save(commit=False)
        customer.stamp(user=request.user, workspace=workspace)
        customer.save()
        logger.info(f"Customer created: {customer.name} by {request.user.email}")
        messages.success(request, f"{customer.name} added to the customer book.")
    else:
        messages.error(request, "Unable to save customer. Please review the form.")
    return redirect("operations:hub")


@login_required
@require_workspace_permission("products.manage")
def product_list(request):
    workspace = _require_workspace(request)
    products = Product.objects.filter(workspace=workspace, is_active=True)
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query) | Q(category__icontains=query))
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "operations/product_list.html",
        {"page_obj": page_obj, "query": query},
    )


@login_required
@require_workspace_permission("products.manage")
def product_detail(request, pk):
    workspace = _require_workspace(request)
    product = get_object_or_404(
        Product.objects.filter(workspace=workspace, is_active=True).prefetch_related("inventory_movements"),
        pk=pk,
    )
    context = {
        "product": product,
        "movements": product.inventory_movements.select_related("inventory_lot")[:10],
        "recent_purchase_lines": product.purchase_order_lines.select_related("purchase_order", "purchase_order__supplier")[:5],
        "recent_sales_lines": product.sales_order_lines.select_related("sales_order", "sales_order__customer")[:5],
    }
    return render(request, "operations/product_detail.html", context)


@login_required
@require_workspace_permission("products.manage")
@require_http_methods(["GET", "POST"])
def product_create(request):
    workspace = _require_workspace(request)
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.stamp(user=request.user, workspace=workspace)
        product.save()
        logger.info(f"Product created: {product.sku} ({product.name}) by {request.user.email}")
        messages.success(request, f"{product.name} is now live in the catalog.")
        return redirect("operations:product_detail", pk=product.pk)
    return render(request, "operations/product_form.html", {"form": form, "title": "New product"})


@login_required
@require_workspace_permission("products.manage")
@require_http_methods(["GET", "POST"])
def product_edit(request, pk):
    workspace = _require_workspace(request)
    product = get_object_or_404(Product, pk=pk, workspace=workspace, is_active=True)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.stamp(user=request.user, workspace=workspace)
        product.save()
        logger.info(f"Product updated: {product.sku} ({product.name}) by {request.user.email}")
        messages.success(request, f"{product.name} updated successfully.")
        return redirect("operations:product_detail", pk=product.pk)
    return render(request, "operations/product_form.html", {"form": form, "title": f"Edit {product.name}"})


@login_required
@require_workspace_permission("procurement.manage")
def purchase_order_list(request):
    workspace = _require_workspace(request)
    purchase_orders = PurchaseOrder.objects.filter(workspace=workspace, is_active=True).select_related("supplier")
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        purchase_orders = purchase_orders.filter(status=status_filter)
    paginator = Paginator(purchase_orders, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "operations/purchase_order_list.html",
        {"page_obj": page_obj, "status_filter": status_filter},
    )


@login_required
@require_workspace_permission("procurement.manage")
@require_http_methods(["GET", "POST"])
def purchase_order_create_view(request):
    workspace = _require_workspace(request)
    if not Supplier.objects.filter(workspace=workspace, is_active=True).exists():
        messages.warning(request, "Create a supplier before opening a purchase order.")
        return redirect("operations:hub")
    if not Product.objects.filter(workspace=workspace, is_active=True).exists():
        messages.warning(request, "Create products before opening a purchase order.")
        return redirect("operations:product_create")

    purchase_order = PurchaseOrder(workspace=workspace)
    form = PurchaseOrderForm(request.POST or None, instance=purchase_order, workspace=workspace)
    formset = PurchaseOrderLineFormSet(request.POST or None, instance=purchase_order, prefix="lines")
    _bind_workspace_to_formset(formset, workspace)
    if request.method == "GET":
        form.initial["expected_on"] = date.today() + timedelta(days=7)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        line_items = []
        for item in formset.cleaned_data:
            # Skip empty line items (deleted items have empty product field)
            if not item or not item.get("product"):
                continue
            line_items.append(
                {
                    "product": item["product"],
                    "quantity_ordered": item["quantity_ordered"],
                    "unit_cost": item["unit_cost"],
                }
            )

        # Ensure at least one valid line item exists
        if not line_items:
            messages.error(request, "Purchase order must have at least one line item.")
        else:
            try:
                purchase_order = create_purchase_order(
                    workspace=workspace,
                    actor=request.user,
                    supplier=form.cleaned_data["supplier"],
                    expected_on=form.cleaned_data["expected_on"],
                    notes=form.cleaned_data.get("notes", ""),
                    line_items=line_items,
                )
            except OperationsServiceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"{purchase_order.code} created successfully.")
                return redirect("operations:purchase_order_detail", pk=purchase_order.pk)

    return render(
        request,
        "operations/purchase_order_form.html",
        {"form": form, "formset": formset, "title": "New purchase order"},
    )


@login_required
@require_workspace_permission("procurement.manage")
def purchase_order_detail(request, pk):
    workspace = _require_workspace(request)
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.filter(workspace=workspace, is_active=True)
        .select_related("supplier")
        .prefetch_related("lines__product", "receipts__lines__product"),
        pk=pk,
    )
    return render(
        request,
        "operations/purchase_order_detail.html",
        {
            "purchase_order": purchase_order,
            "receipts": purchase_order.receipts.prefetch_related("lines__product"),
        },
    )


@login_required
@require_workspace_permission("inventory.manage")
@require_http_methods(["GET", "POST"])
def purchase_order_receive_view(request, pk):
    workspace = _require_workspace(request)
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.filter(workspace=workspace, is_active=True).prefetch_related("lines__product"),
        pk=pk,
    )
    receipt_rows = []
    for line in purchase_order.lines.all():
        receipt_rows.append(
            {
                "line": line,
                "remaining": max(line.quantity_ordered - line.quantity_received, 0),
            }
        )
    if request.method == "POST":
        received_on = _parse_iso_date(request.POST.get("received_on"))
        lines = []
        for row in receipt_rows:
            line = row["line"]
            quantity_received = int(request.POST.get(f"received_{line.pk}", "0") or 0)
            if quantity_received > 0:
                lines.append({"purchase_order_line": line, "quantity_received": quantity_received})
        try:
            goods_receipt = receive_purchase_order(
                workspace=workspace,
                actor=request.user,
                purchase_order=purchase_order,
                received_on=received_on or date.today(),
                reference_number=request.POST.get("reference_number", "").strip(),
                lines=lines,
            )
        except OperationsServiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{goods_receipt.code} recorded and queued for QC.")
            return redirect("operations:purchase_order_detail", pk=purchase_order.pk)
    return render(
        request,
        "operations/goods_receipt_form.html",
        {"purchase_order": purchase_order, "receipt_rows": receipt_rows},
    )


@login_required
@require_workspace_permission("inventory.manage")
def quality_queue(request):
    workspace = _require_workspace(request)
    inspections = (
        QualityInspection.objects.filter(workspace=workspace)
        .select_related("inventory_lot__product", "inventory_lot__goods_receipt_line__goods_receipt__purchase_order")
        .order_by("status", "-created_at")
    )
    paginator = Paginator(inspections, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "operations/quality_queue.html", {"page_obj": page_obj})


@login_required
@require_workspace_permission("inventory.manage")
@require_http_methods(["GET", "POST"])
def quality_inspection_detail(request, pk):
    workspace = _require_workspace(request)
    inspection = get_object_or_404(
        QualityInspection.objects.select_related(
            "inventory_lot__product",
            "inventory_lot__goods_receipt_line__goods_receipt__purchase_order",
        ),
        pk=pk,
        workspace=workspace,
    )
    form = QualityDecisionForm(request.POST or None, inspection=inspection)
    if request.method == "POST" and form.is_valid():
        try:
            inspection = decide_quality(
                workspace=workspace,
                actor=request.user,
                inspection=inspection,
                accepted_quantity=form.cleaned_data["accepted_quantity"],
                rejected_quantity=form.cleaned_data["rejected_quantity"],
                notes=form.cleaned_data["notes"],
            )
        except OperationsServiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{inspection.inventory_lot.lot_code} processed successfully.")
            return redirect("operations:quality_queue")
    return render(request, "operations/quality_detail.html", {"inspection": inspection, "form": form})


@login_required
@require_workspace_permission("orders.manage")
def sales_order_list(request):
    workspace = _require_workspace(request)
    sales_orders = SalesOrder.objects.filter(workspace=workspace, is_active=True).select_related("customer")
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        sales_orders = sales_orders.filter(status=status_filter)
    paginator = Paginator(sales_orders, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "operations/sales_order_list.html",
        {"page_obj": page_obj, "status_filter": status_filter},
    )


@login_required
@require_workspace_permission("orders.manage")
@require_http_methods(["GET", "POST"])
def sales_order_create_view(request):
    workspace = _require_workspace(request)
    if not Customer.objects.filter(workspace=workspace, is_active=True).exists():
        messages.warning(request, "Add a customer before creating a sales order.")
        return redirect("operations:hub")
    if not Product.objects.filter(workspace=workspace, is_active=True).exists():
        messages.warning(request, "Create products before creating a sales order.")
        return redirect("operations:product_create")

    sales_order = SalesOrder(workspace=workspace)
    form = SalesOrderForm(request.POST or None, instance=sales_order, workspace=workspace)
    formset = SalesOrderLineFormSet(request.POST or None, instance=sales_order, prefix="lines")
    _bind_workspace_to_formset(formset, workspace)
    if request.method == "GET":
        form.initial["promised_on"] = date.today() + timedelta(days=3)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        line_items = []
        for item in formset.cleaned_data:
            # Skip empty line items (deleted items have empty product field)
            if not item or not item.get("product"):
                continue
            line_items.append(
                {
                    "product": item["product"],
                    "quantity_ordered": item["quantity_ordered"],
                    "unit_price": item["unit_price"],
                }
            )

        # Ensure at least one valid line item exists
        if not line_items:
            messages.error(request, "Sales order must have at least one line item.")
        else:
            try:
                sales_order = create_sales_order(
                    workspace=workspace,
                    actor=request.user,
                    customer=form.cleaned_data["customer"],
                    promised_on=form.cleaned_data["promised_on"],
                    notes=form.cleaned_data.get("notes", ""),
                    line_items=line_items,
                )
            except OperationsServiceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"{sales_order.code} created successfully.")
                return redirect("operations:sales_order_detail", pk=sales_order.pk)

    return render(
        request,
        "operations/sales_order_form.html",
        {"form": form, "formset": formset, "title": "New sales order"},
    )


@login_required
@require_workspace_permission("orders.manage")
def sales_order_detail(request, pk):
    workspace = _require_workspace(request)
    sales_order = get_object_or_404(
        SalesOrder.objects.filter(workspace=workspace, is_active=True)
        .select_related("customer", "shipment", "invoice")
        .prefetch_related("lines__product"),
        pk=pk,
    )
    return render(
        request,
        "operations/sales_order_detail.html",
        {
            "sales_order": sales_order,
            "shipment": getattr(sales_order, "shipment", None),
            "invoice": getattr(sales_order, "invoice", None),
        },
    )


@login_required
@require_workspace_permission("orders.manage")
@require_http_methods(["GET", "POST"])
def sales_order_dispatch_view(request, pk):
    workspace = _require_workspace(request)
    sales_order = get_object_or_404(
        SalesOrder.objects.filter(workspace=workspace, is_active=True).select_related("customer"),
        pk=pk,
    )
    form = DispatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            dispatch_sales_order(
                workspace=workspace,
                actor=request.user,
                sales_order=sales_order,
                carrier=form.cleaned_data["carrier"],
                tracking_number=form.cleaned_data["tracking_number"],
                notes=form.cleaned_data["notes"],
            )
        except OperationsServiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{sales_order.code} dispatched successfully.")
            return redirect("operations:sales_order_detail", pk=sales_order.pk)
    return render(request, "operations/dispatch_form.html", {"sales_order": sales_order, "form": form})


@api_auth_required("products.manage")
@require_http_methods(["GET", "POST"])
@transaction.atomic
def api_products_view(request):
    workspace = request.api_workspace
    if request.method == "GET":
        products = Product.objects.filter(workspace=workspace, is_active=True)
        query = request.GET.get("q", "").strip()
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(sku__icontains=query) | Q(category__icontains=query)
            )
        paginator = Paginator(products, 20)
        page_obj = paginator.get_page(request.GET.get("page"))
        return json_success(
            data={"items": [api_product_payload(product) for product in page_obj], "pagination": pagination_meta(page_obj)}
        )

    payload = parse_request_data(request)
    form = ProductForm(payload)
    if not form.is_valid():
        return json_error("Invalid product payload.", status=400, errors=form.errors)
    product = form.save(commit=False)
    product.stamp(user=request.actor, workspace=workspace)
    product.save()
    return json_success(data=api_product_payload(product), status=201)


@api_auth_required("products.manage")
@require_http_methods(["GET", "PATCH"])
@transaction.atomic
def api_product_detail_view(request, pk):
    product = get_object_or_404(Product, pk=pk, workspace=request.api_workspace, is_active=True)
    if request.method == "GET":
        return json_success(data=api_product_payload(product))

    payload = parse_request_data(request)
    form = ProductForm(payload, instance=product)
    if not form.is_valid():
        return json_error("Invalid product payload.", status=400, errors=form.errors)
    product = form.save(commit=False)
    product.stamp(user=request.actor, workspace=request.api_workspace)
    product.save()
    return json_success(data=api_product_payload(product))


@api_auth_required("procurement.manage")
@require_http_methods(["GET", "POST"])
def api_purchase_orders_view(request):
    workspace = request.api_workspace
    if request.method == "GET":
        purchase_orders = PurchaseOrder.objects.filter(workspace=workspace, is_active=True).select_related("supplier")
        paginator = Paginator(purchase_orders, 20)
        page_obj = paginator.get_page(request.GET.get("page"))
        return json_success(
            data={
                "items": [api_purchase_order_payload(purchase_order) for purchase_order in page_obj],
                "pagination": pagination_meta(page_obj),
            }
        )

    payload = parse_request_data(request)
    supplier = get_object_or_404(Supplier, pk=payload.get("supplier_id"), workspace=workspace, is_active=True)
    line_items = []
    for item in payload.get("lines", []):
        product = get_object_or_404(Product, pk=item.get("product_id"), workspace=workspace, is_active=True)
        line_items.append(
            {
                "product": product,
                "quantity_ordered": item.get("quantity_ordered"),
                "unit_cost": item.get("unit_cost"),
            }
        )
    try:
        purchase_order = create_purchase_order(
            workspace=workspace,
            actor=request.actor,
            supplier=supplier,
            expected_on=_parse_iso_date(payload.get("expected_on")),
            notes=payload.get("notes", ""),
            line_items=line_items,
        )
    except OperationsServiceError as exc:
        return json_error(str(exc), status=400)
    return json_success(data=api_purchase_order_payload(purchase_order), status=201)


@api_auth_required("procurement.manage")
@require_http_methods(["GET", "PATCH"])
@transaction.atomic
def api_purchase_order_detail_view(request, pk):
    workspace = request.api_workspace
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.filter(workspace=workspace, is_active=True).select_related("supplier"),
        pk=pk,
    )
    if request.method == "GET":
        return json_success(data=api_purchase_order_payload(purchase_order))

    payload = parse_request_data(request)
    form = PurchaseOrderForm(payload, instance=purchase_order, workspace=workspace)
    if not form.is_valid():
        return json_error("Invalid purchase order payload.", status=400, errors=form.errors)
    purchase_order = form.save(commit=False)
    purchase_order.stamp(user=request.actor, workspace=workspace)
    purchase_order.save()
    return json_success(data=api_purchase_order_payload(purchase_order))


@api_auth_required("inventory.manage")
@require_POST
def api_receive_purchase_order_view(request, pk):
    workspace = request.api_workspace
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.filter(workspace=workspace, is_active=True).prefetch_related("lines__product"),
        pk=pk,
    )
    payload = parse_request_data(request)
    lines = []
    for item in payload.get("lines", []):
        purchase_order_line = get_object_or_404(
            purchase_order.lines.select_related("product"),
            pk=item.get("purchase_order_line_id"),
        )
        lines.append({"purchase_order_line": purchase_order_line, "quantity_received": item.get("quantity_received")})
    try:
        goods_receipt = receive_purchase_order(
            workspace=workspace,
            actor=request.actor,
            purchase_order=purchase_order,
            received_on=_parse_iso_date(payload.get("received_on")) or date.today(),
            reference_number=payload.get("reference_number", ""),
            lines=lines,
        )
    except OperationsServiceError as exc:
        return json_error(str(exc), status=400)
    return json_success(data={"goods_receipt": goods_receipt.code, "purchase_order": purchase_order.code})


@api_auth_required("inventory.manage")
def api_quality_inspections_view(request):
    inspections = (
        QualityInspection.objects.filter(workspace=request.api_workspace)
        .select_related("inventory_lot__product", "inventory_lot__goods_receipt_line__goods_receipt")
        .order_by("status", "-created_at")[:25]
    )
    data = [
        {
            "id": inspection.pk,
            "lot_code": inspection.inventory_lot.lot_code,
            "product": inspection.inventory_lot.product.name,
            "status": inspection.status,
            "quantity_received": inspection.inventory_lot.quantity_received,
        }
        for inspection in inspections
    ]
    return json_success(data={"items": data})


@api_auth_required("inventory.manage")
@require_POST
def api_quality_decision_view(request, pk):
    inspection = get_object_or_404(QualityInspection, pk=pk, workspace=request.api_workspace)
    payload = parse_request_data(request)
    try:
        inspection = decide_quality(
            workspace=request.api_workspace,
            actor=request.actor,
            inspection=inspection,
            accepted_quantity=int(payload.get("accepted_quantity", 0)),
            rejected_quantity=int(payload.get("rejected_quantity", 0)),
            notes=payload.get("notes", ""),
        )
    except OperationsServiceError as exc:
        return json_error(str(exc), status=400)
    return json_success(data={"id": inspection.pk, "status": inspection.status})


@api_auth_required("orders.manage")
@require_http_methods(["GET", "POST"])
def api_sales_orders_view(request):
    workspace = request.api_workspace
    if request.method == "GET":
        sales_orders = SalesOrder.objects.filter(workspace=workspace, is_active=True).select_related("customer")
        paginator = Paginator(sales_orders, 20)
        page_obj = paginator.get_page(request.GET.get("page"))
        return json_success(
            data={"items": [api_sales_order_payload(sales_order) for sales_order in page_obj], "pagination": pagination_meta(page_obj)}
        )

    payload = parse_request_data(request)
    customer = get_object_or_404(Customer, pk=payload.get("customer_id"), workspace=workspace, is_active=True)
    line_items = []
    for item in payload.get("lines", []):
        product = get_object_or_404(Product, pk=item.get("product_id"), workspace=workspace, is_active=True)
        line_items.append(
            {
                "product": product,
                "quantity_ordered": item.get("quantity_ordered"),
                "unit_price": item.get("unit_price"),
            }
        )
    try:
        sales_order = create_sales_order(
            workspace=workspace,
            actor=request.actor,
            customer=customer,
            promised_on=_parse_iso_date(payload.get("promised_on")),
            notes=payload.get("notes", ""),
            line_items=line_items,
        )
    except OperationsServiceError as exc:
        return json_error(str(exc), status=400)
    return json_success(data=api_sales_order_payload(sales_order), status=201)


@api_auth_required("orders.manage")
@require_http_methods(["GET", "PATCH"])
def api_sales_order_detail_view(request, pk):
    workspace = request.api_workspace
    sales_order = get_object_or_404(
        SalesOrder.objects.filter(workspace=workspace, is_active=True).select_related("customer"),
        pk=pk,
    )
    if request.method == "GET":
        return json_success(data=api_sales_order_payload(sales_order))

    payload = parse_request_data(request)
    form = SalesOrderForm(payload, instance=sales_order, workspace=workspace)
    if not form.is_valid():
        return json_error("Invalid sales order payload.", status=400, errors=form.errors)
    sales_order = form.save(commit=False)
    sales_order.stamp(user=request.actor, workspace=workspace)
    sales_order.save()
    return json_success(data=api_sales_order_payload(sales_order))


@api_auth_required("orders.manage")
@require_POST
def api_sales_order_dispatch_view(request, pk):
    workspace = request.api_workspace
    sales_order = get_object_or_404(SalesOrder, pk=pk, workspace=workspace, is_active=True)
    payload = parse_request_data(request)
    try:
        shipment = dispatch_sales_order(
            workspace=workspace,
            actor=request.actor,
            sales_order=sales_order,
            carrier=payload.get("carrier", ""),
            tracking_number=payload.get("tracking_number", ""),
            notes=payload.get("notes", ""),
        )
    except OperationsServiceError as exc:
        return json_error(str(exc), status=400)

    # Get associated invoice if exists
    invoice = getattr(sales_order, 'invoice', None)

    response_data = {
        "shipment_code": shipment.shipment_code,
        "tracking_number": shipment.tracking_number,
    }
    if invoice:
        response_data["invoice_number"] = invoice.invoice_number

    return json_success(data=response_data)

# Create your views here.

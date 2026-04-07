import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.models import Workspace
from core.api_auth import api_auth_required
from core.permissions import require_workspace_permission
from services.dashboard import dashboard_snapshot
from utils.api import json_error, json_success


@login_required
@require_workspace_permission("analytics.view")
def home(request):
    if not request.workspace:
        return render(
            request,
            "dashboard/no_workspace.html",
            {
                "workspace_count": Workspace.objects.filter(is_active=True).count(),
                "is_superuser_view": request.user.is_superuser,
            },
        )

    snapshot = dashboard_snapshot(request.workspace)
    trend = snapshot["trend"]
    context = {
        "metrics": snapshot["metrics"],
        "activity": snapshot["activity"],
        "low_stock": snapshot["low_stock"],
        "chart_labels": json.dumps(list(trend.keys())),
        "purchase_order_series": json.dumps([value["purchase_orders"] for value in trend.values()]),
        "sales_order_series": json.dumps([value["sales_orders"] for value in trend.values()]),
    }
    return render(request, "dashboard/home.html", context)


@api_auth_required("analytics.view")
def summary_api_view(request):
    if request.api_workspace is None:
        return json_error("No workspace is available for this account.", status=409)

    snapshot = dashboard_snapshot(request.api_workspace)
    activity = [
        {
            "id": entry.pk,
            "message": entry.message,
            "event_type": entry.event_type,
            "actor": entry.actor.full_name if entry.actor else "",
            "created_at": entry.created_at.isoformat(),
            "link": entry.link,
        }
        for entry in snapshot["activity"]
    ]
    payload = dict(snapshot)
    payload["activity"] = activity
    return json_success(data=payload)

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.notifications.models import Notification
from core.api_auth import api_auth_required
from core.permissions import require_workspace_permission
from services.notifications import unread_notifications
from utils.api import json_success


@login_required
@require_workspace_permission("notifications.view")
def center(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
        workspace=request.workspace,
        is_active=True,
    )
    paginator = Paginator(notifications, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "notifications/center.html", {"page_obj": page_obj})


@login_required
@require_workspace_permission("notifications.view")
@require_GET
def poll(request):
    notifications = unread_notifications(request.user, request.workspace, limit=5)
    payload = [
        {
            "id": notification.pk,
            "title": notification.title,
            "message": notification.message,
            "link": notification.link,
            "level": notification.level,
            "created_at": notification.created_at.isoformat(),
        }
        for notification in notifications
    ]
    unread_count = Notification.objects.filter(
        recipient=request.user,
        workspace=request.workspace,
        is_read=False,
        is_active=True,
    ).count()
    return json_success(data={"notifications": payload, "unread_count": unread_count})


@login_required
@require_workspace_permission("notifications.view")
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
        workspace=request.workspace,
        is_active=True,
    )
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at", "updated_at"])
    messages.success(request, "Notification marked as read.")
    return redirect(request.POST.get("next") or "notifications:center")


@api_auth_required("notifications.view")
def poll_api_view(request):
    notifications = unread_notifications(request.actor, request.api_workspace, limit=5)
    payload = [
        {
            "id": notification.pk,
            "title": notification.title,
            "message": notification.message,
            "link": notification.link,
            "level": notification.level,
            "created_at": notification.created_at.isoformat(),
        }
        for notification in notifications
    ]
    unread_count = Notification.objects.filter(
        recipient=request.actor,
        workspace=request.api_workspace,
        is_read=False,
        is_active=True,
    ).count()
    return json_success(data={"notifications": payload, "unread_count": unread_count})


@api_auth_required("notifications.view")
@require_POST
def mark_read_api_view(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.actor,
        workspace=request.api_workspace,
        is_active=True,
    )
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return json_success(data={"id": notification.pk, "read": True})

# Create your views here.

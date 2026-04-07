from apps.accounts.models import WorkspaceMembership
from apps.notifications.models import Notification


def create_notification(
    *,
    workspace,
    recipient,
    title,
    message,
    link="",
    level=Notification.Level.INFO,
    category="system",
    actor=None,
):
    notification = Notification(
        workspace=workspace,
        recipient=recipient,
        title=title,
        message=message,
        link=link,
        level=level,
        category=category,
    )
    notification.stamp(user=actor, workspace=workspace)
    notification.save()
    return notification


def notify_roles(*, workspace, roles, title, message, link="", level=Notification.Level.INFO, actor=None):
    memberships = WorkspaceMembership.objects.select_related("user").filter(
        workspace=workspace,
        role__in=roles,
        user__is_active=True,
    )
    notifications = []
    for membership in memberships:
        notifications.append(
            create_notification(
                workspace=workspace,
                recipient=membership.user,
                title=title,
                message=message,
                link=link,
                level=level,
                actor=actor,
            )
        )
    return notifications


def unread_notifications(user, workspace, *, limit=5):
    return Notification.objects.filter(
        recipient=user,
        workspace=workspace,
        is_read=False,
        is_active=True,
    ).order_by("-created_at")[:limit]

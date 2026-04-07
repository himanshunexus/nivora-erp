from django.conf import settings


def platform(request):
    return {
        "platform_name": "NIVORA",
        "workspace": getattr(request, "workspace", None),
        "notification_poll_interval_ms": settings.NIVORA_NOTIFICATION_POLL_INTERVAL_MS,
    }

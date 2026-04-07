from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "level", "category", "is_read", "created_at")
    list_filter = ("level", "category", "is_read")
    search_fields = ("title", "message", "recipient__email")

# Register your models here.

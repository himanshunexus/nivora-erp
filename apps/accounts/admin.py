from django.contrib import admin

from apps.accounts.models import OTPChallenge, User, Workspace, WorkspaceMembership


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "job_title", "default_workspace", "is_staff", "is_active")
    search_fields = ("email", "full_name", "phone_number")
    list_filter = ("is_staff", "is_active")


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "is_active", "updated_at")
    search_fields = ("name", "slug", "domain")
    list_filter = ("plan", "is_active")


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ("workspace", "user", "role", "title", "is_default", "joined_at")
    list_filter = ("role", "is_default")
    search_fields = ("workspace__name", "user__email", "user__full_name")


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("email", "expires_at", "consumed_at", "attempts_remaining", "is_active")
    search_fields = ("email",)
    list_filter = ("is_active",)

# Register your models here.

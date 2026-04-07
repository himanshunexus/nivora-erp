from django.utils.functional import SimpleLazyObject


def _resolve_workspace(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    memberships = user.memberships.select_related("workspace")
    workspace_id = request.session.get("active_workspace_id")

    membership = None
    if workspace_id:
        membership = memberships.filter(workspace_id=workspace_id).first()
    if membership is None:
        membership = memberships.filter(is_default=True).first() or memberships.first()
    if membership:
        request.session["active_workspace_id"] = membership.workspace_id
        return membership.workspace

    default_workspace = getattr(user, "default_workspace", None)
    if default_workspace is not None:
        request.session["active_workspace_id"] = default_workspace.pk
        return default_workspace

    if getattr(user, "is_superuser", False):
        from apps.accounts.models import Workspace, WorkspaceMembership
        from core.permissions import ROLE_OWNER

        workspace = Workspace.objects.filter(is_active=True).order_by("name").first()
        if workspace is not None:
            membership, created = WorkspaceMembership.objects.get_or_create(
                workspace=workspace,
                user=user,
                defaults={
                    "role": ROLE_OWNER,
                    "title": "Platform Administrator",
                    "is_default": True,
                },
            )
            if not created and not membership.is_default and not user.memberships.filter(is_default=True).exists():
                membership.is_default = True
                membership.save(update_fields=["is_default"])
            if not user.default_workspace_id:
                user.default_workspace = workspace
                user.save(update_fields=["default_workspace"])
            request.session["active_workspace_id"] = workspace.pk
            return workspace

    return None


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = SimpleLazyObject(lambda: _resolve_workspace(request))
        return self.get_response(request)

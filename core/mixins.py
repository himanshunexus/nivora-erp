from django.core.exceptions import PermissionDenied

from core.permissions import user_has_permission


class WorkspaceQuerysetMixin:
    workspace_field = "workspace"

    def get_workspace(self):
        return getattr(self.request, "workspace", None)

    def get_queryset(self):
        queryset = super().get_queryset()
        workspace = self.get_workspace()
        if workspace and hasattr(queryset.model, self.workspace_field):
            queryset = queryset.filter(**{self.workspace_field: workspace})
        if hasattr(queryset.model, "is_active"):
            queryset = queryset.filter(is_active=True)
        return queryset


class PermissionRequiredMixin:
    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        if self.permission_required and not user_has_permission(
            request.user,
            getattr(request, "workspace", None),
            self.permission_required,
        ):
            raise PermissionDenied("You do not have permission to access this resource.")
        return super().dispatch(request, *args, **kwargs)

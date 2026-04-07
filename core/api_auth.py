from functools import wraps

from django.http import JsonResponse

from core.permissions import user_has_permission
from services.auth import AuthServiceError, authenticate_token


def resolve_api_actor(request):
    if getattr(request, "user", None) and request.user.is_authenticated:
        workspace = getattr(request, "workspace", None)
        membership = request.user.memberships.filter(workspace=workspace).first() if workspace else None
        return request.user, workspace, membership

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif request.COOKIES.get("nivora_access_token"):
        token = request.COOKIES["nivora_access_token"]

    if not token:
        raise AuthServiceError("Authentication required.")

    _, user, workspace, membership = authenticate_token(token)
    return user, workspace, membership


def api_auth_required(permission=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            try:
                actor, workspace, membership = resolve_api_actor(request)
            except AuthServiceError as exc:
                return JsonResponse({"ok": False, "message": str(exc)}, status=401)

            if permission and not user_has_permission(actor, workspace, permission):
                return JsonResponse({"ok": False, "message": "Permission denied."}, status=403)

            if workspace is None:
                return JsonResponse(
                    {"ok": False, "message": "No workspace is available for this account."},
                    status=409,
                )

            request.actor = actor
            request.api_workspace = workspace
            request.api_membership = membership
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

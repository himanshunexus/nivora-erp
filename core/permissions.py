from functools import wraps

from django.core.exceptions import PermissionDenied

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_ANALYST = "analyst"
ROLE_CUSTOMER = "customer"

ROLE_CHOICES = [
    (ROLE_OWNER, "Owner"),
    (ROLE_ADMIN, "Admin"),
    (ROLE_OPERATOR, "Operator"),
    (ROLE_ANALYST, "Analyst"),
    (ROLE_CUSTOMER, "Customer"),
]

PERMISSIONS = {
    ROLE_OWNER: {
        "workspace.manage",
        "users.manage",
        "products.manage",
        "suppliers.manage",
        "procurement.manage",
        "inventory.manage",
        "orders.manage",
        "notifications.view",
        "analytics.view",
    },
    ROLE_ADMIN: {
        "users.manage",
        "products.manage",
        "suppliers.manage",
        "procurement.manage",
        "inventory.manage",
        "orders.manage",
        "notifications.view",
        "analytics.view",
    },
    ROLE_OPERATOR: {
        "products.manage",
        "suppliers.manage",
        "procurement.manage",
        "inventory.manage",
        "orders.manage",
        "notifications.view",
        "analytics.view",
    },
    ROLE_ANALYST: {
        "notifications.view",
        "analytics.view",
    },
    ROLE_CUSTOMER: {
        "orders.manage",
        "notifications.view",
    },
}


def get_membership(user, workspace):
    if not user or not getattr(user, "is_authenticated", False) or workspace is None:
        return None
    return user.memberships.filter(workspace=workspace).first()


def user_has_permission(user, workspace, permission):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    membership = get_membership(user, workspace)
    if membership is None:
        return False
    return permission in PERMISSIONS.get(membership.role, set())


def require_workspace_permission(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not user_has_permission(request.user, getattr(request, "workspace", None), permission):
                raise PermissionDenied("You do not have permission to access this resource.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

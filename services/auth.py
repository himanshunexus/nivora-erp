import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import Workspace, WorkspaceMembership
from core.permissions import ROLE_OWNER
from utils.jwt import JWTError, decode_token, encode_token

User = get_user_model()


class AuthServiceError(Exception):
    pass


def _workspace_slug(name):
    base_slug = slugify(name)[:40] or "nivora-workspace"
    slug = base_slug
    counter = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _token_expiry(minutes):
    return int(time.time() + minutes * 60)


def _issue_token(user, workspace, membership, token_type, ttl_minutes):
    return encode_token(
        {
            "sub": user.pk,
            "workspace": workspace.pk if workspace else None,
            "role": membership.role if membership else None,
            "type": token_type,
            "iat": int(time.time()),
            "exp": _token_expiry(ttl_minutes),
        },
        settings.NIVORA_JWT_SECRET,
    )


def issue_token_payload(user):
    membership = user.memberships.select_related("workspace").filter(is_default=True).first()
    if not membership:
        raise AuthServiceError("User does not have an active workspace.")
    workspace = membership.workspace

    access_token = _issue_token(
        user, workspace, membership, "access", settings.NIVORA_JWT_ACCESS_TTL_MINUTES
    )
    refresh_token = _issue_token(
        user, workspace, membership, "refresh", settings.NIVORA_JWT_REFRESH_TTL_MINUTES
    )
    return {
        "user": user,
        "workspace": workspace,
        "membership": membership,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def authenticate_token(token):
    try:
        payload = decode_token(token, settings.NIVORA_JWT_SECRET)
    except JWTError as exc:
        raise AuthServiceError(str(exc)) from exc

    user = User.objects.filter(pk=payload.get("sub"), is_active=True).first()
    if user is None:
        raise AuthServiceError("User not found for token.")

    workspace = None
    membership = None
    workspace_id = payload.get("workspace")
    if workspace_id:
        membership = user.memberships.select_related("workspace").filter(workspace_id=workspace_id).first()
        if membership is None:
            raise AuthServiceError("Token workspace is no longer accessible.")
        workspace = membership.workspace

    return payload, user, workspace, membership


@transaction.atomic
def register_with_password(*, email, full_name, workspace_name, password):
    email = email.strip().lower()
    if User.objects.filter(email=email).exists():
        raise AuthServiceError("A user with this email already exists.")

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name.strip(),
        is_active=True,
    )

    w_name = workspace_name.strip() or f"{user.full_name.split(' ')[0]}'s Workspace"
    workspace = Workspace.objects.create(
        name=w_name,
        slug=_workspace_slug(w_name),
        created_by=user,
        updated_by=user,
    )
    membership = WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=ROLE_OWNER,
        title="Workspace Owner",
        is_default=True,
    )
    user.default_workspace = workspace
    user.save(update_fields=["default_workspace"])

    return issue_token_payload(user)

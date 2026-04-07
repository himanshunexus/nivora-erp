from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate

from apps.accounts.forms import BrowserLoginForm, BrowserRegisterForm
from services.auth import AuthServiceError, register_with_password, issue_token_payload
from utils.api import is_api_request, json_success


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def _set_auth_cookies(response, auth_payload):
    response.set_cookie(
        "nivora_access_token",
        auth_payload["access_token"],
        max_age=settings.NIVORA_JWT_ACCESS_TTL_MINUTES * 60,
        secure=not settings.DEBUG,
        httponly=True,
        samesite="Lax",
    )
    response.set_cookie(
        "nivora_refresh_token",
        auth_payload["refresh_token"],
        max_age=settings.NIVORA_JWT_REFRESH_TTL_MINUTES * 60,
        secure=not settings.DEBUG,
        httponly=True,
        samesite="Lax",
    )
    return response


def _clear_browser_auth_state(request):
    request.session.pop("register_draft", None)


def _complete_browser_auth(request, auth_payload):
    user = auth_payload["user"]
    workspace = auth_payload["workspace"]
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["active_workspace_id"] = workspace.pk
    _clear_browser_auth_state(request)
    messages.success(request, f"Welcome to {workspace.name}.")
    response = HttpResponseRedirect(reverse("dashboard:home"))
    return _set_auth_cookies(response, auth_payload)


def _register_initial(request):
    draft = request.session.get("register_draft") or {}
    email = request.GET.get("email") or draft.get("email", "")
    return {
        "full_name": draft.get("full_name", ""),
        "email": email,
        "workspace_name": draft.get("workspace_name", ""),
    }


def _render_login_page(request, form=None, *, status=200):
    initial_email = request.GET.get("email", "")
    if form is None:
        form = BrowserLoginForm(initial={"email": initial_email})
    context = {
        "form": form,
    }
    return render(request, "accounts/login.html", context, status=status)


def _render_register_page(request, form=None, *, status=200):
    initial = _register_initial(request)
    if form is None:
        form = BrowserRegisterForm(initial=initial)
    context = {
        "form": form,
    }
    return render(request, "accounts/register.html", context, status=status)


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = BrowserLoginForm(request.POST)
        if not form.is_valid():
            return _render_login_page(request, form=form, status=400)

        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"].strip()

        user = authenticate(request, email=email, password=password)
        if user:
            if not user.is_active:
                messages.error(request, "Account is disabled.")
                return _render_login_page(request, form=form, status=403)
            try:
                auth_payload = issue_token_payload(user)
                return _complete_browser_auth(request, auth_payload)
            except AuthServiceError as exc:
                messages.error(request, str(exc))
                return _render_login_page(request, form=form, status=400)
        else:
            messages.error(request, "Invalid credentials.")
            return _render_login_page(request, form=form, status=400)

    return _render_login_page(request)


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = BrowserRegisterForm(request.POST)
        if not form.is_valid():
            return _render_register_page(request, form=form, status=400)

        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"].strip()
        full_name = form.cleaned_data["full_name"]
        workspace_name = form.cleaned_data["workspace_name"]

        request.session["register_draft"] = {
            "full_name": full_name,
            "email": email,
            "workspace_name": workspace_name,
        }

        try:
            auth_payload = register_with_password(
                email=email,
                password=password,
                full_name=full_name,
                workspace_name=workspace_name,
            )
            return _complete_browser_auth(request, auth_payload)
        except AuthServiceError as exc:
            messages.error(request, str(exc))
            return _render_register_page(request, form=form, status=400)

    return _render_register_page(request)


def logout_view(request):
    logout(request)
    response = json_success(message="Logged out.") if is_api_request(request) else redirect("accounts:login")
    response.delete_cookie("nivora_access_token")
    response.delete_cookie("nivora_refresh_token")
    return response

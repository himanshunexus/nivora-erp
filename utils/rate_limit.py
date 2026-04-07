import time
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect

from utils.api import is_api_request


def _request_identity(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip_address = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
    email = request.POST.get("email") or request.GET.get("email") or ""
    return f"{ip_address}:{email.lower()}"


def rate_limit(scope, *, limit=5, window=60):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            now = time.time()
            cache_key = f"rate-limit:{scope}:{_request_identity(request)}"
            history = cache.get(cache_key, [])
            history = [timestamp for timestamp in history if now - timestamp < window]
            if len(history) >= limit:
                message = "Too many attempts. Please wait and try again."
                if is_api_request(request):
                    return JsonResponse({"ok": False, "message": message}, status=429)
                messages.error(request, message)
                return redirect(request.META.get("HTTP_REFERER") or "accounts:login")
            history.append(now)
            cache.set(cache_key, history, timeout=window)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator

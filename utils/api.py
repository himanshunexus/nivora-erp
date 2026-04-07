import json

from django.http import JsonResponse


def is_api_request(request):
    return request.path.startswith("/api/")


def parse_request_data(request):
    if request.content_type and "application/json" in request.content_type:
        body = request.body.decode("utf-8") or "{}"
        return json.loads(body)
    return request.POST.dict()


def json_error(message, *, status=400, **extra):
    payload = {"ok": False, "message": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def json_success(*, data=None, status=200, **extra):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return JsonResponse(payload, status=status)


def pagination_meta(page_obj):
    return {
        "page": page_obj.number,
        "pages": page_obj.paginator.num_pages,
        "total": page_obj.paginator.count,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from core.api_auth import api_auth_required
from services.search import command_search
from utils.api import json_success


@login_required
@require_GET
def command_search_view(request):
    results = command_search(request.workspace, request.GET.get("q"))
    return json_success(data={"results": results})


@api_auth_required()
@require_GET
def command_search_api_view(request):
    results = command_search(request.api_workspace, request.GET.get("q"))
    return json_success(data={"results": results})

# Create your views here.

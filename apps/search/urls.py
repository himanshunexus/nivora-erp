from django.urls import path

from apps.search import views

app_name = "search"

urlpatterns = [
    path("command/", views.command_search_view, name="command"),
]

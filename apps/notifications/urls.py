from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.center, name="center"),
    path("poll/", views.poll, name="poll"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
]

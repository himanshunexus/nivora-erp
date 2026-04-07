import os

try:
    from celery import Celery
except ImportError:  # pragma: no cover - optional dependency during local bootstrap
    Celery = None

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

if Celery:
    app = Celery("nivora")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()
else:  # pragma: no cover
    app = None

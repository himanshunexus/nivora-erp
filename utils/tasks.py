try:
    from celery import shared_task as celery_shared_task
except ImportError:  # pragma: no cover - local fallback
    celery_shared_task = None


def shared_task(*task_args, **task_kwargs):
    if celery_shared_task:
        return celery_shared_task(*task_args, **task_kwargs)

    def decorator(func):
        def delay(*args, **kwargs):
            return func(*args, **kwargs)

        func.delay = delay
        return func

    return decorator

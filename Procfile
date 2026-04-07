release: python manage.py migrate
web: gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --max-requests 1000 --max-requests-jitter 50


from app import create_app
app = create_app()
celery = app.celery_app
celery.autodiscover_tasks()
celery.start()

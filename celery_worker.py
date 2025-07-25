# celery_worker.py
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import after loading env vars
from app import create_app

def create_celery_app():
    """Create and configure the Celery app"""
    flask_app = create_app()
    return flask_app.celery_app

# Create the Celery instance
celery = create_celery_app()

if __name__ == '__main__':
    celery.start()
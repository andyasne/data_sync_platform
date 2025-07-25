import os
from celery import Celery
from flask import Flask


def make_celery(app: Flask) -> Celery:
    """
    Initialise Celery and automatically switch to the ‘solo’ pool on Windows.
    The solo pool avoids the WinError 5 / WinError 6 issues that occur with
    the default (multiprocessing) pool under Windows.

    Usage:
        app = Flask(__name__)
        # … configure app.config["BROKER_URL"], RESULT_BACKEND, etc.
        celery = make_celery(app)
    """
    celery = Celery(
        app.import_name,
        broker=app.config["BROKER_URL"],
        backend=app.config["RESULT_BACKEND"],
        include=app.config.get("CELERY_INCLUDE"),
    )

    # Copy any other Flask → Celery config
    celery.conf.update(app.config)

    # 🪟  Windows needs the safe ‘solo’ pool.
    if os.name == "nt":
        # Celery ≥5.x – canonical key is 'worker_pool'
        celery.conf.worker_pool = "solo"
        # Celery ≤4.x – fallback keys (ignored by 5.x, but harmless)
        celery.conf.worker_pool_cls = "solo"
        celery.conf.CELERYD_POOL = "solo"

    # Make every task run inside the Flask application context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

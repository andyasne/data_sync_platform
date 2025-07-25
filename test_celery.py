#!/usr/bin/env python3
import os
import time
from urllib.parse import quote_plus
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

 
from dotenv import load_dotenv
# 2) Create your Flask app & Celery
from app import create_app
app = create_app()
celery = app.celery_app
load_dotenv()
# 3) Remove any old-style settings so we only have “broker_url”, “result_backend”, “include”
for legacy in ("BROKER_URL", "CELERY_INCLUDE", "CELERY_RESULT_BACKEND"):
    celery.conf.pop(legacy, None)

# 4) (Optional) run tasks synchronously — no worker needed
celery.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)

# 5) Import & fire off your task
from app.modules.data_transfer.tasks import sync_table_task

if __name__ == "__main__":
    with app.app_context():
        logging.debug("Dispatching sync_table_task synchronously (eager mode)…")
        try:
            # you can still use .delay(); it'll run in–process because of eager mode
            result = sync_table_task.delay("site_code", "")
            
            # Poll for its state just like before
            for _ in range(5):
                logging.debug(f" → state: {result.state}")
                if result.state in ("SUCCESS", "FAILURE"):
                    break
                time.sleep(1)

            if result.successful():
                logging.info(f"✅ Task succeeded, result: {result.result}")
            else:
                logging.error(f"❌ Final state: {result.state}, result: {result.result}")

        except Exception:
            # any exception (e.g. your IndexError) will be logged in full here
            logging.exception("sync_table_task failed with exception")

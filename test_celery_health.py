#!/usr/bin/env python3
import os
from urllib.parse import quote_plus

# -------------------------------------------------------------------
# 1) Make sure your env vars are set (URL-encode that “!” in the PW)
# -------------------------------------------------------------------
pw = "Login2Dash!"
os.environ.setdefault(
    "SOURCE_DB_URI",
    f"postgresql://dash:{quote_plus(pw)}@196.188.120.238:5432/echis_report"
)
os.environ.setdefault("TARGET_DB_URI", "postgresql://commcare_sync:commcare_sync@localhost:5432/sync")
os.environ.setdefault("CELERY_BROKER_URL",   "redis://localhost:6379/5")
os.environ.setdefault("CELERY_RESULT_BACKEND","redis://localhost:6379/6")

# -------------------------------------------------------------------
# 2) Boot your Flask app & grab its Celery instance
# -------------------------------------------------------------------
from app import create_app
app = create_app()
celery = app.celery_app

# remove any legacy keys so we don’t mix new/old formats
for bad in ("BROKER_URL", "CELERY_INCLUDE", "CELERY_RESULT_BACKEND"):
    celery.conf.pop(bad, None)

# -------------------------------------------------------------------
# 3) Turn on eager mode (so you don’t need a running worker)
# -------------------------------------------------------------------
celery.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,   # surface exceptions immediately
)

# -------------------------------------------------------------------
# 4) Define a tiny “ping” task just for health‐checking
# -------------------------------------------------------------------
@celery.task
def ping():
    return "pong"

# -------------------------------------------------------------------
# 5) Fire it off!
# -------------------------------------------------------------------
if __name__=="__main__":
    # since we’re eager, .delay() → runs immediately in‐process
    result = ping.delay()
    print("➤ ping() state:", result.state)
    print("➤ ping() returned:", result.result)

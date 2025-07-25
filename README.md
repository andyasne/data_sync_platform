
# Data‑Sync Platform

Modern Flask + Celery platform with:
* **Tabbed Bootstrap UI:** Config, Run/Monitor, Logs
* **Transfer Home:** `/` routes to transfer dashboard
* **Ready for isolated production use on port 5008**
* **.env.example prefilled for safe local dev**

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env for your DB URIs & credentials!
redis-server &             # or docker‑compose up redis
python run.py              # Web UI @ :5008
celery -A celery_worker worker --loglevel=info
```


commands


celery -A celery_worker worker --loglevel=info --logfile=logs/celery_worker.log
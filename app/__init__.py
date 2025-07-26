import os
from flask import Flask
from dotenv import load_dotenv
from .config import Config
from .utils.db import db
from .utils.celery import make_celery
from .utils.sse import sse_bp
from flask_migrate import Migrate

from .modules.auth.routes import auth_bp
from .modules.data_transfer.routes import transfer_bp
from .modules.pull_api.routes import pull_bp
from .modules.push_api.routes import push_bp
# from .utils.sse import event_stream
from flask import Response, stream_with_context

migrate = Migrate()

def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)
    celery = make_celery(app)
    app.celery_app = celery
    app.register_blueprint(auth_bp)
    app.register_blueprint(transfer_bp, url_prefix="/transfer")
    app.register_blueprint(pull_bp, url_prefix="/api/v1")
    app.register_blueprint(push_bp, url_prefix="/api/v1")
    app.register_blueprint(sse_bp, url_prefix="/events")
    return app

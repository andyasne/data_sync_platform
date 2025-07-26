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
from flask import Response, stream_with_context
from flasgger import Swagger
from flask_cors import CORS

migrate = Migrate()

def unique_id(view_func):
    return f"{view_func.__module__}.{view_func.__name__}"

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
    CORS(app)  
    # Clean Swagger configuration using Swagger 2.0
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Pull API",
            "version": "1.0.0",
            "description": "Read-only endpoints that expose client and biometric_identity data."
        },
        "host": "localhost:5008",  # Update this for production
        "basePath": "/api/v1",
        "schemes": ["http", "https"],
        "securityDefinitions": {
            "basicAuth": {
                "type": "basic"
            }
        },
        "security": [{"basicAuth": []}],
        "definitions": {
            "Client": {
                "type": "object",
                "properties": {
                    "simprintsId": {
                        "type": "string",
                        "description": "The Simprints ID for the client"
                    },
                    "id": {
                        "type": "string",
                        "description": "The client ID"
                    },
                    "subjectActions": {
                        "type": "string",
                        "description": "Subject actions data"
                    }
                },
                "required": ["id"]
            },
            "BiometricIdentity": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The biometric identity ID"
                    }
                    # Add more properties based on your actual table structure
                    # Example:
                    # "created_at": {
                    #     "type": "string",
                    #     "format": "date-time"
                    # }
                },
                "required": ["id"]
            }
        }
    }
    Swagger(app, template=swagger_template)

    return app
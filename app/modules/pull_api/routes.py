from flask import Blueprint, jsonify, current_app
from sqlalchemy import create_engine, text
from ...modules.auth.decorators import basic_auth_required

pull_bp = Blueprint('pull_api', __name__)

engine = None

def get_engine():
    global engine
    if engine is None:
        engine = create_engine(current_app.config['TARGET_DB_URI'])
    return engine

@pull_bp.route('/client/<int:client_id>')
@basic_auth_required
def client(client_id):
    row = get_engine().execute(text('SELECT * FROM client WHERE id=:id'), {'id': client_id}).fetchone()
    return jsonify(dict(row)) if row else ('Not found', 404)

@pull_bp.route('/biometric_identity/<int:bio_id>')
@basic_auth_required
def biometric(bio_id):
    row = get_engine().execute(text('SELECT * FROM biometric_identity WHERE id=:id'), {'id': bio_id}).fetchone()
    return jsonify(dict(row)) if row else ('Not found', 404)

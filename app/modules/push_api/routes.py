from flask import Blueprint, request, jsonify, current_app
import requests
from ...modules.auth.decorators import basic_auth_required
from ...utils.sse import announce

push_bp = Blueprint('push_api', __name__)

@push_bp.route('/push-data', methods=['POST'])
@basic_auth_required
def push_data():
    payload = request.get_json(force=True)
    transformed = {
        "identifier": payload.get("Id"),
        "action": payload.get("subjectAction"),
        "extra": payload.get("info")
    }
    dest_url = current_app.config.get("DESTINATION_URL", "http://other-server/api/receive")
    resp = requests.post(dest_url, json=transformed, timeout=10)
    announce({"push": transformed, "status": resp.status_code})
    return jsonify({"status": resp.status_code, "response": resp.text}), resp.status_code

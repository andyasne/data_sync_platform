from flask import request, Response
from functools import wraps
import os

def basic_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        valid_user = os.environ.get("PULL_API_USER")
        valid_pass = os.environ.get("PULL_API_PASS")

        if not auth or auth.username != valid_user or auth.password != valid_pass:
            return Response(
                "Unauthorized", 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )

        return f(*args, **kwargs)
    return decorated

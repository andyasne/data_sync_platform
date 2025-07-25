from functools import wraps
from flask import request, current_app, Response

def basic_auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == current_app.config['ADMIN_USERNAME']
                            and auth.password == current_app.config['ADMIN_PASSWORD']):
            return Response('Authentication required', 401,
                            {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return wrapper

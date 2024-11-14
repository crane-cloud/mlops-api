from functools import wraps
from jose import jwt
from flask import request
from flask import current_app


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        FLASK_APP_SALT = current_app.config['FLASK_APP_SALT']
        access_token = request.headers.get('Authorization')

        if access_token is None:
            return dict(message='Access token was not supplied'), 401
        try:
            token = access_token.split(' ')[1]
            if (access_token.split(' ')[0] != "Bearer"):
                return dict(message="Bad Authorization header. Expected value 'Bearer <JWT>'"), 422
            payload = jwt.decode(token, FLASK_APP_SALT, algorithms=['HS256'])

        except Exception as e:
            print(e)
            return dict(message="Access token is not valid or key"), 401

        return fn(*args, **kwargs, current_user=payload)
    return wrapper


# def has_role(role_list, role_name):
#     for role in role_list:
#         if role['name'] == role_name:
#             return True
#     return False


def admin_required(fn):
    @wraps(fn)
    @jwt_required
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

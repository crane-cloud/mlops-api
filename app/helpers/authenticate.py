from functools import wraps
from jose import jwt
from flask import request
import os


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):

        access_token = request.headers.get('Authorization')

        if access_token is None:
            return dict(message='Access token was not supplied'), 401
        try:
            token = access_token.split(' ')[1]
            if (access_token.split(' ')[0] != "Bearer"):
                return dict(message="Bad Authorization header. Expected value 'Bearer <JWT>'"), 422

            jwt.decode(token, os.getenv(
                'FLASK_APP_SALT'), algorithms=['HS256'])

        except Exception as e:
            print(e)
            return dict(message="Access token is not valid or key"), 401

        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @jwt_required
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

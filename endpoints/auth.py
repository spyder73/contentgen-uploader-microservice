import os
from flask import request, jsonify
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')


def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        print(auth_header, auth_header == f'Bearer {API_TOKEN}')
        print(f'Bearer {API_TOKEN}')
        if not auth_header or auth_header != f'Bearer {API_TOKEN}':
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated
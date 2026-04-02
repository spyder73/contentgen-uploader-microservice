import os
from flask import request, jsonify
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

# Parse ALLOWED_USER_IDS — supports both plain IDs ("123456") and
# username:id pairs ("dorian:123456"). Returns {username: id} dict.
def _parse_allowed_users() -> dict:
    raw = os.getenv('ALLOWED_USER_IDS', '')
    result = {}
    for entry in raw.split(','):
        entry = entry.strip()
        if not entry:
            continue
        if ':' in entry:
            uname, uid = entry.split(':', 1)
            result[uname.strip().lower().lstrip('@')] = uid.strip()
        else:
            result[entry] = entry  # plain ID — key and value are the same
    return result

ALLOWED_USERS = _parse_allowed_users()


def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f'Bearer {API_TOKEN}':
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated
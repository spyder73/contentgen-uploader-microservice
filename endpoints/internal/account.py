from flask import Blueprint, request, jsonify
from auth import require_token
from models.db import create_account, get_accounts, delete_account, update_account

account_bp = Blueprint('account', __name__)


@account_bp.route('/add-account', methods=['POST'])
@require_token
def add_account():
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'username', 'platforms']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Optional:
    is_ai = data.get('is_ai', False)
    autoposting_properties = data.get('autoposting_properties')
    
    result = create_account(
        user_id=data['user_id'],
        username=data['username'],
        platforms=data['platforms'],
        is_ai=is_ai,
        autoposting_properties=autoposting_properties
    )
    
    if result is None:
        return jsonify({'error': 'Account already exists'}), 409
    
    return jsonify({
        'success': True,
        'id': str(result)
    }), 201
    
    
@account_bp.route('/update-account', methods=['PATCH'])
@require_token
def update_account_route():
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'username']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Optional fields to update
    is_ai = data.get('is_ai')
    autoposting_properties = data.get('autoposting_properties')
    platforms = data.get('platforms')
    
    result = update_account(
        user_id=data['user_id'],
        username=data['username'],
        is_ai=is_ai,
        autoposting_properties=autoposting_properties,
        platforms=platforms
    )
    
    if result == 0:
        return jsonify({'error': 'Account not found'}), 404
    
    return jsonify({
        'success': True,
        'updated': result
    }), 200


@account_bp.route('/list-accounts', methods=['GET'])
@require_token
def list_accounts():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    accounts = get_accounts(user_id)
    
    return jsonify({'accounts': accounts}), 200

@account_bp.route('/delete-account', methods=['DELETE'])
@require_token
def delete_account_route():
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'username']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    deleted = delete_account(
        user_id=data['user_id'],
        username=data['username']
    )
    
    if deleted == 0:
        return jsonify({'error': 'Account not found'}), 404
    
    return jsonify({
        'success': True,
        'deleted': deleted
    }), 200
from flask import Blueprint, request, jsonify
from auth import require_token
from models.db import (
    create_group, get_groups, get_group_by_name,
    add_accounts_to_group, delete_group,
    add_video_to_group, get_group_videos
)

group_bp = Blueprint('group', __name__)


@group_bp.route('/create-group', methods=['POST'])
@require_token
def create_group_route():
    """Create a new group"""
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'group_name']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    account_usernames = data.get('account_usernames', [])
    
    result = create_group(
        user_id=data['user_id'],
        group_name=data['group_name'],
        account_usernames=account_usernames
    )
    
    if result is None:
        return jsonify({'error': 'Group already exists'}), 409
    
    return jsonify({
        'success': True,
        'group_id': result
    }), 201


@group_bp.route('/list-groups', methods=['GET'])
@require_token
def list_groups():
    """List all groups for a user"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    groups = get_groups(user_id)
    
    return jsonify({
        'groups': groups,
        'count': len(groups)
    }), 200


@group_bp.route('/get-group', methods=['GET'])
@require_token
def get_group():
    """Get a specific group by name"""
    user_id = request.args.get('user_id')
    group_name = request.args.get('group_name')
    
    if not all([user_id, group_name]):
        return jsonify({'error': 'user_id and group_name required'}), 400
    
    group = get_group_by_name(user_id, group_name)
    
    if not group:
        return jsonify({'error': 'Group not found'}), 404
    
    return jsonify(group), 200


@group_bp.route('/add-to-group', methods=['PATCH'])
@require_token
def add_to_group():
    """Add accounts to an existing group"""
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'group_name', 'account_usernames']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not isinstance(data['account_usernames'], list):
        return jsonify({'error': 'account_usernames must be a list'}), 400
    
    result = add_accounts_to_group(
        user_id=data['user_id'],
        group_name=data['group_name'],
        account_usernames=data['account_usernames']
    )
    
    if result == 0:
        return jsonify({'error': 'Group not found'}), 404
    
    return jsonify({
        'success': True,
        'updated': result
    }), 200


@group_bp.route('/delete-group', methods=['DELETE'])
@require_token
def delete_group_route():
    """Delete a group"""
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'group_name']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    result = delete_group(
        user_id=data['user_id'],
        group_name=data['group_name']
    )
    
    if result == 0:
        return jsonify({'error': 'Group not found'}), 404
    
    return jsonify({
        'success': True,
        'deleted': result
    }), 200


@group_bp.route('/add-group-video', methods=['POST'])
@require_token
def add_group_video():
    """Add a video to a group"""
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['user_id', 'group_name', 'video_id']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Get group
    group = get_group_by_name(data['user_id'], data['group_name'])
    if not group:
        return jsonify({'error': 'Group not found'}), 404
    
    result = add_video_to_group(
        group_id=group['id'],
        video_id=data['video_id']
    )
    
    if result is None:
        return jsonify({'error': 'Video already in group'}), 409
    
    return jsonify({
        'success': True,
        'id': result
    }), 201


@group_bp.route('/list-group-videos', methods=['GET'])
@require_token
def list_group_videos():
    """List all videos in a group"""
    user_id = request.args.get('user_id')
    group_name = request.args.get('group_name')
    
    if not all([user_id, group_name]):
        return jsonify({'error': 'user_id and group_name required'}), 400
    
    # Get group
    group = get_group_by_name(user_id, group_name)
    if not group:
        return jsonify({'error': 'Group not found'}), 404
    
    videos = get_group_videos(group['id'])
    
    return jsonify({
        'videos': videos,
        'count': len(videos)
    }), 200
from flask import Blueprint, request, jsonify
from auth import require_token
from models.db import create_video, get_videos

video_bp = Blueprint('video', __name__)


@video_bp.route('/add-video', methods=['POST'])
@require_token
def add_video():
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    if not all(k in data for k in ['video_id', 'caption', 'user_id']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    reusable = data.get('reusable', False)
    
    result = create_video(
        video_id=data['video_id'],
        caption=data['caption'],
        user_id=data['user_id'],
        status='available',
        reusable=reusable
    )
    
    if result is None:
        return jsonify({'error': 'Video already exists'}), 409
    
    return jsonify({
        'success': True,
        'id': str(result)
    }), 201


@video_bp.route('/list-videos', methods=['GET'])
@require_token
def list_videos():
    user_id = request.args.get('user_id')
    status = request.args.get('status')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    videos = get_videos(user_id, status)
    
    return jsonify({'videos': videos}), 200


@video_bp.route('/track-job', methods=['POST'])
@require_token
def track_job():
    """Track a scheduled job"""
    data = request.json
    
    if data is None:
        return jsonify({'error': 'No data provided'}), 400
    
    required = ['job_id', 'video_id', 'account_username', 'user_id', 'scheduled_date']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    from models.db import create_scheduled_job
    
    result = create_scheduled_job(
        job_id=data['job_id'],
        video_id=data['video_id'],
        account_username=data['account_username'],
        user_id=data['user_id'],
        scheduled_date=data['scheduled_date']
    )
    
    if result is None:
        return jsonify({'error': 'Job already tracked'}), 409
    
    return jsonify({
        'success': True,
        'id': result
    }), 201
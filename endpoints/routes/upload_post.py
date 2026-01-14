from flask import Blueprint, request, jsonify, g
from upload_post import UploadPostClient
from dotenv import load_dotenv
from auth import require_token
import os
import json
from utils.external_wrapper import track_upload
from utils.auto_schedule import auto_schedule
import logging

logger = logging.getLogger(__name__)

load_dotenv()
upload_bp = Blueprint('upload', __name__)
uploadpost_api_key = os.getenv('UPLOADPOST_API_KEY', '')
client = UploadPostClient(api_key=uploadpost_api_key)

ASSETS_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'assets')
os.makedirs(ASSETS_FOLDER, exist_ok=True)


@upload_bp.route('/upload-video', methods=['POST'])
@require_token
@auto_schedule
@track_upload
def upload_post():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    title = request.form.get('title')
    user = request.form.get('user')
    platforms_raw = request.form.get('platforms')
    scheduled_date = request.form.get('scheduled_date', None)
    params_raw = request.form.get('params')
    
    if not all([title, user, platforms_raw]):
        return jsonify({'error': 'Missing required fields: video, title, user, platforms are required'}), 400
    
    # Parse platforms to list
    try:
        assert platforms_raw is not None
        platforms = json.loads(platforms_raw)
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid platforms format. Use JSON array like ["tiktok"]'}), 400
    
    optional_params = {}
    if params_raw:
        try:
            optional_params = json.loads(params_raw)
            if not isinstance(optional_params, dict):
                raise ValueError("Params must be a JSON object")
        except (json.JSONDecodeError, ValueError) as e:
            return jsonify({'error': f'Invalid params format: {str(e)}'}), 400
    
    # Save video temporarily
    assert video_file.filename is not None
    temp_path = os.path.join(ASSETS_FOLDER, video_file.filename)
    video_file.save(temp_path)
    
    if scheduled_date == 'auto':
        scheduled_date = getattr(g, 'upload_time', None)
    
    try:
        kwargs = {
            'video_path': temp_path,
            'title': title,
            'user': user,
            'platforms': platforms,
        }
        if scheduled_date:
            kwargs['scheduled_date'] = scheduled_date
        
        kwargs.update(optional_params)
        logger.info(f"Uploading with {kwargs}")
        response = client.upload_video(**kwargs)
        logger.info(f"Upload-Post raw response: {response}")
        
        if 'error' in response:
            status_code = 500
        elif response.get('job_id'):
            status_code = 202
        else:
            status_code = 200 # immediate / async
        
        return jsonify(response), status_code
    
    except Exception as e:
        logger.error(f"Upload exception: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Upload failed',
            'details': str(e)
        }), 500
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
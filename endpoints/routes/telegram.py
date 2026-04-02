import os
import logging
import requests
from flask import Blueprint, request, jsonify
from auth import require_token, ALLOWED_USERS

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB Telegram Bot API limit


@telegram_bp.route('/resolve-telegram-username', methods=['GET'])
@require_token
def resolve_telegram_username():
    username = request.args.get('username', '').strip().lstrip('@').lower()
    if not username:
        return jsonify({'error': 'No username provided'}), 400

    user_id = ALLOWED_USERS.get(username)
    if not user_id:
        return jsonify({
            'error': f'Username "{username}" not found. Add it to ALLOWED_USER_IDS in the server .env (format: username:user_id).',
        }), 404

    return jsonify({'user_id': int(user_id), 'username': username}), 200


@telegram_bp.route('/send-telegram-video', methods=['POST'])
@require_token
def send_telegram_video():
    video = request.files.get('video')
    user_id = request.form.get('user_id')
    caption = request.form.get('caption', '')

    if not video:
        return jsonify({'error': 'No video file provided'}), 400
    if not user_id:
        return jsonify({'error': 'No user_id provided'}), 400

    # Check file size
    video.seek(0, 2)
    size = video.tell()
    video.seek(0)
    if size > MAX_FILE_SIZE:
        mb = size / (1024 * 1024)
        return jsonify({
            'error': f'Video too large ({mb:.1f} MB). Telegram limit is 50 MB.',
        }), 413

    # Truncate caption to Telegram's 1024-char limit
    if len(caption) > 1024:
        caption = caption[:1021] + '...'

    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendVideo'
        resp = requests.post(url, data={
            'chat_id': user_id,
            'caption': caption,
            'parse_mode': 'HTML',
        }, files={
            'video': (video.filename or 'video.mp4', video, video.content_type or 'video/mp4'),
        }, timeout=120)

        result = resp.json()
        if not result.get('ok'):
            logger.error(f"Telegram API error: {result}")
            return jsonify({'error': result.get('description', 'Telegram API error')}), 502

        return jsonify({'success': True, 'message': 'Video sent to Telegram'}), 200

    except requests.Timeout:
        return jsonify({'error': 'Telegram API timed out'}), 504
    except Exception as e:
        logger.error(f"Error sending video to Telegram: {e}")
        return jsonify({'error': str(e)}), 500

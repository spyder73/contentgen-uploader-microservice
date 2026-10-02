import json
import os
import logging
import requests
from flask import Blueprint, request, jsonify
from auth import require_token, ALLOWED_USERS
from utils.video_meta import metadata_from_form, probe_upload

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB Telegram Bot API limit
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB Telegram photo limit


def _mp4_filename(name):
    """Telegram keys off the extension as well as the MIME type."""
    base = os.path.basename(name or '').strip()
    if base.lower().endswith('.mp4'):
        return base
    return 'video.mp4'


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

    # Telegram will not derive these from the container. Without width/height it
    # lays the player out as a square, without duration it shows no length, and
    # without supports_streaming the client must download the whole file before
    # it will play. The caller normally probes and sends them; fall back to
    # probing here for callers that don't.
    payload = {
        'chat_id': user_id,
        'caption': caption,
        'parse_mode': 'HTML',
        'supports_streaming': 'true',
    }
    payload.update(metadata_from_form(request.form) or probe_upload(video))

    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendVideo'
        resp = requests.post(url, data=payload, files={
            # Uploads arrive as application/octet-stream (Go's CreateFormFile
            # hard-codes it), and Telegram files a non-video MIME type as a
            # document, so the type is pinned rather than forwarded.
            'video': (_mp4_filename(video.filename), video, 'video/mp4'),
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


MAX_ALBUM = 10  # sendMediaGroup takes 2-10 items
VIDEO_EXTS = ('.mp4', '.mov', '.webm')


def _slide_types(files, form):
    """'photo' or 'video' per file, in order. The caller sends a `slides` JSON list
    (type plus probed width/height/duration); without it, the file itself decides."""
    try:
        slides = json.loads(form.get('slides') or '[]')
    except ValueError:
        slides = []
    if not isinstance(slides, list) or len(slides) != len(files):
        slides = [{} for _ in files]
    typed = []
    for f, slide in zip(files, slides):
        slide = slide if isinstance(slide, dict) else {}
        kind = slide.get('type')
        if kind not in ('photo', 'video'):
            is_video = (f.content_type or '').startswith('video/') or (f.filename or '').lower().endswith(VIDEO_EXTS)
            kind = 'video' if is_video else 'photo'
        typed.append((kind, slide))
    return typed


def _album_sizes(count):
    """The fewest albums of at most MAX_ALBUM, as even as possible: 12 slides post
    as 6 + 6, never 10 + a lone 2 or an invalid album of one."""
    albums = -(-count // MAX_ALBUM)
    base, extra = divmod(count, albums)
    return [base + (1 if i < extra else 0) for i in range(albums)]


def _video_attributes(f, slide):
    meta = metadata_from_form(slide) or probe_upload(f)
    return {key: meta[key] for key in ('width', 'height', 'duration') if key in meta}


@telegram_bp.route('/send-telegram-carousel', methods=['POST'])
@require_token
def send_telegram_carousel():
    """Posts every slide, in order, as Telegram albums. Slides may be photos or
    videos (a technologyCarousel plays clips on some slides); more than 10 are
    split into several albums, the caption riding on the first."""
    files = request.files.getlist('images')
    user_id = request.form.get('user_id')
    caption = request.form.get('caption', '')

    if not files:
        return jsonify({'error': 'No images provided'}), 400
    if not user_id:
        return jsonify({'error': 'No user_id provided'}), 400

    slides = _slide_types(files, request.form)
    for f, (kind, _) in zip(files, slides):
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        limit, label = (MAX_FILE_SIZE, 'Video') if kind == 'video' else (MAX_PHOTO_SIZE, 'Image')
        if size > limit:
            mb = size / (1024 * 1024)
            return jsonify({'error': f'{label} too large ({mb:.1f} MB). Telegram limit is {limit // (1024 * 1024)} MB.'}), 413

    if len(caption) > 1024:
        caption = caption[:1021] + '...'

    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup'
    sizes = _album_sizes(len(files))
    start = 0
    try:
        for album, size in enumerate(sizes):
            media_list = []
            upload = {}
            for i in range(start, start + size):
                f, (kind, slide) = files[i], slides[i]
                attach_key = f'slide_{i}'
                entry = {'type': kind, 'media': f'attach://{attach_key}'}
                if kind == 'video':
                    # Same attributes as sendVideo: without them the player is square,
                    # shows no length and will not stream.
                    entry.update(_video_attributes(f, slide))
                    entry['supports_streaming'] = True
                    upload[attach_key] = (_mp4_filename(f.filename), f, 'video/mp4')
                else:
                    upload[attach_key] = (f.filename or f'image_{i}.jpg', f, f.content_type or 'image/jpeg')
                if i == 0 and caption:
                    entry['caption'] = caption
                    entry['parse_mode'] = 'HTML'
                media_list.append(entry)
            start += size

            resp = requests.post(url, data={
                'chat_id': user_id,
                'media': json.dumps(media_list),
            }, files=upload, timeout=120)
            result = resp.json()
            if not result.get('ok'):
                logger.error(f"Telegram API error (album {album + 1} of {len(sizes)}): {result}")
                prefix = f'Album {album + 1} of {len(sizes)}: ' if len(sizes) > 1 else ''
                return jsonify({'error': prefix + result.get('description', 'Telegram API error')}), 502

        return jsonify({'success': True, 'message': 'Carousel sent to Telegram'}), 200

    except requests.Timeout:
        return jsonify({'error': 'Telegram API timed out'}), 504
    except Exception as e:
        logger.error(f"Error sending carousel to Telegram: {e}")
        return jsonify({'error': str(e)}), 500

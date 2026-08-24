import json
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

PROBE_TIMEOUT = 30


def metadata_from_form(form):
    """Pick up width/height/duration that the calling service already probed."""
    meta = {}
    for key in ('width', 'height', 'duration'):
        try:
            value = int(form.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            meta[key] = value

    if not (meta.get('width') and meta.get('height')):
        return {}
    return meta


def probe_upload(file_storage):
    """Probe an uploaded video for width/height/duration. Returns {} on any failure.

    Only used when the caller did not send the attributes itself, since it spills
    the whole upload to disk to give ffprobe something to seek through.
    """
    if not shutil.which('ffprobe'):
        return {}

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.mp4')
        os.close(fd)
        file_storage.save(tmp_path)
        return probe_file(tmp_path)
    except Exception as e:
        logger.warning(f"Could not probe uploaded video: {e}")
        return {}
    finally:
        file_storage.seek(0)
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def probe_file(path):
    """Return {'width', 'height', 'duration'} in display orientation, or {}."""
    if not shutil.which('ffprobe'):
        return {}

    try:
        proc = subprocess.run(
            [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries',
                'stream=width,height:stream_side_data=rotation:stream_tags=rotate:format=duration',
                '-of', 'json', path,
            ],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT, check=True,
        )
        data = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        logger.warning(f"ffprobe failed on {path}: {e}")
        return {}

    streams = data.get('streams') or []
    stream = streams[0] if streams else {}
    width = stream.get('width')
    height = stream.get('height')
    if not width or not height:
        return {}

    # ffprobe reports coded dimensions. A portrait clip muxed as landscape plus a
    # 90 degree display matrix has to be swapped before Telegram sees it, or the
    # player is laid out in the wrong aspect.
    if _rotation_swaps_axes(stream):
        width, height = height, width

    meta = {'width': int(width), 'height': int(height)}

    try:
        seconds = int(round(float((data.get('format') or {}).get('duration'))))
    except (TypeError, ValueError):
        seconds = 0
    if seconds > 0:
        meta['duration'] = seconds

    return meta


def _rotation_swaps_axes(stream):
    degrees = None
    for side_data in stream.get('side_data_list') or []:
        if 'rotation' in side_data:
            degrees = side_data['rotation']
            break
    if degrees is None:
        degrees = (stream.get('tags') or {}).get('rotate')

    try:
        return int(abs(float(degrees))) % 180 == 90
    except (TypeError, ValueError):
        return False

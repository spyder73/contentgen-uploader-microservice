from functools import wraps
from flask import request, g
import pytz
import logging
from flask import jsonify
from datetime import datetime
from models.db import (
    get_next_upload_time, update_account_last_upload_time
)

logger = logging.getLogger(__name__)

def auto_schedule(func):
    """
    Decorator to automatically schedule the next upload time for AI-generated content.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
    
        # Get scheduled_date from form data
        scheduled_date = request.form.get('scheduled_date')
        user_id = request.form.get('user_id')
        username = request.form.get('user')
        
        if scheduled_date != 'auto':
            return func(*args, **kwargs)
        
        if not user_id or not username:
            logger.info("Auto-schedule skipped - missing user_id or username")
            return jsonify(
                {'error': 'Missing user_id or username for auto-scheduling'}), 400
                    
        try:
            # Fetch current next upload time
            next_upload_time = get_next_upload_time(user_id, username)
            logger.info(f"Current next upload time for {username} (user {user_id}): {next_upload_time}")
            
            if not next_upload_time:
                logger.warning(f"No next upload time set for {username} (user {user_id}), Database error")
                return func(*args, **kwargs)
            
            # Parse both times - ensure both are timezone-aware
            if next_upload_time.endswith('Z'):
                next_time_utc = datetime.fromisoformat(next_upload_time.replace('Z', '+00:00'))
            elif '+' in next_upload_time or next_upload_time.count('-') > 2:
                next_time_utc = datetime.fromisoformat(next_upload_time)
            else:
                # Assume UTC if no timezone
                next_time_utc = datetime.fromisoformat(next_upload_time).replace(tzinfo=pytz.UTC)
            
            now_utc = datetime.now(pytz.UTC)
            
            if next_time_utc < now_utc:
                logger.info(f"Next upload time {next_upload_time} is in the past, setting to None")
                next_upload_time = None
                now = datetime.utcnow().isoformat() + 'Z'
                update_account_last_upload_time(user_id, username, now)
                logger.info(f"Updated last upload time for {username} to {now}")
                
            
            g.upload_time = next_upload_time
        
        except Exception as e:
            logger.error(f"Error fetching next upload time for {username} (user {user_id}): {e}")
            return func(*args, **kwargs)
            
        return func(*args, **kwargs)
        
    return wrapper

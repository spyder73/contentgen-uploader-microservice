from functools import wraps
from models.db import (
    update_video_status, update_video_post_url, 
    add_scheduled_time, create_scheduled_job,
    get_account_by_username, update_next_upload_time,
    update_account_last_upload_time, create_video
)
from utils.upload_handler import parse_upload_response
from flask import request
from utils.determine_time import calculate_next_upload_time
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def calculate_and_update_next_upload_time(account):
    # Calculate next upload time, based on scheduled times using function in determine_time
    next_upload_time = calculate_next_upload_time(account)
    logger.info(f"Next upload time for {account['username']} is {next_upload_time}")
    
    # Update next_upload_time
    update_next_upload_time(account['user_id'], account['username'], next_upload_time)
    logger.info(f"Updated next upload time for {account['username']} to {next_upload_time}")
    
####
#TODO:
# This should be split into a tracking decorator
# and another tracker that handles the scheduling and calculation of times
####
def track_upload(func):
    """
    Decorator to track video upload status and URLs
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        response, status_code = func(*args, **kwargs)
        
        # Get video_id from form data
        video_id = request.form.get('video_id')
        user_id = request.form.get('user_id')
        account_username = request.form.get('user')
        scheduled_date = request.form.get('scheduled_date')
        caption = request.form.get('title', '')
        
        # Check if request came from Telegram
        source = request.headers.get('X-Source')
        
        if not video_id:
            video_id = uuid.uuid4()
            logger.info(f"No video_id provided, generated new id: {video_id}")
        
        # if the video comes outside of telegram, we need to add the video to the DB
        if source != 'telegram':
            create_video(video_id=video_id, caption=caption, 
                         user_id=user_id, status='external', reusable=False)
        
        # Current time
        now = datetime.utcnow().isoformat() + 'Z'
        
        try:
            # Parse response
            response_data = response.get_json() if hasattr(response, 'get_json') else {}
            status_code, parsed = parse_upload_response(response_data)
            logger.info(f"Raw parsed upload response for tracking {parsed}")
            
            logger.info(f"Tracking upload - source: {source}, video: {video_id}, user: {user_id}, account: {account_username}, status: {status_code}")
            
            # 1. Handle scheduled uploads
            if status_code == 202 and parsed.get('scheduled'):
                # Scheduled upload
                scheduled_date = parsed.get('scheduled_date')
                job_id = parsed.get('job_id')
                update_video_status(video_id, 'scheduled', scheduled_at=scheduled_date)
                logger.info(f"Video {video_id} scheduled for {scheduled_date}")
                
                if job_id:
                    # Create scheduled job entry
                    create_scheduled_job(
                        job_id=job_id,
                        video_id=video_id,
                        account_username=account_username,
                        user_id=user_id,
                        scheduled_date=scheduled_date
                    )
                    logger.info(f"Created scheduled job {job_id} for video {video_id}")
                
                # Add to scheduled_times array
                add_scheduled_time(user_id, account_username, scheduled_date)
                logger.info(f"✅ Added {scheduled_date} to {account_username}'s schedule queue")
                
                # Calculate next upload time, based on scheduled times using function in determine_time
                account = get_account_by_username(user_id, account_username)
                calculate_and_update_next_upload_time(account)
                
            # 2. Handle async background uploads
            elif status_code == 200 and parsed.get('async'):
                # Async background upload
                request_id = parsed.get('request_id')
                update_video_status(video_id, 'uploading')
                logger.info(f"Video {video_id} processing asynchronously with request_id: {request_id}")
                check_time = (datetime.utcnow() + timedelta(minutes=10)).isoformat() + 'Z'
                
                # Create a scheduled job to track async upload
                if request_id:
                    create_scheduled_job(
                        job_id=request_id,  
                        video_id=video_id,
                        account_username=account_username,
                        user_id=user_id,
                        scheduled_date=check_time,
                        is_async=True
                    )
                    logger.info(f"Created async tracking job {request_id} for video {video_id}")
                
                # Update last_upload_time:
                update_account_last_upload_time(user_id, account_username, now)
                
                account = get_account_by_username(user_id, account_username)
                calculate_and_update_next_upload_time(account)
                
            # 3. Handle immediate uploads:
            elif status_code == 200 and parsed.get('success') and parsed.get('uploaded'):
                # Immediate successful upload
                update_video_status(video_id, 'posted')
                update_account_last_upload_time(user_id, account_username, now)
                
                account = get_account_by_username(user_id, account_username)
                calculate_and_update_next_upload_time(account)
                
                # Save post URLs
                post_urls = parsed.get('post_urls', {})
                if post_urls:
                    # Join multiple URLs if multiple platforms  ^q  w
                    urls_str = ' | '.join([f"{p}: {url}" for p, url in post_urls.items()])
                    update_video_post_url(video_id, urls_str)
                    logger.info(f"Video {video_id} posted with URLs: {urls_str}")
                else:
                    logger.info(f"Video {video_id} posted successfully (couldn't fetch URL)")
            
            # Handle partial success:
            elif status_code == 207 and parsed.get('success') and parsed.get('partial'):
                # Partial success
                update_video_status(video_id, 'partial')
                update_account_last_upload_time(user_id, account_username, now)
                
                account = get_account_by_username(user_id, account_username)
                calculate_and_update_next_upload_time(account)
                
                post_urls = parsed.get('post_urls', {})
                if post_urls:
                    urls_str = ' | '.join([f"{p}: {url}" for p, url in post_urls.items()])
                    update_video_post_url(video_id, urls_str)
                    logger.info(f"Video {video_id} partially posted with URLs: {urls_str}")
                else:
                    logger.info(f"Video {video_id} partially posted")
            
            else:
                # Failed upload
                update_video_status(video_id, 'failed')
                logger.error(f"Video {video_id} upload failed")
                
        except Exception as e:
            logger.error(f"Error tracking upload for video {video_id}: {str(e)}")
        
        return response
    
    return wrapper

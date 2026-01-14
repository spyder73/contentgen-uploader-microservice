import os
import requests
import logging
from models.db import (
    get_accounts, get_pending_scheduled_jobs, get_pending_async_jobs, update_job_status, 
    update_video_status, update_video_post_url, 
    update_account_last_upload_time, remove_scheduled_time, clear_old_scheduled_times)
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

logger = logging.getLogger(__name__)

UPLOAD_POST_API_KEY = os.getenv('UPLOADPOST_API_KEY')
UPLOAD_POST_API_URL = 'https://api.upload-post.com/api/uploadposts'
TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN')


def check_scheduled_jobs():
    """
    Check all pending scheduled jobs and update their status.
    Uses upload-post /history endpoint to check completion.
    Also checks async upload status using request_id.
    """
    logger.info("Starting job checker...")
    
    try:
        # Separate scheduled jobs and async jobs
        scheduled_jobs = get_pending_scheduled_jobs()
        async_jobs = get_pending_async_jobs()
        
        if not scheduled_jobs and not async_jobs:
            logger.info("No pending jobs to check")
            return
        logger.info(f"Found {len(scheduled_jobs) + len(async_jobs)} pending jobs")
        
        # Check scheduled jobs via history endpoint
        if scheduled_jobs:
            history = fetch_upload_history()
            if history:
                history_map = {item['job_id']: item for item in history if item.get('job_id')}
                
                for job in scheduled_jobs:
                    job_id = job['job_id']
                    now = datetime.utcnow().isoformat() + 'Z'
                    
                    if job_id in history_map:
                        history_item = history_map[job_id]
                        
                        if history_item.get('success'):
                            post_url = history_item.get('post_url', '')
                            platform = history_item.get('platform', '')
                            
                            logger.info(f"Job {job_id} completed: {post_url}")
                            
                            update_job_status(job_id, 'completed', post_url)
                            update_video_status(job['video_id'], 'posted', post_url=post_url)
                            if post_url:
                                update_video_post_url(job['video_id'], post_url)
                            
                            notify_user_completion(
                                user_id=job['user_id'],
                                account=job['account_username'],
                                platform=platform,
                                post_url=post_url,
                                video_id=job['video_id']
                            )
                            
                            remove_scheduled_time(job['user_id'], job['account_username'], job['scheduled_date'])
                            logger.info(f"✅ Removed {job['scheduled_date']} from {job['account_username']}'s queue")
                            update_account_last_upload_time(job['user_id'], job['account_username'], now)
                        else:
                            logger.error(f"Job {job_id} failed")
                            update_job_status(job_id, 'failed')
                            
                            remove_scheduled_time(job['user_id'], job['account_username'], job['scheduled_date'])
                            logger.info(f"✅ Removed failed job {job_id} from {job['account_username']}'s queue")
                            
                            
                            notify_user_failure(
                                user_id=job['user_id'],
                                account=job['account_username'],
                                video_id=job['video_id']
                            )
        
        # Check async jobs via status endpoint
        for job in async_jobs:
            request_id = job['job_id']
            check_async_upload_status(job, request_id)
        
        # Clear old scheduled times
        logging.info("clearing old scheduled times...")
        all_users = set(job['user_id'] for job in (scheduled_jobs + async_jobs))
        for user_id in all_users:
            accounts = get_accounts(user_id)
            for account in accounts:
                clear_old_scheduled_times(user_id, account['username'])
        logger.info("Job checker completed")
        
    except Exception as e:
        logger.error(f"Job checker error: {str(e)}", exc_info=True)


def fetch_upload_history(limit=100):
    """
    Fetch recent upload history from upload-post API
    
    Returns:
        list: Array of upload history items
    """
    try:
        response = requests.get(
            f'{UPLOAD_POST_API_URL}/history',
            params={'limit': limit},
            headers={'Authorization': f'Apikey {UPLOAD_POST_API_KEY}'}
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('history', [])
        else:
            logger.error(f"Failed to fetch history: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        return []


def notify_user_completion(user_id, account, platform, post_url, video_id):
    """Send Telegram notification when video is posted"""
    try:
        message = (
            f'✅ Video Posted!\n\n'
            f'Account: {account}\n'
            f'Platform: {platform.upper()}\n'
            f'Video ID: {video_id[:20]}...\n\n'
            f'🔗 {post_url}'
        )
        
        send_telegram_message(user_id, message)
        
    except Exception as e:
        logger.error(f"Failed to send completion notification: {str(e)}")


def notify_user_failure(user_id, account, video_id):
    """Send Telegram notification when scheduled upload fails"""
    try:
        message = (
            f'❌ Scheduled Upload Failed\n\n'
            f'Account: {account}\n'
            f'Video ID: {video_id[:20]}...\n\n'
            f'Please check your account settings and try again.'
        )
        
        send_telegram_message(user_id, message)
        
    except Exception as e:
        logger.error(f"Failed to send failure notification: {str(e)}")


def send_telegram_message(user_id, message):
    """Send a message via Telegram Bot API"""
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        
        response = requests.post(url, json={
            'chat_id': user_id,
            'text': message,
            'parse_mode': 'HTML'
        })
        
        if response.status_code != 200:
            logger.error(f"Failed to send Telegram message: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")


def check_async_upload_status(job, request_id):
    """Check status of async upload using request_id"""
    try:
        response = requests.get(
            f'{UPLOAD_POST_API_URL}/status',
            params={'request_id': request_id},
            headers={'Authorization': f'Apikey {UPLOAD_POST_API_KEY}'}
        )
        
        if response.status_code != 200:
            logger.warning(f"Failed to fetch async status for {request_id}: {response.status_code}")
            return
        
        data = response.json()
        status = data.get('status')
        now = datetime.utcnow().isoformat() + 'Z'
        
        if status == 'completed':
            # All platforms completed
            results = data.get('results', [])
            succeeded = [r for r in results if r.get('success')]
            failed = [r for r in results if not r.get('success')]
            
            if succeeded:
                # Get URLs from successful uploads
                post_urls = {}
                for result in succeeded:
                    platform = result.get('platform')
                    url = result.get('url', '')
                    if url:
                        post_urls[platform] = url
                
                if post_urls:
                    urls_str = ' | '.join([f"{p}: {url}" for p, url in post_urls.items()])
                    update_video_post_url(job['video_id'], urls_str)
                    logger.info(f"Async video {job['video_id']} completed with URLs: {urls_str}")
                
                # Determine final status
                if failed:
                    update_video_status(job['video_id'], 'partial')
                    update_job_status(request_id, 'completed', urls_str if post_urls else None)
                else:
                    update_video_status(job['video_id'], 'posted')
                    update_job_status(request_id, 'completed', urls_str if post_urls else None)
                
                # Update last_upload_time
                update_account_last_upload_time(job['user_id'], job['account_username'], now)
                
                # Remove from scheduled_times (using video_id as identifier)
                remove_scheduled_time(job['user_id'], job['account_username'], job['video_id'])
                logger.info(f"✅ Removed async job {request_id} from {job['account_username']}'s queue")
                
                # Notify user
                platforms_str = ', '.join([r['platform'].upper() for r in succeeded])
                message = f'✅ Async Upload Completed!\n\nAccount: {job["account_username"]}\nPlatforms: {platforms_str}\n'
                
                if post_urls:
                    message += '\n🔗 Links:\n'
                    for platform, url in post_urls.items():
                        message += f'  • {platform.upper()}: {url}\n'
                
                send_telegram_message(job['user_id'], message)
            else:
                # All failed
                update_video_status(job['video_id'], 'failed')
                update_job_status(request_id, 'failed')
                
                # Remove from scheduled_times even on failure
                remove_scheduled_time(job['user_id'], job['account_username'], job['video_id'])
                logger.info(f"✅ Removed failed async job {request_id} from {job['account_username']}'s queue")
                
                notify_user_failure(
                    user_id=job['user_id'],
                    account=job['account_username'],
                    video_id=job['video_id']
                )
        
        elif status == 'failed':
            update_video_status(job['video_id'], 'failed')
            update_job_status(request_id, 'failed')
            
            # Remove from scheduled_times
            remove_scheduled_time(job['user_id'], job['account_username'], job['video_id'])
            logger.info(f"✅ Removed failed async job {request_id} from {job['account_username']}'s queue")
            
            notify_user_failure(
                user_id=job['user_id'],
                account=job['account_username'],
                video_id=job['video_id']
            )
        
            
    except Exception as e:
        logger.error(f"Error checking async status for {request_id}: {str(e)}")
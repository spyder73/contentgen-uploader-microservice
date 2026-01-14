import os

import requests
from auth import require_auth
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

WAITING_VIDEO = 0
WAITING_CAPTION = 1
WAITING_REUSABLE = 2  # ADD THIS

# ==== HELPER FUNCTIONS ====
async def fetch_videos(user_id, status='available'):
    """Reusable function to fetch videos"""
    response = requests.get(
        f'{API_URL}/list-videos',
        params={'user_id': str(user_id), 'status': status},
        headers={'Authorization': f'Bearer {API_TOKEN}'}
    )
    
    if response.status_code == 200:
        return response.json().get('videos', [])
    return None


async def fetch_accounts(user_id):
    """Reusable function to fetch accounts"""
    response = requests.get(
        f'{API_URL}/list-accounts',
        params={'user_id': str(user_id)},
        headers={'Authorization': f'Bearer {API_TOKEN}'}
    )
    
    if response.status_code == 200:
        return response.json().get('accounts', [])
    return None


# ==== ADD VIDEO ====
@require_auth
async def add_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add video flow"""
    if not update.message:
        return
    
    await update.message.reply_text(
        'Send me a video to add.\n'
        'Or /cancel to abort.'
    )
    return WAITING_VIDEO

async def add_video_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the video"""
    if not update.message:
        return
    
    if not update.message.video:
        await update.message.reply_text('Please send a video file.')
        return WAITING_VIDEO
    
    video = update.message.video
    
    # Check file size (Telegram Bot API limit is 20 MB)
    file_size_mb = video.file_size / (1024 * 1024) if video.file_size else 0
    
    if file_size_mb > 20:
        await update.message.reply_text(
            f'❌ Video too large ({file_size_mb:.1f} MB)\n\n'
            f'Telegram Bot API limit: 20 MB\n\n'
            f'Please compress your video before uploading.'
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text('Video received! Now, please send me the caption for this video.')
    
    # Store video info
    video_id = video.file_id
    context.user_data['video_id'] = video_id # type: ignore
    
    return WAITING_CAPTION

async def add_video_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return WAITING_CAPTION
    
    assert context.user_data is not None
    
    caption = update.message.text
    video_id = context.user_data.get('video_id')
    
    if not video_id:
        await update.message.reply_text('No video found. Please start over with /addvideo')
        return ConversationHandler.END
    
    # Ask if reusable
    context.user_data['video_caption'] = caption
    await update.message.reply_text('Is this video reusable on other accounts (spoofing)? (yes/no):')
    return WAITING_REUSABLE  # NEW STATE

async def add_video_reusable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reusable choice"""
    if not update.message or not update.effective_user or not update.message.text:
        return WAITING_REUSABLE
    
    assert context.user_data is not None
    
    user_id = update.effective_user.id
    video_id = context.user_data.get('video_id')
    caption = context.user_data.get('video_caption')
    reusable = update.message.text.lower() in ['yes', 'y', 'true', '1']
    
    try:
        response = requests.post(
            f'{API_URL}/add-video',
            json={
                'video_id': video_id,
                'caption': caption,
                'user_id': str(user_id),
                'reusable': reusable  # ADD THIS
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 201:
            reuse_msg = '♻️ Spoofable' if reusable else '🔒 One-time use'
            await update.message.reply_text(f'✅ Video added! ({reuse_msg})')
        elif response.status_code == 409:
            await update.message.reply_text('⚠️ This video already exists')
        else:
            await update.message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')
        
    context.user_data.clear()
    return ConversationHandler.END


# ==== LIST VIDEOS =====
@require_auth
async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        response = requests.get(
            f'{API_URL}/list-videos',
            params={'user_id': str(user_id), 'status': 'available'},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
            )
        
        if response.status_code == 200:
            videos = response.json().get('videos', [])
            
            if not videos:
                await update.message.reply_text('No available videos. Upload something.')
                return

            message = 'Available Videos:\n\n'
            for i, video in enumerate(videos, 1):
                caption = video['caption'][:]
                message += f"{i}. {caption}\n ID: {video['video_id'][:]}\n\n"
                
            await update.message.reply_text(message)
        else:
            await update.message.reply_text('Failed to fetch videos')
            
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')


@require_auth
async def list_posted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        response = requests.get(
            f'{API_URL}/list-videos',
            params={'user_id': str(user_id), 'status': 'posted'},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            videos = response.json().get('videos', [])
            
            if not videos:
                await update.message.reply_text('No videos posted yet.')
                return

            message = '✅ Posted Videos:\n\n'
            for i, video in enumerate(videos, 1):
                caption = video['caption'][:50]
                posted_at = video.get('posted_at', 'N/A')
                post_url = video.get('post_url', '')  # ADD THIS
                
                message += f"{i}. {caption}...\n"
                message += f"   ID: {video['video_id'][:20]}...\n"
                message += f"   Posted: {posted_at}\n"
                
                # ADD THIS: Display URL if available
                if post_url:
                    message += f"   🔗 {post_url}\n"
                
                message += "\n"
                
            await update.message.reply_text(message)
        else:
            await update.message.reply_text('Failed to fetch posted videos')
            
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')
            
@require_auth
async def list_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if not update.message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        response = requests.get(
            f'{API_URL}/list-videos',
            params={'user_id': str(user_id), 'status': 'scheduled'},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
            )
        
        if response.status_code == 200:
            videos = response.json().get('videos', [])
            
            if not videos:
                await update.message.reply_text('No videos scheduled yet.')
                return

            message = '📅 Scheduled Videos:\n\n'
            for i, video in enumerate(videos, 1):
                caption = video['caption'][:]
                message += f"{i}. {caption}\n ID: {video['video_id'][:]}\n Scheduled at: {video.get('scheduled_at', 'N/A')}\n\n"
                
            await update.message.reply_text(message)
        else:
            await update.message.reply_text('Failed to fetch scheduled videos')
            
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')

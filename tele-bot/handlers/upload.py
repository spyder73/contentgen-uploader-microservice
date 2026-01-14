import os
import json
import requests
from auth import require_auth
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.ai import user_models
from utils.upload_parser import response_formatting

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

WAITING_UPLOAD_VIDEO = 10
WAITING_UPLOAD_AI_CHOICE = 11
WAITING_UPLOAD_AI_PROMPT = 12
WAITING_UPLOAD_CAPTION = 13

caption_prompt = (
    "You are supposed to just return a caption compatible for social media, "
    "just return that string of text, nothing else, add the hashtags after a "
    "line break using \n. Example Caption: 'What would you do?\n #beautiful #mesmerizing #fyp'"
)


# ==== UPLOAD (immediate) ====
@require_auth
async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /upload <account>
    Example: /upload myaccount
    """
    message = update.effective_message
    if not message or not update.effective_user:
        return ConversationHandler.END
    
    if not context.args:
        await message.reply_text(
            '📤 Upload Command\n\n'
            'Usage: /upload <account>\n'
            'Example: /upload myaccount\n\n'
            'Use /listaccounts to see available accounts.'
        )
        return ConversationHandler.END
    
    assert context.user_data is not None
    account_username = ' '.join(context.args)
    user_id = update.effective_user.id
    
    try:
        response = requests.get(
            f'{API_URL}/list-accounts',
            params={'user_id': str(user_id)},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code != 200:
            await message.reply_text('Failed to fetch accounts')
            return ConversationHandler.END
        
        accounts = response.json().get('accounts', [])
        account = next((a for a in accounts if a['username'] == account_username), None)
        
        if not account:
            await message.reply_text(
                f'⚠️ Account "{account_username}" not found\n\n'
                f'Use /listaccounts to see available accounts.'
            )
            return ConversationHandler.END
        
        context.user_data['upload_account'] = account
        await message.reply_text('Send me the video to upload:')
        return WAITING_UPLOAD_VIDEO
        
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
        return ConversationHandler.END


async def upload_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive video for immediate upload"""
    message = update.effective_message
    if not message or not message.video:
        if message:
            await message.reply_text('Please send a video file.')
        return WAITING_UPLOAD_VIDEO
    
    video = message.video
    
    # Check file size (Telegram Bot API limit is 20 MB)
    file_size_mb = video.file_size / (1024 * 1024) if video.file_size else 0
    
    if file_size_mb > 20:
        await message.reply_text(
            f'❌ Video too large ({file_size_mb:.1f} MB)\n\n'
            f'Telegram Bot API limit: 20 MB\n\n'
            f'Please compress your video before uploading.'
        )
        return ConversationHandler.END
    
    assert context.user_data is not None
    context.user_data['upload_video_id'] = message.video.file_id
    
    await message.reply_text('Generate caption with AI? (yes/no):')
    return WAITING_UPLOAD_AI_CHOICE


async def upload_ai_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI generation choice"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_UPLOAD_AI_CHOICE
    
    assert context.user_data is not None
    use_ai = message.text.lower() in ['yes', 'y', 'true', '1']
    
    if use_ai:
        await message.reply_text('Enter your prompt for AI caption generation:')
        return WAITING_UPLOAD_AI_PROMPT
    else:
        await message.reply_text('Enter your caption:')
        return WAITING_UPLOAD_CAPTION


async def upload_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate caption with AI"""
    message = update.effective_message
    if not message or not message.text or not update.effective_user:
        return WAITING_UPLOAD_AI_PROMPT
    
    assert context.user_data is not None
    user_prompt = message.text
    user_id = update.effective_user.id
    model = user_models.get(user_id, 'x-ai/grok-4-fast')
    
    full_prompt = f"{user_prompt}\n\n{caption_prompt}"
    
    try:
        await message.reply_text('🤖 Generating caption...')
        
        response = requests.post(
            f'{API_URL}/inference',
            json={'text': full_prompt, 'model': model},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            result = response.json()
            caption = result.get('content', '')
            context.user_data['upload_caption'] = caption
            
            await message.reply_text(f'Generated caption:\n\n{caption}\n\nUploading...')
            return await finalize_upload(update, context)
        else:
            await message.reply_text('❌ AI generation failed. Please enter caption manually:')
            return WAITING_UPLOAD_CAPTION
            
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}\n\nPlease enter caption manually:')
        return WAITING_UPLOAD_CAPTION


async def upload_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive manual caption"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_UPLOAD_CAPTION
    
    assert context.user_data is not None
    context.user_data['upload_caption'] = message.text
    
    await message.reply_text('Uploading...')
    return await finalize_upload(update, context)


async def finalize_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload video to platform"""
    message = update.effective_message
    if not message or not update.effective_user:
        return ConversationHandler.END
    
    assert context.user_data is not None
    
    account = context.user_data.get('upload_account')
    video_id = context.user_data.get('upload_video_id')
    caption = context.user_data.get('upload_caption')
    user_id = update.effective_user.id
    
    assert video_id is not None
    assert account is not None
    assert caption is not None
    
    try:
        create_response = requests.post(
            f'{API_URL}/add-video',
            json={
                'video_id': video_id,
                'caption': caption,
                'user_id': str(user_id),
                'status': 'uploading'
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if create_response.status_code not in [201, 409]:
            await message.reply_text('❌ Failed to register video')
            return ConversationHandler.END
        
        file = await context.bot.get_file(video_id)
        video_path = f'/tmp/{video_id}.mp4'
        await file.download_to_drive(video_path)
        
        try:
            optional_params = {}
            if account.get('is_ai'):
                optional_params['is_aigc'] = True
            
            with open(video_path, 'rb') as f:
                upload_response = requests.post(
                    f'{API_URL}/upload-video',
                    files={'video': (f'{video_id}.mp4', f, 'video/mp4')},
                    data={
                        'title': caption,
                        'user': account['username'],
                        'user_id': str(user_id),
                        'platforms': json.dumps(account['platforms']),
                        'video_id': video_id,
                        'params': json.dumps(optional_params) if optional_params else None
                    },
                    headers={
                        'Authorization': f'Bearer {API_TOKEN}',
                        'X-Source': 'telegram'
                    }
                )
            
            msg = response_formatting(upload_response)
            await message.reply_text(msg)
            
        finally:
            if os.path.exists(video_path):
                os.remove(video_path)
                
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
    
    context.user_data.clear()
    return ConversationHandler.END
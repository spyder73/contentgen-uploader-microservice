import os
import json
import requests
from auth import require_auth
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.ai import user_models
from utils.upload_parser import response_formatting
from utils.determine_time import cet_to_utc

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

WAITING_KEEP_CAPTION = 20
WAITING_AI_CHOICE = 21
WAITING_AI_PROMPT = 22
WAITING_NEW_CAPTION = 23

caption_prompt = (
    "You are supposed to just return a caption compatible for social media, "
    "just return that string of text, nothing else, add the hashtags after a "
    "line break using \n. Example Caption: 'What would you do?\n #beautiful #mesmerizing #fyp'"
)


# ==== SCHEDULE ====
@require_auth
async def schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /schedule <video_index> <account> [datetime]
    Example: /schedule 1 myaccount 2025-11-15T14:30:00
    Or: /schedule 1 myaccount (auto-calculates time if autoposting enabled)
    """
    message = update.effective_message
    if not message or not update.effective_user:
        return ConversationHandler.END
    
    if not context.args or len(context.args) < 2:
        await message.reply_text(
            '📅 Schedule Command\n\n'
            'Usage: /schedule <video_index> <account> [datetime]\n'
            'Examples:\n'
            '  • /schedule 1 myaccount 2025-11-15T14:30:00\n'
            '  • /schedule 1 myaccount (auto-schedule)\n\n'
            'Use /listvideos to see available videos.'
        )
        return ConversationHandler.END
    
    assert context.user_data is not None
    user_id = update.effective_user.id
    
    try:
        video_index = int(context.args[0]) - 1
        account_username = context.args[1]
        scheduled_date_input = context.args[2] if len(context.args) > 2 else None
        
        # Fetch videos and accounts
        videos_response = requests.get(
            f'{API_URL}/list-videos',
            params={'user_id': str(user_id), 'status': 'available'},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        accounts_response = requests.get(
            f'{API_URL}/list-accounts',
            params={'user_id': str(user_id)},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if videos_response.status_code != 200 or accounts_response.status_code != 200:
            await message.reply_text('Failed to fetch data')
            return ConversationHandler.END
        
        videos = videos_response.json().get('videos', [])
        accounts = accounts_response.json().get('accounts', [])
        
        if not videos:
            await message.reply_text('No available videos to schedule')
            return ConversationHandler.END
        
        if video_index < 0 or video_index >= len(videos):
            await message.reply_text(f'Invalid index. Choose 1-{len(videos)}')
            return ConversationHandler.END
        
        video = videos[video_index]
        account = next((a for a in accounts if a['username'] == account_username), None)
        
        if not account:
            await message.reply_text(f'Account "{account_username}" not found')
            return ConversationHandler.END
        
        # Calculate time if not provided
        if not scheduled_date_input:
            # Use auto-scheduling (backend will calculate)
            scheduled_date = 'auto'
            await message.reply_text('🤖 Auto-scheduling enabled (backend will calculate optimal time)')
        else:
            try:
                scheduled_date = cet_to_utc(scheduled_date_input)  # Still convert CET → UTC
                await message.reply_text(f'📅 Scheduled for: {scheduled_date_input} CET')
            except Exception as e:
                await message.reply_text(
                    '❌ Invalid datetime format.\n'
                    'Use: YYYY-MM-DDTHH:MM:SS (CET)\n'
                    'Example: 2025-11-18T17:30:00\n'
                    f'Error: {e}'
                )
                return ConversationHandler.END
        
        # Store data
        context.user_data['schedule_video'] = video
        context.user_data['schedule_account'] = account
        context.user_data['schedule_datetime'] = scheduled_date  # Now either 'auto' or UTC string

        # Ask about caption
        caption_preview = 'Auto-scheduled' if scheduled_date == 'auto' else f'{scheduled_date} UTC'
        await message.reply_text(
            f'📹 Video: {video["caption"][:100]}...\n'
            f'👤 Account: {account_username}\n'
            f'🕒 Time: {caption_preview}\n\n'
            f'Keep this caption? (yes/no):'
        )
        return WAITING_KEEP_CAPTION
        
    except ValueError as e:
        await message.reply_text(f'Invalid format: {str(e)}')
        return ConversationHandler.END
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
        return ConversationHandler.END


async def schedule_keep_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask if user wants to keep current caption"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_KEEP_CAPTION
    
    assert context.user_data is not None
    keep = message.text.lower() in ['yes', 'y', 'keep', '1']
    
    if keep:
        # Keep caption, schedule immediately
        video = context.user_data.get('schedule_video')
        assert video is not None
        context.user_data['schedule_caption'] = video['caption']
        
        await message.reply_text('⏳ Scheduling...')
        return await finalize_schedule(update, context)
    else:
        # Ask if they want AI or manual caption
        await message.reply_text('Generate new caption with AI? (yes/no):')
        return WAITING_AI_CHOICE


async def schedule_ai_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask if user wants AI-generated caption"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_AI_CHOICE
    
    use_ai = message.text.lower() in ['yes', 'y', '1']
    
    if use_ai:
        await message.reply_text('Enter your prompt for AI caption generation:')
        return WAITING_AI_PROMPT
    else:
        await message.reply_text('Enter new caption:')
        return WAITING_NEW_CAPTION


async def schedule_ai_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate caption with AI"""
    message = update.effective_message
    if not message or not message.text or not update.effective_user:
        return WAITING_AI_PROMPT
    
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
            context.user_data['schedule_caption'] = caption
            
            await message.reply_text(
                f'✨ Generated caption:\n\n{caption}\n\n'
                f'⏳ Scheduling...'
            )
            return await finalize_schedule(update, context)
        else:
            await message.reply_text('❌ AI generation failed. Please enter caption manually:')
            return WAITING_NEW_CAPTION
            
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}\n\nPlease enter caption manually:')
        return WAITING_NEW_CAPTION


async def schedule_new_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive manual caption"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_NEW_CAPTION
    
    assert context.user_data is not None
    context.user_data['schedule_caption'] = message.text
    
    await message.reply_text('⏳ Scheduling...')
    return await finalize_schedule(update, context)


async def finalize_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedule the video upload"""
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    
    assert context.user_data is not None
    
    video = context.user_data.get('schedule_video')
    account = context.user_data.get('schedule_account')
    scheduled_date = context.user_data.get('schedule_datetime')
    
    assert video is not None
    assert account is not None
    assert scheduled_date is not None
    assert update.effective_user is not None
    
    caption = context.user_data.get('schedule_caption', video['caption'])
    user_id = update.effective_user.id
    
    try:
        file = await context.bot.get_file(video['video_id'])
        video_path = f'/tmp/{video["video_id"]}.mp4'
        await file.download_to_drive(video_path)
        
        try:
            optional_params = {}
            if account.get('is_ai'):
                optional_params['is_aigc'] = True
            
            with open(video_path, 'rb') as f:
                upload_response = requests.post(
                    f'{API_URL}/upload-video',
                    files={'video': (f'{video["video_id"]}.mp4', f, 'video/mp4')},
                    data={
                        'title': caption,
                        'user': account['username'],
                        'user_id': str(user_id),
                        'platforms': json.dumps(account['platforms']),
                        'video_id': video['video_id'],
                        'scheduled_date': scheduled_date,
                        'params': json.dumps(optional_params) if optional_params else None
                    },
                    headers={
                        'Authorization': f'Bearer {API_TOKEN}',
                        'X-Source': 'telegram'
                    }
                )
                
                result = upload_response.json()
                if upload_response.status_code == 202 and result.get('job_id'):
                    job_id = result['job_id']
                    
                    # Store job in database
                    requests.post(
                        f'{API_URL}/track-job',
                        json={
                            'job_id': job_id,
                            'video_id': video['video_id'],
                            'account_username': account['username'],
                            'user_id': str(user_id),
                            'scheduled_date': scheduled_date
                        },
                        headers={'Authorization': f'Bearer {API_TOKEN}'}
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
import os
import requests
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from auth import require_auth
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

WAITING_USERNAME = 1
WAITING_PLATFORMS = 2
WAITING_IS_AI = 3
WAITING_AUTOPOST_ENABLED = 4
WAITING_AUTOPOST_FREQUENCY = 5
WAITING_AUTOPOST_DAILY_POSTS = 6

# Platform daily post limits
PLATFORM_LIMITS = {
    'tiktok': 15,
    'instagram': 50,
    'x': 50,
    'threads': 50,
    'youtube': 10,
    'facebook': 25
}


# ==== ADD ACCOUNT ====
@require_auth
async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    await update.message.reply_text('Enter username for the social media account from upload-post.com below:')
    return WAITING_USERNAME

async def add_account_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    assert context.user_data is not None
    context.user_data['username'] = update.message.text
    await update.message.reply_text('Enter platforms (comma separated, e.g., tiktok,instagram) below:')
    return WAITING_PLATFORMS

async def add_account_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return WAITING_PLATFORMS
    
    assert context.user_data is not None
    
    platforms = [p.strip() for p in message.text.split(',')]
    context.user_data['platforms'] = platforms
    
    await message.reply_text('Is this an AI-generated content account? (yes/no):')
    return WAITING_IS_AI

async def add_account_is_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return WAITING_IS_AI
    
    assert context.user_data is not None

    is_ai = message.text.lower() in ['yes', 'y', 'true', '1']
    context.user_data['is_ai'] = is_ai
    
    await message.reply_text('Enable autoposting? (yes/no):')
    return WAITING_AUTOPOST_ENABLED

async def add_account_autopost_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return WAITING_AUTOPOST_ENABLED
    
    assert context.user_data is not None
    
    autopost_enabled = message.text.lower() in ['yes', 'y', 'true', '1']
    context.user_data['autopost_enabled'] = autopost_enabled
    
    if autopost_enabled:
        await message.reply_text('Posting frequency? (daily/weekly):')
        return WAITING_AUTOPOST_FREQUENCY
    else:
        # Skip to account creation
        return await add_account(update, context)


async def add_account_autopost_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return WAITING_AUTOPOST_FREQUENCY
    
    frequency = message.text.lower()
    if frequency not in ['daily', 'weekly']:
        await message.reply_text('Invalid frequency. Choose: daily, or weekly')
        return WAITING_AUTOPOST_FREQUENCY
    
    assert context.user_data is not None
    context.user_data['posting_frequency'] = frequency
    context.user_data['daily_posts'] = {}
    context.user_data['current_platform_index'] = 0
    
    # Start collecting daily posts per platform
    return await ask_next_platform_posts(update, context)



async def ask_next_platform_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for daily posts for the next platform"""
    message = update.effective_message
    if not message:
        return WAITING_AUTOPOST_DAILY_POSTS
    
    assert context.user_data is not None
    platforms = context.user_data.get('platforms', [])
    current_index = context.user_data.get('current_platform_index', 0)
    
    if current_index >= len(platforms):
        # All platforms done, finalize
        return await add_account(update, context)
    
    platform = platforms[current_index]
    limit = PLATFORM_LIMITS.get(platform, 50)
    
    await message.reply_text(
        f'How many posts per day for {platform.upper()}?\n'
        f'Maximum: {limit} posts/day'
    )
    return WAITING_AUTOPOST_DAILY_POSTS


async def add_account_autopost_daily_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return WAITING_AUTOPOST_DAILY_POSTS
    
    assert context.user_data is not None
    platforms = context.user_data.get('platforms', [])
    current_index = context.user_data.get('current_platform_index', 0)
    platform = platforms[current_index]
    limit = PLATFORM_LIMITS.get(platform, 50)
    
    try:
        daily_posts = int(message.text)
        if daily_posts < 1 or daily_posts > limit:
            await message.reply_text(
                f'Invalid number. Must be between 1 and {limit} for {platform}.\n'
                f'Please try again:'
            )
            return WAITING_AUTOPOST_DAILY_POSTS
    except ValueError:
        await message.reply_text('Invalid number. Please enter a valid integer:')
        return WAITING_AUTOPOST_DAILY_POSTS
    
    # Store this platform's daily posts
    context.user_data['daily_posts'][platform] = daily_posts
    
    # Move to next platform
    context.user_data['current_platform_index'] = current_index + 1
    
    # Ask for next platform or finalize
    return await ask_next_platform_posts(update, context)


async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    message = update.effective_message
    if not message or not update.effective_user:
        return ConversationHandler.END
    
    assert context.user_data is not None
    user_id = update.effective_user.id
    username = context.user_data.get('username')
    platforms = context.user_data.get('platforms', [])
    is_ai = context.user_data.get('is_ai', False)
    autopost_enabled = context.user_data.get('autopost_enabled', False)
    
    
    # Build autoposting properties
    autoposting_properties = {
        'enabled': autopost_enabled
    }
    
    if autopost_enabled:
        autoposting_properties['posting_frequency'] = context.user_data.get('posting_frequency', 'daily')
        autoposting_properties['daily_posts'] = context.user_data.get('daily_posts', {})
    
    
    try:
        response = requests.post(
            f'{API_URL}/add-account',
            json={
                'user_id': str(user_id),
                'username': username,
                'platforms': platforms,
                'is_ai': is_ai,
                'autoposting_properties': autoposting_properties
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 201:
            summary = (
                f'✅ Account added!\n\n'
                f'Username: {username}\n'
                f'Platforms: {", ".join(platforms)}\n'
                f'AI Content: {"Yes" if is_ai else "No"}\n'
                f'Autoposting: {"Enabled" if autopost_enabled else "Disabled"}'
            )
            if autopost_enabled:
                summary += (
                    f'\n  • Frequency: {autoposting_properties["posting_frequency"]}\n'
                    f'  • Posts/day: {autoposting_properties["daily_posts"]}'
                )
            await message.reply_text(summary)
        elif response.status_code == 409:
            await message.reply_text('Account already exists.')
        else:
            await message.reply_text(f'Error: {response.json().get("error")}')
    except Exception as e:
        await message.reply_text(f'Error: {str(e)}')
        
    context.user_data.clear()
    return ConversationHandler.END

@require_auth
async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        response = requests.get(
            f'{API_URL}/list-accounts',
            params={'user_id': str(user_id)},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            accounts = response.json().get('accounts', [])
            
            if not accounts:
                await message.reply_text('No accounts found. Add one using /addaccount')
                return

            text = '📱 Your Accounts:\n\n'
            for i, account in enumerate(accounts, 1):
                username = account['username']
                platforms = ', '.join(account['platforms'])
                is_ai = '🤖' if account.get('is_ai') else ''
                autopost = account.get('autoposting_properties', {})
                autopost_status = '🔄' if autopost.get('enabled') else ''
                
                text += f"{i}. {username} {is_ai}{autopost_status}\n"
                text += f"   Platforms: {platforms}\n"
                
                if autopost.get('enabled'):
                    daily_posts = autopost.get('daily_posts', {})
                    posts_summary = ', '.join([f"{p}: {c}" for p, c in daily_posts.items()])
                    text += f"   Autopost: {autopost.get('posting_frequency')}\n"
                    text += f"   Posts/day: {posts_summary}\n"
                
                text += '\n'
            
            text += '\n🤖 = AI content | 🔄 = Autoposting enabled'
            await message.reply_text(text)
        else:
            await message.reply_text('Failed to fetch accounts')
            
    except Exception as e:
        await message.reply_text(f'Error: {str(e)}')


@require_auth
async def delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /deleteaccount <username>
    """
    
    if not update.message or not update.effective_user: 
        return
    
    if not context.args:
        await update.message.reply_text('Usage: /deleteaccount <username>')
        return
    
    username = ' '.join(context.args)
    user_id = update.effective_user.id
    
    try:
        response = requests.delete(
            f'{API_URL}/delete-account',
            json={
                'user_id': str(user_id),
                'username': username
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            await update.message.reply_text(f'✅ Account "{username}" deleted')
        elif response.status_code == 404:
            await update.message.reply_text(f'⚠️ Account "{username}" not found')
        else:
            await update.message.reply_text(f'❌ Error: {response.json().get("error")}')
            
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')
import os
import requests
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from auth import require_auth
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

WAITING_SETTING_CHOICE = 1
WAITING_IS_AI_UPDATE = 2
WAITING_AUTOPOST_ENABLED_UPDATE = 3
WAITING_AUTOPOST_FREQUENCY_UPDATE = 4
WAITING_AUTOPOST_DAILY_POSTS_UPDATE = 5
WAITING_PLATFORMS_UPDATE = 6
WAITING_DOWNTIME_HOURS = 7

# Platform daily post limits
PLATFORM_LIMITS = {
    'tiktok': 15,
    'instagram': 50,
    'x': 50,
    'threads': 50,
    'youtube': 10,
    'facebook': 50
}


@require_auth
async def settings_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /settings <username>
    Example: /settings vibepollz
    """
    message = update.effective_message
    if not message or not update.effective_user:
        return ConversationHandler.END
    
    if not context.args:
        await message.reply_text(
            '⚙️ Settings Command\n\n'
            'Usage: /settings <username>\n'
            'Example: /settings vibepollz\n\n'
            'Use /listaccounts to see your accounts.'
        )
        return ConversationHandler.END
    
    username = ' '.join(context.args)
    user_id = update.effective_user.id
    
    # Fetch account details
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
        account = next((a for a in accounts if a['username'] == username), None)
        
        if not account:
            await message.reply_text(f'⚠️ Account "{username}" not found')
            return ConversationHandler.END
        
        # Store account info
        assert context.user_data is not None
        context.user_data['settings_username'] = username
        context.user_data['settings_account'] = account
        
        # Show current settings
        platforms = ', '.join(account['platforms'])
        is_ai = '🤖 Yes' if account.get('is_ai') else '❌ No'
        autopost = account.get('autoposting_properties', {})
        autopost_enabled = '🔄 Enabled' if autopost.get('enabled') else '❌ Disabled'
        
        settings_text = (
            f'⚙️ Settings for {username}\n\n'
            f'Platforms: {platforms}\n'
            f'AI Content: {is_ai}\n'
            f'Autoposting: {autopost_enabled}\n'
        )
        
        if autopost.get('enabled'):
            daily_posts = autopost.get('daily_posts', {})
            posts_summary = ', '.join([f"{p}: {c}" for p, c in daily_posts.items()])
            settings_text += (
                f'  • Frequency: {autopost.get("posting_frequency")}\n'
                f'  • Posts/day: {posts_summary}\n'
            )
        
        settings_text += (
            '\nWhat would you like to change?\n\n'
            '1️⃣ AI Content setting\n'
            '2️⃣ Autoposting settings\n'
            '3️⃣ Platforms\n'  
            '❌ Cancel\n\n'
            'Reply with the number:'
        )
        
        await message.reply_text(settings_text)
        return WAITING_SETTING_CHOICE
        
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
        return ConversationHandler.END


async def settings_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's choice of what to update"""
    message = update.effective_message
    if not message or not message.text or not context.user_data:
        return WAITING_SETTING_CHOICE
    
    choice = message.text.strip()
    
    if choice == '1':
        # Update AI setting
        account = context.user_data.get('settings_account', {})
        current = 'Yes' if account.get('is_ai') else 'No'
        await message.reply_text(
            f'Current AI Content setting: {current}\n\n'
            f'Enable AI content? (yes/no):'
        )
        return WAITING_IS_AI_UPDATE
    
    elif choice == '2':
        # Update autoposting
        account = context.user_data.get('settings_account', {})
        autopost = account.get('autoposting_properties', {})
        current = 'Enabled' if autopost.get('enabled') else 'Disabled'
        await message.reply_text(
            f'Current Autoposting: {current}\n\n'
            f'Enable autoposting? (yes/no):'
        )
        return WAITING_AUTOPOST_ENABLED_UPDATE
    
    elif choice == '3':  # ADD THIS BLOCK
        # Update platforms
        account = context.user_data.get('settings_account', {})
        current_platforms = ', '.join(account.get('platforms', []))
        await message.reply_text(
            f'Current platforms: {current_platforms}\n\n'
            f'Enter new platforms (comma separated):\n'
            f'Available: tiktok, instagram, youtube, facebook, x, threads, linkedin\n\n'
            f'Example: tiktok,instagram,youtube'
        )
        return WAITING_PLATFORMS_UPDATE
    
    else:
        await message.reply_text('Invalid choice. Reply with 1, 2, or 3:')
        return WAITING_SETTING_CHOICE


async def update_is_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update AI content setting"""
    message = update.effective_message
    if not message or not message.text or not update.effective_user or not context.user_data:
        return WAITING_IS_AI_UPDATE
    
    is_ai = message.text.lower() in ['yes', 'y', 'true', '1']
    username = context.user_data.get('settings_username')
    user_id = update.effective_user.id
    
    try:
        response = requests.patch(
            f'{API_URL}/update-account',
            json={
                'user_id': str(user_id),
                'username': username,
                'is_ai': is_ai
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            await message.reply_text(f'✅ AI Content setting updated to: {"Yes" if is_ai else "No"}')
        else:
            await message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
    
    context.user_data.clear()
    return ConversationHandler.END


async def update_autopost_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update autoposting enabled/disabled"""
    message = update.effective_message
    if not message or not message.text or not context.user_data:
        return WAITING_AUTOPOST_ENABLED_UPDATE
    
    autopost_enabled = message.text.lower() in ['yes', 'y', 'true', '1']
    context.user_data['autopost_enabled'] = autopost_enabled
    
    if not autopost_enabled:
        # Disable autoposting and finish
        return await finalize_autopost_update(update, context)
    
    # Continue to frequency
    await message.reply_text('Posting frequency? (daily/weekly):')
    return WAITING_AUTOPOST_FREQUENCY_UPDATE


async def update_autopost_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update posting frequency"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_AUTOPOST_FREQUENCY_UPDATE
    
    assert context.user_data is not None
    
    frequency = message.text.lower()
    if frequency not in ['daily', 'weekly']:
        await message.reply_text('Invalid frequency. Choose: daily, or weekly')
        return WAITING_AUTOPOST_FREQUENCY_UPDATE
    
    context.user_data['posting_frequency'] = frequency
    context.user_data['daily_posts'] = {}
    context.user_data['current_platform_index'] = 0
    
    # Start collecting daily posts per platform
    return await ask_next_platform_posts_update(update, context)


async def ask_next_platform_posts_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for daily posts for the next platform"""
    message = update.effective_message
    if not message or not context.user_data:
        return WAITING_AUTOPOST_DAILY_POSTS_UPDATE
    
    account = context.user_data.get('settings_account', {})
    platforms = account.get('platforms', [])
    current_index = context.user_data.get('current_platform_index', 0)
    
    if current_index >= len(platforms):
        # All platforms done, finalize
        return await finalize_autopost_update(update, context)
    
    platform = platforms[current_index]
    limit = PLATFORM_LIMITS.get(platform, 50)
    
    await message.reply_text(
        f'How many posts per day for {platform.upper()}?\n'
        f'Maximum: {limit} posts/day'
    )
    return WAITING_AUTOPOST_DAILY_POSTS_UPDATE


async def update_autopost_daily_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect daily posts per platform"""
    message = update.effective_message
    if not message or not message.text or not context.user_data:
        return WAITING_AUTOPOST_DAILY_POSTS_UPDATE
    
    assert context.user_data is not None
    
    account = context.user_data.get('settings_account', {})
    platforms = account.get('platforms', [])
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
            return WAITING_AUTOPOST_DAILY_POSTS_UPDATE
    except ValueError:
        await message.reply_text('Invalid number. Please enter a valid integer:')
        return WAITING_AUTOPOST_DAILY_POSTS_UPDATE
    
    # Store this platform's daily posts
    context.user_data['daily_posts'][platform] = daily_posts
    
    # Move to next platform
    context.user_data['current_platform_index'] = current_index + 1
    
    # Check if all platforms done
    if current_index + 1 >= len(platforms):
        return await ask_downtime_hours(update, context)  # CHANGED: Ask for downtime
    else:
        return await ask_next_platform_posts_update(update, context)


async def ask_downtime_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for downtime duration"""
    message = update.effective_message
    if not message:
        return WAITING_DOWNTIME_HOURS
    
    await message.reply_text(
        '🌙 Downtime Configuration\n\n'
        'During downtime, no posts will be scheduled.\n'
        'Enter downtime duration in hours (e.g., 8):\n\n'
        'Recommended: 6-10 hours'
    )
    return WAITING_DOWNTIME_HOURS


async def update_downtime_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store downtime duration"""
    message = update.effective_message
    if not message or not message.text:
        return WAITING_DOWNTIME_HOURS
    
    assert context.user_data is not None
    
    try:
        downtime_hours = int(message.text)
        if downtime_hours < 0 or downtime_hours > 24:
            await message.reply_text('Invalid hours. Must be between 0 and 24:')
            return WAITING_DOWNTIME_HOURS
        
        context.user_data['downtime_hours'] = downtime_hours
        
        # Generate random downtime window
        from utils.determine_time import generate_downtime_window
        downtime_start, downtime_end = generate_downtime_window(downtime_hours)
        
        context.user_data['downtime_start'] = downtime_start
        context.user_data['downtime_end'] = downtime_end
        
        await message.reply_text(
            f'✅ Downtime set: {downtime_hours} hours\n'
            f'Window: {downtime_start} - {downtime_end} CET\n\n'
            f'Finalizing settings...'
        )
        
        return await finalize_autopost_update(update, context)
        
    except ValueError:
        await message.reply_text('Invalid number. Please enter an integer:')
        return WAITING_DOWNTIME_HOURS


# Add new function at the end, before finalize_autopost_update:
async def update_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update account platforms"""
    message = update.effective_message
    if not message or not message.text or not update.effective_user or not context.user_data:
        return WAITING_PLATFORMS_UPDATE
    
    # Parse platforms
    platforms_input = message.text.strip().lower()
    platforms = [p.strip() for p in platforms_input.split(',')]
    
    # Validate platforms
    valid_platforms = {'tiktok', 'instagram', 'youtube', 'facebook', 'x', 'threads', 'linkedin'}
    invalid = [p for p in platforms if p not in valid_platforms]
    
    if invalid:
        await message.reply_text(
            f'❌ Invalid platforms: {", ".join(invalid)}\n\n'
            f'Valid options: {", ".join(sorted(valid_platforms))}\n'
            f'Please try again:'
        )
        return WAITING_PLATFORMS_UPDATE
    
    if not platforms:
        await message.reply_text('❌ Please provide at least one platform:')
        return WAITING_PLATFORMS_UPDATE
    
    # Update account
    username = context.user_data.get('settings_username')
    user_id = update.effective_user.id
    
    try:
        response = requests.patch(
            f'{API_URL}/update-account',
            json={
                'user_id': str(user_id),
                'username': username,
                'platforms': platforms
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            platforms_display = ', '.join(platforms)
            await message.reply_text(f'✅ Platforms updated to: {platforms_display}')
        else:
            await message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
    
    context.user_data.clear()
    return ConversationHandler.END


async def finalize_autopost_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save autoposting settings"""
    message = update.effective_message
    if not message or not update.effective_user or not context.user_data:
        return ConversationHandler.END
    
    assert context.user_data is not None
    
    user_id = update.effective_user.id
    username = context.user_data.get('settings_username')
    autopost_enabled = context.user_data.get('autopost_enabled', False)
    
    # Build autoposting properties
    autoposting_properties = {
        'enabled': autopost_enabled
    }
    
    if autopost_enabled:
        autoposting_properties['posting_frequency'] = context.user_data.get('posting_frequency', 'daily')
        autoposting_properties['daily_posts'] = context.user_data.get('daily_posts', {})
        autoposting_properties['downtime_hours'] = context.user_data.get('downtime_hours', 8)  # ADD
        autoposting_properties['downtime_start'] = context.user_data.get('downtime_start')  # ADD
        autoposting_properties['downtime_end'] = context.user_data.get('downtime_end')  # ADD
    
    try:
        response = requests.patch(
            f'{API_URL}/update-account',
            json={
                'user_id': str(user_id),
                'username': username,
                'autoposting_properties': autoposting_properties
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            summary = '✅ Autoposting settings updated!\n\n'
            
            if autopost_enabled:
                summary += 'Status: Enabled\n'
                summary += f'Frequency: {autoposting_properties["posting_frequency"]}\n'
                summary += f'Downtime: {autoposting_properties.get("downtime_start")} - {autoposting_properties.get("downtime_end")} CET\n'
                summary += 'Posts/day:\n'
                for platform, count in autoposting_properties['daily_posts'].items():
                    summary += f'  • {platform}: {count}\n'
            else:
                summary += 'Status: Disabled'
            
            await message.reply_text(summary)
        else:
            await message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
    
    context.user_data.clear()
    return ConversationHandler.END
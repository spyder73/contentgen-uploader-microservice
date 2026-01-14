import os
import requests
from auth import require_auth
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

# States
WAITING_GROUP_NAME = 1
WAITING_GROUP_ACCOUNTS = 2
WAITING_ADD_ACCOUNTS = 3
WAITING_GROUP_VIDEO = 4


# ===== CREATE GROUP =====

@require_auth
async def create_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /creategroup
    """
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    
    await message.reply_text('Enter a name for the new group:')
    return WAITING_GROUP_NAME


async def create_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive group name"""
    message = update.effective_message
    if not message or not message.text or not update.effective_user:
        return WAITING_GROUP_NAME
    
    assert context.user_data is not None
    
    group_name = message.text.strip()
    user_id = update.effective_user.id
    
    # Check if group exists
    try:
        response = requests.get(
            f'{API_URL}/get-group',
            params={'user_id': str(user_id), 'group_name': group_name},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            await message.reply_text(f'⚠️ Group "{group_name}" already exists. Choose another name:')
            return WAITING_GROUP_NAME
    except Exception:
        await message.reply_text('❌ Error checking group existence. Try again.')
        pass
    
    context.user_data['group_name'] = group_name
    
    # List available accounts
    try:
        accounts_response = requests.get(
            f'{API_URL}/list-accounts',
            params={'user_id': str(user_id)},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if accounts_response.status_code == 200:
            accounts = accounts_response.json().get('accounts', [])
            
            account_list = '\n'.join([f"{i+1}. {acc['username']}" for i, acc in enumerate(accounts)])
            context.user_data['available_accounts'] = accounts
            
            await message.reply_text(
                f'Available accounts:\n{account_list}\n\n'
                f'Enter account numbers to add (comma-separated, e.g., 1,3,5)\n'
                f'Or type "skip" to create empty group:'
            )
            return WAITING_GROUP_ACCOUNTS
        else:
            await message.reply_text('❌ Failed to fetch accounts')
            return ConversationHandler.END
            
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
        return ConversationHandler.END


async def create_group_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive account selection"""
    message = update.effective_message
    if not message or not message.text or not update.effective_user:
        return WAITING_GROUP_ACCOUNTS
    
    assert context.user_data is not None
    
    user_id = update.effective_user.id
    group_name = context.user_data.get('group_name')
    available_accounts = context.user_data.get('available_accounts', [])
    
    account_usernames = []
    
    if message.text.lower() != 'skip':
        try:
            # Parse indices
            indices = [int(x.strip()) - 1 for x in message.text.split(',')]
            
            # Validate indices
            if any(i < 0 or i >= len(available_accounts) for i in indices):
                await message.reply_text('Invalid account numbers. Try again:')
                return WAITING_GROUP_ACCOUNTS
            
            account_usernames = [available_accounts[i]['username'] for i in indices]
            
        except ValueError:
            await message.reply_text('Invalid format. Use numbers separated by commas (e.g., 1,3,5):')
            return WAITING_GROUP_ACCOUNTS
    
    # Create group
    try:
        response = requests.post(
            f'{API_URL}/create-group',
            json={
                'user_id': str(user_id),
                'group_name': group_name,
                'account_usernames': account_usernames
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 201:
            accounts_str = ', '.join(account_usernames) if account_usernames else 'None'
            await message.reply_text(
                f'✅ Group "{group_name}" created!\n'
                f'Accounts: {accounts_str}'
            )
        elif response.status_code == 409:
            await message.reply_text('⚠️ Group already exists')
        else:
            await message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
    
    context.user_data.clear()
    return ConversationHandler.END


# ===== ADD TO GROUP =====

@require_auth
async def add_to_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /addtogroup <group_name> <account1,account2,...>
    Example: /addtogroup mygroup acc1,acc2,acc3
    """
    message = update.effective_message
    if not message or not update.effective_user:
        return
    
    if not context.args or len(context.args) < 2:
        await message.reply_text(
            '📎 Add to Group\n\n'
            'Usage: /addtogroup <group_name> <accounts>\n'
            'Example: /addtogroup mygroup acc1,acc2,acc3\n\n'
            'Use /listgroups to see groups\n'
            'Use /listaccounts to see accounts'
        )
        return
    
    user_id = update.effective_user.id
    group_name = context.args[0]
    accounts_arg = ' '.join(context.args[1:])
    account_usernames = [a.strip() for a in accounts_arg.split(',')]
    
    try:
        response = requests.patch(
            f'{API_URL}/add-to-group',
            json={
                'user_id': str(user_id),
                'group_name': group_name,
                'account_usernames': account_usernames
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            await message.reply_text(
                f'✅ Added to group "{group_name}":\n' +
                '\n'.join([f'  • {acc}' for acc in account_usernames])
            )
        elif response.status_code == 404:
            await message.reply_text(f'❌ Group "{group_name}" not found')
        else:
            await message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')


# ===== LIST GROUPS =====

@require_auth
async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all groups"""
    message = update.effective_message
    if not message or not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        response = requests.get(
            f'{API_URL}/list-groups',
            params={'user_id': str(user_id)},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            groups = response.json().get('groups', [])
            
            if not groups:
                await message.reply_text('No groups found. Create one with /creategroup')
                return
            
            groups_text = '📁 Your Groups:\n\n'
            for i, group in enumerate(groups, 1):
                accounts = ', '.join(group['account_usernames']) if group['account_usernames'] else 'Empty'
                groups_text += f'{i}. {group["group_name"]}\n   Accounts: {accounts}\n\n'
            
            await message.reply_text(groups_text)
        else:
            await message.reply_text('❌ Failed to fetch groups')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')


# ===== DELETE GROUP =====

@require_auth
async def delete_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /deletegroup <group_name>
    """
    message = update.effective_message
    if not message or not update.effective_user:
        return
    
    if not context.args:
        await message.reply_text('Usage: /deletegroup <group_name>')
        return
    
    user_id = update.effective_user.id
    group_name = ' '.join(context.args)
    
    try:
        response = requests.delete(
            f'{API_URL}/delete-group',
            json={
                'user_id': str(user_id),
                'group_name': group_name
            },
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            await message.reply_text(f'✅ Group "{group_name}" deleted')
        elif response.status_code == 404:
            await message.reply_text(f'❌ Group "{group_name}" not found')
        else:
            await message.reply_text(f'❌ Error: {response.json().get("error")}')
    
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')


# ===== ADD GROUP VIDEO =====

@require_auth
async def add_group_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /addgroupvideo
    """
    message = update.effective_message
    if not message or not update.effective_user:
        return ConversationHandler.END
    
    assert context.user_data is not None
    user_id = update.effective_user.id
    
    # List groups
    try:
        response = requests.get(
            f'{API_URL}/list-groups',
            params={'user_id': str(user_id)},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            groups = response.json().get('groups', [])
            
            if not groups:
                await message.reply_text('No groups found. Create one with /creategroup')
                return ConversationHandler.END
            
            groups_list = '\n'.join([f"{i+1}. {g['group_name']}" for i, g in enumerate(groups)])
            context.user_data['available_groups'] = groups
            
            await message.reply_text(
                f'Select a group:\n{groups_list}\n\n'
                f'Reply with the number:'
            )
            return WAITING_GROUP_VIDEO
        else:
            await message.reply_text('❌ Failed to fetch groups')
            return ConversationHandler.END
            
    except Exception as e:
        await message.reply_text(f'❌ Error: {str(e)}')
        return ConversationHandler.END


async def add_group_video_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select group and send video"""
    message = update.effective_message
    
    # Handle video upload
    if message and message.video:
        assert context.user_data is not None
        
        group_name = context.user_data.get('selected_group_name')
        if not group_name:
            await message.reply_text('❌ No group selected')
            return ConversationHandler.END
        
        user_id = update.effective_user.id if update.effective_user else None
        video_id = message.video.file_id
        
        # Add video to database first (as reusable)
        try:
            add_response = requests.post(
                f'{API_URL}/add-video',
                json={
                    'video_id': video_id,
                    'caption': f'Group video for {group_name}',
                    'user_id': str(user_id),
                    'reusable': True
                },
                headers={'Authorization': f'Bearer {API_TOKEN}'}
            )
            
            if add_response.status_code not in [201, 409]:
                await message.reply_text('❌ Failed to add video')
                return ConversationHandler.END
            
            # Add to group
            group_response = requests.post(
                f'{API_URL}/add-group-video',
                json={
                    'user_id': str(user_id),
                    'group_name': group_name,
                    'video_id': video_id
                },
                headers={'Authorization': f'Bearer {API_TOKEN}'}
            )
            
            if group_response.status_code == 201:
                await message.reply_text(f'✅ Video added to group "{group_name}"')
            elif group_response.status_code == 409:
                await message.reply_text('⚠️ Video already in group')
            else:
                await message.reply_text(f'❌ Error: {group_response.json().get("error")}')
        
        except Exception as e:
            await message.reply_text(f'❌ Error: {str(e)}')
        
        context.user_data.clear()
        return ConversationHandler.END
    
    # Handle group selection
    if not message or not message.text:
        return WAITING_GROUP_VIDEO
    
    assert context.user_data is not None
    
    try:
        group_index = int(message.text.strip()) - 1
        available_groups = context.user_data.get('available_groups', [])
        
        if group_index < 0 or group_index >= len(available_groups):
            await message.reply_text('Invalid number. Try again:')
            return WAITING_GROUP_VIDEO
        
        selected_group = available_groups[group_index]
        context.user_data['selected_group_name'] = selected_group['group_name']
        
        await message.reply_text(f'Group "{selected_group["group_name"]}" selected.\n\nNow send the video:')
        return WAITING_GROUP_VIDEO
        
    except ValueError:
        await message.reply_text('Invalid input. Enter a number:')
        return WAITING_GROUP_VIDEO
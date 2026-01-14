from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from auth import require_auth


@require_auth
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    await update.message.reply_text(
        '👋 Welcome to Piper!\n\n'
        'Use /listcommands to see available commands.'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return ConversationHandler.END
    
    if context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text('❌ Cancelled.')
    return ConversationHandler.END


async def conversation_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation timeout"""
    if context.user_data:
        context.user_data.clear()
    
    if update.effective_message:
        try:
            await update.effective_message.reply_text(
                '⏰ Conversation timed out due to inactivity.\n\n'
                'Please start again with the command.'
            )
        except Exception:
            pass  # Ignore errors when sending timeout message
    
    return ConversationHandler.END


@require_auth
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    await update.message.reply_text('Received video file!')


@require_auth
async def list_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available commands with their usage"""
    message = update.effective_message
    if not message:
        return
    
    commands_text = """
📚 **Available Commands**

**Notation:**
• `<arg>` = Required argument
• `[arg]` = Optional argument

**Video Management:**
• `/addvideo` - Add a new video to library
• `/listvideos` - Show available videos
• `/listposted` - Show posted videos
• `/listscheduled` - Show scheduled videos

**Account Management:**
• `/addaccount` - Add social media account
• `/listaccounts` - Show all accounts
• `/deleteaccount <username>` - Delete account
• `/settings <username>` - Update account settings

**Group Management:**
• `/creategroup` - Create account group
• `/listgroups` - Show all groups
• `/addtogroup <group_name> <account1,account2>` - Add accounts to group
• `/deletegroup <group_name>` - Delete a group
• `/addgroupvideo` - Add video to group

**Upload & Schedule:**
• `/upload <account>` - Upload video immediately
• `/schedule <video_index> <account> [datetime]` - Schedule video
  Format: YYYY-MM-DDTHH:MM:SS (CET)
  Example: `/schedule 1 myaccount 2025-11-18T14:30:00`
  Or: `/schedule 1 myaccount` (auto-schedule)

**AI Features:**
• `/ai <prompt>` - Chat with AI
• `/model <model_name>` - Select AI model
• `/listmodels` - Show available models

**General:**
• `/start` - Start the bot
• `/listcommands` - Show this help message
• `/cancel` - Cancel current operation
"""
    
    await message.reply_text(commands_text, parse_mode='Markdown')
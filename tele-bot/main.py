import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from datetime import timedelta
from handlers import (
    start, cancel, list_commands, conversation_timeout,
    add_video_start, add_video_receive, add_video_caption, add_video_reusable, list_videos, list_posted, list_scheduled,
    add_account_start, add_account_username, add_account_platforms, add_account_is_ai,
    add_account_autopost_enabled, add_account_autopost_frequency, add_account_autopost_daily_posts,
    list_accounts, delete_account,
    settings_start, settings_choice, update_is_ai, update_autopost_enabled, update_platforms, update_downtime_hours,
    update_autopost_frequency, update_autopost_daily_posts,
    list_models, select_model, ai_command,
    upload_start, upload_receive_video, upload_ai_choice, upload_ai_prompt, upload_caption,
    schedule_start, schedule_ai_choice, schedule_ai_prompt, schedule_keep_caption, schedule_new_caption,
    create_group_start, create_group_name, create_group_accounts,
    add_to_group_start, list_groups, delete_group,
    add_group_video_start, add_group_video_select,
    WAITING_UPLOAD_VIDEO, WAITING_UPLOAD_AI_CHOICE, WAITING_UPLOAD_AI_PROMPT, WAITING_UPLOAD_CAPTION,
    WAITING_KEEP_CAPTION, WAITING_AI_CHOICE, WAITING_AI_PROMPT, WAITING_NEW_CAPTION,
    WAITING_VIDEO, WAITING_CAPTION, WAITING_USERNAME, WAITING_PLATFORMS, WAITING_REUSABLE,
    WAITING_IS_AI, WAITING_AUTOPOST_ENABLED, WAITING_AUTOPOST_FREQUENCY, WAITING_AUTOPOST_DAILY_POSTS,
    WAITING_SETTING_CHOICE, WAITING_IS_AI_UPDATE, WAITING_AUTOPOST_ENABLED_UPDATE, WAITING_DOWNTIME_HOURS,
    WAITING_AUTOPOST_FREQUENCY_UPDATE, WAITING_AUTOPOST_DAILY_POSTS_UPDATE, WAITING_PLATFORMS_UPDATE,
    WAITING_GROUP_NAME, WAITING_GROUP_ACCOUNTS, WAITING_GROUP_VIDEO
)

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# Conversation timeout (e.g., 30 minutes)
CONVERSATION_TIMEOUT = timedelta(minutes=30)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversations with timeout
    add_video_conv = ConversationHandler(
        entry_points=[CommandHandler('addvideo', add_video_start)],
        states={
            WAITING_VIDEO: [MessageHandler(filters.VIDEO, add_video_receive)],
            WAITING_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_video_caption)],
            WAITING_REUSABLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_video_reusable)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )
    
    add_account_conv = ConversationHandler(
        entry_points=[CommandHandler('addaccount', add_account_start)],
        states={
            WAITING_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_username)],
            WAITING_PLATFORMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_platforms)],
            WAITING_IS_AI: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_is_ai)],
            WAITING_AUTOPOST_ENABLED: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_autopost_enabled)],
            WAITING_AUTOPOST_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_autopost_frequency)],
            WAITING_AUTOPOST_DAILY_POSTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_autopost_daily_posts)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )
    
    settings_conv = ConversationHandler(
        entry_points=[CommandHandler('settings', settings_start)],
        states={
            WAITING_SETTING_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_choice)],
            WAITING_IS_AI_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_is_ai)],
            WAITING_AUTOPOST_ENABLED_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_autopost_enabled)],
            WAITING_AUTOPOST_FREQUENCY_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_autopost_frequency)],
            WAITING_AUTOPOST_DAILY_POSTS_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_autopost_daily_posts)],
            WAITING_DOWNTIME_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_downtime_hours)],
            WAITING_PLATFORMS_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_platforms)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )
    
    upload_conv = ConversationHandler(
        entry_points=[CommandHandler('upload', upload_start)],
        states={
            WAITING_UPLOAD_VIDEO: [MessageHandler(filters.VIDEO, upload_receive_video)],
            WAITING_UPLOAD_AI_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload_ai_choice)],
            WAITING_UPLOAD_AI_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload_ai_prompt)],
            WAITING_UPLOAD_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload_caption)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )

    schedule_conv = ConversationHandler(
        entry_points=[CommandHandler('schedule', schedule_start)],
        states={
            WAITING_KEEP_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_keep_caption)],
            WAITING_AI_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_ai_choice)],
            WAITING_AI_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_ai_prompt)],
            WAITING_NEW_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_new_caption)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )
    
    create_group_conv = ConversationHandler(
        entry_points=[CommandHandler('creategroup', create_group_start)],
        states={
            WAITING_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_name)],
            WAITING_GROUP_ACCOUNTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_accounts)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )
    
    add_group_video_conv = ConversationHandler(
        entry_points=[CommandHandler('addgroupvideo', add_group_video_start)],
        states={
            WAITING_GROUP_VIDEO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_group_video_select),
                MessageHandler(filters.VIDEO, add_group_video_select)
            ],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, conversation_timeout)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=CONVERSATION_TIMEOUT
    )
    
    
    # Convos
    app.add_handler(add_video_conv)
    app.add_handler(add_account_conv)
    app.add_handler(settings_conv)
    app.add_handler(upload_conv)
    app.add_handler(schedule_conv)
    app.add_handler(create_group_conv)
    app.add_handler(add_group_video_conv)
    
    # Single Commands
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('listcommands', list_commands))
    app.add_handler(CommandHandler('listvideos', list_videos))
    app.add_handler(CommandHandler('listscheduled', list_scheduled))
    app.add_handler(CommandHandler('listposted', list_posted))
    app.add_handler(CommandHandler('listaccounts', list_accounts))
    app.add_handler(CommandHandler('deleteaccount', delete_account))
    app.add_handler(CommandHandler('listmodels', list_models))
    app.add_handler(CommandHandler('model', select_model))
    app.add_handler(CommandHandler('ai', ai_command))
    app.add_handler(CommandHandler('addtogroup', add_to_group_start))
    app.add_handler(CommandHandler('listgroups', list_groups))
    app.add_handler(CommandHandler('deletegroup', delete_group))
    
    print('Bot started...')
    app.run_polling()


if __name__ == '__main__':
    main()
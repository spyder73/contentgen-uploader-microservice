import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv

load_dotenv()

ALLOWED_USERS = [int(uid) for uid in os.getenv('ALLOWED_USER_IDS', '').split(',') if uid]


def require_auth(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.message or not update.effective_user:
            return
        if update.effective_user.id not in ALLOWED_USERS:
            await update.message.reply_text(f'User ID: {update.effective_user.id} is not authorized.')
            await update.message.reply_text('Unauthorized')
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
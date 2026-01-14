import os
import requests
from telegram import Update
from telegram.ext import ContextTypes
from auth import require_auth
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

user_models = {}

@require_auth
async def list_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if not update.message:
        return
    
    try:
        response = requests.get(f'{API_URL}/models')
        
        if response.status_code == 200:
            result = response.json()
            models = result.get('data', [])
            
            model_list = [f"• {m['id']}" for m in models[:]]
            message = "Available models:\n" + "\n".join(model_list)
            message += f"\n\n(Showing {len(model_list)} of {len(models)} models)"
            message += "\n\nUse /model <model-id> to select"
            
            await update.message.reply_text(message)
        else:
            await update.message.reply_text('Failed to fetch models')
    
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')


@require_auth
async def select_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    if not context.args:
        await update.message.reply_text('Usage: /model <model-id>')
        return
    
    model_id = ' '.join(context.args)
    user_id = update.effective_user.id
    user_models[user_id] = model_id
    
    await update.message.reply_text(f'Model set to: {model_id}')


@require_auth
async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    if not context.args:
        await update.message.reply_text('Usage: /ai <your text>')
        return
    
    text = ' '.join(context.args)
    user_id = update.effective_user.id
    model = user_models.get(user_id, 'x-ai/grok-4-fast')
    
    try:
        response = requests.post(
            f'{API_URL}/inference',
            json={'text': text, 'model': model},
            headers={'Authorization': f'Bearer {API_TOKEN}'}
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('content', 'No content')
            model_used = result.get('model_used', model)
            
            await update.message.reply_text(f"Model: {model_used}\n\n{content}")
        else:
            await update.message.reply_text(f"Error: {response.json().get('error', 'Unknown')}")
    
    except Exception as e:
        await update.message.reply_text(f'Error: {str(e)}')
        
from flask import Blueprint, request, jsonify
from auth import require_token
import requests
import os
import json
from utils.json_parse import extract_json

openrouter_bp = Blueprint('openrouter', __name__)
openrouter_api_key = os.getenv('OPENROUTER_API_KEY')


@openrouter_bp.route('/inference', methods=['POST'])
@require_token
def openrouter_post():
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    text_content = data.get('text')
    model = data.get('model', 'x-ai/grok-4-fast')
    payload = {"model": model, "messages": [{"role": "user", "content": text_content}]}
    
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload)
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        content_json = extract_json(content)
        
        return jsonify({
            'success': True,
            'content': content,
            'content_json': content_json,
            'model_used': model
        }), 200
    else:
        return jsonify({
            'error': 'Failed to get response from OpenRouter',
            'details': response.text
        }), response.status_code


@openrouter_bp.route('/models', methods=['GET'])
def openrouter_get():
    try:
        response = requests.get(
            url="https://openrouter.ai/api/v1/models",
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        models_data = response.json()
        
        # Filter for OpenAI, Grok, Claude, and Gemini models
        filtered = []
        providers = ['openai', 'x-ai', 'anthropic', 'google']
        for model in models_data.get('data', []):
            model_id = model['id'].lower()
            if any(provider in model_id for provider in providers):
                filtered.append({'id': model['id'], 'name': model.get('name', model['id'])})
        
        return jsonify({'message': 'OpenRouter GET successful', 'data': filtered}), 200
    
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to get models from OpenRouter', 'details': str(e)}), 500
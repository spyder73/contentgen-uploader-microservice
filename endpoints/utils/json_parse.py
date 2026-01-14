import json
import re

def extract_json(content):
    """
    Extract and parse JSON from LLM responses that may contain markdown formatting.
    Returns parsed JSON object or None if extraction fails.
    """
    if not content or not isinstance(content, str):
        return None
    
    # Try direct parse first (fastest path)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Method 1: Extract from markdown JSON blocks (```json ... ```)
    json_block_match = re.search(r'```json\s*\n([\s\S]*?)\n```', content)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Method 2: Extract from generic code blocks (``` ... ```)
    code_block_match = re.search(r'```\s*\n([\s\S]*?)\n```', content)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass
        
        
    # Method 3: Find JSON object by looking for { ... }
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Method 4: Clean common prefixes/suffixes
    cleaned = content.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^```\s*', '', cleaned)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # All methods failed
    return None
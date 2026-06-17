import config


def build_chat_headers() -> dict:
    headers = {
        'Authorization': f'Bearer {config.AI_API_KEY}',
        'Content-Type': 'application/json',
    }
    if config.AI_PROVIDER == 'openrouter':
        if config.AI_HTTP_REFERER:
            headers['HTTP-Referer'] = config.AI_HTTP_REFERER
        if config.AI_APP_TITLE:
            headers['X-Title'] = config.AI_APP_TITLE
    return headers

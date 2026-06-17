import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

VERCEL = os.environ.get('VERCEL', '').lower() in ('1', 'true')
WEBSOCKET_ENABLED = os.environ.get(
    'WEBSOCKET_ENABLED',
    'false' if VERCEL else 'true',
).lower() == 'true'

_DEFAULT_UPLOAD_MB = 4 if VERCEL else 16
MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', str(_DEFAULT_UPLOAD_MB)))
MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

AI_PROVIDER = os.environ.get('AI_PROVIDER', 'openrouter').lower()
AI_RECOMMENDATIONS_ENABLED = os.environ.get('AI_RECOMMENDATIONS_ENABLED', 'false').lower() == 'true'
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_API_URL = os.environ.get(
    'AI_API_URL',
    'https://openrouter.ai/api/v1/chat/completions'
    if AI_PROVIDER == 'openrouter'
    else 'https://api.openai.com/v1/chat/completions',
)
AI_MODEL = os.environ.get(
    'AI_MODEL',
    'openai/gpt-4o-mini' if AI_PROVIDER == 'openrouter' else 'gpt-4o-mini',
)
AI_HTTP_REFERER = os.environ.get('AI_HTTP_REFERER', 'http://localhost:5000')
AI_APP_TITLE = os.environ.get('AI_APP_TITLE', 'JobRes.ai')

JOB_FEEDS_ENABLED = os.environ.get('JOB_FEEDS_ENABLED', 'false').lower() == 'true'

ARBEITNOW_ENABLED = os.environ.get('ARBEITNOW_ENABLED', 'true').lower() == 'true'
ARBEITNOW_API_URL = os.environ.get('ARBEITNOW_API_URL', 'https://www.arbeitnow.com/api/job-board-api')
ARBEITNOW_MAX_PAGES = int(os.environ.get('ARBEITNOW_MAX_PAGES', '1'))

REMOTIVE_ENABLED = os.environ.get('REMOTIVE_ENABLED', 'true').lower() == 'true'
REMOTIVE_API_URL = os.environ.get('REMOTIVE_API_URL', 'https://remotive.com/api/remote-jobs')

REMOTEJOBS_ORG_ENABLED = os.environ.get('REMOTEJOBS_ORG_ENABLED', 'true').lower() == 'true'
REMOTEJOBS_ORG_API_URL = os.environ.get('REMOTEJOBS_ORG_API_URL', 'https://remotejobs.org/api/v1/jobs')

INDEED_API_KEY = os.environ.get('INDEED_API_KEY', '')
INDEED_API_URL = os.environ.get('INDEED_API_URL', 'https://indeed12.p.rapidapi.com/jobs/search')
INDEED_API_HOST = os.environ.get('INDEED_API_HOST', 'indeed12.p.rapidapi.com')
LINKEDIN_API_KEY = os.environ.get('LINKEDIN_API_KEY', '')
LINKEDIN_API_URL = os.environ.get('LINKEDIN_API_URL', 'https://api.linkedin.com/v2/jobSearch')

COVER_LETTER_AI_ENABLED = os.environ.get('COVER_LETTER_AI_ENABLED', 'false').lower() == 'true'

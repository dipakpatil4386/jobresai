import logging
from typing import Dict, List

import requests

import config
from services.job_utils import strip_html

logger = logging.getLogger(__name__)


class RemotiveClient:
    def __init__(self):
        self.enabled = config.REMOTIVE_ENABLED
        self.api_url = config.REMOTIVE_API_URL.rstrip('/')

    def get_status(self) -> Dict:
        return {
            'enabled': self.enabled,
            'configured': True,
            'message': 'Remotive API enabled (free, no key).' if self.enabled else 'Remotive disabled.',
        }

    def fetch_raw(self, search: str = '') -> List[Dict]:
        if not self.enabled:
            return []
        try:
            params = {}
            if search:
                params['search'] = search
            response = requests.get(
                self.api_url,
                params=params,
                timeout=20,
                headers={'Accept': 'application/json', 'User-Agent': 'JobRes.ai/1.0'},
            )
            response.raise_for_status()
            return response.json().get('jobs') or []
        except Exception as exc:
            logger.warning('Remotive API failed: %s', exc)
            return []

    def normalize(self, item: Dict) -> Dict:
        description = strip_html(item.get('description', ''))
        tags = item.get('tags') or []
        tag_list = tags if isinstance(tags, list) else [str(tags)]
        salary = item.get('salary') or 'See listing'

        return {
            'id': f"remotive-{item.get('id', item.get('url', ''))}",
            'title': item.get('title', 'Role'),
            'company': item.get('company_name', 'Company'),
            'location': item.get('candidate_required_location') or 'Remote',
            'description': description[:3000],
            'requirements': ', '.join(tag_list) if tag_list else description[:400],
            'salary': salary if salary else 'See listing',
            'type': item.get('job_type', 'Full-time'),
            'remote': True,
            'url': item.get('url', 'https://remotive.com'),
            'source': 'Remotive',
            'posted': item.get('publication_date', 'Recently'),
            'posted_at': item.get('publication_date'),
            'snippet': description[:200] + ('...' if len(description) > 200 else ''),
            'tags': tag_list,
            'category': item.get('category', ''),
        }

    def fetch_jobs(self, search: str = '', limit: int = 50) -> List[Dict]:
        return [self.normalize(item) for item in self.fetch_raw(search)[:limit]]

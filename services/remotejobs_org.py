import logging
from typing import Dict, List

import requests

import config
from services.job_utils import strip_html

logger = logging.getLogger(__name__)


class RemoteJobsOrgClient:
    def __init__(self):
        self.enabled = config.REMOTEJOBS_ORG_ENABLED
        self.api_url = config.REMOTEJOBS_ORG_API_URL.rstrip('/')

    def get_status(self) -> Dict:
        return {
            'enabled': self.enabled,
            'configured': True,
            'message': 'RemoteJobs.org API enabled (free, no key).' if self.enabled else 'RemoteJobs.org disabled.',
        }

    def fetch_raw(self, search: str = '', limit: int = 50) -> List[Dict]:
        if not self.enabled:
            return []
        try:
            params = {'limit': min(limit, 50)}
            if search:
                params['q'] = search
            response = requests.get(
                self.api_url,
                params=params,
                timeout=20,
                headers={'Accept': 'application/json', 'User-Agent': 'JobRes.ai/1.0'},
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get('data') or []
        except Exception as exc:
            logger.warning('RemoteJobs.org API failed: %s', exc)
            return []

    def normalize(self, item: Dict) -> Dict:
        description = strip_html(item.get('description', ''))
        company = item.get('company') or {}
        company_name = company.get('name', 'Company') if isinstance(company, dict) else str(company)
        category = item.get('category') or {}
        category_name = category.get('name', '') if isinstance(category, dict) else str(category)
        salary_text = item.get('salary_text')
        if not salary_text and (item.get('salary_min') or item.get('salary_max')):
            salary_text = f"{item.get('salary_min', '')} - {item.get('salary_max', '')}".strip(' -')

        location = item.get('location') or 'Remote'
        is_remote = 'remote' in location.lower() if location else True

        return {
            'id': f"remotejobs-{item.get('id', item.get('url', ''))}",
            'title': item.get('title', 'Role'),
            'company': company_name,
            'location': location,
            'description': description[:3000],
            'requirements': category_name or description[:400],
            'salary': salary_text or 'See listing',
            'type': item.get('type', 'Full-time'),
            'remote': is_remote,
            'url': item.get('url') or item.get('apply_url', 'https://remotejobs.org'),
            'source': 'RemoteJobs.org',
            'posted': item.get('posted_at', 'Recently'),
            'posted_at': item.get('posted_at'),
            'snippet': description[:200] + ('...' if len(description) > 200 else ''),
            'tags': [category_name] if category_name else [],
            'category': category_name,
        }

    def fetch_jobs(self, search: str = '', limit: int = 50) -> List[Dict]:
        return [self.normalize(item) for item in self.fetch_raw(search, limit)[:limit]]

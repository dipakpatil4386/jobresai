import logging
import re
from html import unescape
from typing import Dict, List, Optional

import requests

import config

logger = logging.getLogger(__name__)

ARBEITNOW_ATTRIBUTION = 'Jobs via Arbeitnow.com'


class ArbeitnowClient:
    def __init__(self):
        self.enabled = config.ARBEITNOW_ENABLED
        self.api_url = config.ARBEITNOW_API_URL.rstrip('/')
        self.max_pages = config.ARBEITNOW_MAX_PAGES
        self.per_page = 100

    def get_status(self) -> Dict:
        return {
            'enabled': self.enabled,
            'configured': True,
            'api_url': self.api_url,
            'message': (
                'Arbeitnow live job feed is active (free, no API key).'
                if self.enabled
                else 'Arbeitnow feed is disabled. Set ARBEITNOW_ENABLED=true in .env.'
            ),
        }

    def fetch_raw_jobs(self, page: int = 1) -> List[Dict]:
        if not self.enabled:
            return []

        jobs: List[Dict] = []
        current_page = page

        for _ in range(self.max_pages):
            try:
                response = requests.get(
                    self.api_url,
                    params={'page': current_page},
                    timeout=20,
                    headers={'Accept': 'application/json', 'User-Agent': 'JobRes.ai/1.0'},
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.warning('Arbeitnow API request failed (page %s): %s', current_page, exc)
                break

            batch = payload.get('data') or []
            if not batch:
                break
            jobs.extend(batch)

            links = payload.get('links') or {}
            if not links.get('next'):
                break
            current_page += 1

        return jobs

    def fetch_jobs(
        self,
        query: str = '',
        skills: Optional[Dict[str, List[str]]] = None,
        remote_only: bool = False,
        limit: int = 12,
    ) -> List[Dict]:
        raw = self.fetch_raw_jobs()
        if not raw:
            return []

        normalized = [self._normalize_job(item) for item in raw]
        ranked = self._rank_jobs(normalized, query, skills or {}, remote_only)
        return ranked[:limit]

    def fetch_jobs_for_matching(self, query: str = '', skills: Optional[Dict[str, List[str]]] = None) -> List[Dict]:
        return self.fetch_jobs(query=query, skills=skills, limit=50)

    @staticmethod
    def _strip_html(text: str) -> str:
        if not text:
            return ''
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = unescape(clean)
        return ' '.join(clean.split())

    def _normalize_job(self, item: Dict) -> Dict:
        description = self._strip_html(item.get('description', ''))
        tags = item.get('tags') or []
        job_types = item.get('job_types') or []
        tag_str = ', '.join(tags) if isinstance(tags, list) else str(tags)

        return {
            'id': item.get('slug', item.get('url', '')),
            'title': item.get('title', 'Role'),
            'company': item.get('company_name', 'Company'),
            'location': item.get('location') or ('Remote' if item.get('remote') else 'Not specified'),
            'description': description[:3000],
            'requirements': tag_str or description[:500],
            'salary': 'See listing',
            'type': ', '.join(job_types) if job_types else 'Full-time',
            'remote': bool(item.get('remote')),
            'url': item.get('url', 'https://www.arbeitnow.com'),
            'source': 'Arbeitnow',
            'posted': item.get('created_at', 'Recently'),
            'snippet': description[:200] + ('...' if len(description) > 200 else ''),
            'tags': tags,
        }

    def _rank_jobs(
        self,
        jobs: List[Dict],
        query: str,
        skills: Dict[str, List[str]],
        remote_only: bool,
    ) -> List[Dict]:
        terms = set()
        if query:
            terms.update(query.replace('_', ' ').lower().split())
        for skill_list in skills.values():
            for skill in skill_list:
                terms.add(skill.lower())
                terms.update(skill.lower().replace('.', ' ').split())

        terms = {t for t in terms if len(t) > 1}

        def score(job: Dict) -> float:
            if remote_only and not job.get('remote'):
                return -1.0
            haystack = ' '.join([
                job.get('title', ''),
                job.get('company', ''),
                job.get('description', ''),
                job.get('requirements', ''),
                job.get('location', ''),
            ]).lower()
            if not terms:
                return 0.0
            return float(sum(1 for term in terms if term in haystack))

        scored = [(job, score(job)) for job in jobs]
        scored = [(j, s) for j, s in scored if s >= 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [job for job, s in scored]

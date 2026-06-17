import logging
from datetime import datetime
from typing import Dict, List, Optional

from services.arbeitnow import ArbeitnowClient
from services.job_utils import (
    dedupe_jobs,
    filter_by_posted_days,
    filter_work_mode,
    matches_search_query,
    rank_jobs_by_query,
)
from services.remotejobs_org import RemoteJobsOrgClient
from services.remotive import RemotiveClient

logger = logging.getLogger(__name__)

POSTED_FILTER_DAYS = {
    '': None,
    'all': None,
    '1': 1,
    '24h': 1,
    '7': 7,
    '7d': 7,
    '30': 30,
    '30d': 30,
}


class JobSearchService:
    def __init__(self):
        self.arbeitnow = ArbeitnowClient()
        self.remotive = RemotiveClient()
        self.remotejobs = RemoteJobsOrgClient()

    def get_sources_status(self) -> Dict:
        return {
            'arbeitnow': self.arbeitnow.get_status(),
            'remotive': self.remotive.get_status(),
            'remotejobs_org': self.remotejobs.get_status(),
        }

    def search(
        self,
        query: str = '',
        work_mode: str = 'all',
        posted_within: str = 'all',
        limit: int = 30,
        skills: Optional[Dict[str, List[str]]] = None,
    ) -> Dict:
        query = (query or '').strip()
        skills = skills or {}
        days = POSTED_FILTER_DAYS.get(str(posted_within).lower(), POSTED_FILTER_DAYS.get(posted_within))

        all_jobs: List[Dict] = []
        sources_used = []

        if self.arbeitnow.enabled:
            jobs = self.arbeitnow.fetch_jobs(query=query, skills=skills, limit=limit)
            if jobs:
                all_jobs.extend(jobs)
                sources_used.append('arbeitnow')

        if self.remotive.enabled:
            jobs = self.remotive.fetch_jobs(search=query, limit=limit)
            all_jobs.extend(jobs)
            sources_used.append('remotive')

        if self.remotejobs.enabled:
            jobs = self.remotejobs.fetch_jobs(search=query, limit=limit)
            all_jobs.extend(jobs)
            sources_used.append('remotejobs_org')

        if query:
            all_jobs = [j for j in all_jobs if matches_search_query(j, query)]

        all_jobs = filter_work_mode(all_jobs, work_mode)
        all_jobs = filter_by_posted_days(all_jobs, days)
        all_jobs = dedupe_jobs(all_jobs)
        all_jobs = rank_jobs_by_query(all_jobs, query)[:limit]

        return {
            'status': 'success',
            'query': query,
            'work_mode': work_mode,
            'posted_within': posted_within,
            'jobs': all_jobs,
            'count': len(all_jobs),
            'sources': sources_used,
            'fetched_at': datetime.now().isoformat(),
            'attribution': self._attribution(sources_used),
        }

    def fetch_for_pipeline(self, query: str, skills: Dict, limit: int = 12) -> Dict:
        result = self.search(
            query=query,
            work_mode='all',
            posted_within='all',
            limit=limit,
            skills=skills,
        )
        live = bool(result['jobs'])
        source_type = 'multi' if len(result['sources']) > 1 else (result['sources'][0] if result['sources'] else 'preview')
        return {
            'live': live,
            'source_type': source_type,
            'jobs': result['jobs'],
            'count': result['count'],
            'fetched_at': result['fetched_at'],
            'status': self.get_feed_status(),
            'attribution': result.get('attribution'),
            'sources': result['sources'],
        }

    def fetch_all_for_matching(self, query: str, skills: Dict, limit: int = 60) -> List[Dict]:
        result = self.search(query=query, work_mode='all', posted_within='all', limit=limit, skills=skills)
        return result['jobs']

    def get_feed_status(self) -> Dict:
        sources = self.get_sources_status()
        active = [name for name, s in sources.items() if s.get('enabled')]
        return {
            'enabled': len(active) > 0,
            'sources': sources,
            'active_sources': active,
            'message': (
                f'Live jobs from {", ".join(active)} (free APIs).'
                if active
                else 'No job APIs enabled.'
            ),
        }

    @staticmethod
    def _attribution(sources: List[str]) -> List[str]:
        links = []
        if 'arbeitnow' in sources:
            links.append({'name': 'Arbeitnow', 'url': 'https://www.arbeitnow.com'})
        if 'remotive' in sources:
            links.append({'name': 'Remotive', 'url': 'https://remotive.com'})
        if 'remotejobs_org' in sources:
            links.append({'name': 'RemoteJobs.org', 'url': 'https://remotejobs.org'})
        return links

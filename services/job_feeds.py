import logging
from typing import Dict

from services.job_search import JobSearchService

logger = logging.getLogger(__name__)


class JobFeedService:
    def __init__(self):
        self.search_service = JobSearchService()

    def get_status(self) -> Dict:
        return self.search_service.get_feed_status()

    def fetch_jobs(self, query: str, location: str = '', skills: Dict = None) -> Dict:
        return self.search_service.fetch_for_pipeline(query, skills or {})

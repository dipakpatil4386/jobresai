import re
from datetime import datetime, timezone
from html import unescape
from typing import Dict, List, Optional


def strip_html(text: str) -> str:
    if not text:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = unescape(clean)
    return ' '.join(clean.split())


def parse_posted_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def job_posted_timestamp(job: Dict) -> Optional[float]:
    dt = parse_posted_datetime(job.get('posted_at') or job.get('posted'))
    return dt.timestamp() if dt else None


def matches_search_query(job: Dict, query: str) -> bool:
    if not query or not query.strip():
        return True
    terms = [t for t in query.lower().split() if len(t) > 1]
    if not terms:
        return True

    company = job.get('company', '')
    if isinstance(company, dict):
        company = company.get('name', '')

    haystack = ' '.join([
        job.get('title', ''),
        str(company),
        job.get('description', ''),
        job.get('requirements', ''),
        job.get('location', ''),
        job.get('category', '') if isinstance(job.get('category'), str) else '',
        ' '.join(job.get('tags') or []) if isinstance(job.get('tags'), list) else str(job.get('tags') or ''),
    ]).lower()

    return all(term in haystack for term in terms)


def filter_work_mode(jobs: List[Dict], work_mode: str) -> List[Dict]:
    mode = (work_mode or 'all').lower()
    if mode == 'all':
        return jobs
    if mode == 'remote':
        return [j for j in jobs if j.get('remote') is True]
    if mode == 'onsite':
        return [j for j in jobs if j.get('remote') is False]
    return jobs


def filter_by_posted_days(jobs: List[Dict], days: Optional[int]) -> List[Dict]:
    if not days or days <= 0:
        return jobs
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - (days * 86400)
    filtered = []
    for job in jobs:
        ts = job_posted_timestamp(job)
        if ts is None or ts >= cutoff:
            filtered.append(job)
    return filtered


def dedupe_jobs(jobs: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for job in jobs:
        key = (job.get('url') or '').strip().lower()
        if not key:
            key = f"{job.get('title', '')}|{job.get('company', '')}".lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def rank_jobs_by_query(jobs: List[Dict], query: str) -> List[Dict]:
    if not query or not query.strip():
        return sorted(jobs, key=lambda j: job_posted_timestamp(j) or 0, reverse=True)

    terms = [t for t in query.lower().split() if len(t) > 1]

    def score(job: Dict) -> float:
        company = job.get('company', '')
        if isinstance(company, dict):
            company = company.get('name', '')
        title = job.get('title', '').lower()
        company_l = str(company).lower()
        desc = (job.get('description', '') or '')[:1500].lower()
        s = 0.0
        for term in terms:
            if term in title:
                s += 4
            if term in company_l:
                s += 3
            if term in desc:
                s += 1
        ts = job_posted_timestamp(job) or 0
        return s + (ts / 1e12)

    return sorted(jobs, key=score, reverse=True)

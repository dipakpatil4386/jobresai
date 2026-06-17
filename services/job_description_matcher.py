import re
from typing import Dict, List, Set

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from services.resume_processor import ResumeProcessor
from services.score_calibration import calibrate_cosine_percent, combined_job_match


class JobDescriptionMatcher:
    STOPWORDS = frozenset({
        'the', 'and', 'for', 'with', 'this', 'that', 'will', 'your', 'our', 'you',
        'are', 'have', 'from', 'able', 'work', 'team', 'role', 'job', 'using', 'use',
        'including', 'required', 'requirements', 'experience', 'years', 'year', 'must',
        'should', 'would', 'about', 'into', 'their', 'they', 'them', 'than', 'then',
    })

    def __init__(self):
        self.resume_processor = ResumeProcessor()

    def _all_known_skills(self) -> Dict[str, str]:
        mapping = {}
        for category, keywords in self.resume_processor.skill_keywords.items():
            for kw in keywords:
                mapping[kw.lower()] = kw
        return mapping

    def _extract_jd_skills(self, job_description: str) -> Set[str]:
        known = self._all_known_skills()
        text_lower = job_description.lower()
        found = set()
        for skill_key, display in known.items():
            if self.resume_processor._skill_in_text(text_lower, skill_key):
                found.add(display)
        return found

    def _extract_jd_keywords(self, job_description: str, jd_skills: Set[str]) -> List[str]:
        text = job_description.lower()
        tokens = re.findall(r'\b[a-z][a-z0-9+#./-]{2,}\b', text)
        skill_lower = {s.lower() for s in jd_skills}
        freq: Dict[str, int] = {}
        for token in tokens:
            if token in self.STOPWORDS or token in skill_lower or len(token) < 3:
                continue
            freq[token] = freq.get(token, 0) + 1
        ranked = sorted(freq.keys(), key=lambda k: (-freq[k], k))
        return ranked[:25]

    def _flatten_resume_skills(self, skills: Dict[str, List[str]]) -> Set[str]:
        flat = set()
        for items in skills.values():
            for item in items:
                flat.add(item.lower())
        return flat

    def _skill_overlap(self, resume_skills: Set[str], jd_skills: Set[str]) -> Dict:
        matched = {s for s in jd_skills if s.lower() in resume_skills}
        if not matched and jd_skills:
            matched = {
                s for s in jd_skills
                if any(rs in s.lower() or s.lower() in rs for rs in resume_skills)
            }
        missing = jd_skills - matched
        pct = round(len(matched) / len(jd_skills) * 100, 1) if jd_skills else 0.0
        return {
            'matched_skills': sorted(matched),
            'missing_skills': sorted(missing),
            'skill_match_percent': pct,
        }

    def _keyword_overlap(self, resume_text: str, keywords: List[str]) -> Dict:
        text_lower = resume_text.lower()
        matched = []
        missing = []
        for kw in keywords:
            if re.search(rf'\b{re.escape(kw)}\b', text_lower):
                matched.append(kw)
            else:
                missing.append(kw)
        pct = round(len(matched) / len(keywords) * 100, 1) if keywords else 0.0
        return {
            'matched_keywords': matched,
            'missing_keywords': missing[:15],
            'keyword_match_percent': pct,
        }

    def _guess_title(self, job_description: str) -> str:
        lines = [ln.strip() for ln in job_description.strip().splitlines() if ln.strip()]
        if not lines:
            return 'Custom role'
        first = lines[0]
        if len(first) < 80 and not first.endswith('.'):
            return first
        return 'Custom role'

    def match(self, resume_text: str, resume_analysis: Dict, job_description: str) -> Dict:
        jd = job_description.strip()
        if len(jd) < 40:
            raise ValueError('Job description is too short. Paste the full posting.')

        jd_skills = self._extract_jd_skills(jd)
        jd_keywords = self._extract_jd_keywords(jd, jd_skills)
        resume_skills = self._flatten_resume_skills(resume_analysis.get('skills', {}))

        vectorizer = TfidfVectorizer(max_features=8000, stop_words='english', ngram_range=(1, 2))
        matrix = vectorizer.fit_transform([resume_text, jd])
        raw_sim = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
        text_score = calibrate_cosine_percent(raw_sim)

        skill_result = self._skill_overlap(resume_skills, jd_skills)
        keyword_result = self._keyword_overlap(resume_text, jd_keywords)

        skill_pct = skill_result['skill_match_percent']
        keyword_pct = keyword_result['keyword_match_percent']
        overall = round(0.50 * text_score + 0.35 * skill_pct + 0.15 * keyword_pct, 1)
        overall = max(0.0, min(100.0, overall))

        if overall >= 75:
            verdict = 'Strong match'
        elif overall >= 55:
            verdict = 'Moderate match'
        elif overall >= 35:
            verdict = 'Partial match'
        else:
            verdict = 'Weak match'

        return {
            'job_title': self._guess_title(jd),
            'overall_match_score': overall,
            'verdict': verdict,
            'text_similarity_score': text_score,
            'raw_text_similarity': round(raw_sim, 4),
            'skill_match_score': skill_pct,
            'keyword_match_score': keyword_pct,
            'combined_display_score': combined_job_match(text_score / 100, skill_pct),
            'matched_skills': skill_result['matched_skills'],
            'missing_skills': skill_result['missing_skills'],
            'matched_keywords': keyword_result['matched_keywords'],
            'missing_keywords': keyword_result['missing_keywords'],
            'jd_skills_detected': sorted(jd_skills),
            'summary': self._build_summary(overall, skill_result, keyword_result),
        }

    def _build_summary(self, overall: float, skill_result: Dict, keyword_result: Dict) -> str:
        parts = [f'Overall alignment: {overall}%.']
        if skill_result['missing_skills']:
            parts.append(
                f"Missing {len(skill_result['missing_skills'])} key skills from the posting."
            )
        elif skill_result['matched_skills']:
            parts.append('Core skills from the posting appear on your resume.')
        if keyword_result['missing_keywords']:
            parts.append('Consider adding posting keywords to your experience bullets.')
        return ' '.join(parts)

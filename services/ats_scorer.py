import math
import re
from typing import Dict, List, Optional


class ATSScorer:
    ATS_KEYWORDS = [
        'experience', 'skills', 'education', 'projects', 'certification',
        'leadership', 'managed', 'developed', 'implemented', 'achieved',
        'python', 'java', 'sql', 'aws', 'agile', 'scrum',
    ]

    SECTION_HINTS = ['experience', 'education', 'skills', 'summary', 'projects', 'certifications']

    def score(
        self,
        text: str,
        skills: Dict[str, List[str]],
        job_description: Optional[str] = None,
    ) -> Dict:
        text_lower = text.lower()
        found_keywords = [kw for kw in self.ATS_KEYWORDS if re.search(rf'\b{re.escape(kw)}\b', text_lower)]
        keyword_score = min(len(found_keywords) / len(self.ATS_KEYWORDS) * 100, 92)

        sections_found = [s for s in self.SECTION_HINTS if re.search(rf'\b{re.escape(s)}\b', text_lower)]
        section_score = min(len(sections_found) / len(self.SECTION_HINTS) * 100, 95)

        total_skills = sum(len(v) for v in skills.values())
        skill_score = min(math.sqrt(total_skills / 18) * 100, 95) if total_skills else 0

        word_count = len(text.split())
        length_score = min(word_count / 450 * 100, 90) if word_count else 0

        jd_score = None
        if job_description and len(job_description.strip()) > 40:
            jd_lower = job_description.lower()
            jd_terms = set(re.findall(r'\b[a-z][a-z0-9+#]{2,}\b', jd_lower))
            jd_terms -= {'the', 'and', 'for', 'with', 'will', 'your', 'our', 'are', 'have', 'this', 'that'}
            if jd_terms:
                hits = sum(1 for t in jd_terms if re.search(rf'\b{re.escape(t)}\b', text_lower))
                jd_score = round(min(hits / min(len(jd_terms), 40) * 100, 95), 1)

        if jd_score is not None:
            overall = round(
                keyword_score * 0.2
                + section_score * 0.2
                + skill_score * 0.2
                + length_score * 0.1
                + jd_score * 0.3,
                1,
            )
        else:
            overall = round(
                keyword_score * 0.3 + section_score * 0.3 + skill_score * 0.25 + length_score * 0.15,
                1,
            )

        tips = []
        if keyword_score < 45:
            tips.append('Add more ATS-friendly keywords from job descriptions')
        if section_score < 50:
            tips.append('Use clear section headings (Experience, Skills, Education)')
        if skill_score < 40:
            tips.append('List more relevant technical skills in a dedicated section')
        if length_score < 50:
            tips.append('Expand role descriptions with measurable outcomes')
        if jd_score is not None and jd_score < 50:
            tips.append('Mirror more keywords and skills from the target job description')

        return {
            'overall_ats_score': overall,
            'keyword_score': round(keyword_score, 1),
            'section_score': round(section_score, 1),
            'skill_density_score': round(skill_score, 1),
            'content_length_score': round(length_score, 1),
            'job_description_alignment_score': jd_score,
            'keywords_found': found_keywords,
            'sections_detected': sections_found,
            'tips': tips,
        }

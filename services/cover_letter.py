from typing import Dict, Optional

import config
import requests

from services.ai_client import build_chat_headers


class CoverLetterGenerator:
    def generate(
        self,
        resume_analysis: Dict,
        job: Optional[Dict],
        resume_text: str,
        target_role: str = '',
    ) -> Dict:
        contact = resume_analysis.get('contact_info', {})
        name = self._extract_name(resume_text) or 'Applicant'
        role_title = job['title'] if job else (target_role.replace('_', ' ').title() or 'the open position')
        company = job['company'] if job else 'your organization'

        skills = []
        for items in resume_analysis.get('skills', {}).values():
            skills.extend(items[:3])
        skill_phrase = ', '.join(skills[:5]) if skills else 'relevant technical and professional skills'

        body = self._template_letter(name, role_title, company, skill_phrase, job)
        ai_enhanced = False

        if config.COVER_LETTER_AI_ENABLED and config.AI_API_KEY and job:
            enhanced = self._try_ai_letter(name, role_title, company, resume_text[:2500], skill_phrase)
            if enhanced:
                body = enhanced
                ai_enhanced = True

        return {
            'letter': body,
            'recipient': company,
            'position': role_title,
            'ai_enhanced': ai_enhanced,
            'word_count': len(body.split()),
        }

    def regenerate_for_job(self, resume_analysis: Dict, job: Dict, resume_text: str) -> Dict:
        return self.generate(resume_analysis, job, resume_text)

    def _extract_name(self, text: str) -> str:
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        if lines:
            first = lines[0]
            if len(first.split()) <= 4 and '@' not in first:
                return first
        return ''

    def _template_letter(self, name: str, role: str, company: str, skills: str, job: Optional[Dict]) -> str:
        job_hook = ''
        if job and job.get('description'):
            job_hook = f"\nI am particularly drawn to this role because of your focus on {job['description'][:120].strip()}...\n"

        return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {role} position at {company}. With a proven background in {skills}, I am confident I can contribute meaningfully to your team from day one.
{job_hook}
In my recent experience, I have delivered results by applying the same competencies highlighted in your job requirements. I excel at collaborating across teams, translating complex problems into clear solutions, and continuously improving processes.

I would welcome the opportunity to discuss how my background aligns with {company}'s goals. Thank you for your time and consideration.

Sincerely,
{name}"""

    def _try_ai_letter(self, name: str, role: str, company: str, resume_excerpt: str, skills: str) -> Optional[str]:
        try:
            headers = build_chat_headers()
            payload = {
                'model': config.AI_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'Write professional cover letters. Output only the letter body.'},
                    {'role': 'user', 'content': (
                        f'Write a cover letter for {name} applying to {role} at {company}. '
                        f'Skills: {skills}. Resume excerpt:\n{resume_excerpt}'
                    )},
                ],
                'max_tokens': 600,
                'temperature': 0.6,
            }
            response = requests.post(config.AI_API_URL, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception:
            return None

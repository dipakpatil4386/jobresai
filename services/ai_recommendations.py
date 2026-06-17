import logging
from typing import Dict, List, Optional

import requests

import config
from services.ai_client import build_chat_headers

logger = logging.getLogger(__name__)

USER_ERROR_MESSAGE = 'An error occurred. Please try again later.'
USER_UNAVAILABLE_MESSAGE = 'AI resume coach is not available.'
USER_DISABLED_MESSAGE = 'AI resume coach is not enabled.'


class AIRecommendationService:
    def __init__(self):
        self.enabled = config.AI_RECOMMENDATIONS_ENABLED
        self.api_key = config.AI_API_KEY
        self.api_url = config.AI_API_URL
        self.model = config.AI_MODEL
        self.provider = config.AI_PROVIDER

    def get_status(self) -> Dict:
        provider_label = 'OpenRouter' if self.provider == 'openrouter' else self.provider.title()
        return {
            'enabled': self.enabled,
            'configured': bool(self.api_key),
            'provider': self.provider,
            'model': self.model,
            'message': (
                f'AI resume coach is active ({provider_label}).'
                if self.enabled and self.api_key
                else USER_DISABLED_MESSAGE
            ),
        }

    def get_recommendations(
        self,
        resume_text: str,
        skills: Dict[str, List[str]],
        job_titles: Optional[List[str]] = None,
    ) -> Dict:
        if not self.enabled:
            return {
                'available': False,
                'disabled': True,
                'error': False,
                'recommendations': [],
                'summary': None,
                'message': USER_DISABLED_MESSAGE,
            }

        if not self.api_key:
            return {
                'available': False,
                'disabled': True,
                'error': False,
                'recommendations': [],
                'summary': None,
                'message': USER_UNAVAILABLE_MESSAGE,
            }

        try:
            return self._call_external_api(resume_text, skills, job_titles or [])
        except Exception as exc:
            logger.error('AI recommendation failed: %s', exc)
            return self._error_result()

    def _call_external_api(
        self,
        resume_text: str,
        skills: Dict[str, List[str]],
        job_titles: List[str],
    ) -> Dict:
        skill_summary = ', '.join(
            f'{cat}: {", ".join(items)}' for cat, items in skills.items() if items
        )
        jobs_context = ', '.join(job_titles[:3]) if job_titles else 'general tech roles'

        prompt = (
            'You are an expert resume coach. Analyze this resume and provide 5 specific, '
            'actionable improvement recommendations. Focus on content, keywords, structure, and gaps. '
            'Be concise (1-2 sentences each).\n\n'
            f'Target roles context: {jobs_context}\n'
            f'Skills detected: {skill_summary}\n\n'
            f'Resume excerpt:\n{resume_text[:4000]}'
        )

        headers = build_chat_headers()
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': 'You are a professional resume improvement coach.'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': 800,
            'temperature': 0.7,
        }

        response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        if not response.ok:
            logger.error(
                'AI API request failed: status=%s body=%s',
                response.status_code,
                response.text[:500],
            )
            raise RuntimeError('ai_request_failed')

        data = response.json()
        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            logger.error('Unexpected AI API response shape: %s', str(data)[:300])
            raise RuntimeError('unexpected_response_shape')

        lines = [line.strip().lstrip('0123456789.-) ') for line in content.split('\n') if line.strip()]
        recommendations = [line for line in lines if len(line) > 10][:8]

        return {
            'available': True,
            'disabled': False,
            'error': False,
            'recommendations': recommendations,
            'summary': recommendations[0] if recommendations else None,
            'message': f'AI-powered recommendations via {self.provider.title()}.',
        }

    def _error_result(self) -> Dict:
        return {
            'available': False,
            'disabled': False,
            'error': True,
            'recommendations': [],
            'summary': None,
            'message': USER_ERROR_MESSAGE,
        }

    def get_placeholder_preview(self, skills: Dict[str, List[str]], feedback: Dict) -> Dict:
        previews = []
        if feedback.get('improvements'):
            previews.append(f'Address: {feedback["improvements"][0]}')
        if not skills.get('soft_skills'):
            previews.append('Add measurable soft-skill examples (leadership, collaboration).')
        previews.append('Tailor your summary to match your top matched job titles.')
        previews.append('Quantify impact in bullet points (%, $, time saved).')
        previews.append('Mirror keywords from job descriptions in your skills section.')

        return {
            'available': False,
            'disabled': True,
            'error': False,
            'recommendations': previews,
            'summary': 'Preview of AI coaching (enable API for full personalized analysis)',
            'message': self.get_status()['message'],
        }

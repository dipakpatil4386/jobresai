import base64
import io
from typing import Callable, Dict, Optional

from services.ai_recommendations import AIRecommendationService
from services.ats_scorer import ATSScorer
from services.cover_letter import CoverLetterGenerator
from services.feedback import ResumeFeedbackGenerator
from services.job_feeds import JobFeedService
from services.job_matcher import JobMatcher
from services.resume_processor import ResumeProcessor

ProgressCallback = Callable[[str, int, str], None]


class AnalysisPipeline:
    STEPS = [
        ('parse', 10, 'Parsing resume...'),
        ('skills', 25, 'Extracting skills...'),
        ('jobs', 45, 'Matching jobs...'),
        ('feeds', 60, 'Fetching live job listings...'),
        ('ats', 75, 'Calculating ATS score...'),
        ('feedback', 85, 'Generating feedback...'),
        ('cover_letter', 92, 'Drafting cover letter...'),
        ('ai', 96, 'Running AI coach...'),
        ('done', 100, 'Complete'),
    ]

    def __init__(self):
        self.resume_processor = ResumeProcessor()
        self.job_matcher = JobMatcher()
        self.feedback_generator = ResumeFeedbackGenerator()
        self.ats_scorer = ATSScorer()
        self.ai_service = AIRecommendationService()
        self.job_feeds = JobFeedService()
        self.cover_letter_gen = CoverLetterGenerator()

    def _emit(self, callback: Optional[ProgressCallback], step: str, percent: int, message: str):
        if callback:
            callback(step, percent, message)

    def _public_analysis(self, resume_analysis: dict) -> dict:
        return {k: v for k, v in resume_analysis.items() if not k.startswith('_')}

    def run(
        self,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        pasted_text: Optional[str] = None,
        target_role: str = '',
        progress: Optional[ProgressCallback] = None,
    ) -> Dict:
        self._emit(progress, 'parse', 10, 'Parsing resume...')

        if pasted_text and pasted_text.strip():
            resume_analysis = self.resume_processor.analyze_text(pasted_text.strip())
            resume_analysis['_resume_text'] = pasted_text.strip()
        elif file_bytes and filename:
            text = self.resume_processor.extract_text_from_bytes(file_bytes, filename)
            if not text.strip():
                raise ValueError('Could not extract text from file')
            resume_analysis = self.resume_processor.analyze_text(text)
            resume_analysis['_resume_text'] = text
        else:
            raise ValueError('Provide a resume file or paste resume text')

        resume_text = resume_analysis.pop('_resume_text', '')

        self._emit(progress, 'skills', 25, 'Extracting skills...')
        self._emit(progress, 'jobs', 45, 'Matching jobs...')
        job_recommendations = self.job_matcher.generate_recommendations(
            resume_analysis, resume_text, target_role=target_role
        )

        self._emit(progress, 'feeds', 60, 'Fetching live job listings...')
        job_titles = [r['job']['title'] for r in job_recommendations.get('recommendations', [])]
        live_feeds = self.job_feeds.fetch_jobs(
            query=target_role or job_titles[0] if job_titles else 'software developer',
            location='',
            skills=resume_analysis.get('skills', {}),
        )

        self._emit(progress, 'ats', 75, 'Calculating ATS score...')
        ats_result = self.ats_scorer.score(resume_text, resume_analysis['skills'])

        self._emit(progress, 'feedback', 85, 'Generating feedback...')
        resume_feedback = self.feedback_generator.analyze_resume_strength(
            resume_analysis, ats_result
        )
        improvement_suggestions = self.feedback_generator.generate_improvement_suggestions(
            resume_analysis, job_recommendations
        )

        self._emit(progress, 'cover_letter', 92, 'Drafting cover letter...')
        top_job = job_recommendations['recommendations'][0]['job'] if job_recommendations['recommendations'] else None
        cover_letter = self.cover_letter_gen.generate(
            resume_analysis, top_job, resume_text, target_role
        )

        self._emit(progress, 'ai', 96, 'Running AI coach...')
        if self.ai_service.enabled:
            ai_result = self.ai_service.get_recommendations(resume_text, resume_analysis['skills'], job_titles)
        else:
            ai_result = self.ai_service.get_placeholder_preview(resume_analysis['skills'], resume_feedback)

        self._emit(progress, 'done', 100, 'Complete')

        return {
            'status': 'success',
            'resume_analysis': self._public_analysis(resume_analysis),
            'job_recommendations': job_recommendations,
            'live_job_feeds': live_feeds,
            'resume_feedback': resume_feedback,
            'improvement_suggestions': improvement_suggestions,
            'ats_score': ats_result,
            'cover_letter': cover_letter,
            'ai_recommendations': ai_result,
            'ai_status': self.ai_service.get_status(),
            'job_feeds_status': self.job_feeds.search_service.get_feed_status(),
        }

    @staticmethod
    def decode_file_payload(data: dict) -> tuple:
        content_b64 = data.get('file_content')
        filename = data.get('filename', 'resume.pdf')
        if content_b64:
            return base64.b64decode(content_b64), filename
        return None, filename

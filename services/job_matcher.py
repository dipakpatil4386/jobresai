from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config
from services.job_search import JobSearchService
from services.resume_processor import ResumeProcessor
from services.score_calibration import calibrate_similarity_batch, combined_job_match


class JobMatcher:
    TARGET_ROLE_KEYWORDS = {
        'software_developer': 'python django flask javascript react api development',
        'data_scientist': 'machine learning python tensorflow pandas statistics sql',
        'frontend_developer': 'react javascript typescript html css vue angular',
        'devops_engineer': 'aws docker kubernetes jenkins terraform ci/cd linux',
        'full_stack': 'react node.js python mongodb javascript full stack',
    }

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        self.job_database = self._create_job_database()
        self._fit_vectorizer()
        self.job_search = JobSearchService()
        self.resume_processor = ResumeProcessor()

    def _create_job_database(self) -> List[Dict]:
        return [
            {
                'id': 1,
                'title': 'Senior Python Developer',
                'company': 'TechCorp Inc.',
                'location': 'San Francisco, CA',
                'description': 'Looking for experienced Python developer with Django, Flask, REST APIs, PostgreSQL, Docker, AWS.',
                'requirements': 'Python, Django, Flask, PostgreSQL, Docker, AWS, REST APIs',
                'salary': '$120,000 - $150,000',
                'type': 'Full-time',
                'remote': False,
            },
            {
                'id': 2,
                'title': 'Data Scientist',
                'company': 'DataTech Solutions',
                'location': 'New York, NY',
                'description': 'Seeking data scientist with machine learning, Python, R, TensorFlow, pandas, numpy.',
                'requirements': 'Python, R, Machine Learning, TensorFlow, pandas, numpy, SQL, AWS',
                'salary': '$100,000 - $130,000',
                'type': 'Full-time',
                'remote': False,
            },
            {
                'id': 3,
                'title': 'Frontend Developer',
                'company': 'WebDesign Pro',
                'location': 'Austin, TX',
                'description': 'Frontend developer with React, JavaScript, HTML, CSS, TypeScript.',
                'requirements': 'JavaScript, React, HTML, CSS, TypeScript, Node.js',
                'salary': '$80,000 - $110,000',
                'type': 'Full-time',
                'remote': True,
            },
            {
                'id': 4,
                'title': 'DevOps Engineer',
                'company': 'CloudOps Inc.',
                'location': 'Seattle, WA',
                'description': 'DevOps engineer with AWS, Docker, Kubernetes, Jenkins, Terraform.',
                'requirements': 'AWS, Docker, Kubernetes, Jenkins, Terraform, CI/CD, Linux',
                'salary': '$110,000 - $140,000',
                'type': 'Full-time',
                'remote': True,
            },
            {
                'id': 5,
                'title': 'Full Stack Developer',
                'company': 'StartupXYZ',
                'location': 'Remote',
                'description': 'Full stack developer with React, Node.js, Python, MongoDB.',
                'requirements': 'React, Node.js, Python, MongoDB, JavaScript, HTML, CSS',
                'salary': '$90,000 - $120,000',
                'type': 'Full-time',
                'remote': True,
            },
            {
                'id': 6,
                'title': 'ML Engineer',
                'company': 'AI Labs',
                'location': 'Boston, MA',
                'description': 'Build production ML pipelines with PyTorch, scikit-learn, and cloud deployment.',
                'requirements': 'Python, PyTorch, Machine Learning, AWS, Docker, SQL',
                'salary': '$115,000 - $145,000',
                'type': 'Full-time',
                'remote': True,
            },
        ]

    def _fit_vectorizer(self):
        job_texts = [job['description'] + ' ' + job['requirements'] for job in self.job_database]
        self.job_vectors = self.vectorizer.fit_transform(job_texts)

    def calculate_similarity(self, resume_text: str, target_role: str = '', top_n: int = 5) -> List[Tuple[Dict, float]]:
        query = resume_text
        if target_role and target_role in self.TARGET_ROLE_KEYWORDS:
            query = resume_text + ' ' + self.TARGET_ROLE_KEYWORDS[target_role]

        resume_vector = self.vectorizer.transform([query])
        similarities = cosine_similarity(resume_vector, self.job_vectors)[0]
        top_indices = similarities.argsort()[-top_n:][::-1]

        raw = [float(similarities[idx]) for idx in top_indices]
        calibrated = calibrate_similarity_batch(raw)
        return [(self.job_database[idx], calibrated[i]) for i, idx in enumerate(top_indices)]

    def _job_required_skills(self, job: Dict, job_text: str) -> set:
        req_raw = job.get('requirements', '')
        job_requirements = {r.strip().lower() for r in req_raw.split(',') if r.strip()}
        if not job_requirements and job.get('tags'):
            job_requirements = {t.lower() for t in job['tags'] if isinstance(t, str)}
        if not job_requirements:
            combined = f"{job.get('title', '')} {job_text}".lower()
            for category, keywords in self.resume_processor.skill_keywords.items():
                for skill in keywords:
                    if self.resume_processor._skill_in_text(combined, skill):
                        job_requirements.add(skill.lower())
        return job_requirements

    def _recommendations_from_job_list(
        self,
        jobs: List[Dict],
        resume_analysis: Dict,
        resume_text: str,
        target_role: str,
        top_n: int,
    ) -> List[Tuple[Dict, float]]:
        if not jobs:
            return []

        query = resume_text
        if target_role and target_role in self.TARGET_ROLE_KEYWORDS:
            query = resume_text + ' ' + self.TARGET_ROLE_KEYWORDS[target_role]

        job_texts = [
            f"{j.get('title', '')} {j.get('description', '')} {j.get('requirements', '')}"
            for j in jobs
        ]
        live_vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        vectors = live_vectorizer.fit_transform(job_texts)
        resume_vector = live_vectorizer.transform([query])
        similarities = cosine_similarity(resume_vector, vectors)[0]
        calibrated = calibrate_similarity_batch([float(s) for s in similarities])
        top_indices = similarities.argsort()[-top_n:][::-1]
        return [(jobs[idx], calibrated[idx]) for idx in top_indices]

    def generate_recommendations(self, resume_analysis: Dict, resume_text: str, target_role: str = '', top_n: int = 5) -> Dict:
        skills = resume_analysis.get('skills', {})
        recommendations = []
        source = 'local'

        if config.ARBEITNOW_ENABLED or config.REMOTIVE_ENABLED or config.REMOTEJOBS_ORG_ENABLED:
            live_jobs = self.job_search.fetch_all_for_matching(
                query=target_role or 'developer',
                skills=skills,
            )
            if live_jobs:
                recommendations = self._recommendations_from_job_list(
                    live_jobs, resume_analysis, resume_text, target_role, top_n
                )
                source = 'live'

        if not recommendations:
            recommendations = self.calculate_similarity(resume_text, target_role, top_n)
            source = 'local'

        user_skills = set()
        for skill_category in skills.values():
            user_skills.update(skill.lower() for skill in skill_category)

        detailed = []
        for job, similarity_score in recommendations:
            job_text = f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}"
            job_requirements = self._job_required_skills(job, job_text)

            matched_skills = user_skills.intersection(job_requirements)
            if not matched_skills and job_requirements:
                matched_skills = {
                    s for s in user_skills if any(s in r or r in s for r in job_requirements)
                }

            skill_match_percentage = round(
                len(matched_skills) / len(job_requirements) * 100, 1
            ) if job_requirements else 0.0

            match_percent = combined_job_match(similarity_score, skill_match_percentage)

            detailed.append({
                'job': job,
                'similarity_score': similarity_score,
                'similarity_percent': round(similarity_score * 100, 1),
                'skill_match_percentage': skill_match_percentage,
                'match_percent': match_percent,
                'matched_skills': sorted(matched_skills),
                'missing_skills': sorted(job_requirements - user_skills) if job_requirements else [],
            })

        return {
            'recommendations': detailed,
            'total_recommendations': len(detailed),
            'source': source,
        }

from typing import Dict


class ResumeFeedbackGenerator:
    def analyze_resume_strength(self, resume_analysis: Dict, ats_result: Dict = None) -> Dict:
        skills = resume_analysis['skills']
        total_skills = resume_analysis['total_skills']
        word_count = resume_analysis.get('word_count', 0)

        categories_with_skills = sum(1 for v in skills.values() if v)
        diversity_score = min(categories_with_skills / 4 * 100, 100)
        length_score = min(word_count / 400 * 100, 95) if word_count else 20
        skill_depth = min(total_skills / 14 * 100, 90) if total_skills else 15
        ats_component = ats_result.get('overall_ats_score', 50) if ats_result else 50

        overall = round(
            ats_component * 0.45 + skill_depth * 0.25 + diversity_score * 0.15 + length_score * 0.15,
            1,
        )
        overall = max(12.0, min(98.0, overall))

        feedback = {
            'overall_score': overall,
            'strengths': [],
            'improvements': [],
            'recommendations': [],
        }

        for category, skill_list in skills.items():
            label = category.replace('_', ' ')
            if len(skill_list) > 3:
                feedback['strengths'].append(f'Strong {label} skills')
            elif len(skill_list) == 0:
                feedback['improvements'].append(f'Add {label} skills')

        if total_skills < 5:
            feedback['recommendations'].append('Add more technical skills relevant to your target role')
        if not skills.get('soft_skills'):
            feedback['recommendations'].append('Include soft skills like leadership and communication')
        if not skills.get('programming') and not skills.get('data_science'):
            feedback['recommendations'].append('Highlight programming or data skills for tech roles')

        return feedback

    def generate_improvement_suggestions(self, resume_analysis: Dict, job_recommendations: Dict) -> Dict:
        suggestions = {
            'skill_gaps': [],
            'resume_sections': [],
            'formatting_tips': [
                'Use bullet points for achievements',
                'Quantify accomplishments with numbers',
                'Keep resume to 1-2 pages',
                'Use consistent professional formatting',
            ],
            'keyword_optimization': [
                'Include industry-specific keywords',
                'Use action verbs to describe experiences',
                'Align language with target job descriptions',
                'List relevant certifications',
            ],
        }

        if job_recommendations.get('recommendations'):
            all_missing = set()
            for rec in job_recommendations['recommendations'][:3]:
                all_missing.update(rec['missing_skills'])
            suggestions['skill_gaps'] = list(all_missing)[:10]

        contact_info = resume_analysis.get('contact_info', {})
        if 'email' not in contact_info:
            suggestions['resume_sections'].append('Add a professional email address')
        if 'phone' not in contact_info:
            suggestions['resume_sections'].append('Include a phone number')

        word_count = resume_analysis.get('word_count', 0)
        if word_count < 150:
            suggestions['resume_sections'].append('Expand experience descriptions with measurable outcomes')

        return suggestions

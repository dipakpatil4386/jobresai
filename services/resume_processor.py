import io
import re
import logging
from datetime import datetime
from typing import Dict, Optional

import nltk
import PyPDF2
import docx2txt
import spacy
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)


class ResumeProcessor:
    def __init__(self):
        self._setup_nltk()
        self._load_spacy_model()
        self.skill_keywords = self._load_skill_keywords()

    def _setup_nltk(self):
        for resource in ('punkt', 'punkt_tab', 'stopwords', 'wordnet'):
            try:
                nltk.data.find(f'tokenizers/{resource}' if 'punkt' in resource else f'corpora/{resource}')
            except LookupError:
                nltk.download(resource, quiet=True)

    def _load_spacy_model(self):
        try:
            self.nlp = spacy.load('en_core_web_sm')
        except OSError:
            logger.warning('spaCy model not found')
            self.nlp = None

    def _load_skill_keywords(self) -> Dict[str, list]:
        return {
            'programming': [
                'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php', 'golang', 'rust',
                'typescript', 'swift', 'kotlin', 'scala', 'matlab', 'sql', 'html',
                'css', 'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring',
            ],
            'data_science': [
                'machine learning', 'deep learning', 'data analysis', 'statistics',
                'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch', 'keras',
                'data visualization', 'tableau', 'power bi', 'excel', 'hadoop', 'spark',
            ],
            'cloud': [
                'aws', 'azure', 'google cloud', 'docker', 'kubernetes', 'jenkins',
                'terraform', 'ansible', 'microservices', 'devops', 'ci/cd',
            ],
            'soft_skills': [
                'leadership', 'communication', 'teamwork', 'problem solving',
                'project management', 'agile', 'scrum', 'critical thinking',
            ],
        }

    def extract_text_from_bytes(self, data: bytes, filename: str) -> str:
        lower = filename.lower()
        if lower.endswith('.pdf'):
            return self._extract_pdf_bytes(data)
        if lower.endswith('.docx'):
            return self._extract_docx_bytes(data)
        raise ValueError('Unsupported file format. Use PDF or DOCX.')

    def _extract_pdf_bytes(self, data: bytes) -> str:
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        return ''.join(page.extract_text() or '' for page in reader.pages)

    def _extract_docx_bytes(self, data: bytes) -> str:
        return docx2txt.process(io.BytesIO(data)) or ''

    _SECTION_SKILL_ALIASES = {
        'go': 'Go',
        'golang': 'Go',
        'r': 'R',
        'js': 'JavaScript',
        'ts': 'TypeScript',
        'py': 'Python',
    }

    def _skill_in_text(self, text: str, skill: str) -> bool:
        skill = skill.lower().strip()
        if not skill:
            return False
        if skill == 'golang':
            return bool(re.search(r'\b(?:golang|go\s+lang)\b', text, re.I))
        escaped = re.escape(skill)
        if ' ' in skill or '.' in skill or '+' in skill or '#' in skill:
            pattern = rf'(?<![a-z0-9_]){escaped}(?![a-z0-9_])'
        else:
            pattern = rf'\b{escaped}\b'
        return bool(re.search(pattern, text, re.I))

    def _extract_skills_section_text(self, text: str) -> str:
        match = re.search(
            r'(?im)^(?:technical\s+)?skills?\s*[:\-]?\s*\n(.*?)(?=^\s*(?:experience|work\s+experience|'
            r'employment|education|projects?|certifications?|summary|profile|references?|awards?)\b|\Z)',
            text,
            re.DOTALL,
        )
        if match:
            return match.group(1)
        match = re.search(
            r'(?im)^(?:technical\s+)?skills?\s*[:\-]\s*(.+?)(?:\n\n|\Z)',
            text,
        )
        return match.group(1) if match else ''

    def _tokens_from_skills_section(self, section: str) -> list:
        if not section:
            return []
        tokens = re.split(r'[,|•·\t;/]|\n(?=\s*[-*•])|\s{2,}', section)
        cleaned = []
        for token in tokens:
            token = re.sub(r'^[\s\-*•]+', '', token).strip()
            token = re.sub(r'\s*\([^)]*\)\s*', ' ', token).strip()
            if 2 <= len(token) <= 48 and not re.match(r'^\d+$', token):
                cleaned.append(token)
        return cleaned

    def _canonical_skill(self, token: str) -> Optional[tuple]:
        token_lower = token.lower().strip()
        if token_lower in self._SECTION_SKILL_ALIASES:
            return 'programming', self._SECTION_SKILL_ALIASES[token_lower]
        for category, keywords in self.skill_keywords.items():
            for skill in keywords:
                skill_lower = skill.lower()
                if token_lower == skill_lower or token_lower.replace(' ', '') == skill_lower.replace(' ', ''):
                    return category, skill
                if self._skill_in_text(token_lower, skill):
                    return category, skill
        return None

    def extract_skills(self, text: str) -> Dict[str, list]:
        found_skills = {category: [] for category in self.skill_keywords}
        seen = set()

        def add_skill(category: str, skill: str) -> None:
            key = (category, skill.lower())
            if key not in seen:
                seen.add(key)
                found_skills[category].append(skill)

        for category, keywords in self.skill_keywords.items():
            sorted_keywords = sorted(keywords, key=len, reverse=True)
            for skill in sorted_keywords:
                if self._skill_in_text(text, skill):
                    add_skill(category, skill)

        section_text = self._extract_skills_section_text(text)
        for token in self._tokens_from_skills_section(section_text):
            match = self._canonical_skill(token)
            if match:
                add_skill(match[0], match[1])

        return found_skills

    def extract_contact_info(self, text: str) -> Dict[str, str]:
        contact_info = {}
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_info['email'] = emails[0]

        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text)
        if phones:
            contact_info['phone'] = ''.join(phones[0]) if isinstance(phones[0], tuple) else phones[0]

        return contact_info

    def analyze_text(self, text: str) -> Dict:
        if not text or not text.strip():
            raise ValueError('Resume text is empty')

        skills = self.extract_skills(text)
        contact_info = self.extract_contact_info(text)
        total_skills = sum(len(skill_list) for skill_list in skills.values())
        skill_distribution = {
            category: (len(skill_list) / total_skills * 100) if total_skills > 0 else 0
            for category, skill_list in skills.items()
        }

        return {
            'skills': skills,
            'contact_info': contact_info,
            'skill_distribution': skill_distribution,
            'total_skills': total_skills,
            'word_count': len(text.split()),
            'analysis_date': datetime.now().isoformat(),
        }

    def analyze_file(self, file: FileStorage) -> Dict:
        data = file.read()
        text = self.extract_text_from_bytes(data, file.filename or 'resume.pdf')
        if not text.strip():
            raise ValueError('Could not extract text from file')
        result = self.analyze_text(text)
        result['_resume_text'] = text
        return result

    def analyze_upload(self, file: Optional[FileStorage], pasted_text: Optional[str]) -> Dict:
        if pasted_text and pasted_text.strip():
            result = self.analyze_text(pasted_text.strip())
            result['_resume_text'] = pasted_text.strip()
            return result
        if file and file.filename:
            return self.analyze_file(file)
        raise ValueError('Provide a resume file or paste resume text')

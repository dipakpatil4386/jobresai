import io
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFReportExporter:
    def generate(self, results: Dict) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=12, textColor=colors.HexColor('#0f766e'))
        h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor('#115e59'))
        body = styles['BodyText']
        story = []

        story.append(Paragraph('JobRes.ai — Analysis Report', title_style))
        story.append(Paragraph('Generated in memory. No data stored on server.', body))
        story.append(Spacer(1, 0.2 * inch))

        ra = results.get('resume_analysis', {})
        fb = results.get('resume_feedback', {})
        ats = results.get('ats_score', {})
        jobs = results.get('job_recommendations', {}).get('recommendations', [])

        story.append(Paragraph(f'<b>Overall Score:</b> {fb.get("overall_score", 0)}%', h2))
        story.append(Paragraph(f'<b>ATS Score:</b> {ats.get("overall_ats_score", 0)}%', body))
        story.append(Paragraph(f'<b>Total Skills:</b> {ra.get("total_skills", 0)} | <b>Words:</b> {ra.get("word_count", 0)}', body))

        contact = ra.get('contact_info', {})
        if contact:
            story.append(Paragraph(
                f'<b>Contact:</b> {contact.get("email", "—")} | {contact.get("phone", "—")}', body
            ))

        story.append(Paragraph('Skills by Category', h2))
        for cat, skill_list in ra.get('skills', {}).items():
            if skill_list:
                story.append(Paragraph(f'<b>{cat.replace("_", " ").title()}:</b> {", ".join(skill_list)}', body))

        story.append(Paragraph('Top Job Matches', h2))
        job_rows = [['Title', 'Company', 'Match %', 'Skill %']]
        for rec in jobs[:5]:
            j = rec['job']
            job_rows.append([
                j.get('title', ''),
                j.get('company', ''),
                f'{rec.get("similarity_score", 0) * 100:.1f}',
                f'{rec.get("skill_match_percentage", 0):.0f}',
            ])
        if len(job_rows) > 1:
            t = Table(job_rows, colWidths=[2.2 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ccfbf1')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#134e4a')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdfa')]),
            ]))
            story.append(t)

        feeds = results.get('live_job_feeds', {}).get('jobs', [])
        if feeds:
            story.append(Paragraph('Live Job Feed Highlights', h2))
            for job in feeds[:4]:
                story.append(Paragraph(
                    f'• {job.get("title")} at {job.get("company")} ({job.get("source", "")}) — {job.get("location", "")}',
                    body,
                ))

        cl = results.get('cover_letter', {})
        if cl.get('letter'):
            story.append(Paragraph('Cover Letter Draft', h2))
            for para in cl['letter'].split('\n\n'):
                if para.strip():
                    story.append(Paragraph(para.strip().replace('\n', '<br/>'), body))
                    story.append(Spacer(1, 0.08 * inch))

        ai = results.get('ai_recommendations', {})
        recs = ai.get('recommendations') or []
        if recs:
            story.append(Paragraph('AI / Coaching Recommendations', h2))
            for r in recs[:6]:
                story.append(Paragraph(f'• {r}', body))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

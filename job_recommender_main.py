#!/usr/bin/env python3
"""JobRes.ai - Real-time resume analysis (no persistent storage)."""

import logging
import time

from flask import Flask, jsonify, render_template, request, send_file
import io

import config
from services.ai_recommendations import AIRecommendationService
from services.job_matcher import JobMatcher
from services.pdf_export import PDFReportExporter
from services.job_search import JobSearchService
from services.job_description_matcher import JobDescriptionMatcher
from services.pipeline import AnalysisPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH


class _LazyService:
    def __init__(self, factory):
        self._factory = factory
        self._instance = None

    def _get(self):
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)


def _build_services():
    if config.VERCEL:
        return {
            'pipeline': _LazyService(AnalysisPipeline),
            'pdf_exporter': _LazyService(PDFReportExporter),
            'ai_service': _LazyService(AIRecommendationService),
            'job_search': _LazyService(JobSearchService),
            'jd_matcher': _LazyService(JobDescriptionMatcher),
        }
    return {
        'pipeline': AnalysisPipeline(),
        'pdf_exporter': PDFReportExporter(),
        'ai_service': AIRecommendationService(),
        'job_search': JobSearchService(),
        'jd_matcher': JobDescriptionMatcher(),
    }


_services = _build_services()
pipeline = _services['pipeline']
pdf_exporter = _services['pdf_exporter']
ai_service = _services['ai_service']
job_search = _services['job_search']
jd_matcher = _services['jd_matcher']

socketio = None
if config.WEBSOCKET_ENABLED:
    from flask_socketio import SocketIO

    socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')


@app.route('/')
def index():
    from services.job_feeds import JobFeedService
    feeds = JobFeedService()
    return render_template(
        'index.html',
        ai_status=ai_service.get_status(),
        feeds_status=feeds.get_status(),
        target_roles=list(JobMatcher.TARGET_ROLE_KEYWORDS.keys()),
        websocket_enabled=config.WEBSOCKET_ENABLED,
        max_upload_mb=config.MAX_UPLOAD_MB,
        vercel_deploy=config.VERCEL,
    )


@app.route('/robots.txt')
def robots_txt():
    from flask import Response
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: https://jobres.ai/sitemap.xml\n"
    )
    return Response(body, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    from flask import Response
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        '    <loc>https://jobres.ai/</loc>\n'
        '    <changefreq>weekly</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
        '</urlset>\n'
    )
    return Response(body, mimetype='application/xml')


@app.route('/api/status')
def api_status():
    from services.job_feeds import JobFeedService
    return jsonify({
        'ai': ai_service.get_status(),
        'job_feeds': JobFeedService().get_status(),
        'storage': 'none',
        'mode': 'real-time' if config.WEBSOCKET_ENABLED else 'http',
        'websocket': config.WEBSOCKET_ENABLED,
        'vercel': config.VERCEL,
        'max_upload_mb': config.MAX_UPLOAD_MB,
    })


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    try:
        file = request.files.get('resume')
        pasted_text = request.form.get('resume_text', '').strip()
        target_role = request.form.get('target_role', '').strip()

        file_bytes = None
        filename = None
        if file and file.filename:
            file_bytes = file.read()
            filename = file.filename

        result = pipeline.run(
            file_bytes=file_bytes,
            filename=filename,
            pasted_text=pasted_text or None,
            target_role=target_role,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'status': 'error', 'error': str(exc)}), 400
    except Exception as exc:
        logger.exception('Analysis failed')
        return jsonify({'status': 'error', 'error': str(exc)}), 500


@app.route('/api/export/pdf', methods=['POST'])
def api_export_pdf():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No report data provided'}), 400
        pdf_bytes = pdf_exporter.generate(data)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'jobres-report-{int(time.time())}.pdf',
        )
    except Exception as exc:
        logger.exception('PDF export failed')
        return jsonify({'error': str(exc)}), 500


@app.route('/api/cover-letter', methods=['POST'])
def api_cover_letter():
    try:
        data = request.get_json(force=True)
        job = data.get('job')
        resume_analysis = data.get('resume_analysis')
        resume_text = data.get('resume_text', '')
        if not job or not resume_analysis:
            return jsonify({'error': 'job and resume_analysis required'}), 400
        letter = pipeline.cover_letter_gen.regenerate_for_job(resume_analysis, job, resume_text)
        return jsonify(letter)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/jobs')
def api_jobs():
    remote_only = request.args.get('remote') == 'true'
    jobs = pipeline.job_matcher.job_database
    if remote_only:
        jobs = [j for j in jobs if j.get('remote')]
    return jsonify(jobs)


@app.route('/api/match-job-description', methods=['POST'])
def api_match_job_description():
    try:
        job_description = ''
        file_bytes = None
        filename = None
        pasted_text = ''

        if request.content_type and 'multipart/form-data' in request.content_type:
            job_description = (request.form.get('job_description') or '').strip()
            pasted_text = (request.form.get('resume_text') or '').strip()
            upload = request.files.get('resume')
            if upload and upload.filename:
                file_bytes = upload.read()
                filename = upload.filename
        else:
            data = request.get_json(silent=True) or {}
            job_description = (data.get('job_description') or '').strip()
            pasted_text = (data.get('resume_text') or '').strip()
            file_bytes, filename = AnalysisPipeline.decode_file_payload(data)

        if not job_description:
            return jsonify({'status': 'error', 'error': 'Job description is required'}), 400

        if pasted_text:
            resume_analysis = pipeline.resume_processor.analyze_text(pasted_text.strip())
            resume_text = pasted_text.strip()
        elif file_bytes and filename:
            text = pipeline.resume_processor.extract_text_from_bytes(file_bytes, filename)
            if not text.strip():
                raise ValueError('Could not extract text from resume')
            resume_analysis = pipeline.resume_processor.analyze_text(text)
            resume_text = text
        else:
            return jsonify({'status': 'error', 'error': 'Provide a resume file or paste resume text'}), 400

        public_analysis = {k: v for k, v in resume_analysis.items() if not k.startswith('_')}
        match_result = jd_matcher.match(resume_text, public_analysis, job_description)
        ats_for_jd = pipeline.ats_scorer.score(
            resume_text, public_analysis.get('skills', {}), job_description=job_description
        )

        return jsonify({
            'status': 'success',
            'resume_analysis': public_analysis,
            'job_description_match': match_result,
            'ats_score': ats_for_jd,
        })
    except ValueError as exc:
        return jsonify({'status': 'error', 'error': str(exc)}), 400
    except Exception as exc:
        logger.exception('Job description match failed')
        return jsonify({'status': 'error', 'error': 'An error occurred. Please try again.'}), 500


@app.route('/api/jobs/search', methods=['GET', 'POST'])
def api_jobs_search():
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            query = (data.get('q') or data.get('query') or '').strip()
            work_mode = data.get('work_mode', 'all')
            posted_within = data.get('posted_within', 'all')
            try:
                limit = min(int(data.get('limit', 30) or 30), 50)
            except (ValueError, TypeError):
                limit = 30
        else:
            query = (request.args.get('q') or request.args.get('query') or '').strip()
            work_mode = request.args.get('work_mode', 'all')
            posted_within = request.args.get('posted_within', 'all')
            try:
                limit = min(int(request.args.get('limit', 30)), 50)
            except (ValueError, TypeError):
                limit = 30

        result = job_search.search(
            query=query,
            work_mode=work_mode,
            posted_within=posted_within,
            limit=limit,
        )
        return jsonify(result)
    except Exception as exc:
        logger.exception('Job search failed')
        return jsonify({'status': 'error', 'error': str(exc)}), 500


if config.WEBSOCKET_ENABLED and socketio:
    from flask_socketio import emit

    @socketio.on('connect')
    def on_connect():
        emit('connected', {'message': 'WebSocket ready'})

    @socketio.on('analyze')
    def on_analyze(data):
        sid = request.sid

        def progress(step, percent, message):
            socketio.emit('progress', {'step': step, 'percent': percent, 'message': message}, to=sid)

        try:
            pasted_text = (data or {}).get('resume_text', '').strip()
            target_role = (data or {}).get('target_role', '').strip()
            file_bytes, filename = AnalysisPipeline.decode_file_payload(data or {})

            result = pipeline.run(
                file_bytes=file_bytes,
                filename=filename,
                pasted_text=pasted_text or None,
                target_role=target_role,
                progress=progress,
            )
            emit('complete', result)
        except ValueError as exc:
            emit('error', {'error': str(exc)})
        except Exception as exc:
            logger.exception('WebSocket analysis failed')
            emit('error', {'error': 'An error occurred. Please try again.'})


if __name__ == '__main__':
    if not socketio:
        raise RuntimeError('WebSocket is disabled. Set WEBSOCKET_ENABLED=true for local dev server.')
    print('Starting JobRes.ai with WebSocket support')
    print(f'AI: {"on" if config.AI_RECOMMENDATIONS_ENABLED else "off"} | Job feeds: {"on" if config.JOB_FEEDS_ENABLED else "preview"}')
    print('Open http://localhost:5000')
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

(function () {
    const THEME_KEY = 'jobres-theme';
    let lastResults = null;
    let lastResumeText = '';
    let socket = null;

    const themeToggle = document.getElementById('themeToggle');
    const analyzeForm = document.getElementById('analyzeForm');
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadArea');
    const uploadFilename = document.getElementById('uploadFilename');
    const loadingPanel = document.getElementById('loadingPanel');
    const resultsSection = document.getElementById('resultsSection');
    const uploadSection = document.getElementById('uploadSection');
    const resultsGrid = document.getElementById('resultsGrid');
    const errorAlert = document.getElementById('errorAlert');
    const submitBtn = document.getElementById('submitBtn');
    const remoteFilter = document.getElementById('remoteFilter');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const loadingMessage = document.getElementById('loadingMessage');

    const STEP_ORDER = ['parse', 'skills', 'jobs', 'feeds', 'ats', 'feedback', 'cover_letter', 'ai', 'done'];
    const JOBRES = window.JOBRES_CONFIG || {};
    const WEBSOCKET_ENABLED = JOBRES.websocketEnabled !== false;
    const MAX_UPLOAD_BYTES = JOBRES.maxUploadBytes || 16 * 1024 * 1024;

    function initSocket() {
        if (!WEBSOCKET_ENABLED || typeof io === 'undefined') return;

        socket = io({ transports: ['websocket', 'polling'] });

        socket.on('connect', () => {});
        socket.on('disconnect', () => {});
        socket.on('connect_error', () => {});

        socket.on('progress', (data) => {
            updateProgress(data.step, data.percent, data.message);
        });

        socket.on('complete', (data) => {
            finishLoading();
            lastResults = data;
            renderResults(data);
        });

        socket.on('error', (data) => {
            finishLoading();
            showError(data.error || 'Analysis failed');
        });
    }

    function initTheme() {
        applyTheme(localStorage.getItem(THEME_KEY) || 'light');
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        themeToggle.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
        localStorage.setItem(THEME_KEY, theme);
    }

    themeToggle.addEventListener('click', () => {
        const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    });

    document.querySelectorAll('#uploadSection .tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('#uploadSection .tab').forEach((t) => t.classList.remove('active'));
            tab.classList.add('active');
            const isFile = tab.dataset.tab === 'file';
            document.getElementById('fileTab').classList.toggle('hidden', !isFile);
            document.getElementById('pasteTab').classList.toggle('hidden', isFile);
        });
    });

    function initJdMatchTabs() {
        document.querySelectorAll('#jdMatchSection .tab').forEach((tab) => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('#jdMatchSection .tab').forEach((t) => t.classList.remove('active'));
                tab.classList.add('active');
                const isFile = tab.dataset.jdTab === 'file';
                document.getElementById('jdFileTab').classList.toggle('hidden', !isFile);
                document.getElementById('jdPasteTab').classList.toggle('hidden', isFile);
            });
        });
    }

    initJdMatchTabs();

    function assignMainUploadFile(file) {
        if (!file) return;
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        if (uploadFilename) uploadFilename.textContent = file.name;
        uploadArea.classList.add('has-file');
    }

    function clearMainUploadFile() {
        fileInput.value = '';
        if (uploadFilename) uploadFilename.textContent = '';
        uploadArea.classList.remove('has-file');
    }

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        if (e.dataTransfer.files.length) assignMainUploadFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files[0]) assignMainUploadFile(fileInput.files[0]);
        else clearMainUploadFile();
    });

    function showError(msg) {
        errorAlert.textContent = msg;
        errorAlert.classList.add('visible');
    }

    function hideError() {
        errorAlert.classList.remove('visible');
    }

    function updateProgress(step, percent, message) {
        if (message) loadingMessage.textContent = message;
        if (typeof percent === 'number') {
            progressBar.style.width = `${percent}%`;
            progressPercent.textContent = `${percent}%`;
        }
        const stepIdx = STEP_ORDER.indexOf(step);
        document.querySelectorAll('.progress-step').forEach((el) => {
            const idx = STEP_ORDER.indexOf(el.dataset.step);
            el.classList.remove('active', 'done');
            if (idx < stepIdx) el.classList.add('done');
            else if (idx === stepIdx) el.classList.add('active');
        });
    }

    function startLoading() {
        submitBtn.disabled = true;
        loadingPanel.classList.add('visible');
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        document.querySelectorAll('.progress-step').forEach((el) => el.classList.remove('active', 'done'));
        updateProgress('parse', 0, 'Starting analysis...');
    }

    function finishLoading() {
        loadingPanel.classList.remove('visible');
        submitBtn.disabled = false;
    }

    function scoreClass(score) {
        if (score >= 70) return 'score-high';
        if (score >= 40) return 'score-medium';
        return 'score-low';
    }

    function escapeHtml(str) {
        if (str == null) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }

    function formatPosted(job) {
        const raw = job.posted_at || job.posted;
        if (!raw) return '';
        try {
            const d = new Date(raw);
            if (Number.isNaN(d.getTime())) return String(raw);
            return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        } catch {
            return String(raw);
        }
    }

    function jobCompanyName(job) {
        const c = job.company;
        if (c && typeof c === 'object') return c.name || 'Company';
        return c || 'Company';
    }

    function jobSnippet(job) {
        const text = job.snippet || job.description || '';
        if (!text) return '';
        return text.length > 160 ? `${text.slice(0, 160).trim()}...` : text;
    }

    function workModeLabel(mode) {
        const labels = { all: 'All locations', remote: 'Remote only', onsite: 'On-site only' };
        return labels[mode] || mode;
    }

    function postedLabel(within) {
        const labels = { all: 'Any time', '1': 'Last 24 hours', '7': 'Last 7 days', '30': 'Last 30 days' };
        return labels[within] || within;
    }

    function renderJobListingCard(job, options = {}) {
        const company = jobCompanyName(job);
        const remote = job.remote === true;
        const workLabel = remote ? 'Remote' : 'On-site';
        const workClass = remote ? 'job-pill-remote' : 'job-pill-onsite';
        const posted = formatPosted(job);
        const snippet = jobSnippet(job);
        const title = escapeHtml(job.title || 'Role');

        let matchHtml = '';
        const matchPct = options.match_percent != null
            ? options.match_percent
            : (options.similarity_score != null ? options.similarity_score * 100 : null);
        if (matchPct != null) {
            const textPct = options.similarity_percent != null
                ? options.similarity_percent
                : (options.similarity_score != null ? options.similarity_score * 100 : null);
            matchHtml = `
                <div class="job-match-row">
                    <span class="job-match-pill">${Number(matchPct).toFixed(0)}% match</span>
                    ${textPct != null ? `<span class="job-match-pill subtle">${Number(textPct).toFixed(0)}% text</span>` : ''}
                    ${options.skill_match_percentage != null ? `<span class="job-match-pill subtle">${options.skill_match_percentage.toFixed(0)}% skills</span>` : ''}
                </div>`;
        }

        let extraHtml = '';
        if (options.matched_skills?.length) {
            extraHtml += `<p class="job-extra matched">Matched: ${options.matched_skills.map(escapeHtml).join(', ')}</p>`;
        }
        if (options.missing_skills?.length) {
            extraHtml += `<p class="job-extra missing">Gaps: ${options.missing_skills.slice(0, 4).map(escapeHtml).join(', ')}</p>`;
        }

        const footerBtn = options.showRegenerateBtn
            ? `<button type="button" class="btn btn-secondary job-card-btn" data-job-index="${options.index}">Cover letter</button>`
            : (job.url && job.url !== '#'
                ? `<a class="job-apply-btn" href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer">View job</a>`
                : '');

        return `
            <article class="job-listing-card">
                <div class="job-card-top">
                    <span class="job-pill job-pill-source">${escapeHtml(job.source || 'Job board')}</span>
                    <span class="job-pill ${workClass}">${workLabel}</span>
                    ${posted ? `<span class="job-pill job-pill-muted">${escapeHtml(posted)}</span>` : ''}
                </div>
                <h3 class="job-card-title" title="${title}">${title}</h3>
                <p class="job-card-company">${escapeHtml(company)}</p>
                ${job.location ? `<p class="job-card-location">${escapeHtml(job.location)}</p>` : ''}
                ${matchHtml}
                ${snippet ? `<p class="job-card-snippet">${escapeHtml(snippet)}</p>` : ''}
                ${extraHtml}
                <div class="job-card-footer">${footerBtn}</div>
            </article>
        `;
    }

    function renderJobListingGrid(jobs, mapOptions) {
        if (!jobs?.length) return '';
        const cards = jobs.map((job, i) => {
            const opts = typeof mapOptions === 'function' ? mapOptions(job, i) : {};
            return renderJobListingCard(job, opts);
        }).join('');
        return `<div class="job-listing-grid">${cards}</div>`;
    }

    function renderAttributionLinks(attribution) {
        if (!attribution?.length) return '';
        return `<div class="search-attribution">${attribution.map((a) =>
            `<a href="${escapeHtml(a.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.name)}</a>`
        ).join('')}</div>`;
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    function renderSkillChart(distribution) {
        const rows = Object.entries(distribution || {})
            .filter(([, v]) => v > 0)
            .map(([cat, val]) => `
                <div class="chart-row">
                    <span class="chart-label">${escapeHtml(cat.replace(/_/g, ' '))}</span>
                    <div class="chart-bar-wrap"><div class="chart-bar" style="width:0" data-width="${val}"></div></div>
                    <span class="chart-value">${val.toFixed(0)}%</span>
                </div>
            `).join('');
        return `<div class="chart-bars">${rows || '<p class="subtitle">No skills detected</p>'}</div>`;
    }

    function animateCharts() {
        requestAnimationFrame(() => {
            document.querySelectorAll('.chart-bar[data-width]').forEach((bar) => {
                bar.style.width = `${bar.dataset.width}%`;
            });
        });
    }

    function renderJobs(recommendations) {
        const remoteOnly = remoteFilter.checked;
        const filtered = (recommendations || []).filter((rec) => !remoteOnly || rec.job.remote);
        if (!filtered.length) return '<p class="subtitle">No jobs match this filter.</p>';
        const cards = filtered.map((rec) => renderJobListingCard(rec.job, {
            similarity_score: rec.similarity_score,
            similarity_percent: rec.similarity_percent,
            match_percent: rec.match_percent,
            skill_match_percentage: rec.skill_match_percentage,
            matched_skills: rec.matched_skills,
            missing_skills: rec.missing_skills,
            showRegenerateBtn: true,
            index: (recommendations || []).indexOf(rec),
        })).join('');
        return `<div class="job-listing-grid">${cards}</div>`;
    }

    function renderLiveFeeds(feeds) {
        if (!feeds || !feeds.jobs || !feeds.jobs.length) {
            return '<p class="subtitle">No feed results</p>';
        }
        let attribution = renderAttributionLinks(feeds.attribution);
        if (!attribution && (feeds.source_type === 'arbeitnow' || feeds.source_type === 'multi')) {
            attribution = '<div class="search-attribution"><a href="https://www.arbeitnow.com" target="_blank" rel="noopener noreferrer">Arbeitnow</a><a href="https://remotive.com" target="_blank" rel="noopener noreferrer">Remotive</a><a href="https://remotejobs.org" target="_blank" rel="noopener noreferrer">RemoteJobs.org</a></div>';
        }
        return renderJobListingGrid(feeds.jobs) + attribution;
    }

    function renderResults(data) {
        const ra = data.resume_analysis;
        const fb = data.resume_feedback;
        const jobs = data.job_recommendations;
        const sug = data.improvement_suggestions;
        const ats = data.ats_score;
        const ai = data.ai_recommendations;
        const feeds = data.live_job_feeds;
        const feedsStatus = data.job_feeds_status || {};
        const cl = data.cover_letter || {};

        const skillsHtml = Object.entries(ra.skills || {})
            .filter(([, list]) => list.length)
            .map(([cat, list]) => `
                <h4 style="margin-top:0.75rem;font-size:0.9rem">${escapeHtml(cat.replace(/_/g, ' '))}</h4>
                <div class="skill-tags">${list.map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('')}</div>
            `).join('');

        const contact = ra.contact_info || {};
        const contactHtml = (contact.email || contact.phone)
            ? `<p><strong>Email:</strong> ${escapeHtml(contact.email || '—')}</p><p><strong>Phone:</strong> ${escapeHtml(contact.phone || '—')}</p>`
            : '<p class="subtitle">No contact info detected</p>';

        const aiEnabled = ai.available && !ai.disabled;
        const aiPanelClass = aiEnabled ? 'ai-panel enabled' : 'ai-panel';
        const aiBadge = aiEnabled ? 'AI Active' : (ai.error ? 'Unavailable' : 'AI Disabled');
        const aiCoachMessage = ai.error
            ? 'An error occurred. Please try again later.'
            : (ai.message || (ai.disabled ? 'AI resume coach is not available.' : ''));
        const feedBadge = feeds?.live ? 'Live feeds' : 'Preview feeds';
        const recSourceNote = jobs.source === 'live' || jobs.source === 'arbeitnow'
            ? '<p class="subtitle" style="margin-bottom:0.75rem;font-size:0.85rem">Ranked from live job listings (Arbeitnow, Remotive, RemoteJobs.org) matched to your resume.</p>'
            : '';

        resultsGrid.innerHTML = `
            <div class="panel card resume-overview-card full-width">
                <h2>Resume overview</h2>
                <div class="resume-overview-layout">
                    <div class="resume-overview-score">
                        <div class="score-ring ${scoreClass(fb.overall_score)}">${fb.overall_score}%</div>
                        <p class="resume-overview-score-label">Overall score</p>
                        <div class="resume-overview-contact">${contactHtml}</div>
                        <p class="resume-overview-meta">Words: ${ra.word_count || '—'}</p>
                    </div>
                    <div class="resume-overview-skills">
                        <h3>Skills (${ra.total_skills})</h3>
                        ${skillsHtml}
                    </div>
                    <div class="resume-overview-chart">
                        <h3>Skill distribution</h3>
                        ${renderSkillChart(ra.skill_distribution)}
                    </div>
                </div>
            </div>

            <div class="panel card ats-card">
                <h2>ATS readiness</h2>
                <div class="ats-card-body">
                    <div class="score-ring ${scoreClass(ats.overall_ats_score)}">${ats.overall_ats_score}%</div>
                    <div class="ats-metrics">
                        <div class="ats-metric"><strong>${ats.keyword_score}%</strong><span>Keywords</span></div>
                        <div class="ats-metric"><strong>${ats.section_score}%</strong><span>Sections</span></div>
                        <div class="ats-metric"><strong>${ats.skill_density_score}%</strong><span>Skills</span></div>
                    </div>
                </div>
                ${(ats.tips || []).length ? `<ul class="suggestion-list ats-tips">${ats.tips.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}</ul>` : ''}
            </div>

            <div class="panel card">
                <h2>Resume feedback</h2>
                ${(fb.strengths || []).length ? `<h4>Strengths</h4><ul class="feedback-list">${fb.strengths.map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
                ${(fb.improvements || []).length ? `<h4 style="margin-top:0.75rem">Improve</h4><ul class="feedback-list">${fb.improvements.map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
            </div>

            <div class="panel card">
                <h2>Improvement suggestions</h2>
                ${(sug.skill_gaps || []).length ? `<h4>Skill gaps</h4><ul class="suggestion-list">${sug.skill_gaps.slice(0, 6).map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
                <h4 style="margin-top:0.75rem">Formatting</h4>
                <ul class="suggestion-list">${(sug.formatting_tips || []).map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
            </div>

            <div class="panel card full-width">
                <h2>Job recommendations</h2>
                ${recSourceNote}
                <div id="jobList">${renderJobs(jobs.recommendations)}</div>
            </div>

            <div class="panel card full-width">
                <h2>Live job feeds</h2>
                <span class="status-badge" style="position:static;display:inline-block;margin-bottom:0.75rem;background:var(--surface-alt)">${feedBadge}</span>
                <p class="subtitle" style="margin-bottom:1rem;font-size:0.85rem">${escapeHtml(feedsStatus.message || '')}</p>
                <div id="liveFeedList">${renderLiveFeeds(feeds)}</div>
            </div>

            <div class="panel card full-width">
                <h2>Cover letter</h2>
                <p class="subtitle">For: ${escapeHtml(cl.position || 'Top match')} at ${escapeHtml(cl.recipient || 'Company')}</p>
                <div class="cover-letter-box" id="coverLetterBox">${escapeHtml(cl.letter || '')}</div>
                <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
                    <button type="button" class="btn btn-secondary" id="copyLetterBtn">Copy letter</button>
                    <span style="font-size:0.85rem;color:var(--text-muted);align-self:center">${cl.word_count || 0} words ${cl.ai_enhanced ? '(AI enhanced)' : '(template)'}</span>
                </div>
            </div>

            <div class="panel card ${aiPanelClass} full-width">
                <span class="ai-badge">${aiBadge}</span>
                <h2>AI resume coach</h2>
                <p class="subtitle" style="margin-bottom:1rem">${escapeHtml(aiCoachMessage)}</p>
                <ul class="suggestion-list">${(ai.recommendations || []).map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
            </div>
        `;

        const letterBox = document.getElementById('coverLetterBox');
        if (letterBox && cl.letter) letterBox.textContent = cl.letter;

        document.getElementById('copyLetterBtn')?.addEventListener('click', async (e) => {
            const text = letterBox?.textContent || cl.letter || '';
            try {
                await navigator.clipboard.writeText(text);
                const btn = e.currentTarget;
                const orig = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => { btn.textContent = orig; }, 2000);
            } catch {
                showError('Could not copy to clipboard. Please select and copy manually.');
            }
        });

        document.querySelectorAll('[data-job-index]').forEach((btn) => {
            btn.addEventListener('click', async () => {
                const idx = parseInt(btn.dataset.jobIndex, 10);
                const job = jobs.recommendations[idx]?.job;
                if (!job) return;
                btn.disabled = true;
                btn.textContent = 'Generating...';
                try {
                    const res = await fetch('/api/cover-letter', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            job,
                            resume_analysis: ra,
                            resume_text: lastResumeText,
                        }),
                    });
                    const letter = await res.json();
                    if (letter.letter) {
                        document.getElementById('coverLetterBox').textContent = letter.letter;
                        lastResults.cover_letter = letter;
                    }
                } catch (err) {
                    showError(err.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Regenerate cover letter';
                }
            });
        });

        resultsSection.classList.add('visible');
        animateCharts();
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    remoteFilter.addEventListener('change', () => {
        if (lastResults) renderResults(lastResults);
    });

    async function buildPayload() {
        const isPaste = document.querySelector('#uploadSection .tab.active')?.dataset.tab === 'paste';
        const targetRole = document.getElementById('targetRole').value;

        if (isPaste) {
            const text = document.getElementById('resumeText').value.trim();
            if (!text) throw new Error('Paste your resume text or switch to file upload.');
            lastResumeText = text;
            return { resume_text: text, target_role: targetRole };
        }

        if (!fileInput.files.length) throw new Error('Select a PDF or DOCX file.');
        const file = fileInput.files[0];
        if (file.size > MAX_UPLOAD_BYTES) {
            const mb = Math.round(MAX_UPLOAD_BYTES / (1024 * 1024));
            throw new Error(`File is too large. Maximum size is ${mb}MB.`);
        }
        lastResumeText = '';
        if (WEBSOCKET_ENABLED) {
            const base64 = await fileToBase64(file);
            return {
                file_content: base64,
                filename: file.name,
                target_role: targetRole,
            };
        }
        return {
            filename: file.name,
            target_role: targetRole,
            use_file_input: true,
        };
    }

    async function analyzeViaWebSocket(payload) {
        return new Promise((resolve, reject) => {
            if (!socket?.connected) {
                reject(new Error('WebSocket not connected. Retrying...'));
                return;
            }

            const onComplete = (data) => {
                socket.off('complete', onComplete);
                socket.off('error', onError);
                resolve(data);
            };
            const onError = (data) => {
                socket.off('complete', onComplete);
                socket.off('error', onError);
                reject(new Error(data?.error || 'Analysis failed'));
            };

            socket.once('complete', onComplete);
            socket.once('error', onError);
            socket.emit('analyze', payload);
        });
    }

    async function analyzeViaHttpWithProgress(payload) {
        const steps = [
            ['parse', 12, 'Parsing resume...'],
            ['skills', 28, 'Extracting skills...'],
            ['jobs', 45, 'Matching jobs...'],
            ['feeds', 58, 'Fetching live job listings...'],
            ['ats', 72, 'Calculating ATS score...'],
            ['feedback', 84, 'Generating feedback...'],
            ['cover_letter', 92, 'Drafting cover letter...'],
            ['ai', 97, 'Running AI coach...'],
        ];
        let stepIdx = 0;
        updateProgress(steps[0][0], steps[0][1], steps[0][2]);
        const timer = setInterval(() => {
            stepIdx = Math.min(stepIdx + 1, steps.length - 1);
            const [step, percent, message] = steps[stepIdx];
            updateProgress(step, percent, message);
        }, 1200);

        try {
            return await analyzeViaHttp(payload);
        } finally {
            clearInterval(timer);
            updateProgress('done', 100, 'Complete');
        }
    }

    async function analyzeViaHttp(payload) {
        const formData = new FormData();
        if (payload.resume_text) {
            formData.append('resume_text', payload.resume_text);
        } else if (payload.use_file_input && fileInput.files[0]) {
            formData.append('resume', fileInput.files[0], fileInput.files[0].name);
        } else if (payload.file_content) {
            const bytes = Uint8Array.from(atob(payload.file_content), (c) => c.charCodeAt(0));
            const blob = new Blob([bytes]);
            formData.append('resume', blob, payload.filename);
        }
        formData.append('target_role', payload.target_role || '');
        const res = await fetch('/api/analyze', { method: 'POST', body: formData });
        let data;
        try {
            data = await res.json();
        } catch {
            throw new Error(`Server error (${res.status})`);
        }
        if (!res.ok || data.status === 'error') throw new Error(data.error || 'Analysis failed');
        return data;
    }

    analyzeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideError();
        startLoading();

        try {
            const payload = await buildPayload();
            let data;

            if (WEBSOCKET_ENABLED && socket?.connected) {
                data = await analyzeViaWebSocket(payload);
            } else {
                if (!WEBSOCKET_ENABLED) {
                    loadingMessage.textContent = 'Analyzing resume...';
                } else {
                    loadingMessage.textContent = 'Using HTTP fallback...';
                }
                data = await analyzeViaHttpWithProgress(payload);
            }

            lastResults = data;
            if (payload.resume_text) lastResumeText = payload.resume_text;
            renderResults(data);
        } catch (err) {
            if (err.message.includes('WebSocket')) {
                try {
                    const payload = await buildPayload();
                    const data = await analyzeViaHttpWithProgress(payload);
                    lastResults = data;
                    renderResults(data);
                    return;
                } catch (fallbackErr) {
                    showError(fallbackErr.message);
                }
            } else {
                showError(err.message);
            }
        } finally {
            finishLoading();
        }
    });

    document.getElementById('newAnalysisBtn').addEventListener('click', () => {
        resultsSection.classList.remove('visible');
        lastResults = null;
        analyzeForm.reset();
        clearMainUploadFile();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    document.getElementById('exportBtn').addEventListener('click', () => {
        if (!lastResults) return;
        const blob = new Blob([JSON.stringify(lastResults, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `jobres-analysis-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
    });

    document.getElementById('exportPdfBtn').addEventListener('click', async () => {
        if (!lastResults) return;
        const btn = document.getElementById('exportPdfBtn');
        btn.disabled = true;
        btn.textContent = 'Generating PDF...';
        try {
            const res = await fetch('/api/export/pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lastResults),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'PDF export failed');
            }
            const blob = await res.blob();
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `jobres-report-${Date.now()}.pdf`;
            a.click();
            URL.revokeObjectURL(a.href);
        } catch (err) {
            showError(err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Export PDF';
        }
    });

    function getJobSearchValues() {
        return {
            query: document.getElementById('jobSearchInput')?.value.trim() || '',
            work_mode: document.getElementById('workModeFilter')?.value || 'all',
            posted_within: document.getElementById('postedFilter')?.value || 'all',
        };
    }

    function showSearchError(msg) {
        const el = document.getElementById('searchErrorAlert');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('visible');
    }

    function hideSearchError() {
        document.getElementById('searchErrorAlert')?.classList.remove('visible');
    }

    async function executeJobSearch() {
        hideSearchError();

        const { query, work_mode, posted_within } = getJobSearchValues();
        const loading = document.getElementById('searchLoadingPanel');
        const btn = document.getElementById('jobSearchBtn');

        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Searching...';
        }
        loading?.classList.add('visible');

        setActiveNav('jobSearchSection');
        document.getElementById('jobSearchSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });

        try {
            const res = await fetch('/api/jobs/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ q: query, work_mode, posted_within, limit: 30 }),
            });
            const data = await res.json();
            if (!res.ok || data.status === 'error') {
                throw new Error(data.error || 'Search failed');
            }
            renderSearchResults(data);
        } catch (err) {
            showSearchError(err.message);
        } finally {
            loading?.classList.remove('visible');
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Search jobs';
            }
        }
    }

    function renderSearchResults(data) {
        const container = document.getElementById('jobSearchResults');
        if (!container) return;

        if (!data.jobs || !data.jobs.length) {
            container.innerHTML = `
                <div class="search-empty-state">
                    <p class="search-empty-title">No jobs found</p>
                    <p class="search-empty-text">Try broader keywords, another company name, or relax your filters.</p>
                </div>`;
            container.classList.remove('hidden');
            return;
        }

        const sources = (data.sources || []).map((s) => s.replace('_org', '.org')).join(', ') || 'job boards';
        const attribution = renderAttributionLinks(data.attribution) || (
            data.sources?.length
                ? '<div class="search-attribution"><a href="https://www.arbeitnow.com" target="_blank" rel="noopener noreferrer">Arbeitnow</a><a href="https://remotive.com" target="_blank" rel="noopener noreferrer">Remotive</a><a href="https://remotejobs.org" target="_blank" rel="noopener noreferrer">RemoteJobs.org</a></div>'
                : ''
        );

        const workMode = document.getElementById('workModeFilter')?.value || data.work_mode || 'all';
        const postedWithin = document.getElementById('postedFilter')?.value || data.posted_within || 'all';

        container.innerHTML = `
            <div class="search-results-header">
                <p class="search-results-count"><strong>${data.count}</strong> job${data.count === 1 ? '' : 's'} found</p>
                <p class="search-results-query">${data.query ? `for "<span>${escapeHtml(data.query)}</span>"` : 'Latest listings'}</p>
                <div class="search-results-filters">
                    <span class="filter-chip">${escapeHtml(workModeLabel(workMode))}</span>
                    <span class="filter-chip">${escapeHtml(postedLabel(postedWithin))}</span>
                    <span class="filter-chip">${escapeHtml(sources)}</span>
                </div>
            </div>
            ${renderJobListingGrid(data.jobs)}
            ${attribution}
        `;
        container.classList.remove('hidden');
        container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    const jobSearchForm = document.getElementById('jobSearchForm');
    if (jobSearchForm) {
        jobSearchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            executeJobSearch();
        });
    }

    function showJdMatchError(msg) {
        const el = document.getElementById('jdMatchErrorAlert');
        if (!el) return;
        el.textContent = msg;
        el.classList.add('visible');
    }

    function hideJdMatchError() {
        document.getElementById('jdMatchErrorAlert')?.classList.remove('visible');
    }

    function renderJdMatchResults(data) {
        const container = document.getElementById('jdMatchResults');
        if (!container) return;

        const m = data.job_description_match;
        const ats = data.ats_score || {};
        const ringClass = scoreClass(m.overall_match_score);

        container.innerHTML = `
            <div class="jd-match-results-panel panel">
                <div class="jd-match-header">
                    <div>
                        <h3>${escapeHtml(m.job_title)}</h3>
                        <p class="subtitle" style="margin:0.25rem 0 0">${escapeHtml(m.verdict)} — ${escapeHtml(m.summary)}</p>
                    </div>
                    <div class="score-ring ${ringClass}">${m.overall_match_score}%</div>
                </div>
                <div class="jd-match-metrics">
                    <div class="ats-metric"><strong>${m.text_similarity_score}%</strong><span>Text fit</span></div>
                    <div class="ats-metric"><strong>${m.skill_match_score}%</strong><span>Skills</span></div>
                    <div class="ats-metric"><strong>${m.keyword_match_score}%</strong><span>Keywords</span></div>
                    <div class="ats-metric"><strong>${ats.overall_ats_score ?? '—'}%</strong><span>ATS vs JD</span></div>
                </div>
                ${m.matched_skills?.length ? `<p class="job-extra matched"><strong>Matched skills:</strong> ${m.matched_skills.map(escapeHtml).join(', ')}</p>` : ''}
                ${m.missing_skills?.length ? `<p class="job-extra missing"><strong>Missing skills:</strong> ${m.missing_skills.map(escapeHtml).join(', ')}</p>` : ''}
                ${m.matched_keywords?.length ? `<p class="job-extra matched"><strong>Matched keywords:</strong> ${m.matched_keywords.slice(0, 12).map(escapeHtml).join(', ')}</p>` : ''}
                ${m.missing_keywords?.length ? `<p class="job-extra missing"><strong>Keywords to add:</strong> ${m.missing_keywords.slice(0, 10).map(escapeHtml).join(', ')}</p>` : ''}
                ${(ats.tips || []).length ? `<ul class="suggestion-list">${ats.tips.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}</ul>` : ''}
            </div>
        `;
        container.classList.remove('hidden');
        setActiveNav('jdMatchSection');
        document.getElementById('jdMatchSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function initJdUploadArea() {
        const area = document.getElementById('jdUploadArea');
        const input = document.getElementById('jdMatchFile');
        const nameEl = document.getElementById('jdUploadFilename');
        if (!area || !input) return;

        const assignFile = (file) => {
            if (!file) return;
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
            if (nameEl) nameEl.textContent = file.name;
            area.classList.add('has-file');
        };

        const clearFile = () => {
            input.value = '';
            if (nameEl) nameEl.textContent = '';
            area.classList.remove('has-file');
        };

        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            area.classList.add('dragover');
        });
        area.addEventListener('dragleave', () => area.classList.remove('dragover'));
        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('dragover');
            if (e.dataTransfer.files.length) assignFile(e.dataTransfer.files[0]);
        });
        input.addEventListener('change', () => {
            if (input.files.length) assignFile(input.files[0]);
            else clearFile();
        });

    }

    initJdUploadArea();

    const jdMatchForm = document.getElementById('jdMatchForm');
    if (jdMatchForm) {
        jdMatchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            hideJdMatchError();

            const jobDescription = document.getElementById('jdJobDescription')?.value.trim() || '';
            const isJdPaste = document.querySelector('#jdMatchSection .tab.active')?.dataset.jdTab === 'paste';
            const resumeText = document.getElementById('jdMatchResumeText')?.value.trim() || '';
            const jdFileInput = document.getElementById('jdMatchFile');
            const loading = document.getElementById('jdMatchLoadingPanel');
            const btn = document.getElementById('jdMatchBtn');

            if (!jobDescription) {
                showJdMatchError('Paste a job description to match against.');
                return;
            }
            if (isJdPaste) {
                if (!resumeText) {
                    showJdMatchError('Paste your resume text or switch to Upload file.');
                    return;
                }
            } else if (!jdFileInput?.files?.length) {
                showJdMatchError('Select a PDF or DOCX file or switch to Paste text.');
                return;
            }

            if (btn) btn.disabled = true;
            loading?.classList.add('visible');

            try {
                const formData = new FormData();
                formData.append('job_description', jobDescription);
                if (isJdPaste) {
                    formData.append('resume_text', resumeText);
                } else {
                    formData.append('resume', jdFileInput.files[0]);
                }

                const res = await fetch('/api/match-job-description', {
                    method: 'POST',
                    body: formData,
                });
                const data = await res.json();
                if (!res.ok || data.status === 'error') {
                    throw new Error(data.error || 'Match failed');
                }
                renderJdMatchResults(data);
            } catch (err) {
                showJdMatchError(err.message);
            } finally {
                loading?.classList.remove('visible');
                if (btn) btn.disabled = false;
            }
        });
    }

    function setActiveNav(targetId) {
        document.querySelectorAll('.site-nav-link').forEach((link) => {
            link.classList.toggle('active', link.dataset.navTarget === targetId);
        });
    }

    function initSiteNav() {
        const nav = document.getElementById('siteNav');
        const sticky = document.querySelector('.site-sticky-top');
        if (!nav) return;

        const sectionIds = ['uploadSection', 'jdMatchSection', 'jobSearchSection'];
        const targets = sectionIds.map((id) => document.getElementById(id)).filter(Boolean);

        const updateStickyOffset = () => {
            if (sticky) {
                document.documentElement.style.setProperty(
                    '--site-sticky-height',
                    `${sticky.offsetHeight + 16}px`
                );
            }
        };
        updateStickyOffset();
        window.addEventListener('resize', updateStickyOffset);

        nav.querySelectorAll('.site-nav-link').forEach((link) => {
            link.addEventListener('click', () => {
                setActiveNav(link.dataset.navTarget);
            });
        });

        if ('IntersectionObserver' in window && targets.length && sticky) {
            const observer = new IntersectionObserver(
                (entries) => {
                    const visible = entries
                        .filter((e) => e.isIntersecting)
                        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
                    if (visible.length) {
                        setActiveNav(visible[0].target.id);
                    }
                },
                {
                    rootMargin: `-${sticky.offsetHeight + 8}px 0px -50% 0px`,
                    threshold: [0.12, 0.3, 0.5],
                }
            );
            targets.forEach((section) => observer.observe(section));
        }
    }

    document.body.style.fontFamily = "'Inter', 'Segoe UI', system-ui, sans-serif";
    initTheme();
    initSiteNav();
    if (WEBSOCKET_ENABLED) initSocket();
})();





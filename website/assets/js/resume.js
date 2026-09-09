/*
 * MavaraResume — the shared resume/profile module (schema v18 —
 * "یکپارچه‌سازی ماژول رزومه", requested: give every team member the same
 * resume-building + profile-editing capabilities Mansour Nasiri's page
 * had, as one shared module for both admin edit and public display).
 *
 * Ported from about-mansour.html's original inline script, generalized to
 * take a `member` object (the /api/v1/team[/<slug>] shape — a
 * team_members row with its `portfolio` array embedded, see
 * api/server.py's _team_public()) instead of being hardwired to fetch
 * Mansour's own settings + API.portfolio.*.
 *
 * Loaded after app.js + site.js, before each page's own inline script.
 * Both about-mansour.html (fixed to slug 'mansour-nasiri') and team.html's
 * ?slug= detail view carry the SAME static "mv*"-id HTML skeleton (see
 * CHANGELOG.md for the exact structure) — this module only fills those
 * ids in on mount(); it never builds page structure. Namespaced under
 * MavaraResume.* (not bare globals, unlike the rest of this codebase's
 * per-page inline scripts) since this is the first genuinely shared
 * module in the project.
 */
const MavaraResume = (() => {
    const CATS = [
        { key: 'CINEMA', fa: 'سینما', en: 'Cinema', highlight: false },
        { key: 'SERIES', fa: 'نمایش خانگی', en: 'Series', highlight: false },
        { key: 'SHORT', fa: 'فیلم کوتاه', en: 'Short films', highlight: true },
        { key: 'THEATER', fa: 'تئاتر', en: 'Theater', highlight: false },
    ];

    let member = null;
    let activeProject = null;
    let currentTab = 'all';
    let viewerImages = [];
    let viewerIndex = 0;

    // ── per-project helpers (unchanged from about-mansour.html) ──
    const pfTitle = p => (lang() === 'en' && p.title_en) ? p.title_en : p.title_fa;
    const pfDirector = p => (lang() === 'en' && p.director_en) ? p.director_en : p.director;
    const pfRole = p => (lang() === 'en' && p.role_en) ? p.role_en : p.role;
    const pfFestival = p => (lang() === 'en' && p.festival_en) ? p.festival_en : p.festival;
    const pfDesc = p => (lang() === 'en' && p.desc_en) ? p.desc_en : p.desc_fa;
    // Year: Jalali in FA, Gregorian in EN (year-only; exact conversion needs full dates).
    const FA_D = '۰۱۲۳۴۵۶۷۸۹';
    const toFa = n => String(n).replace(/\d/g, d => FA_D[d]);
    const pfYear = p => lang() === 'en' ? String(p.year || '') : toFa((Number(p.year) || 0) - 621);
    const isLive = p => p.status === 'now_showing' || p.status === 'NOW_SHOWING' || p.nowShowing === true;
    const livePill = () => `<span class="live-pill"><i class="live-dot"></i>${T('live_pill')}</span>`;

    // When a resume item is currently running (isLive), clicking through
    // to it offers a direct path to reserve a ticket. Matches by title
    // against the active/ongoing events list rather than a dedicated
    // field.
    function reserveButtonHTML(p) {
        if (!isLive(p)) return '';
        const activeEvents = (typeof API !== 'undefined' && API.events && API.events.active) ? API.events.active() : [];
        const matched = activeEvents.find(e => e.title === p.title_fa || e.title_en === p.title_en);
        if (!matched) return '';
        return `<a class="btn btn--gold" href="event-detail.html?id=${encodeURIComponent(matched.id)}" style="display:block;text-align:center;margin-top:12px">${T('b_book') || 'رزرو بلیت'}</a>`;
    }

    // ── per-member helpers ──
    function memberName() { return (lang() === 'en' && member.full_name_en) ? member.full_name_en : member.full_name; }
    function memberEyebrow() { return (lang() === 'en' && member.eyebrow_en) ? member.eyebrow_en : (member.eyebrow || ''); }
    function memberSub() { return (lang() === 'en' && member.role_title_en) ? member.role_title_en : (member.role_title || ''); }
    function memberBio() { return (lang() === 'en' && member.bio_en) ? member.bio_en : (member.bio_fa || ''); }
    function memberBioFull() { return (lang() === 'en' && member.bio_full_en) ? member.bio_full_en : (member.bio_full_fa || ''); }
    function linksHTML() {
        return (member.links || []).map(l => `<a class="btn btn--outline" href="${esc(l.url)}" target="_blank" rel="noopener" style="font-size:12px">${esc(l.label)}</a>`).join('');
    }
    function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }

    // ── mount: entry point called by each page once member data is loaded ──
    function mount(m) {
        member = m;
        activeProject = null;
        currentTab = 'all';
        renderProfile();
        renderResumeList();
        renderSamples(currentTab);
        setupSamplesTabs();
        initBioToggle();
    }

    function renderProfile() {
        if (!member) return;
        const img = document.getElementById('mvProfilePhoto');
        if (img && member.photo) img.src = pp(member.photo);
        setText('mvEyebrow', memberEyebrow());
        setText('mvTitle', memberName());
        setText('mvSub', memberSub());
        const bioP = document.getElementById('mvBioP');
        if (bioP) bioP.innerHTML = `<span>${esc(memberBio())}</span><span class="resume-bio-full">${esc(memberBioFull())}</span>`;
        const moreBtn = document.getElementById('mvBioMore');
        if (moreBtn) moreBtn.style.display = memberBioFull() ? '' : 'none';
        const linksBox = document.getElementById('mvLinksProfile');
        if (linksBox) linksBox.innerHTML = linksHTML();
    }

    function initBioToggle() {
        const box = document.getElementById('mvBioText');
        const btn = document.getElementById('mvBioMore');
        if (!box || !btn || btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';
        btn.onclick = () => {
            const expanded = box.classList.toggle('expanded');
            btn.setAttribute('aria-expanded', expanded);
        };
    }

    function renderResumeList() {
        const root = document.getElementById('mvResumeList');
        if (!root || !member) return;
        root.innerHTML = '';
        CATS.forEach(cat => {
            const items = (member.portfolio || []).filter(p => p.category === cat.key);
            if (!items.length) return;
            const div = document.createElement('div');
            div.className = 'resume-cat' + (cat.highlight ? ' resume-cat--highlight' : '');
            div.innerHTML = `<div class="resume-cat-title"><span class="fa">${lang() === 'en' ? cat.en : cat.fa}</span><span class="en">${lang() === 'en' ? cat.fa : cat.en}</span></div>`;
            const list = document.createElement('div');
            list.className = cat.highlight ? 'resume-grid-2' : '';
            items.forEach(p => {
                const row = document.createElement('div');
                row.className = 'resume-row';
                row.onclick = () => openModal(p);
                const thumb = p.poster ? `<img class="row-poster" src="${pp(p.poster)}" alt="" loading="lazy">` : '';
                if (cat.highlight) {
                    row.innerHTML = `${thumb}<div class="title">${esc(pfTitle(p))}${isLive(p) ? livePill() : ''}<span class="role-tag">(${esc(pfDirector(p))})</span></div><div class="festival"><span class="year">${esc(pfYear(p))}</span>${pfFestival(p) ? ' · ' + esc(pfFestival(p)) : ''}</div>`;
                } else {
                    row.innerHTML = `${thumb}<div class="title">${esc(pfTitle(p))}${isLive(p) ? livePill() : ''}<span class="role-tag">(${esc(pfRole(p))})</span></div><div class="meta"><span class="year">${esc(pfYear(p))}</span> — ${esc(pfDirector(p))}</div>`;
                }
                list.appendChild(row);
            });
            div.appendChild(list);
            root.appendChild(div);
        });
    }

    function openModal(p) {
        activeProject = p;
        renderModal();
        const modal = document.getElementById('mvModal');
        if (modal) modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function openModalById(id) {
        const p = (member && member.portfolio || []).find(x => Number(x.id) === Number(id));
        if (p) openModal(p);
    }

    function renderModal() {
        const p = activeProject; if (!p) return;
        document.getElementById('mvModalTitle').innerHTML = esc(pfTitle(p)) + ' (' + esc(pfYear(p)) + ')' + (isLive(p) ? livePill() : '');
        const header = document.querySelector('#mvModal .modal-header');
        header.querySelector('.modal-language')?.remove();
        const toggle = document.createElement('div'); toggle.className = 'modal-language lang-toggle';
        toggle.innerHTML = `<button type="button" class="${lang() === 'fa' ? 'active' : ''}" onclick="setLang('fa')">فا</button><button type="button" class="${lang() === 'en' ? 'active' : ''}" onclick="setLang('en')">EN</button>`;
        header.insertBefore(toggle, header.querySelector('.modal-close'));
        const body = document.getElementById('mvModalBody');
        // viewerImages is what openViewer()/viewerStep() browse — fullscreen
        // gallery viewer with prev/next.
        viewerImages = (p.gallery || []).map(pp);
        body.innerHTML = `
            ${p.poster ? `<img class="modal-poster" src="${pp(p.poster)}" alt="${esc(pfTitle(p))}" loading="lazy">` : ''}
            <dl class="modal-meta">
                <dt>${T('m_en_title')}</dt><dd>${esc(lang() === 'en' ? (p.title_fa || '—') : (p.title_en || '—'))}</dd>
                <dt>${T('m_year')}</dt><dd>${esc(p.year)}</dd>
                <dt>${T('m_director')}</dt><dd>${esc(pfDirector(p) || '—')}</dd>
                <dt>${T('m_role')}</dt><dd>${esc(pfRole(p) || '—')}</dd>
                ${pfFestival(p) ? `<dt>${T('m_festival')}</dt><dd>${esc(pfFestival(p))}</dd>` : ''}
                ${pfDesc(p) ? `<dt>${T('m_desc')}</dt><dd>${esc(pfDesc(p))}</dd>` : ''}
            </dl>
            ${p.video ? `<video controls src="${pp(p.video)}" style="width:100%;border-radius:var(--radius-sm)"></video>` : ''}
            ${viewerImages.length ? `<div class="modal-gallery">${viewerImages.map((img, i) => `<img src="${img}" alt="" loading="lazy" onclick="MavaraResume.openViewer(${i})">`).join('')}</div>` : ''}
            ${reserveButtonHTML(p)}
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">${linksHTML()}</div>`;
    }

    function closeModal() {
        const modal = document.getElementById('mvModal');
        if (modal) modal.style.display = 'none';
        document.body.style.overflow = '';
    }

    function openViewer(index) {
        viewerIndex = index;
        renderViewerImage();
        const v = document.getElementById('mvViewer');
        if (v) v.style.display = 'flex';
    }

    function renderViewerImage() {
        const img = document.getElementById('mvViewerImg');
        img.src = viewerImages[viewerIndex];
        img.style.display = 'block';
        document.getElementById('mvViewerVideo').style.display = 'none';
        const multi = viewerImages.length > 1;
        document.getElementById('mvViewerPrev').style.display = multi ? 'flex' : 'none';
        document.getElementById('mvViewerNext').style.display = multi ? 'flex' : 'none';
    }

    function viewerStep(dir) {
        if (viewerImages.length < 2) return;
        viewerIndex = (viewerIndex + dir + viewerImages.length) % viewerImages.length;
        renderViewerImage();
    }

    function renderSamples(tab) {
        currentTab = tab;
        const all = member ? (member.portfolio || []) : [];
        const withMedia = all.filter(p => p.poster || p.video || (p.gallery || []).length);
        const filtered = tab === 'photo'
            ? withMedia.filter(p => p.poster && !p.video)
            : tab === 'video'
            ? withMedia.filter(p => p.video)
            : withMedia;
        const gallery = document.getElementById('mvSamplesGallery');
        if (!gallery) return;
        gallery.innerHTML = filtered.map(p => `
            <div class="sample-card" onclick="MavaraResume.openModalById(${p.id})">
                ${p.video ? `<video src="${pp(p.video)}" muted loop preload="metadata"></video><div class="play-icon">▶</div>` : p.poster ? `<img src="${pp(p.poster)}" alt="${esc(pfTitle(p))}" loading="lazy">` : ''}
                <div class="sample-label">${esc(pfTitle(p))}</div>
            </div>
        `).join('') || '<p style="text-align:center;grid-column:1/-1;color:var(--text-muted);padding:40px">' + T('empty_sample') + '</p>';
    }

    function setupSamplesTabs() {
        document.querySelectorAll('#mvSamplesTabs .samples-tab-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('#mvSamplesTabs .samples-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderSamples(btn.dataset.tab);
            };
        });
    }

    // Registered once at module load — work regardless of which page/member
    // is currently mounted.
    document.addEventListener('click', e => { if (e.target.id === 'mvModal') closeModal(); });
    document.addEventListener('keydown', e => {
        const viewer = document.getElementById('mvViewer');
        if (e.key === 'Escape') { closeModal(); if (viewer) viewer.style.display = 'none'; }
        if (viewer && viewer.style.display === 'flex') {
            if (e.key === 'ArrowLeft') viewerStep(-1);
            if (e.key === 'ArrowRight') viewerStep(1);
        }
    });
    document.addEventListener('mv-lang', () => {
        if (!member) return;
        renderProfile();
        renderResumeList();
        renderSamples(currentTab);
        if (activeProject) renderModal();
    });

    return { CATS, mount, openModal, openModalById, closeModal, openViewer, viewerStep };
})();

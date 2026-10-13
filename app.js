/**
 * ResidentEcho Dashboard — Clean Static App
 * Vanilla JS · RTL Arabic · GitHub Pages ready
 */

const state = {
  data: null,
  idIndex: null,
  activeId: null,
  platformFilter: 'all',
  severityFilter: 'all',
  globalSearch: '',
  streamSearch: '',
  streamSort: 'asc',
  page: 1,
  pageSize: 40,
  mobileView: 'clusters'
};

const $ = id => document.getElementById(id);

// ── Utilities ────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const months = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                    'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
    return `${d.getDate()} ${months[d.getMonth()]} • ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
  } catch { return iso.replace('T',' '); }
}

function esc(t) {
  if (!t) return '';
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function escAttr(t) {
  if (!t) return '';
  return t.replace(/'/g,"\\'").replace(/"/g,'&quot;').replace(/\n/g,' ');
}

function sevLabel(s) {
  if (s === 'critical') return 'حرج';
  if (s === 'high')     return 'مرتفع';
  return 'متوسط';
}

function copyText(text, msg) {
  navigator.clipboard.writeText(text).then(() => showToast(msg || 'تم النسخ'))
    .catch(() => {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta);
      ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
      showToast(msg || 'تم النسخ');
    });
}
window.copyText = copyText;  // expose for inline onclick

function showToast(msg) {
  $('toast-text').textContent = msg;
  $('toast-notify').classList.remove('hidden');
  setTimeout(() => $('toast-notify').classList.add('hidden'), 2400);
}

function setMobileView(view) {
  state.mobileView = view;
  document.body.dataset.mobileView = view;

  const btnClusters = $('btn-view-clusters');
  const btnDetail   = $('btn-view-detail');
  if (btnClusters && btnDetail) {
    btnClusters.classList.toggle('active', view === 'clusters');
    btnDetail.classList.toggle('active', view === 'detail');
  }

  if (view === 'detail') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

// ── Boot ─────────────────────────────────────────────────────

async function initApp() {
  try {
    const res = await fetch('monthly_analysis/2026-09_analysis.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();

    $('metric-total-msgs').textContent    = state.data.total_raw_messages.toLocaleString('ar-SA');
    $('metric-total-clusters').textContent = state.data.clusters_count;
    $('metric-feedback-msgs').textContent  = state.data.unique_feedback_messages.toLocaleString('ar-SA');

    const badge = $('mobile-clusters-badge');
    if (badge) badge.textContent = state.data.clusters_count;

    if (state.data.clusters?.length) state.activeId = state.data.clusters[0].cluster_id;

    setMobileView('clusters');

    renderSidebar();
    renderDetail();
    bindEvents();
  } catch (e) {
    $('clusters-list').innerHTML = `
      <div class="error-state">
        <i class="fa-solid fa-circle-exclamation"></i>
        <span>تعذّر تحميل بيانات التحليل<br><small style="opacity:.7">${e.message}</small></span>
      </div>`;
  }
}

// ── Sidebar ───────────────────────────────────────────────────

function renderSidebar() {
  if (!state.data?.clusters) return;
  let clusters = state.data.clusters;

  if (state.severityFilter !== 'all')
    clusters = clusters.filter(c => c.severity === state.severityFilter);

  if (state.globalSearch) {
    const q = state.globalSearch.toLowerCase();
    clusters = clusters.filter(c =>
      c.title_ar.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q) ||
      (c.affected_buildings || []).some(b => b.toLowerCase().includes(q))
    );
  }

  const el = $('clusters-list');

  if (!clusters.length) {
    el.innerHTML = `<div class="no-msgs" style="padding:20px 12px"><i class="fa-solid fa-magnifying-glass"></i><span>لا توجد نتائج</span></div>`;
    return;
  }

  el.innerHTML = clusters.map(c => {
    const active = c.cluster_id === state.activeId ? 'active' : '';
    return `
      <div class="cluster-card ${active}" data-id="${c.cluster_id}">
        <div class="cluster-card-top">
          <span class="cluster-category"><i class="fa-solid fa-tag" style="font-size:9px"></i> ${esc(c.category)}</span>
          <span class="sev-badge ${c.severity}">${sevLabel(c.severity)}</span>
        </div>
        <div class="cluster-title">${esc(c.title_ar)}</div>
        <div class="cluster-stats">
          <i class="fa-regular fa-message"></i>
          ${c.total_messages_count.toLocaleString('ar-SA')} رسالة
          &nbsp;·&nbsp;
          <i class="fa-brands fa-telegram plat-tg"></i> ${(c.platforms_breakdown?.tg || 0).toLocaleString()}
          &nbsp;
          <i class="fa-brands fa-whatsapp plat-wa"></i> ${(c.platforms_breakdown?.wa || 0).toLocaleString()}
        </div>
      </div>
    `;
  }).join('');

  el.querySelectorAll('.cluster-card').forEach(card => {
    card.addEventListener('click', () => {
      const id = card.dataset.id;
      if (id !== state.activeId) {
        state.activeId = id;
        state.page = 1;
        state.streamSearch = '';
        $('stream-filter-input').value = '';
        el.querySelectorAll('.cluster-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        renderDetail();
      }
      if (window.innerWidth <= 900) {
        setMobileView('detail');
      }
    });
  });
}

// ── Detail Panel ──────────────────────────────────────────────

function renderDetail() {
  const c = state.data?.clusters?.find(x => x.cluster_id === state.activeId);
  if (!c) return;

  const detail = $('cluster-detail');
  const tg = (c.platforms_breakdown?.tg || 0).toLocaleString('ar-SA');
  const wa = (c.platforms_breakdown?.wa || 0).toLocaleString('ar-SA');

  const bldgs = c.affected_buildings?.length
    ? c.affected_buildings.map(b => `<span class="bldg-tag">${esc(b)}</span>`).join('')
    : '<span style="font-size:12px;color:var(--text-muted)">شامل جميع المباني</span>';

  const rootCauses = (c.root_causes || []).map(r => `<li>${esc(r)}</li>`).join('');
  const actions    = (c.student_initiatives_and_resolutions || []).map(a => `<li>${esc(a)}</li>`).join('');

  detail.innerHTML = `
    <div class="detail-head">
      <div class="detail-head-top">
        <h2>${esc(c.title_ar)}</h2>
        <div class="detail-chips">
          <span class="sev-badge ${c.severity}" style="font-size:12px">${sevLabel(c.severity)}</span>
          <span class="detail-chip"><i class="fa-solid fa-folder"></i> ${esc(c.category)}</span>
          <span class="detail-chip"><i class="fa-solid fa-users"></i> ${c.unique_users_count.toLocaleString('ar-SA')} طالب</span>
        </div>
      </div>
      <div class="detail-numbers">
        <div class="detail-num">
          <span class="detail-num-val">${c.total_messages_count.toLocaleString('ar-SA')}</span>
          <span class="detail-num-lbl">إجمالي الرسائل</span>
        </div>
        <div class="detail-num">
          <span class="detail-num-val" style="color:var(--tg-color)">${tg}</span>
          <span class="detail-num-lbl"><i class="fa-brands fa-telegram"></i> تليغرام</span>
        </div>
        <div class="detail-num">
          <span class="detail-num-val" style="color:var(--wa-color)">${wa}</span>
          <span class="detail-num-lbl"><i class="fa-brands fa-whatsapp"></i> واتساب</span>
        </div>
      </div>
    </div>
    <div class="detail-sections">
      ${rootCauses ? `
      <div class="detail-section">
        <div class="detail-section-title"><i class="fa-solid fa-bullseye"></i> الأسباب الجذرية</div>
        <ul class="detail-list">${rootCauses}</ul>
      </div>` : ''}
      ${c.timeline_and_evolution ? `
      <div class="detail-section">
        <div class="detail-section-title"><i class="fa-solid fa-timeline"></i> التسلسل الزمني</div>
        <div class="timeline-text">${esc(c.timeline_and_evolution)}</div>
      </div>` : ''}
      ${actions ? `
      <div class="detail-section">
        <div class="detail-section-title"><i class="fa-solid fa-hand-fist"></i> تحركات الطلاب</div>
        <ul class="detail-list">${actions}</ul>
      </div>` : ''}
      <div class="detail-section">
        <div class="detail-section-title"><i class="fa-solid fa-building"></i> المباني المتأثرة</div>
        <div class="buildings-wrap">${bldgs}</div>
      </div>
    </div>
  `;

  renderFeed(false);
}

// ── Feed ──────────────────────────────────────────────────────

function renderFeed(append = false) {
  const c = state.data?.clusters?.find(x => x.cluster_id === state.activeId);
  if (!c?.messages) { $('visible-msgs-count').textContent = '—'; return; }

  let msgs = c.messages;

  if (state.platformFilter !== 'all')
    msgs = msgs.filter(m => m.source === state.platformFilter);

  if (state.streamSearch) {
    const q = state.streamSearch.toLowerCase();
    msgs = msgs.filter(m =>
      m.text?.toLowerCase().includes(q) ||
      String(m.id).includes(q) ||
      String(m.user_id).includes(q)
    );
  }

  if (state.streamSort === 'desc')
    msgs = [...msgs].sort((a,b) => new Date(b.time) - new Date(a.time));
  else if (state.streamSort === 'asc')
    msgs = [...msgs].sort((a,b) => new Date(a.time) - new Date(b.time));
  else if (state.streamSort === 'length')
    msgs = [...msgs].sort((a,b) => (b.text?.length || 0) - (a.text?.length || 0));

  $('visible-msgs-count').textContent = msgs.length.toLocaleString('ar-SA');

  const maxItems = state.page * state.pageSize;
  const visible  = msgs.slice(0, maxItems);
  $('stream-footer').style.display = maxItems < msgs.length ? 'flex' : 'none';

  const stream = $('chat-bubbles-stream');

  if (!msgs.length) {
    stream.innerHTML = `<div class="no-msgs"><i class="fa-regular fa-comment-dots"></i><span>لا توجد رسائل</span></div>`;
    return;
  }

  const html = visible.map(m => {
    const isTg = m.source === 'tg';
    const platCls = isTg ? 'tg' : 'wa';
    const platIcon = isTg
      ? '<i class="fa-brands fa-telegram"></i> تليغرام'
      : '<i class="fa-brands fa-whatsapp"></i> واتساب';

    return `
      <div class="msg-card" id="msg-${m.id}">
        <div class="msg-meta">
          <span class="msg-platform ${platCls}">${platIcon}</span>
          <span class="msg-sep">·</span>
          <span class="msg-uid">مستخدم ${m.user_id}</span>
          <span class="msg-time">${formatTime(m.time)}</span>
          <span class="msg-id">#${m.id}</span>
        </div>
        <div class="msg-text">${esc(m.text)}</div>
        <div class="msg-actions">
          <button class="msg-action-btn" onclick="copyText('${escAttr(m.text)}','تم نسخ الرسالة')">
            <i class="fa-regular fa-copy"></i> نسخ
          </button>
          <button class="msg-action-btn" onclick="copyText('${m.id}','تم نسخ المعرف #${m.id}')">
            <i class="fa-solid fa-hashtag"></i> ID
          </button>
        </div>
      </div>`;
  }).join('');

  if (append) stream.innerHTML += html;
  else { stream.innerHTML = html; stream.scrollTop = 0; }
}

// ── ID Lookup ─────────────────────────────────────────────────

async function lookupById() {
  const raw = $('quick-id-input').value.trim();
  if (!raw) return;
  const id = parseInt(raw, 10);
  if (isNaN(id)) { showToast('أدخل رقماً صحيحاً'); return; }

  let msg = null, cluster = null;

  // 1. Search in loaded clusters
  for (const c of (state.data?.clusters || [])) {
    const m = c.messages?.find(x => x.id === id);
    if (m) { msg = m; cluster = c; break; }
  }

  // 2. Fall back to ID index
  if (!msg) {
    if (!state.idIndex) {
      showToast('جاري تحميل الفهرس...');
      try {
        const r = await fetch('monthly_analysis/2026-09_id_index.json');
        if (r.ok) state.idIndex = await r.json();
      } catch {}
    }
    const raw = state.idIndex?.[id];
    if (raw) msg = { id, source: raw.s, user_id: raw.u, time: raw.d, text: raw.t };
  }

  const body = $('modal-body');

  if (!msg) {
    body.innerHTML = `
      <div class="error-state">
        <i class="fa-solid fa-circle-question"></i>
        <span>الرسالة رقم #${id} غير موجودة في سجلات سبتمبر 2026</span>
      </div>`;
    $('message-modal').classList.remove('hidden');
    return;
  }

  const isTg = msg.source === 'tg';
  const platCls = isTg ? 'tg' : 'wa';
  const platIcon = isTg
    ? '<i class="fa-brands fa-telegram"></i> تليغرام'
    : '<i class="fa-brands fa-whatsapp"></i> واتساب';

  body.innerHTML = `
    ${cluster ? `
    <div class="modal-cluster-ref">
      <div>
        <div class="modal-cluster-ref-title">${esc(cluster.title_ar)}</div>
        <div class="modal-cluster-ref-sub">${esc(cluster.category)} · ${cluster.total_messages_count.toLocaleString()} رسالة</div>
      </div>
      <button id="modal-jump" class="modal-jump-btn">الانتقال للعنقود ←</button>
    </div>` : ''}
    <div class="modal-msg">
      <div class="modal-msg-meta">
        <span class="msg-platform ${platCls}">${platIcon}</span>
        <span class="msg-sep">·</span>
        <span class="msg-uid">مستخدم ${msg.user_id}</span>
        <span class="msg-time" style="margin-right:auto">${formatTime(msg.time)}</span>
        <span class="msg-id">#${msg.id}</span>
      </div>
      <div class="modal-msg-text">${esc(msg.text)}</div>
      <div class="modal-msg-actions">
        <button class="msg-action-btn" onclick="copyText('${escAttr(msg.text)}','تم نسخ الرسالة')">
          <i class="fa-regular fa-copy"></i> نسخ الرسالة
        </button>
        <button class="msg-action-btn" onclick="copyText('${msg.id}','تم نسخ المعرف')">
          <i class="fa-solid fa-hashtag"></i> نسخ ID
        </button>
      </div>
    </div>`;

  $('message-modal').classList.remove('hidden');

  const jumpBtn = $('modal-jump');
  if (jumpBtn && cluster) {
    jumpBtn.addEventListener('click', () => {
      $('message-modal').classList.add('hidden');
      state.activeId = cluster.cluster_id;
      state.page = 1;
      renderSidebar();
      renderDetail();
      if (window.innerWidth <= 900) {
        setMobileView('detail');
      }
      setTimeout(() => {
        const el = $(`msg-${msg.id}`);
        if (el) { el.scrollIntoView({ behavior:'smooth', block:'center' }); }
      }, 300);
    });
  }
}

// ── Events ───────────────────────────────────────────────────

function bindEvents() {
  // Mobile View Navigation
  $('btn-view-clusters')?.addEventListener('click', () => setMobileView('clusters'));
  $('btn-view-detail')?.addEventListener('click', () => setMobileView('detail'));
  $('mobile-back-btn')?.addEventListener('click', () => setMobileView('clusters'));

  // Severity filter
  $('severity-filter').addEventListener('click', e => {
    const btn = e.target.closest('.stab');
    if (!btn) return;
    $('severity-filter').querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.severityFilter = btn.dataset.severity;
    renderSidebar();
  });

  // Global search
  $('global-search-input').addEventListener('input', e => {
    state.globalSearch = e.target.value.trim().toLowerCase();
    $('clear-search-btn').classList.toggle('hidden', !state.globalSearch);
    renderSidebar();
  });
  $('clear-search-btn').addEventListener('click', () => {
    $('global-search-input').value = '';
    state.globalSearch = '';
    $('clear-search-btn').classList.add('hidden');
    renderSidebar();
  });

  // Platform filter
  $('platform-filter').addEventListener('click', e => {
    const btn = e.target.closest('.ptab');
    if (!btn) return;
    $('platform-filter').querySelectorAll('.ptab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.platformFilter = btn.dataset.platform;
    state.page = 1;
    renderFeed(false);
  });

  // Stream search
  $('stream-filter-input').addEventListener('input', e => {
    state.streamSearch = e.target.value.trim().toLowerCase();
    state.page = 1;
    renderFeed(false);
  });

  // Sort
  $('stream-sort-select').addEventListener('change', e => {
    state.streamSort = e.target.value;
    state.page = 1;
    renderFeed(false);
  });

  // Load more
  $('load-more-btn').addEventListener('click', () => {
    state.page++;
    renderFeed(true);
  });

  // ID Lookup
  $('quick-id-btn').addEventListener('click', lookupById);
  $('quick-id-input').addEventListener('keydown', e => { if (e.key === 'Enter') lookupById(); });

  // Modal close
  $('modal-close-btn').addEventListener('click', () => $('message-modal').classList.add('hidden'));
  $('message-modal').addEventListener('click', e => {
    if (e.target === $('message-modal')) $('message-modal').classList.add('hidden');
  });
}

// ── Start ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', initApp);

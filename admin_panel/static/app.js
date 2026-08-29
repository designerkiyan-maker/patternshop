'use strict';

/* ============================================================ state === */
let ME = null;
let CURRENT_TAB = 'dashboard';
let SUPPORT_POLL_TIMER = null;
function stopSupportPoll() { if (SUPPORT_POLL_TIMER) { clearInterval(SUPPORT_POLL_TIMER); SUPPORT_POLL_TIMER = null; } }

/* ============================================================= theme === */
// هر آیتم یک تم کامل رو توصیف می‌کنه: نه فقط رنگ، بلکه چیدمان/کارت/نمودار.
// وقتی تم جدیدی پیاده بشه، فقط کافیه یک آیتم اینجا با ready:true اضافه بشه
// و بلوک CSS مربوطه با سلکتور html[data-theme="..."] در style.css اضافه بشه.
const THEMES = [
  {
    id: 'bento',
    name: 'Bento Grid',
    desc: 'کارت‌های نامنظم چندسایز مثل ویجت‌های اپل',
    ready: true,
    supportsMode: true,
    defaultMode: 'light',
    swatch: ['#0A84FF', '#30D158', '#FF9F0A'],
  },
  {
    id: 'brutalist',
    name: 'Neo-brutalist',
    desc: 'کادر ضخیم، بی‌سایه، تایپوگرافی بولد',
    ready: true,
    supportsMode: true,
    defaultMode: 'light',
    swatch: ['#FFE600', '#000000', '#FFFFFF'],
  },
  {
    id: 'cyberpunk',
    name: 'Cyberpunk',
    desc: 'ترمینال نئون، اسکن‌لاین، منوی بالای صفحه',
    ready: true,
    supportsMode: false,
    defaultMode: 'dark',
    swatch: ['#FF2A6D', '#00FFF0', '#05050A'],
  },
  {
    id: 'streetops',
    name: 'Street Ops',
    desc: 'HUD الهام‌گرفته از بازی‌های شهر باز — نوار سلامت، ستاره‌ی تحت‌تعقیب، منوی پایین صفحه',
    ready: true,
    supportsMode: false,
    defaultMode: 'dark',
    swatch: ['#FFB020', '#22D3EE', '#14161C'],
  },
];
const DEFAULT_THEME = 'bento';

function loadTheme() {
  try {
    const t = JSON.parse(localStorage.getItem('sv-theme')) || {};
    return { theme: t.theme || DEFAULT_THEME, mode: t.mode || 'dark' };
  } catch (e) { return { theme: DEFAULT_THEME, mode: 'dark' }; }
}
// هر تم حالت روشن/تیره‌ی دلخواه خودش رو جدا به خاطر می‌سپاره — با defaultMode
// خود تم به عنوان مقدار اول، پیش از اینکه کاربر چیزی انتخاب کرده باشه.
function getModeForTheme(themeId) {
  try {
    const map = JSON.parse(localStorage.getItem('sv-theme-modes')) || {};
    if (map[themeId]) return map[themeId];
  } catch (e) {}
  const meta = THEMES.find(t => t.id === themeId);
  return (meta && meta.defaultMode) || 'dark';
}
function rememberModeForTheme(themeId, mode) {
  let map = {};
  try { map = JSON.parse(localStorage.getItem('sv-theme-modes')) || {}; } catch (e) {}
  map[themeId] = mode;
  try { localStorage.setItem('sv-theme-modes', JSON.stringify(map)); } catch (e) {}
}
function applyThemeChoice(themeId, mode) {
  const meta = THEMES.find(t => t.id === themeId) || THEMES[0];
  const finalTheme = meta.ready ? meta.id : DEFAULT_THEME;
  const finalMode = mode || getModeForTheme(finalTheme);
  document.documentElement.setAttribute('data-theme', finalTheme);
  document.documentElement.setAttribute('data-mode', finalMode);
  localStorage.setItem('sv-theme', JSON.stringify({ theme: finalTheme, mode: finalMode }));
  rememberModeForTheme(finalTheme, finalMode);
  if (typeof syncTopbarModeToggle === 'function') syncTopbarModeToggle();
}
// دکمه‌ی تعویض حالت روشن/تیره در نوار بالا؛ فقط برای تم‌هایی که ازش
// پشتیبانی می‌کنن نمایش داده می‌شه (بقیه‌ی تم‌ها فقط یک حالت تیره دارن).
function syncTopbarModeToggle() {
  const btn = document.getElementById('topbar-mode-toggle');
  if (!btn) return;
  const cur = loadTheme();
  const meta = THEMES.find(t => t.id === cur.theme);
  if (!meta || !meta.supportsMode) { btn.style.display = 'none'; return; }
  btn.style.display = '';
  const isDark = cur.mode === 'dark';
  btn.textContent = isDark ? '☀️' : '🌙';
  btn.title = isDark ? 'رفتن به حالت روشن' : 'رفتن به حالت تیره';
}
// نگه‌داری سازگاری با کدهای قدیمی‌تر که فقط applyTheme(mode) صدا می‌زنن
function applyTheme(mode) { applyThemeChoice(loadTheme().theme, mode); }
{ const t0 = loadTheme(); applyThemeChoice(t0.theme, t0.mode); }

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ============================================================= icons === */
const ICONS = {
  dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="14" width="7" height="7" rx="1.5"></rect><rect x="3" y="14" width="7" height="7" rx="1.5"></rect>',
  orders: '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path>',
  topups: '<rect x="1" y="4" width="22" height="16" rx="2.5"></rect><line x1="1" y1="10" x2="23" y2="10"></line>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>',
  catalog: '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line>',
  discounts: '<path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82Z"></path><circle cx="7" cy="7" r="1.4"></circle>',
  tickets: '<path d="M21 11.5a8.38 8.38 0 0 1-4.5 7.4 8.5 8.5 0 0 1-7.6-.1L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 8-8.5h.5a8.48 8.48 0 0 1 8 8v.5Z"></path>',
  broadcast: '<path d="m3 11 18-5v12L3 14v-3z"></path><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"></path>',
  support: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>',
  settings: '<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"></path>',
  logs: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="8" y1="13" x2="16" y2="13"></line><line x1="8" y1="17" x2="16" y2="17"></line>',
  system: '<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>',
  webadmins: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"></path>',
  account: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line>',
  revenue: '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline>',
  check: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>',
  empty: '<path d="M22 12h-6l-2 3h-4l-2-3H2"></path><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"></path>',
};
const svg = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ''}</svg>`;
const fmt = n => (n === null || n === undefined) ? '—' : Number(n).toLocaleString('fa-IR');
const fmtDate = iso => iso ? new Date(iso.replace(' ', 'T') + (iso.includes('Z') ? '' : 'Z')).toLocaleString('fa-IR') : '—';
// برای تاریخ‌های خالص بدون ساعت (مثل start_date/end_date بازه‌ی آمار که به
// شکل 'YYYY-MM-DD' میلادی از سرور میاد) — به تاریخ شمسی تبدیل می‌کنه.
const fmtDateOnly = iso => {
  if (!iso) return '—';
  try {
    return new Date(iso + 'T00:00:00Z').toLocaleDateString('fa-IR', { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' });
  } catch (e) { return iso; }
};
const esc = s => (s ?? '').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* ==================================================== micro-animation === */
// شمارش انیمیشنی اعداد هنگام بارگذاری کارت‌ها
function animateCount(el, target, duration = 900) {
  if (!el) return;
  const start = 0;
  const t0 = performance.now();
  function tick(now) {
    const p = Math.min((now - t0) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(Math.round(start + (target - start) * eased));
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
// پر شدن حلقه‌های سیگنال بعد از mount (برای انیمیشن conic-gradient)
function activateRings(root) {
  requestAnimationFrame(() => {
    setTimeout(() => {
      $$('.ring[data-pct], .res-ring[data-pct]', root).forEach(r => { r.style.setProperty('--pct', r.dataset.pct); });
    }, 60);
  });
}
// رشد میله‌های نمودار بعد از mount
function activateBars(root) {
  requestAnimationFrame(() => {
    setTimeout(() => {
      $$('.spark i[data-h]', root).forEach(b => { b.style.height = b.dataset.h + '%'; });
    }, 60);
  });
}
// پر شدن نوار‌های افقی (تفکیک درآمد / پرفروش‌ترین‌ها)
function activateBarFills(root) {
  requestAnimationFrame(() => {
    setTimeout(() => {
      $$('.bar-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
    }, 60);
  });
}
// انیمیشن گیج SVG (سلامت سیستم)
function activateGauge(root, pct) {
  const ring = $('#gaugeRing', root);
  if (!ring) return;
  const c = 2 * Math.PI * 64;
  ring.style.strokeDasharray = c;
  ring.style.strokeDashoffset = c;
  requestAnimationFrame(() => {
    setTimeout(() => {
      ring.style.transition = 'stroke-dashoffset 1.3s cubic-bezier(.16,1,.3,1)';
      ring.style.strokeDashoffset = c - Math.max(0, Math.min(100, pct)) / 100 * c;
    }, 60);
  });
}
// رسم رادار عملکرد از مقادیر ۰..۱
function drawRadar(root, axes, values, color = '#8B5CF6') {
  const svgEl = $('#radarChart', root);
  if (!svgEl) return;
  const cx = 110, cy = 95, r = 62, n = axes.length;
  const pt = (i, scale) => {
    const ang = -Math.PI / 2 + i * (Math.PI * 2 / n);
    return [cx + Math.cos(ang) * r * scale, cy + Math.sin(ang) * r * scale];
  };
  let out = '';
  [0.33, 0.66, 1].forEach(scale => {
    out += `<polygon points="${axes.map((_, i) => pt(i, scale).join(',')).join(' ')}" fill="none" stroke="var(--border)" stroke-width="1"/>`;
  });
  axes.forEach((label, i) => {
    const [x, y] = pt(i, 1.18), [x2, y2] = pt(i, 1);
    out += `<line x1="${cx}" y1="${cy}" x2="${x2}" y2="${y2}" stroke="var(--border)" stroke-width="1"/>`;
    out += `<text x="${x}" y="${y}" font-size="9.5" fill="var(--text-muted)" text-anchor="middle" font-family="Vazirmatn">${esc(label)}</text>`;
  });
  const vp = axes.map((_, i) => pt(i, values[i]).join(',')).join(' ');
  out += `<polygon points="${vp}" fill="${color}33" stroke="${color}" stroke-width="1.6"/>`;
  axes.forEach((_, i) => { const [x, y] = pt(i, values[i]); out += `<circle cx="${x}" cy="${y}" r="2.6" fill="${color}"/>`; });
  svgEl.innerHTML = out;
}
// بوم امبیانت نقطه‌ها و بسته‌های متحرک در کارت خوش‌آمدگویی
function drawHeroNet(canvas) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth || 150, h = canvas.clientHeight || 150;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const colors = ['#22D3EE', '#EC4899', '#8B5CF6'];
  const N = 6;
  const nodes = Array.from({ length: N }, (_, i) => ({
    ang: (i / N) * Math.PI * 2, radius: 0.62 + (i % 2) * 0.16, speed: 0.15 + Math.random() * 0.08,
  }));
  const packets = nodes.map(() => ({ t: Math.random(), speed: 0.006 + Math.random() * 0.006 }));
  let t = 0;
  const cx = w / 2, cy = h / 2;
  function pos(n) { const a = n.ang + t * n.speed * 0.2; return [cx + Math.cos(a) * w * 0.36 * n.radius, cy + Math.sin(a) * h * 0.36 * n.radius]; }
  function frame() {
    if (!canvas.isConnected) return;
    t += 0.016;
    ctx.clearRect(0, 0, w, h);
    nodes.forEach((n, i) => {
      const [x, y] = pos(n);
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y);
      ctx.strokeStyle = 'rgba(139,92,246,0.18)'; ctx.lineWidth = 1; ctx.stroke();
      const p = packets[i]; p.t += p.speed; if (p.t > 1) p.t = 0;
      const px = cx + (x - cx) * p.t, py = cy + (y - cy) * p.t;
      ctx.beginPath(); ctx.arc(px, py, 2.2, 0, Math.PI * 2);
      ctx.fillStyle = colors[i % 3]; ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 8; ctx.fill(); ctx.shadowBlur = 0;
      ctx.beginPath(); ctx.arc(x, y, 3.2, 0, Math.PI * 2); ctx.fillStyle = 'rgba(245,242,255,0.75)'; ctx.fill();
    });
    const pulse = (Math.sin(t * 1.6) + 1) / 2;
    const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, 26 + pulse * 8);
    grad.addColorStop(0, 'rgba(236,72,153,0.9)'); grad.addColorStop(1, 'rgba(139,92,246,0)');
    ctx.beginPath(); ctx.arc(cx, cy, 14 + pulse * 6, 0, Math.PI * 2); ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2); ctx.fillStyle = '#F5F2FF'; ctx.fill();
    requestAnimationFrame(frame);
  }
  frame();
}

/* ============================================================== api === */
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    method: opts.method || 'GET',
    credentials: 'include',
    headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) { showLogin(); throw new Error('unauthorized'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const err = new Error(formatApiError(data.detail)); err.status = res.status; throw err; }
  return data;
}
function formatApiError(detail) {
  if (!detail) return 'خطای ناشناخته';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(d => (d && (d.msg || d.detail)) || JSON.stringify(d)).join('، ') || 'خطای ناشناخته';
  }
  return typeof detail === 'object' ? JSON.stringify(detail) : String(detail);
}
const apiGet = p => api(p);
const apiPost = (p, body) => api(p, { method: 'POST', body: body || {} });
const apiPut = (p, body) => api(p, { method: 'PUT', body: body || {} });
const apiDelete = p => api(p, { method: 'DELETE' });

/* ============================================================ toast === */
function toast(msg, isError = false) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}
function handleErr(e) { if (e.message !== 'unauthorized') toast(e.message, true); }

/* ==================================================== receipt viewer === */
function showReceiptModal(kind, id) {
  const paths = { order: `orders/${id}`, topup: `topups/${id}` };
  const url = `/api/${paths[kind] || `orders/${id}`}/receipt`;
  openModal('رسید پرداخت', `
    <div class="receipt-view" style="text-align:center">
      <img src="${url}" alt="رسید پرداخت" style="max-width:100%;max-height:70vh;border-radius:10px" />
      <div style="margin-top:12px">
        <a href="${url}" target="_blank" rel="noopener" class="btn btn-sm">باز کردن در تب جدید</a>
      </div>
    </div>
  `, body => {
    const img = body.querySelector('img');
    img.addEventListener('error', () => {
      body.innerHTML = `
        <div class="empty-state">${svg('empty')}<div>نمایش پیش‌نمایش ممکن نشد (شاید فایل رسید سند/PDF باشد).</div></div>
        <div style="text-align:center;margin-top:12px"><a href="${url}" target="_blank" rel="noopener" class="btn btn-sm">باز کردن رسید</a></div>
      `;
    });
  });
}

/* ============================================================ modal === */
function openModal(title, bodyHtml, onMount, opts = {}) {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `<div class="modal${opts.wide ? ' modal-lg' : ''}"><h3>${title}</h3><div class="modal-body">${bodyHtml}</div></div>`;
  backdrop.addEventListener('click', e => { if (e.target === backdrop) backdrop.remove(); });
  document.body.appendChild(backdrop);
  if (onMount) onMount(backdrop.querySelector('.modal-body'), () => backdrop.remove());
  return backdrop;
}

/* ============================================================== nav === */
const NAV = [
  // نمای کلی
  { key: 'dashboard', label: 'داشبورد', icon: 'dashboard', role: 'any', section: null },

  // عملیات مالی
  { key: 'orders', label: 'سفارش‌ها', icon: 'orders', role: 'any', section: 'عملیات مالی' },
  { key: 'topups', label: 'شارژ کیف پول', icon: 'topups', role: 'any', section: 'عملیات مالی' },

  // کاربران و پشتیبانی
  { key: 'users', label: 'کاربران', icon: 'users', role: 'any', section: 'کاربران و پشتیبانی' },
  { key: 'tickets', label: 'تیکت‌ها', icon: 'tickets', role: 'any', section: 'کاربران و پشتیبانی' },
  { key: 'support', label: 'چت زنده', icon: 'support', role: 'any', section: 'کاربران و پشتیبانی' },

  // محصولات و بازاریابی
  { key: 'catalog', label: 'محصولات و فایل‌های الگو', icon: 'catalog', role: 'catalog', section: 'محصولات و بازاریابی' },
  { key: 'discounts', label: 'کدهای تخفیف', icon: 'discounts', role: 'discounts', section: 'محصولات و بازاریابی' },
  { key: 'broadcast', label: 'پیام همگانی', icon: 'broadcast', role: 'broadcast', section: 'محصولات و بازاریابی' },

  // تنظیمات و سیستم — نگهداری، دسترسی و پیکربندی
  { key: 'settings', label: 'تنظیمات و برندینگ', icon: 'settings', role: 'settings', section: 'تنظیمات و سیستم' },
  { key: 'salessettings', label: 'تنظیمات فروش', icon: 'settings', role: 'settings', section: 'تنظیمات و سیستم' },
  { key: 'webadmins', label: 'کاربران پنل', icon: 'webadmins', role: 'owner', section: 'تنظیمات و سیستم' },
  { key: 'system', label: 'سیستم و نگهداری', icon: 'system', role: 'system', section: 'تنظیمات و سیستم' },
  { key: 'logs', label: 'لاگ فعالیت ادمین‌ها', icon: 'logs', role: 'system', section: 'تنظیمات و سیستم' },

  // حساب کاربری
  { key: 'account', label: 'حساب من', icon: 'account', role: 'any', section: 'حساب کاربری' },
];
function hasPerm(perm) {
  return ME.role === 'owner' || (ME.permissions || []).includes(perm);
}
function canSee(navRole) {
  if (navRole === 'any') return true;
  if (navRole === 'owner') return ME.role === 'owner';
  return hasPerm(navRole);
}
const ROLE_LABEL = { owner: 'مالک', admin: 'مدیر کامل', mid: 'ادمین میانی', support: 'پشتیبان' };

/* ==================================================== live notifications === */
let NOTIF_COUNTS = {};

function renderNav() {
  const el = $('#nav-tunnel');
  const CYCLE = ['nav-c1', 'nav-c2', 'nav-c3', 'nav-c4'];
  const visible = NAV.filter(n => canSee(n.role));
  let html = '';
  let lastSection = undefined;
  visible.forEach((n, i) => {
    if (n.section !== lastSection) {
      if (n.section) html += `<div class="nav-section">${n.section}</div>`;
      lastSection = n.section;
    }
    const count = NOTIF_COUNTS[n.key] || 0;
    html += `
    <div class="nav-item ${CYCLE[i % 4]} ${n.key === CURRENT_TAB ? 'active' : ''}" data-tab="${n.key}">
      <span class="nav-icon">${svg(n.icon)}</span><span>${n.label}</span>${count ? `<span class="dot-count">${count > 99 ? '99+' : count}</span>` : ''}
    </div>`;
  });
  el.innerHTML = html;
  $$('.nav-item', el).forEach(item => item.addEventListener('click', () => { goTo(item.dataset.tab); closeSidebar(); }));
}

function goTo(tab) {
  stopSupportPoll();
  CURRENT_TAB = tab;
  try { localStorage.setItem('admin_current_tab', tab); } catch (e) {}
  renderNav();
  $('#page-title').textContent = NAV.find(n => n.key === tab)?.label || '';
  renderPage(tab);
}

/* ---- صدای هشدار برای موارد جدید (بدون فایل صوتی، سنتز با Web Audio) ---- */
let NOTIF_AUDIO_CTX = null;
function playNotifSound() {
  try {
    NOTIF_AUDIO_CTX = NOTIF_AUDIO_CTX || new (window.AudioContext || window.webkitAudioContext)();
    const ctx = NOTIF_AUDIO_CTX;
    const now = ctx.currentTime;
    [880, 1180].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, now + i * 0.14);
      gain.gain.linearRampToValueAtTime(0.18, now + i * 0.14 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.14 + 0.22);
      osc.connect(gain).connect(ctx.destination);
      osc.start(now + i * 0.14);
      osc.stop(now + i * 0.14 + 0.24);
    });
  } catch (e) { /* مرورگر صدای وب را پشتیبانی نمی‌کند */ }
}

/* ---- بج‌های زنده‌ی منو: هر چند ثانیه شمارش pending را می‌گیرد و اگر رشد
   کرده بود صدا هم پخش می‌کند. این جدا از Push است و فقط وقتی تب باز باشد کار
   می‌کند؛ برای اعلان وقتی مرورگر بسته است به بخش Push پایین‌تر نگاه کن. ---- */
let NOTIF_POLL_STARTED = false;
function startNotificationPolling() {
  if (NOTIF_POLL_STARTED) return;
  NOTIF_POLL_STARTED = true;
  const poll = async () => {
    try {
      const summary = await apiGet('/notifications/summary');
      let grew = false;
      Object.keys(summary).forEach(key => { if (summary[key] > (NOTIF_COUNTS[key] || 0)) grew = true; });
      NOTIF_COUNTS = summary;
      renderNav();
      if (grew) playNotifSound();
    } catch (e) { /* silent */ }
  };
  poll();
  setInterval(poll, 15000);
}

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-history]');
  if (!btn) return;
  const [recordType, recordId] = btn.dataset.history.split(':');
  showRecordHistory(recordType, recordId);
});

/* ============================================================= boot === */
async function boot() {
  // مسیر قدیمی /setup هم توسط سرور همان SPA را سرو می‌کند؛ فقط صفحه‌ی ورود نشان بده.
  try {
    ME = await apiGet('/me');
    showApp();
  } catch (e) {
    showLogin();
  }
}

function showLogin() {
  $('#app').hidden = true;
  $('#login-screen').hidden = false;
}

function showApp() {
  $('#login-screen').hidden = true;
  $('#app').hidden = false;
  $('#me-username').textContent = ME.username;
  $('#me-role').textContent = ROLE_LABEL[ME.role] || ME.role;
  $('#me-avatar').textContent = ME.username.slice(0, 2).toUpperCase();
  tickClock();
  setInterval(tickClock, 1000);
  startNotificationPolling();
  const pushBtn = $('#push-toggle-btn');
  if (pushBtn) pushBtn.addEventListener('click', openPushSettingsModal);
  const modeBtn = $('#topbar-mode-toggle');
  if (modeBtn) modeBtn.addEventListener('click', () => {
    const cur = loadTheme();
    applyThemeChoice(cur.theme, cur.mode === 'dark' ? 'light' : 'dark');
  });
  syncTopbarModeToggle();
  initInstallApp();
  let saved = null;
  try { saved = localStorage.getItem('admin_current_tab'); } catch (e) {}
  const savedValid = saved && NAV.find(n => n.key === saved && canSee(n.role));
  goTo(savedValid ? saved : 'dashboard');
}

/* ==================================================== web push (level 2) ===
   اعلان مرورگر واقعی که حتی وقتی مرورگر کاملاً بسته است هم می‌رسد؛ از طریق
   Service Worker + سرویس Push خودِ مرورگر. برخلاف بج‌های بالا، این یکی نیاز
   به یک‌بار «فعال‌سازی» دستی توسط هر ادمین (روی هر دستگاه) دارد چون مرورگرها
   بدون اجازه‌ی صریح کاربر Push را قبول نمی‌کنند. */
const PUSH_SUPPORTED = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const arr = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) arr[i] = rawData.charCodeAt(i);
  return arr;
}

async function pushStatus() {
  if (!PUSH_SUPPORTED) return 'unsupported';
  if (Notification.permission === 'denied') return 'denied';
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    if (!sub) return 'not-subscribed';
    // subscription محلی مرورگر کافی نیست؛ باید مطمئن شویم سرور هم واقعاً آن را ذخیره کرده
    try {
      const { registered } = await apiGet(`/push/status?endpoint=${encodeURIComponent(sub.endpoint)}`);
      return registered ? 'subscribed' : 'not-subscribed';
    } catch (e) {
      return 'not-subscribed';
    }
  } catch (e) {
    return 'not-subscribed';
  }
}

async function enablePushNotifications() {
  if (!PUSH_SUPPORTED) { toast('این مرورگر از اعلان Push پشتیبانی نمی‌کند.', true); return false; }
  try {
    const { publicKey, enabled } = await apiGet('/push/vapid-public-key');
    if (!enabled) { toast('اعلان Push هنوز روی سرور تنظیم نشده (کلید VAPID غایب است).', true); return false; }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') { toast('اجازه‌ی اعلان داده نشد.', true); return false; }
    const reg = await navigator.serviceWorker.register('/sw.js');
    await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    }
    const raw = sub.toJSON();
    await apiPost('/push/subscribe', { endpoint: raw.endpoint, keys: raw.keys, user_agent: navigator.userAgent });
    toast('اعلان مرورگر فعال شد — حتی وقتی مرورگر بسته باشد پیام می‌رسد.');
    return true;
  } catch (e) {
    handleErr(e);
    return false;
  }
}

async function disablePushNotifications() {
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    if (sub) {
      await apiPost('/push/unsubscribe', { endpoint: sub.endpoint });
      await sub.unsubscribe();
    }
    toast('اعلان مرورگر روی این دستگاه غیرفعال شد.');
  } catch (e) { handleErr(e); }
}

function openPushSettingsModal() {
  openModal('اعلان مرورگر (Push)', `<div id="push-modal-body"><p class="card-sub">در حال بررسی وضعیت...</p></div>`, (body) => {
    const paint = async () => {
      const status = await pushStatus();
      const label = {
        unsupported: 'این مرورگر از اعلان Push پشتیبانی نمی‌کند.',
        denied: 'اجازه‌ی اعلان قبلاً رد شده؛ باید از تنظیمات خودِ مرورگر برای این سایت دوباره اجازه بدهی.',
        subscribed: 'اعلان مرورگر روی این دستگاه فعال است — برای سفارش، شارژ کیف پول و تیکت جدید، حتی وقتی مرورگر کاملاً بسته باشد اعلان دریافت می‌کنی.',
        'not-subscribed': 'اعلان مرورگر روی این دستگاه فعال نیست.',
      }[status];
      body.innerHTML = `
        <p class="card-sub" style="margin-bottom:14px;line-height:1.9">${label}</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${status === 'not-subscribed' ? '<button class="btn btn-primary btn-sm" id="push-enable-btn">فعال‌سازی</button>' : ''}
          ${status === 'subscribed' ? '<button class="btn btn-sm" id="push-test-btn">ارسال اعلان تست</button><button class="btn btn-danger btn-sm" id="push-disable-btn">غیرفعال‌سازی</button>' : ''}
        </div>
      `;
      const enableBtn = $('#push-enable-btn', body);
      const testBtn = $('#push-test-btn', body);
      const disableBtn = $('#push-disable-btn', body);
      if (enableBtn) enableBtn.addEventListener('click', async () => { enableBtn.disabled = true; await enablePushNotifications(); paint(); });
      if (testBtn) testBtn.addEventListener('click', async () => {
        testBtn.disabled = true;
        try { await apiPost('/push/test'); toast('اعلان تست ارسال شد.'); } catch (e) { handleErr(e); }
        testBtn.disabled = false;
      });
      if (disableBtn) disableBtn.addEventListener('click', async () => { await disablePushNotifications(); paint(); });
    };
    paint();
  });
}

/* ============================================== نصب به عنوان اپ (PWA) === === */
/* اندروید (کروم): با beforeinstallprompt یک دیالوگ نصب بومی نشون میدیم.
   آیفون (سافاری): هیچ API ای برای نصب برنامه‌ای وجود نداره، پس فقط راهنمای
   دستی «Share -> Add to Home Screen» رو نشون می‌دیم. */
let deferredInstallPrompt = null;

function isStandalonePwa() {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}
function isIosDevice() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); // آیپد جدید خودش رو مک معرفی می‌کنه
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  $('#install-app-btn')?.style && ($('#install-app-btn').style.display = '');
});

window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  $('#install-app-btn')?.style && ($('#install-app-btn').style.display = 'none');
  toast('پنل به عنوان اپلیکیشن روی این دستگاه نصب شد.');
});

function openIosInstallModal() {
  openModal('نصب پنل روی آیفون', `
    <p class="card-sub" style="margin-bottom:14px;line-height:2">
      سافاری روی آیفون نصب خودکار را پشتیبانی نمی‌کند؛ برای اضافه کردن پنل به هوم‌اسکرین
      (شبیه یک اپ مستقل، با آیکون و بدون نوار آدرس) این مراحل را دنبال کن:
    </p>
    <ol style="padding-inline-start:20px;line-height:2.2;color:var(--text-muted)">
      <li>از نوار پایین سافاری، دکمه‌ی <b>Share</b> (مربع با فلش رو به بالا) را بزن.</li>
      <li>در لیست، گزینه‌ی <b>Add to Home Screen</b> را انتخاب کن.</li>
      <li>روی <b>Add</b> بزن.</li>
      <li>از این به بعد، پنل را فقط از آیکونی که روی هوم‌اسکرین اضافه شد باز کن —
        <b>فقط از همان آیکون</b> اعلان مرورگر (Push) هم قابل فعال‌سازی است، نه از تب معمولی سافاری.</li>
    </ol>
  `);
}

async function initInstallApp() {
  const btn = $('#install-app-btn');
  if (!btn) return;
  if (isStandalonePwa()) { btn.style.display = 'none'; return; }
  if (isIosDevice()) {
    btn.style.display = ''; // روی آیفون همیشه نشون بده (beforeinstallprompt وجود نداره)
    btn.addEventListener('click', openIosInstallModal);
    return;
  }
  // اندروید/دسکتاپ کروم: تا وقتی beforeinstallprompt فایر نشده دکمه مخفی می‌ماند
  btn.addEventListener('click', async () => {
    if (!deferredInstallPrompt) {
      toast('این مرورگر امکان نصب مستقیم را نمی‌دهد؛ از منوی مرورگر «Add to Home screen» را بزن.');
      return;
    }
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    btn.style.display = 'none';
  });
}

/* ===================================================== sidebar (mobile) === */
function closeSidebar() {
  $('.sidebar')?.classList.remove('open');
  $('#sidebar-overlay')?.classList.remove('show');
}
function openSidebar() {
  $('.sidebar')?.classList.add('open');
  $('#sidebar-overlay')?.classList.add('show');
}
$('#hamburger-btn')?.addEventListener('click', () => {
  $('.sidebar')?.classList.contains('open') ? closeSidebar() : openSidebar();
});
$('#sidebar-overlay')?.addEventListener('click', closeSidebar);

function tickClock() {
  $('#topbar-clock').textContent = new Date().toLocaleString('fa-IR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

$('#login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = $('#login-submit');
  const errBox = $('#login-error');
  errBox.hidden = true;
  btn.disabled = true; btn.textContent = 'در حال ورود...';
  try {
    ME = await apiPost('/login', {
      username: $('#login-username').value.trim(),
      password: $('#login-password').value,
    });
    showApp();
  } catch (e) {
    errBox.textContent = e.message;
    errBox.hidden = false;
  } finally {
    btn.disabled = false; btn.textContent = 'ورود';
  }
});

$('#logout-btn').addEventListener('click', async () => {
  await apiPost('/logout');
  ME = null;
  showLogin();
});

/* ============================================================== page === */
function content() { return $('#content'); }
function setContent(html) { content().innerHTML = html; }

async function renderPage(tab) {
  setContent('<div class="loading">در حال بارگذاری...</div>');
  try {
    switch (tab) {
      case 'dashboard': return renderDashboard();
      case 'orders': return renderOrders();
      case 'topups': return renderTopups();
      case 'users': return renderUsers();
      case 'catalog': return renderCatalog();
      case 'discounts': return renderDiscounts();
      case 'tickets': return renderTickets();
      case 'support': return renderSupport();
      case 'broadcast': return renderBroadcast();
      case 'system': return renderSystem();
      case 'settings': return renderSettings();
      case 'salessettings': return renderSalesSettings();
      case 'logs': return renderLogs();
      case 'webadmins': return renderWebAdmins();
      case 'account': return renderAccount();
    }
  } catch (e) { handleErr(e); setContent(`<div class="empty-state">${esc(e.message)}</div>`); }
}

/* ========================================================= dashboard === */
function greetingByHour() {
  const h = new Date().getHours();
  if (h < 12) return 'صبح بخیر';
  if (h < 18) return 'ظهر بخیر';
  return 'شب بخیر';
}

function resRingHtml(pct, colorVar, title, sub) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  return `
    <div class="card res-card">
      <div class="res-ring" style="--ring-a:${colorVar}" data-pct="${p}"><span>${p}٪</span></div>
      <div class="res-info"><strong>${title}</strong><span>${sub}</span></div>
    </div>`;
}

// بازه‌ی زمانی داشبورد — به انتخاب ادمین، بین صفحات نگه داشته می‌شه
// (localStorage). خالی/null یعنی پیش‌فرض سرور (۱۴ روز اخیر).
const DASH_RANGE_PRESETS = [
  { key: '7', label: '۷ روز', days: 7 },
  { key: '14', label: '۱۴ روز', days: 14 },
  { key: '30', label: '۳۰ روز', days: 30 },
  { key: '90', label: '۹۰ روز', days: 90 },
];
function getDashRange() {
  try { return JSON.parse(localStorage.getItem('sv-dash-range')) || null; } catch (e) { return null; }
}
function setDashRange(range) {
  try {
    if (range) localStorage.setItem('sv-dash-range', JSON.stringify(range));
    else localStorage.removeItem('sv-dash-range');
  } catch (e) {}
}
function isoDaysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function dashRangeBarHtml(s) {
  const saved = getDashRange();
  const activePreset = saved && saved.preset ? saved.preset : '14';
  const chips = DASH_RANGE_PRESETS.map(p => `
    <button class="btn btn-sm dash-range-chip ${p.key === activePreset ? 'active' : ''}" data-preset="${p.key}">${p.label}</button>
  `).join('');
  const customStart = saved && !saved.preset ? saved.start : '';
  const customEnd = saved && !saved.preset ? saved.end : '';
  return `
    <div class="card dash-range-bar" style="margin-bottom:16px">
      <div class="dash-range-row">
        <div class="dash-range-chips">${chips}
          <button class="btn btn-sm dash-range-chip ${saved && !saved.preset ? 'active' : ''}" id="dash-range-custom-toggle">بازه‌ی دلخواه</button>
        </div>
        <span class="card-sub">${fmtDateOnly(s.start_date)} تا ${fmtDateOnly(s.end_date)}</span>
      </div>
      <div class="dash-range-custom" id="dash-range-custom" ${saved && !saved.preset ? '' : 'hidden'}>
        <input type="date" class="input" id="dash-range-start" value="${customStart}">
        <span>تا</span>
        <input type="date" class="input" id="dash-range-end" value="${customEnd}">
        <button class="btn btn-primary btn-sm" id="dash-range-apply">اعمال</button>
      </div>
    </div>`;
}
function wireDashRangeBar() {
  const root = content();
  if (!root) return;
  $$('.dash-range-chip[data-preset]', root).forEach(btn => btn.addEventListener('click', () => {
    const days = Number(btn.dataset.preset);
    setDashRange({ preset: btn.dataset.preset, start: isoDaysAgo(days - 1), end: isoDaysAgo(0) });
    renderDashboard();
  }));
  const customToggle = $('#dash-range-custom-toggle', root);
  const customBox = $('#dash-range-custom', root);
  if (customToggle && customBox) {
    customToggle.addEventListener('click', () => { customBox.hidden = !customBox.hidden; });
  }
  const applyBtn = $('#dash-range-apply', root);
  if (applyBtn) applyBtn.addEventListener('click', () => {
    const start = $('#dash-range-start', root).value;
    const end = $('#dash-range-end', root).value;
    if (!start || !end) { toast('هر دو تاریخ رو انتخاب کن.'); return; }
    if (start > end) { toast('تاریخ شروع نباید بعد از تاریخ پایان باشه.'); return; }
    setDashRange({ preset: null, start, end });
    renderDashboard();
  });
}
async function renderDashboard() {
  const range = getDashRange();
  const q = range ? `?start=${range.start}&end=${range.end}` : '';
  const s = await apiGet('/dashboard' + q);
  let sys = null;
  try { sys = await apiGet('/system/stats'); } catch (e) { /* psutil ممکن است نصب نباشد */ }
  const theme = loadTheme().theme;
  if (theme === 'brutalist') await renderDashboardBrutalist(s, sys);
  else if (theme === 'cyberpunk') await renderDashboardCyberpunk(s, sys);
  else if (theme === 'streetops') await renderDashboardStreetOps(s, sys);
  else await renderDashboardBento(s, sys);
  const root = content();
  if (root) root.insertAdjacentHTML('afterbegin', dashRangeBarHtml(s));
  wireDashRangeBar();
  appendExtraStatsPanel(s);
}

/* ------------------------------------------ dashboard: extra stats panel --- */
/* مالی + تیکت‌ها + نرخ مشتری تکراری. یک پنل مشترک که مستقل از تم زیر داشبورد
   هر تم اضافه می‌شود. */
function appendExtraStatsPanel(s) {
  const root = content();
  if (!root) return;
  const old = $('#extra-stats-panel', root);
  if (old) old.remove();

  const respText = s.avg_ticket_response_minutes != null ? `${s.avg_ticket_response_minutes} دقیقه` : '—';
  const refShare = (s.referral_revenue + s.direct_revenue) > 0
    ? Math.round((s.referral_revenue / (s.referral_revenue + s.direct_revenue)) * 100)
    : 0;
  const el = document.createElement('div');
  el.className = 'card';
  el.id = 'extra-stats-panel';
  el.style.marginTop = '16px';
  el.innerHTML = `
    <div class="card-head"><h3>مالی و پشتیبانی</h3><span class="card-sub">${fmtDateOnly(s.start_date)} تا ${fmtDateOnly(s.end_date)}</span></div>
    <div class="grid grid-2" style="gap:16px;align-items:start">
      <div>
        <div class="card-sub" style="margin-bottom:8px">تصویر مالی</div>
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border,rgba(128,128,128,.15))">
          <span>موجودی کل کیف پول کاربران</span>
          <span class="mono">${fmt(s.wallet_total)} تومان</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border,rgba(128,128,128,.15))">
          <span>درآمد از خرید مستقیم</span>
          <span class="mono">${fmt(s.direct_revenue)} تومان</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border,rgba(128,128,128,.15))">
          <span>درآمد از زیرمجموعه‌گیری (${refShare}٪ فروش)</span>
          <span class="mono">${fmt(s.referral_revenue)} تومان</span>
        </div>
        <div style="display:flex;justify-content:space-between;padding:6px 0">
          <span>میانگین سبد خرید</span>
          <span class="mono">${fmt(s.aov)} تومان</span>
        </div>
      </div>
      <div>
        <div class="card-sub" style="margin-bottom:8px">تیکت‌های پشتیبانی و مشتریان</div>
        <div style="display:flex;justify-content:space-between;padding:6px 0"><span>تیکت ثبت‌شده در بازه</span><span class="mono">${fmt(s.tickets_created)}</span></div>
        <div style="display:flex;justify-content:space-between;padding:6px 0"><span>تیکت باز</span><span class="mono">${fmt(s.tickets_open)}</span></div>
        <div style="display:flex;justify-content:space-between;padding:6px 0"><span>میانگین زمان پاسخ اول</span><span class="mono">${respText}</span></div>
        <div style="display:flex;justify-content:space-between;padding:6px 0"><span>نرخ مشتری تکراری</span><span class="mono">${s.repeat_customer_rate}٪ (${fmt(s.repeat_customers)}/${fmt(s.total_customers)})</span></div>
      </div>
    </div>
  `;
  root.appendChild(el);
}

/* ----------------------------------------------------- dashboard: glass --- */
function donutSegments(cx, cy, r, data, colors, strokeWidth) {
  const total = data.reduce((a, b) => a + b.value, 0) || 1;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return data.map((d, i) => {
    const frac = d.value / total;
    const seg = `
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="${strokeWidth}"
        stroke-dasharray="${(frac * c).toFixed(2)} ${c.toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}"
        stroke-linecap="round" transform="rotate(-90 ${cx} ${cy})" class="glass-donut-seg"
        style="filter:drop-shadow(0 0 5px ${colors[i % colors.length]}99)"/>`;
    offset += frac * c;
    return seg;
  }).join('');
}

/* --------------------------------------------- dashboard: cyberpunk --- */
function cyberSmoothPath(values, w, h, pad = 6) {
  const max = Math.max(...values, 1), min = Math.min(...values, 0);
  const range = (max - min) || 1;
  const step = (w - pad * 2) / Math.max(values.length - 1, 1);
  const pts = values.map((v, i) => [pad + i * step, h - pad - ((v - min) / range) * (h - pad * 2)]);
  if (pts.length < 2) {
    const p = pts[0] || [pad, h - pad];
    return { line: `M${p[0]},${p[1]}`, area: `M${p[0]},${p[1]} L${p[0]},${h} Z`, last: p };
  }
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)} `;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += `C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)} `;
  }
  const last = pts[pts.length - 1];
  const area = d + `L${last[0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;
  return { line: d.trim(), area, last };
}
function cyberArc(cx, cy, r, pct, color, width) {
  const c = 2 * Math.PI * r;
  const off = c - Math.max(0, Math.min(100, pct)) / 100 * c;
  return `
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(0,255,156,.12)" stroke-width="${width}"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="butt"
      stroke-dasharray="${c}" stroke-dashoffset="${c}" data-final="${off}" transform="rotate(-90 ${cx} ${cy})"
      class="cp-gauge-seg" style="filter:drop-shadow(0 0 6px ${color})"/>`;
}

function renderDashboardCyberpunk(s, sys) {
  const trend = cyberSmoothPath(s.daily_series.map(d => d.revenue), 620, 160, 10);
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const gauges = sys ? [
    { pct: sys.cpu.percent, color: 'var(--cyan)', label: 'CPU', sub: `${sys.cpu.cores} CORES` },
    { pct: sys.ram.percent, color: 'var(--primary)', label: 'RAM', sub: `${sys.ram.used_gb}/${sys.ram.total_gb} GB` },
    { pct: sys.disk.percent, color: 'var(--emerald)', label: 'DISK', sub: `${sys.disk.used_gb}/${sys.disk.total_gb} GB` },
  ] : [];
  const gaugeHtml = gauges.map(g => `
    <div class="cp-gauge">
      <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="50"/>${cyberArc(60, 60, 50, g.pct, g.color, 8)}</svg>
      <div class="cp-gauge-txt"><b class="mono" style="color:${g.color}">${g.pct}%</b><span>${g.label}</span></div>
      <span class="cp-gauge-sub mono">${g.sub}</span>
    </div>`).join('');

  const maxCatRev = Math.max(...s.category_breakdown.map(c => c.revenue), 1);
  const catRows = s.category_breakdown.map((c, i) => `
    <div class="cp-bar-row">
      <span class="cp-bar-label">${esc(c.name)}</span>
      <span class="cp-bar-track"><span class="cp-bar-fill" data-w="${(c.revenue / maxCatRev) * 100}"></span></span>
      <span class="cp-bar-val mono">${fmt(c.revenue)}</span>
    </div>`).join('') || '<span class="card-sub">// NO_DATA</span>';

  const prodRows = s.top_products.map((p, i) => `
    <div class="cp-list-row">
      <span class="cp-list-idx mono">${String(i + 1).padStart(2, '0')}</span>
      <span class="cp-list-name">${esc(p.name)}</span>
      <span class="cp-list-val mono">${fmt(p.orders)}x</span>
    </div>`).join('') || '<span class="card-sub">// NO_DATA</span>';

  setContent(`
    <div class="cp-hero">
      <div class="cp-hero-line"><span class="cp-prompt">root@algoshop</span><span class="cp-path">:~$</span> <span class="cp-cmd">whoami</span></div>
      <h2>${greetingByHour().toUpperCase()}, ${esc(ME.username).toUpperCase()}<span class="cp-cursor">_</span></h2>
      <p class="mono">RANGE ${fmtDateOnly(s.start_date)} :: ${fmtDateOnly(s.end_date)}</p>
    </div>

    <div class="cp-stat-grid">
      <div class="cp-stat cp-stat-a">
        <span class="cp-stat-label">TOTAL_REVENUE</span>
        <span class="cp-stat-val mono" data-count="${s.revenue}">0</span>
        <span class="cp-stat-tag ${deltaUp ? 'up' : 'down'}">${deltaUp ? '▲' : '▼'} ${Math.abs(s.revenue_change_pct ?? 0)}%</span>
      </div>
      <div class="cp-stat"><span class="cp-stat-label">ORDERS_OK</span><span class="cp-stat-val mono" data-count="${s.approved}">0</span></div>
      <div class="cp-stat"><span class="cp-stat-label">USERS_TOTAL</span><span class="cp-stat-val mono" data-count="${s.total_users}">0</span></div>
      <div class="cp-stat"><span class="cp-stat-label">PENDING_ORDERS</span><span class="cp-stat-val mono" data-count="${s.pending}">0</span><span class="cp-stat-tag">${fmt(s.open_tickets)} OPEN_TICKETS</span></div>
    </div>

    <div class="cp-panel" style="margin-top:16px">
      <div class="cp-panel-head">// REVENUE_TREND.LOG</div>
      <svg class="cp-trend" viewBox="0 0 620 160" preserveAspectRatio="none">
        <defs><linearGradient id="cpTrendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--emerald)" stop-opacity=".35"/><stop offset="100%" stop-color="var(--emerald)" stop-opacity="0"/>
        </linearGradient></defs>
        <g class="cp-grid">${[0, 40, 80, 120, 160].map(y => `<line x1="0" y1="${y}" x2="620" y2="${y}"/>`).join('')}</g>
        <path d="${trend.area}" fill="url(#cpTrendFill)"/>
        <path d="${trend.line}" fill="none" stroke="var(--emerald)" stroke-width="2" style="filter:drop-shadow(0 0 6px var(--emerald))"/>
      </svg>
    </div>

    ${gaugeHtml ? `<div class="cp-panel" style="margin-top:16px"><div class="cp-panel-head">// SYS_RESOURCES</div><div class="cp-gauge-row">${gaugeHtml}</div></div>` : ''}

    <div class="cp-cols" style="margin-top:16px">
      <div class="cp-panel"><div class="cp-panel-head">// REVENUE_BY_CATEGORY</div>${catRows}</div>
      <div class="cp-panel"><div class="cp-panel-head">// TOP_PRODUCTS</div>${prodRows}</div>
    </div>
  `);

  const root = content();
  $$('.cp-stat-val[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  requestAnimationFrame(() => setTimeout(() => {
    $$('.cp-gauge-seg[data-final]', root).forEach(seg => {
      seg.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.16,1,.3,1)';
      seg.style.strokeDashoffset = seg.dataset.final;
    });
    $$('.cp-bar-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
  }, 60));
}

/* ------------------------------------------------ dashboard: streetops --- */
function soSegBar(pct, segments = 12) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  const filled = Math.round((p / 100) * segments);
  const color = p >= 60 ? 'var(--emerald)' : p >= 30 ? 'var(--amber)' : 'var(--rose)';
  let html = '';
  for (let i = 0; i < segments; i++) html += `<span class="so-seg${i < filled ? ' on' : ''}" style="${i < filled ? `background:${color};box-shadow:0 0 6px ${color}` : ''}"></span>`;
  return html;
}
function soWantedStars(ratio) {
  const level = Math.max(0, Math.min(5, Math.round(ratio * 5)));
  let html = '';
  for (let i = 0; i < 5; i++) html += `<span class="so-star${i < level ? ' on' : ''}">★</span>`;
  return html;
}
function renderDashboardStreetOps(s, sys) {
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const wantedRatio = s.approved ? Math.min((s.open_tickets / s.approved) * 3, 1) : 0;
  const health = sys ? Math.max(0, 100 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 3) : 80;

  const resHtml = sys ? `
    <div class="so-panel">
      <div class="so-panel-head">SERVER VITALS</div>
      <div class="so-vital-row"><span>CPU</span>${soSegBar(sys.cpu.percent)}<b class="mono">${sys.cpu.percent}%</b></div>
      <div class="so-vital-row"><span>RAM</span>${soSegBar(sys.ram.percent)}<b class="mono">${sys.ram.percent}%</b></div>
      <div class="so-vital-row"><span>DISK</span>${soSegBar(sys.disk.percent)}<b class="mono">${sys.disk.percent}%</b></div>
    </div>` : '';

  const maxCatRev = Math.max(...s.category_breakdown.map(c => c.revenue), 1);
  const loadout = s.category_breakdown.map(c => `
    <div class="so-vital-row"><span>${esc(c.name)}</span>${soSegBar((c.revenue / maxCatRev) * 100, 16)}<b class="mono">${fmt(c.revenue)}</b></div>
  `).join('') || '<span class="card-sub">بدون داده</span>';

  const missions = s.top_products.map((p, i) => `
    <div class="so-mission-row"><span class="so-mission-check">✓</span><span class="so-mission-name">${esc(p.name)}</span><span class="so-mission-val mono">${fmt(p.orders)}x</span></div>
  `).join('') || '<span class="card-sub">بدون داده</span>';

  setContent(`
    <div class="so-hero">
      <div class="so-hero-bar top"></div>
      <div class="so-hero-body">
        <span class="so-hero-tag">OBJECTIVE</span>
        <h2>${greetingByHour()}، ${esc(ME.username)}</h2>
        <p class="mono">${fmtDateOnly(s.start_date)} — ${fmtDateOnly(s.end_date)}</p>
      </div>
      <div class="so-hero-bar bottom"></div>
    </div>

    <div class="so-stat-grid">
      <div class="so-stat so-stat-cash">
        <span class="so-stat-label">CASH</span>
        <span class="so-stat-val mono">$<span data-count="${s.revenue}">0</span></span>
        <span class="so-stat-tag ${deltaUp ? 'up' : 'down'}">${deltaUp ? '▲' : '▼'} ${Math.abs(s.revenue_change_pct ?? 0)}%</span>
      </div>
      <div class="so-stat"><span class="so-stat-label">CREW (کاربران)</span><span class="so-stat-val mono" data-count="${s.total_users}">0</span></div>
      <div class="so-stat"><span class="so-stat-label">MISSIONS DONE</span><span class="so-stat-val mono" data-count="${s.approved}">0</span></div>
      <div class="so-stat">
        <span class="so-stat-label">WANTED (تیکت باز)</span>
        <span class="so-stat-stars">${soWantedStars(wantedRatio)}</span>
        <span class="so-stat-tag">${fmt(s.open_tickets)} باز</span>
      </div>
    </div>

    <div class="so-cols" style="margin-top:16px">
      <div class="so-panel">
        <div class="so-panel-head">HEALTH &amp; PERFORMANCE</div>
        <div class="so-vital-row"><span>نرخ تبدیل</span>${soSegBar(s.conversion_rate)}<b class="mono">${fmt(Math.round(s.conversion_rate))}%</b></div>
        <div class="so-vital-row"><span>سلامت سرور</span>${soSegBar(health)}<b class="mono">${fmt(Math.round(health))}%</b></div>
        <div class="so-vital-row"><span>سفارش در انتظار</span>${soSegBar(Math.min(Math.round((s.pending / Math.max(s.approved + s.pending, 1)) * 100), 100))}<b class="mono">${fmt(s.pending)}</b></div>
      </div>
      ${resHtml}
    </div>

    <div class="so-cols" style="margin-top:16px">
      <div class="so-panel"><div class="so-panel-head">LOADOUT — درآمد به تفکیک دسته</div>${loadout}</div>
      <div class="so-panel"><div class="so-panel-head">MISSION LOG — پرفروش‌ترین محصولات</div>${missions}</div>
    </div>
  `);

  const root = content();
  $$('.so-stat-val [data-count], .so-stat-val[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
}

/* ------------------------------------------------ dashboard: brutalist --- */
function renderDashboardBrutalist(s, sys) {
  const maxRev = Math.max(...s.daily_series.map(d => d.revenue), 1);
  const bruColors = ['#FFE600', '#2B6CFF', '#00C853', '#FF3B3B', '#FF3EA5'];
  const resHtml = sys ? `
    <div class="bru-res-grid">
      <div class="bru-res-card">
        <span class="bru-res-label">پردازنده CPU</span>
        <span class="bru-res-val mono">${sys.cpu.percent}٪</span>
        <span class="bru-res-track"><span class="bru-res-fill" data-w="${sys.cpu.percent}" style="background:#2B6CFF"></span></span>
        <span class="bru-res-sub">${sys.cpu.cores} هسته</span>
      </div>
      <div class="bru-res-card">
        <span class="bru-res-label">حافظه RAM</span>
        <span class="bru-res-val mono">${sys.ram.percent}٪</span>
        <span class="bru-res-track"><span class="bru-res-fill" data-w="${sys.ram.percent}" style="background:#FF8A00"></span></span>
        <span class="bru-res-sub">${sys.ram.used_gb} از ${sys.ram.total_gb} گیگ</span>
      </div>
      <div class="bru-res-card">
        <span class="bru-res-label">فضای دیسک</span>
        <span class="bru-res-val mono">${sys.disk.percent}٪</span>
        <span class="bru-res-track"><span class="bru-res-fill" data-w="${sys.disk.percent}" style="background:#00C853"></span></span>
        <span class="bru-res-sub">${sys.disk.used_gb} از ${sys.disk.total_gb} گیگ</span>
      </div>
    </div>` : '';
  const bars = s.daily_series.map((d, i) => `
    <div class="bru-bar-col" title="${d.date}: ${fmt(d.revenue)} تومان">
      <span class="bru-bar-val mono">${fmt(d.revenue)}</span>
      <div class="bru-bar" data-h="${Math.max((d.revenue / maxRev) * 100, 4)}" style="background:${bruColors[i % bruColors.length]}"></div>
    </div>`).join('');

  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;

  const metrics = [
    { label: 'نرخ تبدیل', pct: s.conversion_rate, color: '#2B6CFF' },
    { label: 'سلامت سرور', pct: sys ? Math.max(0, 100 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 3) : 80, color: '#00C853' },
    { label: 'نسبت تیکت باز', pct: s.approved ? Math.min(Math.round((s.open_tickets / s.approved) * 100), 100) : 0, color: '#FF3B3B' },
    { label: 'سهم فروش رفرال', pct: (s.referral_revenue + s.direct_revenue) ? Math.round((s.referral_revenue / (s.referral_revenue + s.direct_revenue)) * 100) : 0, color: '#FF3EA5' },
  ];
  const metricBars = metrics.map(m => `
    <div class="bru-metric-row">
      <span class="bru-metric-label">${m.label}</span>
      <span class="bru-metric-track"><span class="bru-metric-fill" data-w="${m.pct}" style="background:${m.color}"></span></span>
      <span class="bru-metric-val mono">${fmt(Math.round(m.pct))}٪</span>
    </div>`).join('');

  const maxCatRev = Math.max(...s.category_breakdown.map(c => c.revenue), 1);
  const catStack = s.category_breakdown.map((c, i) => `
    <span class="bru-stack-seg" data-w="${(c.revenue / maxCatRev / s.category_breakdown.length) * 100 + (100 / s.category_breakdown.length) * 0}"
      style="background:${bruColors[i % bruColors.length]}; flex:${c.revenue}" title="${esc(c.name)}: ${fmt(c.revenue)}"></span>`).join('');
  const catLegend = s.category_breakdown.map((c, i) => `
    <span class="bru-legend-item"><i style="background:${bruColors[i % bruColors.length]}"></i>${esc(c.name)} — ${fmt(c.revenue)}</span>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  const prodList = s.top_products.map((p, i) => `
    <div class="bru-prod-row">
      <span class="bru-prod-num mono">${(i + 1).toString().padStart(2, '۰')}</span>
      <span class="bru-prod-name">${esc(p.name)}</span>
      <span class="bru-prod-val mono">${fmt(p.orders)}</span>
    </div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  setContent(`
    <div class="bru-hero">
      <h2>${greetingByHour()}، ${esc(ME.username).toUpperCase()}</h2>
      <p>${fmtDateOnly(s.start_date)} تا ${fmtDateOnly(s.end_date)}</p>
    </div>

    ${resHtml}
    <div class="bru-grid-4">
      <div class="bru-block bru-yellow">
        <span class="bru-block-label">درآمد ۱۴ روز</span>
        <span class="bru-block-val mono" data-count="${s.revenue}">۰</span>
        <span class="bru-block-tag ${deltaUp ? '' : 'neg'}">${deltaUp ? '▲' : '▼'} ${Math.abs(s.revenue_change_pct ?? 0)}٪</span>
      </div>
      <div class="bru-block bru-white">
        <span class="bru-block-label">سفارش تایید شده</span>
        <span class="bru-block-val mono" data-count="${s.approved}">۰</span>
      </div>
      <div class="bru-block bru-black">
        <span class="bru-block-label">کاربران کل</span>
        <span class="bru-block-val mono" data-count="${s.total_users}">۰</span>
      </div>
      <div class="bru-block bru-white">
        <span class="bru-block-label">سفارش در انتظار / تیکت باز</span>
        <span class="bru-block-val mono" data-count="${s.pending}">۰</span>
        <span class="bru-block-tag">${fmt(s.open_tickets)} تیکت باز</span>
      </div>
    </div>

    <div class="bru-panel" style="margin-top:16px">
      <div class="bru-panel-head">روند فروش روزانه</div>
      <div class="bru-bars">${bars}</div>
    </div>

    <div class="bru-cols" style="margin-top:16px">
      <div class="bru-panel">
        <div class="bru-panel-head">شاخص‌های عملکرد</div>
        ${metricBars}
      </div>
      <div class="bru-panel">
        <div class="bru-panel-head">تفکیک درآمد</div>
        <div class="bru-stack">${catStack}</div>
        <div class="bru-legend">${catLegend}</div>
      </div>
    </div>

    <div class="bru-panel" style="margin-top:16px">
      <div class="bru-panel-head">پرفروش‌ترین محصولات</div>
      ${prodList}
    </div>
  `);

  const root = content();
  $$('.bru-block-val[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  requestAnimationFrame(() => setTimeout(() => {
    $$('.bru-bar[data-h]', root).forEach(b => { b.style.height = b.dataset.h + '%'; });
    $$('.bru-metric-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
    $$('.bru-res-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
  }, 60));
}

/* ---------------------------------------------------- dashboard: bento --- */
function sparklinePath(values, w, h, pad = 4) {
  const max = Math.max(...values, 1), min = Math.min(...values, 0);
  const range = (max - min) || 1;
  const step = (w - pad * 2) / Math.max(values.length - 1, 1);
  const pts = values.map((v, i) => [pad + i * step, h - pad - ((v - min) / range) * (h - pad * 2)]);
  const line = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = line + ` L${pts[pts.length - 1][0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;
  return { line, area, last: pts[pts.length - 1] };
}
function ringSegment(cx, cy, r, pct, color, width) {
  const c = 2 * Math.PI * r;
  const off = c - Math.max(0, Math.min(100, pct)) / 100 * c;
  return `
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--border)" stroke-width="${width}"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${c}" data-final="${off}" transform="rotate(-90 ${cx} ${cy})" class="bento-ring-seg"/>`;
}
function renderDashboardBento(s, sys) {
  const trend = sparklinePath(s.daily_series.map(d => d.revenue), 100, 40);
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const maxCatRev = Math.max(...s.category_breakdown.map(c => c.revenue), 1);
  const widgetColors = ['w-blue', 'w-green', 'w-orange', 'w-pink', 'w-purple'];
  const resWidgets = sys ? `
    <div class="bw w-white span-2">
      <div class="bw-head"><span class="bw-label" style="color:var(--text-muted)">منابع سرور</span></div>
      <div class="bw-res-grid">
        <div class="bw-res-item">
          <div class="bw-res-top"><span>CPU</span><b class="mono">${sys.cpu.percent}٪</b></div>
          <span class="bw-res-track"><span class="bw-res-fill" data-w="${sys.cpu.percent}" style="background:#0A84FF"></span></span>
        </div>
        <div class="bw-res-item">
          <div class="bw-res-top"><span>RAM</span><b class="mono">${sys.ram.percent}٪</b></div>
          <span class="bw-res-track"><span class="bw-res-fill" data-w="${sys.ram.percent}" style="background:#FF9F0A"></span></span>
        </div>
        <div class="bw-res-item">
          <div class="bw-res-top"><span>دیسک</span><b class="mono">${sys.disk.percent}٪</b></div>
          <span class="bw-res-track"><span class="bw-res-fill" data-w="${sys.disk.percent}" style="background:#30D158"></span></span>
        </div>
      </div>
    </div>` : '';
  const catBento = s.category_breakdown.slice(0, 4).map((c, i) => `
    <div class="bw-mini ${widgetColors[i % widgetColors.length]}">
      <span class="bw-mini-name">${esc(c.name)}</span>
      <span class="bw-mini-val mono">${fmt(c.revenue)}</span>
    </div>`).join('') || `<span class="card-sub">داده‌ای نیست</span>`;
  const prodBento = s.top_products.slice(0, 4).map((p, i) => `
    <div class="bw-row">
      <span class="bw-row-dot ${widgetColors[i % widgetColors.length]}"></span>
      <span class="bw-row-name">${esc(p.name)}</span>
      <span class="bw-row-val mono">${fmt(p.orders)}</span>
    </div>`).join('') || `<span class="card-sub">داده‌ای نیست</span>`;

  const ringsData = [
    { pct: s.conversion_rate, color: 'var(--primary)', label: 'تبدیل' },
    { pct: sys ? Math.max(0, 100 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 3) : 80, color: 'var(--emerald)', label: 'سلامت' },
    { pct: s.approved ? Math.min(Math.round((s.open_tickets / s.approved) * 100), 100) : 0, color: 'var(--rose)', label: 'تیکت' },
  ];

  setContent(`
    <div class="bento-grid">
      <div class="bw w-blue span-2 rows-2">
        <div class="bw-head">
          <span class="bw-label">درآمد ۱۴ روز اخیر</span>
          <span class="bw-badge ${deltaUp ? 'up' : 'down'}">${deltaUp ? '▲' : '▼'} ${Math.abs(s.revenue_change_pct ?? 0)}%</span>
        </div>
        <span class="bw-value mono" data-count="${s.revenue}">۰</span>
        <svg class="bw-trend" viewBox="0 0 100 40" preserveAspectRatio="none">
          <defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#fff" stop-opacity=".55"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/>
          </linearGradient></defs>
          <path d="${trend.area}" fill="url(#trendFill)"/>
          <path d="${trend.line}" fill="none" stroke="#fff" stroke-width="2"/>
        </svg>
      </div>

      <div class="bw w-green">
        <span class="bw-label">کاربران کل</span>
        <span class="bw-value mono" data-count="${s.total_users}">۰</span>
        <span class="bw-sub">${fmt(s.new_users)}+ جدید</span>
      </div>
      <div class="bw w-orange">
        <span class="bw-label">سفارش تایید شده</span>
        <span class="bw-value mono" data-count="${s.approved}">۰</span>
        <span class="bw-sub">${s.conversion_rate}٪ نرخ تبدیل</span>
      </div>

      <div class="bw w-white rows-2 span-2 bento-rings-card">
        <div class="bw-head"><span class="bw-label" style="color:var(--text-muted)">شاخص‌های کلیدی</span></div>
        <div class="bento-rings">
          <svg viewBox="0 0 120 120">
            ${ringSegment(60, 60, 50, ringsData[0].pct, ringsData[0].color, 10)}
            ${ringSegment(60, 60, 36, ringsData[1].pct, ringsData[1].color, 10)}
            ${ringSegment(60, 60, 22, ringsData[2].pct, ringsData[2].color, 10)}
          </svg>
          <div class="bento-rings-legend">
            ${ringsData.map(r => `<span><i style="background:${r.color}"></i>${r.label} · ${fmt(Math.round(r.pct))}٪</span>`).join('')}
          </div>
        </div>
      </div>

      <div class="bw w-pink">
        <span class="bw-label">در انتظار بررسی</span>
        <span class="bw-value mono" data-count="${s.pending}">۰</span>
      </div>
      <div class="bw w-purple">
        <span class="bw-label">تیکت باز</span>
        <span class="bw-value mono" data-count="${s.open_tickets}">۰</span>
      </div>

      <div class="bw w-white span-2">
        <div class="bw-head"><span class="bw-label" style="color:var(--text-muted)">تفکیک درآمد</span></div>
        <div class="bw-mini-grid">${catBento}</div>
      </div>
      <div class="bw w-white span-2">
        <div class="bw-head"><span class="bw-label" style="color:var(--text-muted)">پرفروش‌ترین محصولات</span></div>
        ${prodBento}
      </div>
      ${resWidgets}
    </div>
  `);

  const root = content();
  $$('.bw-value[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  requestAnimationFrame(() => setTimeout(() => {
    $$('.bento-ring-seg', root).forEach(seg => {
      seg.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.16,1,.3,1)';
      seg.style.strokeDashoffset = seg.dataset.final;
    });
    $$('.bw-res-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
  }, 60));
}

/* ----------------------------------------------------- dashboard: flat --- */


/* ------------------------------------------------------ dashboard: clay --- */

/* ----------------------------------------------------- dashboard: paper --- */

/* -------------------------------------------------- dashboard: obsidian --- */
/* ------------------------------------------------------- dashboard: warp --- */
function warpRingHtml(pct, color, label, value) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  return `
    <div class="warp-ring-item">
      <div class="ring warp-ring" style="--ring-a:${color}" data-pct="${p}"><span>${p}٪</span></div>
      <div class="warp-ring-info"><strong>${value}</strong><span>${label}</span></div>
    </div>`;
}


/* ============================================================ orders === */
let ordersStatus = 'pending';
async function renderOrders() {
  const canAct = hasPerm('orders');
  const orders = await apiGet(`/orders?status=${ordersStatus}`);
  if (loadTheme().theme === 'brutalist') return renderOrdersBrutalist(orders, canAct);
  if (loadTheme().theme === 'bento') return renderOrdersBento(orders, canAct);
  setContent(`
    <div class="tabs">
      ${['pending', 'approved', 'rejected'].map(s => `<button class="tab-btn ${s === ordersStatus ? 'active' : ''}" data-status="${s}">${{ pending: 'در انتظار', approved: 'تایید شده', rejected: 'رد شده' }[s]}</button>`).join('')}
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>#</th><th>کاربر</th><th>محصول</th><th>تعداد</th><th>مبلغ</th><th>تاریخ</th><th>رسید</th>${canAct && ordersStatus === 'pending' ? '<th>عملیات</th>' : ''}</tr></thead>
        <tbody>
          ${orders.map(o => `<tr>
            <td class="mono">#${o.id} ${historyBtn('order', o.id)}</td>
            <td>${esc(o.username || o.user_id)}</td>
            <td>${esc(o.product_name)} ${o.has_files === false && ordersStatus === 'pending' ? '<span class="badge badge-rejected">⛔️ بدون فایل</span>' : ''}</td>
            <td class="mono">${fmt(o.quantity || 1)}</td>
            <td class="mono">${fmt(o.final_price ?? o.base_price)}</td>
            <td class="mono">${fmtDate(o.created_at)}</td>
            <td>${o.receipt_file_id ? `<button class="btn btn-sm" data-receipt="order:${o.id}">مشاهده رسید</button>` : '<span class="mono">-</span>'}</td>
            ${canAct && ordersStatus === 'pending' ? `<td>
              <button class="btn btn-primary btn-sm" data-approve="${o.id}">تایید</button>
              <button class="btn btn-danger btn-sm" data-reject="${o.id}">رد</button>
            </td>` : ''}
          </tr>`).join('') || `<tr><td colspan="8" class="empty-state"><div class="icon">${svg('empty')}</div>سفارشی در این وضعیت نیست</td></tr>`}
        </tbody>
      </table></div>
    </div>
  `);
  $$('.tab-btn', content()).forEach(b => b.addEventListener('click', () => { ordersStatus = b.dataset.status; renderOrders(); }));
  $$('[data-receipt]', content()).forEach(b => b.addEventListener('click', () => {
    const [kind, id] = b.dataset.receipt.split(':');
    showReceiptModal(kind, id);
  }));
  $$('[data-approve]', content()).forEach(b => b.addEventListener('click', async () => {
    b.disabled = true;
    try { await apiPost(`/orders/${b.dataset.approve}/approve`); toast('✅ تایید شد — فایل‌ها برای خریدار ارسال شد.'); renderOrders(); }
    catch (e) { handleErr(e); b.disabled = false; }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('سفارش رد شود؟')) return;
    try { await apiPost(`/orders/${b.dataset.reject}/reject`); toast('سفارش رد شد.'); renderOrders(); }
    catch (e) { handleErr(e); }
  }));
}

/* -------------------------------------------------------- orders: bento -- */
function renderOrdersBento(orders, canAct) {
  const total = orders.reduce((sum, o) => sum + Number(o.final_price ?? o.base_price ?? 0), 0);
  setContent(`
    <div class="bn-hero">
      <div><h2>سفارش‌ها</h2><p>${fmt(orders.length)} مورد · جمع ${fmt(total)} تومان</p></div>
      <div class="bn-seg">${['pending', 'approved', 'rejected'].map(s => `<button class="bn-seg-btn ${s === ordersStatus ? 'active' : ''}" data-status="${s}">${ORDERS_STATUS_LABEL[s]}</button>`).join('')}</div>
    </div>
    <div class="bn-list">
      ${orders.map((o, i) => `
        <div class="bn-row-wrap bn-card-anim" style="animation-delay:${Math.min(i * 30, 260)}ms">
          <div class="bn-row">
            ${bnAvatar((o.product_name || '?').trim().charAt(0), i)}
            <div class="bn-row-main">
              <span class="bn-row-title">${esc(o.product_name)}</span>
              <span class="bn-row-sub">${esc(o.username || o.user_id)} · ${fmtDate(o.created_at)}${o.has_files === false && ordersStatus === 'pending' ? ' · ⛔️ بدون فایل' : ''}</span>
            </div>
            <div class="bn-row-trail">
              <span class="bn-row-amount mono">${fmt(o.final_price ?? o.base_price)} ت</span>
              ${o.receipt_file_id ? `<button class="bn-btn bn-btn-ghost" data-receipt="order:${o.id}">رسید</button>` : ''}
              ${historyBtn('order', o.id)}
            </div>
          </div>
          ${canAct && ordersStatus === 'pending' ? `<div class="bn-row-actions">
            <button class="bn-btn bn-btn-ok" data-approve="${o.id}">تایید</button>
            <button class="bn-btn bn-btn-no" data-reject="${o.id}">رد</button>
          </div>` : ''}
        </div>
      `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>سفارشی در این وضعیت نیست</div>`}
    </div>
  `);
  $$('.bn-seg-btn', content()).forEach(b => b.addEventListener('click', () => { ordersStatus = b.dataset.status; renderOrders(); }));
  $$('[data-receipt]', content()).forEach(b => b.addEventListener('click', () => {
    const [kind, id] = b.dataset.receipt.split(':');
    showReceiptModal(kind, id);
  }));
  $$('[data-approve]', content()).forEach(b => b.addEventListener('click', async function () {
    this.disabled = true;
    try { await apiPost(`/orders/${b.dataset.approve}/approve`); toast('✅ تایید شد — فایل‌ها برای خریدار ارسال شد.'); renderOrders(); }
    catch (e) { handleErr(e); this.disabled = false; }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async function () {
    if (!confirm('سفارش رد شود؟')) return;
    try { await apiPost(`/orders/${b.dataset.reject}/reject`); toast('سفارش رد شد.'); renderOrders(); }
    catch (e) { handleErr(e); }
  }));
}

/* -------------------------------------------------------- orders: glass -- */

/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* -------------------------------------------------- orders: brutalist --- */
// چیدمان «پرونده/تیکت» به‌جای جدول: هر سفارش یه کارت با ته‌برگ شماره‌دار،
// دکمه‌های تایید/رد به‌شکل مهر (استمپ) که با کلیک می‌کوبن (چرخش+بزرگنمایی).
const ORDERS_STATUS_LABEL = { pending: 'در انتظار', approved: 'تایید شده', rejected: 'رد شده' };
function renderOrdersBrutalist(orders, canAct) {
  const total = orders.reduce((sum, o) => sum + Number(o.final_price ?? o.base_price ?? 0), 0);
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>پرونده‌های سفارش</h2>
        <p>${fmt(orders.length)} مورد در وضعیت «${ORDERS_STATUS_LABEL[ordersStatus]}» — جمع مبلغ ${fmt(total)} تومان</p>
      </div>
      <div class="bru-seg" role="tablist">
        ${['pending', 'approved', 'rejected'].map(s => `<button class="bru-seg-btn ${s === ordersStatus ? 'active' : ''}" data-status="${s}">${ORDERS_STATUS_LABEL[s]}</button>`).join('')}
      </div>
    </div>

    <div class="bru-ticket-grid">
      ${orders.map((o, i) => `
        <div class="bru-ticket bru-card-anim" style="animation-delay:${Math.min(i * 40, 320)}ms">
          <div class="bru-ticket-stub">
            <span class="bru-ticket-num mono">#${o.id}</span>
            ${historyBtn('order', o.id)}
          </div>
          <div class="bru-ticket-body">
            <div class="bru-ticket-row"><span>کاربر</span><b>${esc(o.username || o.user_id)}</b></div>
            <div class="bru-ticket-row"><span>محصول</span><b>${esc(o.product_name)}${o.has_files === false && ordersStatus === 'pending' ? ' ⛔️' : ''}</b></div>
            <div class="bru-ticket-row"><span>تعداد</span><b class="mono">${fmt(o.quantity || 1)}</b></div>
            <div class="bru-ticket-row"><span>مبلغ</span><b class="mono bru-amount">${fmt(o.final_price ?? o.base_price)} ت</b></div>
            <div class="bru-ticket-row"><span>تاریخ</span><b class="mono">${fmtDate(o.created_at)}</b></div>
          </div>
          <div class="bru-ticket-actions">
            ${o.receipt_file_id ? `<button class="btn btn-sm" data-receipt="order:${o.id}">رسید</button>` : ''}
            ${canAct && ordersStatus === 'pending' ? `
              <button class="bru-stamp bru-stamp-ok" data-approve="${o.id}" style="--r:-6deg">تایید</button>
              <button class="bru-stamp bru-stamp-no" data-reject="${o.id}" style="--r:4deg">رد</button>
            ` : ''}
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>سفارشی در این وضعیت نیست</div>`}
    </div>
  `);
  $$('.bru-seg-btn', content()).forEach(b => b.addEventListener('click', () => { ordersStatus = b.dataset.status; renderOrders(); }));
  $$('[data-receipt]', content()).forEach(b => b.addEventListener('click', () => {
    const [kind, id] = b.dataset.receipt.split(':');
    showReceiptModal(kind, id);
  }));
  $$('[data-approve]', content()).forEach(b => b.addEventListener('click', async function () {
    this.classList.add('hit'); this.disabled = true;
    try { await apiPost(`/orders/${b.dataset.approve}/approve`); toast('✅ تایید شد — فایل‌ها برای خریدار ارسال شد.'); setTimeout(() => renderOrders(), 260); }
    catch (e) { handleErr(e); this.disabled = false; this.classList.remove('hit'); }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async function () {
    if (!confirm('سفارش رد شود؟')) return;
    this.classList.add('hit'); this.disabled = true;
    try { await apiPost(`/orders/${b.dataset.reject}/reject`); toast('سفارش رد شد.'); setTimeout(() => renderOrders(), 260); }
    catch (e) { handleErr(e); this.disabled = false; this.classList.remove('hit'); }
  }));
}

/* ============================================================ topups === */
let topupsStatus = 'pending';
async function renderTopups() {
  const canAct = hasPerm('orders');
  const topups = await apiGet(`/topups?status=${topupsStatus}`);
  if (loadTheme().theme === 'brutalist') return renderTopupsBrutalist(topups, canAct);
  if (loadTheme().theme === 'bento') return renderTopupsBento(topups, canAct);
  setContent(`
    <div class="tabs">
      ${['pending', 'approved', 'rejected'].map(s => `<button class="tab-btn ${s === topupsStatus ? 'active' : ''}" data-status="${s}">${{ pending: 'در انتظار', approved: 'تایید شده', rejected: 'رد شده' }[s]}</button>`).join('')}
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>#</th><th>کاربر</th><th>مبلغ</th><th>تاریخ</th><th>رسید</th>${canAct && topupsStatus === 'pending' ? '<th>عملیات</th>' : ''}</tr></thead>
        <tbody>${topups.map(t => `<tr>
          <td class="mono">#${t.id}</td><td>${esc(t.username || t.user_id)}</td>
          <td class="mono">${fmt(t.amount)}</td><td class="mono">${fmtDate(t.created_at)}</td>
          <td>${t.receipt_file_id ? `<button class="btn btn-sm" data-receipt="topup:${t.id}">مشاهده رسید</button>` : '<span class="mono">-</span>'}</td>
          ${canAct && topupsStatus === 'pending' ? `<td>
            <button class="btn btn-primary btn-sm" data-approve="${t.id}">تایید</button>
            <button class="btn btn-danger btn-sm" data-reject="${t.id}">رد</button>
          </td>` : ''}
        </tr>`).join('') || `<tr><td colspan="6" class="empty-state"><div class="icon">${svg('empty')}</div>درخواستی در این وضعیت نیست</td></tr>`}</tbody>
      </table></div>
    </div>
  `);
  $$('.tab-btn', content()).forEach(b => b.addEventListener('click', () => { topupsStatus = b.dataset.status; renderTopups(); }));
  $$('[data-receipt]', content()).forEach(b => b.addEventListener('click', () => {
    const [kind, id] = b.dataset.receipt.split(':');
    showReceiptModal(kind, id);
  }));
  $$('[data-approve]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/topups/${b.dataset.approve}/approve`); toast('شارژ تایید شد.'); renderTopups(); } catch (e) { handleErr(e); }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این شارژ رد شود؟')) return;
    try { await apiPost(`/topups/${b.dataset.reject}/reject`); toast('رد شد.'); renderTopups(); } catch (e) { handleErr(e); }
  }));
}

/* -------------------------------------------------------- topups: bento -- */
function renderTopupsBento(topups, canAct) {
  const total = topups.reduce((sum, t) => sum + Number(t.amount || 0), 0);
  setContent(`
    <div class="bn-hero">
      <div><h2>شارژ کیف پول</h2><p>${fmt(topups.length)} مورد · جمع ${fmt(total)} تومان</p></div>
      <div class="bn-seg">${['pending', 'approved', 'rejected'].map(s => `<button class="bn-seg-btn ${s === topupsStatus ? 'active' : ''}" data-status="${s}">${ORDERS_STATUS_LABEL[s]}</button>`).join('')}</div>
    </div>
    <div class="bn-list">
      ${topups.map((t, i) => `
        <div class="bn-row-wrap bn-card-anim" style="animation-delay:${Math.min(i * 30, 260)}ms">
          <div class="bn-row">
            ${bnAvatar((t.username || '؟').trim().charAt(0), i)}
            <div class="bn-row-main">
              <span class="bn-row-title">${esc(t.username || t.user_id)}</span>
              <span class="bn-row-sub">${fmtDate(t.created_at)}</span>
            </div>
            <div class="bn-row-trail">
              <span class="bn-row-amount mono">${fmt(t.amount)} ت</span>
              ${t.receipt_file_id ? `<button class="bn-btn bn-btn-ghost" data-receipt="topup:${t.id}">رسید</button>` : ''}
            </div>
          </div>
          ${canAct && topupsStatus === 'pending' ? `<div class="bn-row-actions">
            <button class="bn-btn bn-btn-ok" data-approve="${t.id}">تایید</button>
            <button class="bn-btn bn-btn-no" data-reject="${t.id}">رد</button>
          </div>` : ''}
        </div>
      `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>درخواستی در این وضعیت نیست</div>`}
    </div>
  `);
  $$('.bn-seg-btn', content()).forEach(b => b.addEventListener('click', () => { topupsStatus = b.dataset.status; renderTopups(); }));
  $$('[data-receipt]', content()).forEach(b => b.addEventListener('click', () => {
    const [kind, id] = b.dataset.receipt.split(':');
    showReceiptModal(kind, id);
  }));
  $$('[data-approve]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/topups/${b.dataset.approve}/approve`); toast('شارژ تایید شد.'); renderTopups(); } catch (e) { handleErr(e); }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این شارژ رد شود؟')) return;
    try { await apiPost(`/topups/${b.dataset.reject}/reject`); toast('رد شد.'); renderTopups(); } catch (e) { handleErr(e); }
  }));
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* -------------------------------------------------- topups: brutalist --- */
function renderTopupsBrutalist(topups, canAct) {
  const total = topups.reduce((sum, t) => sum + Number(t.amount || 0), 0);
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>پرونده‌های شارژ کیف پول</h2>
        <p>${fmt(topups.length)} مورد در وضعیت «${ORDERS_STATUS_LABEL[topupsStatus]}» — جمع مبلغ ${fmt(total)} تومان</p>
      </div>
      <div class="bru-seg" role="tablist">
        ${['pending', 'approved', 'rejected'].map(s => `<button class="bru-seg-btn ${s === topupsStatus ? 'active' : ''}" data-status="${s}">${ORDERS_STATUS_LABEL[s]}</button>`).join('')}
      </div>
    </div>

    <div class="bru-ticket-grid">
      ${topups.map((t, i) => `
        <div class="bru-ticket bru-card-anim" style="animation-delay:${Math.min(i * 40, 320)}ms">
          <div class="bru-ticket-stub">
            <span class="bru-ticket-num mono">#${t.id}</span>
            ${t.receipt_file_id ? `<button class="btn btn-sm" data-receipt="topup:${t.id}" style="background:transparent;color:#fff;border-color:#fff;box-shadow:none">رسید</button>` : ''}
          </div>
          <div class="bru-ticket-body">
            <div class="bru-ticket-row"><span>کاربر</span><b>${esc(t.username || t.user_id)}</b></div>
            <div class="bru-ticket-row"><span>مبلغ</span><b class="mono bru-amount">${fmt(t.amount)} ت</b></div>
            <div class="bru-ticket-row"><span>تاریخ</span><b class="mono">${fmtDate(t.created_at)}</b></div>
          </div>
          ${canAct && topupsStatus === 'pending' ? `
          <div class="bru-ticket-actions">
            <button class="bru-stamp bru-stamp-ok" data-approve="${t.id}" style="--r:-6deg">تایید</button>
            <button class="bru-stamp bru-stamp-no" data-reject="${t.id}" style="--r:4deg">رد</button>
          </div>` : ''}
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>درخواستی در این وضعیت نیست</div>`}
    </div>
  `);
  $$('.bru-seg-btn', content()).forEach(b => b.addEventListener('click', () => { topupsStatus = b.dataset.status; renderTopups(); }));
  $$('[data-receipt]', content()).forEach(b => b.addEventListener('click', () => {
    const [kind, id] = b.dataset.receipt.split(':');
    showReceiptModal(kind, id);
  }));
  $$('[data-approve]', content()).forEach(b => b.addEventListener('click', async function () {
    this.classList.add('hit'); this.disabled = true;
    try { await apiPost(`/topups/${b.dataset.approve}/approve`); toast('شارژ تایید شد.'); setTimeout(() => renderTopups(), 260); }
    catch (e) { handleErr(e); this.disabled = false; this.classList.remove('hit'); }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async function () {
    if (!confirm('این شارژ رد شود؟')) return;
    this.classList.add('hit'); this.disabled = true;
    try { await apiPost(`/topups/${b.dataset.reject}/reject`); toast('رد شد.'); setTimeout(() => renderTopups(), 260); }
    catch (e) { handleErr(e); this.disabled = false; this.classList.remove('hit'); }
  }));
}

/* ============================================================= users === */
let usersState = { q: '', status: 'all', page: 1 };
const USERS_STATUS_LABEL = { all: 'همه', active: 'خریدار', expired: 'بدون خرید موفق', blocked: 'مسدود' };
async function renderUsers() {
  const res = await apiGet(`/users?q=${encodeURIComponent(usersState.q)}&status=${usersState.status}&page=${usersState.page}`);
  const pages = Math.max(Math.ceil(res.total / res.limit), 1);
  if (loadTheme().theme === 'brutalist') return renderUsersBrutalist(res, pages);
  if (loadTheme().theme === 'bento') return renderUsersBento(res, pages);
  setContent(`
    <div class="toolbar">
      <input class="input" id="user-search" placeholder="جستجو (آیدی، یوزرنیم، نام)..." value="${esc(usersState.q)}">
      <select class="input" id="user-status">
        ${[['all', 'همه'], ['active', 'خریدار'], ['expired', 'بدون خرید موفق'], ['blocked', 'مسدود']].map(([v, l]) => `<option value="${v}" ${v === usersState.status ? 'selected' : ''}>${l}</option>`).join('')}
      </select>
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>آیدی</th><th>یوزرنیم</th><th>نام</th><th>وضعیت</th><th>عضویت</th><th>عملیات</th></tr></thead>
        <tbody>${res.items.map(u => `<tr>
          <td class="mono">${u.telegram_id}</td><td>${esc(u.username || '—')}</td><td>${esc(u.first_name || '—')}</td>
          <td>${u.is_blocked ? '<span class="badge badge-rejected">مسدود</span>' : '<span class="badge badge-approved">فعال</span>'}</td>
          <td class="mono">${fmtDate(u.joined_at)}</td>
          <td>
            <button class="btn btn-ghost btn-sm" data-detail="${u.telegram_id}">جزئیات</button>
            ${hasPerm('users') ? (u.is_blocked
              ? `<button class="btn btn-sm" data-unblock="${u.telegram_id}">رفع مسدودی</button>`
              : `<button class="btn btn-danger btn-sm" data-block="${u.telegram_id}">مسدودسازی</button>`) : ''}
          </td>
        </tr>`).join('') || `<tr><td colspan="6" class="empty-state"><div class="icon">${svg('empty')}</div>کاربری یافت نشد</td></tr>`}</tbody>
      </table></div>
      <div class="pager">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === usersState.page ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
    </div>
  `);
  $('#user-search').addEventListener('keydown', e => { if (e.key === 'Enter') { usersState.q = e.target.value; usersState.page = 1; renderUsers(); } });
  $('#user-status').addEventListener('change', e => { usersState.status = e.target.value; usersState.page = 1; renderUsers(); });
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { usersState.page = Number(b.dataset.page); renderUsers(); }));
  $$('[data-block]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/users/${b.dataset.block}/block`); toast('کاربر مسدود شد.'); renderUsers(); } catch (e) { handleErr(e); }
  }));
  $$('[data-unblock]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/users/${b.dataset.unblock}/unblock`); toast('رفع مسدودیت شد.'); renderUsers(); } catch (e) { handleErr(e); }
  }));
  $$('[data-detail]', content()).forEach(b => b.addEventListener('click', () => showUserDetail(Number(b.dataset.detail))));
}

/* ---------------------------------------------------------- users: bento */
function renderUsersBento(res, pages) {
  setContent(`
    <div class="bn-hero">
      <div><h2>کاربران</h2><p>${fmt(res.total)} کاربر ثبت‌شده</p></div>
      <div class="bn-seg">${['all', 'active', 'expired', 'blocked'].map(s => `<button class="bn-seg-btn ${s === usersState.status ? 'active' : ''}" data-ustatus="${s}">${USERS_STATUS_LABEL[s]}</button>`).join('')}</div>
    </div>
    <input class="bn-search" id="user-search" placeholder="جستجو: آیدی، یوزرنیم، نام..." value="${esc(usersState.q)}" style="margin-bottom:14px">
    <div class="bn-list">
      ${res.items.map((u, i) => `
        <div class="bn-row bn-card-anim" style="animation-delay:${Math.min(i * 25, 240)}ms">
          ${bnAvatar((u.first_name || u.username || '؟').trim().charAt(0).toUpperCase(), i)}
          <div class="bn-row-main">
            <span class="bn-row-title">${esc(u.username ? '@' + u.username : (u.first_name || '—'))}</span>
            <span class="bn-row-sub">ID: ${u.telegram_id} · عضویت ${fmtDate(u.joined_at)}</span>
          </div>
          <div class="bn-row-trail">
            ${bnPill(u.is_blocked ? 'مسدود' : 'فعال', u.is_blocked ? 'no' : 'ok')}
            <button class="bn-btn bn-btn-ghost" data-detail="${u.telegram_id}">جزئیات</button>
            ${hasPerm('users') ? (u.is_blocked
              ? `<button class="bn-btn bn-btn-ok" data-unblock="${u.telegram_id}">رفع مسدودی</button>`
              : `<button class="bn-btn bn-btn-no" data-block="${u.telegram_id}">مسدودسازی</button>`) : ''}
          </div>
        </div>
      `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>کاربری یافت نشد</div>`}
    </div>
    <div class="pager" style="margin-top:16px">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === usersState.page ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
  `);
  $('#user-search').addEventListener('keydown', e => { if (e.key === 'Enter') { usersState.q = e.target.value; usersState.page = 1; renderUsers(); } });
  $$('.bn-seg-btn[data-ustatus]', content()).forEach(b => b.addEventListener('click', () => { usersState.status = b.dataset.ustatus; usersState.page = 1; renderUsers(); }));
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { usersState.page = Number(b.dataset.page); renderUsers(); }));
  $$('[data-block]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/users/${b.dataset.block}/block`); toast('کاربر مسدود شد.'); renderUsers(); } catch (e) { handleErr(e); }
  }));
  $$('[data-unblock]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/users/${b.dataset.unblock}/unblock`); toast('رفع مسدودیت شد.'); renderUsers(); } catch (e) { handleErr(e); }
  }));
  $$('[data-detail]', content()).forEach(b => b.addEventListener('click', () => showUserDetail(Number(b.dataset.detail))));
}

/* ---------------------------------------------------------- users: glass */

/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* --------------------------------------------------- users: brutalist --- */
// چیدمان «دایرکتوری/تابلوی اعلانات» به‌جای جدول: هر کاربر یه کارت با
// آواتار حرفی درشت و برچسب وضعیت مثل استیکر گوشه‌ی پرونده.
function renderUsersBrutalist(res, pages) {
  const activeCount = res.items.filter(u => !u.is_blocked).length;
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>دایرکتوری کاربران</h2>
        <p>${fmt(res.total)} کاربر ثبت‌شده — ${fmt(activeCount)} فعال در این صفحه</p>
      </div>
    </div>

    <div class="bru-toolbar">
      <input class="bru-search-input" id="user-search" placeholder="جستجو: آیدی، یوزرنیم، نام..." value="${esc(usersState.q)}">
      <div class="bru-seg" role="tablist">
        ${['all', 'active', 'expired', 'blocked'].map(s => `<button class="bru-seg-btn ${s === usersState.status ? 'active' : ''}" data-ustatus="${s}">${USERS_STATUS_LABEL[s]}</button>`).join('')}
      </div>
    </div>

    <div class="bru-user-grid">
      ${res.items.map((u, i) => `
        <div class="bru-user-card bru-card-anim" style="animation-delay:${Math.min(i * 35, 300)}ms">
          <span class="bru-flag ${u.is_blocked ? 'bru-flag-no' : 'bru-flag-ok'}">${u.is_blocked ? 'مسدود' : 'فعال'}</span>
          <div class="bru-user-avatar mono">${esc((u.first_name || u.username || String(u.telegram_id)).trim().charAt(0).toUpperCase())}</div>
          <div class="bru-user-name">${esc(u.username ? '@' + u.username : (u.first_name || '—'))}</div>
          <div class="bru-user-id mono">ID: ${u.telegram_id}</div>
          <div class="bru-user-joined mono">عضویت: ${fmtDate(u.joined_at)}</div>
          <div class="bru-user-actions">
            <button class="btn btn-sm btn-ghost" data-detail="${u.telegram_id}">جزئیات</button>
            ${hasPerm('users') ? (u.is_blocked
              ? `<button class="btn btn-sm" data-unblock="${u.telegram_id}">رفع مسدودی</button>`
              : `<button class="btn btn-sm btn-danger" data-block="${u.telegram_id}">مسدودسازی</button>`) : ''}
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>کاربری یافت نشد</div>`}
    </div>

    <div class="pager" style="margin-top:16px">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === usersState.page ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
  `);
  $('#user-search').addEventListener('keydown', e => { if (e.key === 'Enter') { usersState.q = e.target.value; usersState.page = 1; renderUsers(); } });
  $$('.bru-seg-btn[data-ustatus]', content()).forEach(b => b.addEventListener('click', () => { usersState.status = b.dataset.ustatus; usersState.page = 1; renderUsers(); }));
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { usersState.page = Number(b.dataset.page); renderUsers(); }));
  $$('[data-block]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/users/${b.dataset.block}/block`); toast('کاربر مسدود شد.'); renderUsers(); } catch (e) { handleErr(e); }
  }));
  $$('[data-unblock]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/users/${b.dataset.unblock}/unblock`); toast('رفع مسدودیت شد.'); renderUsers(); } catch (e) { handleErr(e); }
  }));
  $$('[data-detail]', content()).forEach(b => b.addEventListener('click', () => showUserDetail(Number(b.dataset.detail))));
}

async function showUserDetail(tgId) {
  const d = await apiGet(`/users/${tgId}`);
  const isSenior = hasPerm('users');
  const u = d.user;
  const displayName = u.username ? '@' + u.username : (u.first_name || tgId);
  const initial = (u.first_name || u.username || String(tgId)).trim().charAt(0).toUpperCase();

  const statCards = [
    { label: 'کیف پول', val: `${fmt(u.referral_credit)} تومان` },
    { label: 'زیرمجموعه‌ها', val: fmt(d.referral.count) },
    { label: 'تاریخ عضویت', val: fmtDate(u.joined_at) },
    { label: 'الگوی نمونه', val: u.test_used ? 'دریافت کرده' : '—' },
  ];
  if (u.referred_by) statCards.push({ label: 'دعوت‌شده توسط', val: `#${u.referred_by}` });

  openModal(`کاربر ${esc(displayName)}`, `
    <div class="ud-head">
      <div class="ud-avatar">${esc(initial)}</div>
      <div class="ud-id">
        <strong>${esc(displayName)}</strong>
        <span class="mono">ID: ${tgId}</span>
      </div>
      <span class="badge ${u.is_blocked ? 'badge-rejected' : 'badge-approved'}">${u.is_blocked ? 'مسدود' : 'فعال'}</span>
      ${historyBtn('user', tgId)}
    </div>

    <div class="ud-stats">
      ${statCards.map(s => `<div class="ud-stat"><span>${s.label}</span><b class="mono">${s.val}</b></div>`).join('')}
    </div>

    ${isSenior ? `<div class="form-row" style="margin:16px 0">
      <input class="input" id="wallet-delta" type="number" placeholder="مبلغ (مثبت=افزایش، منفی=کاهش)">
      <button class="btn btn-primary" id="wallet-submit">اعمال</button>
    </div>` : ''}

    <h4 class="ud-section-title">سفارش‌های اخیر</h4>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>محصول</th><th>مبلغ</th><th>وضعیت</th><th>تاریخ</th></tr></thead>
    <tbody>${d.orders.slice(0, 10).map(o => `<tr><td class="mono">#${o.id}</td><td>${esc(o.product_name || '-')}</td><td class="mono">${fmt(o.final_price)}</td><td>${esc(o.status)}</td><td class="mono">${fmtDate(o.created_at)}</td></tr>`).join('') || `<tr><td colspan="5" class="empty-state"><div class="icon">${svg('empty')}</div>سفارشی نیست</td></tr>`}</tbody></table></div>

    <h4 class="ud-section-title">شارژهای کیف پول</h4>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>مبلغ</th><th>وضعیت</th><th>تاریخ</th></tr></thead>
    <tbody>${(d.topups || []).slice(0, 10).map(t => `<tr><td class="mono">#${t.id}</td><td class="mono">${fmt(t.amount)}</td><td>${esc(t.status)}</td><td class="mono">${fmtDate(t.created_at)}</td></tr>`).join('') || `<tr><td colspan="4" class="empty-state"><div class="icon">${svg('empty')}</div>شارژی ثبت نشده</td></tr>`}</tbody></table></div>
  `, (body, close) => {
    const submitBtn = $('#wallet-submit', body);
    if (submitBtn) submitBtn.addEventListener('click', async () => {
      const delta = Number($('#wallet-delta', body).value);
      if (!delta) return;
      try { await apiPost(`/users/${tgId}/wallet`, { delta }); toast('کیف پول به‌روزرسانی شد.'); close(); }
      catch (e) { handleErr(e); }
    });
  }, { wide: true });
}

/* ============================================================ catalog === */
let catalogTab = 'products';

/* آپلود multipart (فایل الگو / عکس پیش‌نمایش) — برخلاف api() بدنه FormData است
   و نباید هدر Content-Type: application/json ست شود. */
async function apiUpload(path, formData) {
  const res = await fetch('/api' + path, { method: 'POST', credentials: 'include', body: formData });
  if (res.status === 401) { showLogin(); throw new Error('unauthorized'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const err = new Error(formatApiError(data.detail)); err.status = res.status; throw err; }
  return data;
}

/* بندانگشتی عکس پیش‌نمایش محصول (پروکسی تلگرام سمت سرور). اگر عکسی ثبت نشده
   باشد درخواست 404 می‌شود و wireThumbFallback آن را به fallback تبدیل می‌کند. */
function productThumbHtml(p) {
  return `<img class="thumb" data-fallback src="/api/products/${p.id}/preview" alt="" loading="lazy">`;
}
function wireThumbFallback(root) {
  $$('.thumb[data-fallback]', root).forEach(img => img.addEventListener('error', () => {
    const fb = document.createElement('span');
    fb.className = 'thumb thumb-fallback';
    fb.textContent = '🧵';
    img.replaceWith(fb);
  }));
}
/* وضعیت بانک فایل هر محصول: فروش نامحدود است؛ فقط وجود حداقل یک فایل کافی است */
function fileStatusChip(p) {
  return p.has_files
    ? '<span class="badge badge-approved">✅ فایل آماده</span>'
    : '<span class="badge badge-rejected">⛔️ بدون فایل</span>';
}

function openProductAddModal(categories) {
  openModal('محصول جدید', `
    <div class="form-grid">
      <select class="input" id="prod-cat">${categories.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select>
      <input class="input" id="prod-name" placeholder="نام الگو">
      <input class="input" id="prod-price" type="number" placeholder="قیمت (تومان)">
      <textarea class="input" id="prod-desc" placeholder="توضیحات (اختیاری)" rows="2"></textarea>
      <button class="btn btn-primary" id="prod-save">ثبت</button>
    </div>`, (b, close) => {
    $('#prod-save', b).addEventListener('click', async () => {
      const name = $('#prod-name', b).value.trim();
      const price = Number($('#prod-price', b).value);
      if (!name || !price) return toast('نام و قیمت الزامی است.', true);
      try {
        await apiPost('/products', {
          category_id: Number($('#prod-cat', b).value), name, price,
          description: $('#prod-desc', b).value,
        });
        toast('محصول اضافه شد؛ حالا فایل‌های الگو را برایش آپلود کن.');
        close(); renderCatalog();
      } catch (e) { handleErr(e); }
    });
  });
}

function wireProductRowActions(body, products) {
  $$('[data-toggle-prod]', body).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/products/${b.dataset.toggleProd}/toggle`); renderCatalog(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del-prod]', body).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این محصول حذف شود؟ فایل‌های الگویش هم حذف می‌شوند.')) return;
    try { await apiDelete(`/products/${b.dataset.delProd}`); toast('حذف شد.'); renderCatalog(); } catch (e) { handleErr(e); }
  }));
  $$('[data-edit-prod]', body).forEach(b => b.addEventListener('click', () => {
    const p = products.find(x => x.id === Number(b.dataset.editProd));
    if (p) openProductEditor(p);
  }));
  $$('[data-files]', body).forEach(b => b.addEventListener('click', () => {
    const p = products.find(x => x.id === Number(b.dataset.files));
    if (p) showProductFiles(p);
  }));
}

/* ویرایش محصول: نام/قیمت/توضیحات + آپلود عکس پیش‌نمایش (multipart) */
async function openProductEditor(p) {
  openModal(`ویرایش «${esc(p.name)}»`, `
    <div class="form-grid">
      <input class="input" id="pe-name" value="${esc(p.name)}" placeholder="نام الگو">
      <input class="input" id="pe-price" type="number" value="${p.price}" placeholder="قیمت (تومان)">
      <textarea class="input" id="pe-desc" rows="3" placeholder="توضیحات">${esc(p.description || '')}</textarea>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        ${productThumbHtml(p)}
        <input type="file" accept="image/*" id="pe-preview-file" hidden>
        <button type="button" class="btn btn-sm" id="pe-preview-pick">🖼 تنظیم عکس پیش‌نمایش</button>
        <span class="card-sub">این عکس در ویترین فروشگاه نمایش داده می‌شود.</span>
      </div>
      <button class="btn btn-primary" id="pe-save">ذخیره تغییرات</button>
    </div>`, (body, close) => {
    wireThumbFallback(body);
    $('#pe-preview-pick', body).addEventListener('click', () => $('#pe-preview-file', body).click());
    $('#pe-preview-file', body).addEventListener('change', async () => {
      const file = $('#pe-preview-file', body).files[0];
      if (!file) return;
      const btn = $('#pe-preview-pick', body);
      btn.disabled = true; btn.textContent = '⏳ در حال آپلود...';
      const fd = new FormData();
      fd.append('photo', file);
      try {
        await apiUpload(`/products/${p.id}/preview`, fd);
        toast('عکس پیش‌نمایش تنظیم شد.');
        close(); renderCatalog();
      } catch (e) { handleErr(e); btn.disabled = false; btn.textContent = '🖼 تنظیم عکس پیش‌نمایش'; }
    });
    $('#pe-save', body).addEventListener('click', async () => {
      const name = $('#pe-name', body).value.trim();
      const price = Number($('#pe-price', body).value);
      if (!name || !price) return toast('نام و قیمت الزامی است.', true);
      try {
        await apiPut(`/products/${p.id}`, { name, price, description: $('#pe-desc', body).value });
        toast('ذخیره شد.'); close(); renderCatalog();
      } catch (e) { handleErr(e); }
    });
  }, { wide: true });
}

/* مدیر فایل‌های الگوی یک محصول: لیست، مشاهده، حذف و آپلود چندتایی (multipart) */
async function showProductFiles(p) {
  let res;
  try { res = await apiGet(`/products/${p.id}/files`); }
  catch (e) { handleErr(e); return; }
  const files = res.items || [];
  const rowHtml = f => `
    <div class="file-row">
      <span class="file-row-icon">${svg('catalog')}</span>
      <span class="file-row-name">فایل الگو #${f.id}</span>
      <span class="file-row-size mono">${fmtDate(f.created_at)}</span>
      <span class="file-row-actions">
        <a class="btn btn-ghost btn-sm" href="/api/files/${encodeURIComponent(f.file_id)}" target="_blank" rel="noopener">مشاهده</a>
        <button class="btn btn-danger btn-sm" data-del-file="${esc(f.file_id)}" title="حذف">🗑</button>
      </span>
    </div>`;
  openModal(`فایل‌های «${esc(p.name)}»`, `
    <div class="card-sub" style="margin-bottom:10px">${fmt(res.count ?? files.length)} فایل ثبت شده — بعد از تایید سفارش، همه‌ی این فایل‌ها برای خریدار ارسال می‌شوند (فروش نامحدود).</div>
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
      <input type="file" id="pf-file" hidden multiple accept=".pdf,image/*,.zip,.rar,.doc,.docx,.ai,.svg,.pptx">
      <button type="button" class="btn btn-primary btn-sm" id="pf-pick">➕ آپلود فایل</button>
      <span class="card-sub" id="pf-progress"></span>
    </div>
    <div id="pf-list">${files.map(rowHtml).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>هنوز فایلی آپلود نشده — بدون فایل، سفارش قابل تایید نیست.</div>`}</div>
  `, (body, close) => {
    const input = $('#pf-file', body);
    $('#pf-pick', body).addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
      const picked = Array.from(input.files || []);
      if (!picked.length) return;
      const progress = $('#pf-progress', body);
      const btn = $('#pf-pick', body);
      btn.disabled = true;
      let added = 0, duplicates = 0, failed = 0;
      for (let i = 0; i < picked.length; i++) {
        progress.textContent = `⏳ در حال آپلود ${i + 1} از ${picked.length}...`;
        const fd = new FormData();
        fd.append('file', picked[i]);
        try {
          const r = await apiUpload(`/products/${p.id}/files`, fd);
          added += r.added || 0; duplicates += r.duplicates || 0;
        } catch (e) { handleErr(e); failed++; }
      }
      btn.disabled = false;
      progress.textContent = '';
      toast(`${added} فایل اضافه شد${duplicates ? ` (${duplicates} تکراری نادیده گرفته شد)` : ''}${failed ? ` — ${failed} ناموفق` : ''}.`);
      close(); renderCatalog(); showProductFiles(p);
    });
    $$('[data-del-file]', body).forEach(b => b.addEventListener('click', async () => {
      if (!confirm('این فایل از بانک الگو حذف شود؟')) return;
      try {
        await apiDelete(`/files/${encodeURIComponent(b.dataset.delFile)}`);
        toast('فایل حذف شد.');
        close(); renderCatalog(); showProductFiles(p);
      } catch (e) { handleErr(e); }
    }));
  }, { wide: true });
}

async function renderCatalog() {
  const [categories, products] = await Promise.all([apiGet('/categories'), apiGet('/products')]);
  if (loadTheme().theme === 'brutalist') return renderCatalogBrutalist(categories, products);
  if (loadTheme().theme === 'bento') return renderCatalogBento(categories, products);
  setContent(`
    <div class="tabs">
      <button class="tab-btn ${catalogTab === 'products' ? 'active' : ''}" data-t="products">محصولات</button>
      <button class="tab-btn ${catalogTab === 'categories' ? 'active' : ''}" data-t="categories">دسته‌بندی‌ها</button>
    </div>
    <div id="catalog-body"></div>
  `);
  $$('.tab-btn', content()).forEach(b => b.addEventListener('click', () => { catalogTab = b.dataset.t; renderCatalog(); }));

  const body = $('#catalog-body');
  if (catalogTab === 'categories') {
    body.innerHTML = `
      <div class="toolbar"><button class="btn btn-primary btn-sm" id="add-cat">+ دسته‌بندی جدید</button></div>
      <div class="card"><div class="table-wrap"><table><thead><tr><th>نام</th><th>وضعیت</th><th>عملیات</th></tr></thead>
      <tbody>${categories.map(c => `<tr>
        <td>${esc(c.name)}</td>
        <td>${c.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
        <td><button class="btn btn-sm" data-toggle-cat="${c.id}">${c.is_active ? 'غیرفعال کن' : 'فعال کن'}</button>
        <button class="btn btn-danger btn-sm" data-del-cat="${c.id}">حذف</button></td>
      </tr>`).join('') || '<tr><td colspan="3" class="empty-state">دسته‌بندی‌ای نیست</td></tr>'}</tbody></table></div></div>`;
    $('#add-cat').addEventListener('click', () => openModal('دسته‌بندی جدید', `
      <div class="form-grid"><input class="input" id="cat-name" placeholder="نام دسته‌بندی">
      <button class="btn btn-primary" id="cat-save">ثبت</button></div>`, (b, close) => {
      $('#cat-save', b).addEventListener('click', async () => {
        const name = $('#cat-name', b).value.trim(); if (!name) return;
        try { await apiPost('/categories', { name }); toast('اضافه شد.'); close(); renderCatalog(); } catch (e) { handleErr(e); }
      });
    }));
    $$('[data-toggle-cat]', body).forEach(b => b.addEventListener('click', async () => {
      try { await apiPost(`/categories/${b.dataset.toggleCat}/toggle`); renderCatalog(); } catch (e) { handleErr(e); }
    }));
    $$('[data-del-cat]', body).forEach(b => b.addEventListener('click', async () => {
      if (!confirm('حذف شود؟ (محصولات این دسته هم حذف می‌شوند)')) return;
      try { await apiDelete(`/categories/${b.dataset.delCat}`); toast('حذف شد.'); renderCatalog(); } catch (e) { handleErr(e); }
    }));
    return;
  }

  body.innerHTML = `
    <div class="toolbar"><button class="btn btn-primary btn-sm" id="add-prod">+ محصول جدید</button></div>
    <div class="card"><div class="table-wrap"><table><thead><tr><th></th><th>نام</th><th>دسته</th><th>قیمت</th><th>فایل الگو</th><th>وضعیت</th><th>عملیات</th></tr></thead>
    <tbody>${products.map(p => `<tr>
      <td>${productThumbHtml(p)}</td>
      <td>${esc(p.name)}</td><td>${esc(p.category_name)}</td><td class="mono">${fmt(p.price)}</td>
      <td>${fileStatusChip(p)}</td>
      <td>${p.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-sm" data-files="${p.id}">📁 فایل‌ها</button>
        <button class="btn btn-sm" data-edit-prod="${p.id}">ویرایش</button>
        <button class="btn btn-sm" data-toggle-prod="${p.id}">${p.is_active ? 'غیرفعال' : 'فعال'}</button>
        <button class="btn btn-danger btn-sm" data-del-prod="${p.id}">حذف</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="7" class="empty-state">محصولی نیست</td></tr>'}</tbody></table></div></div>`;

  $('#add-prod').addEventListener('click', () => openProductAddModal(categories));
  wireThumbFallback(body);
  wireProductRowActions(body, products);
}

/* ---------------------------------------------------------- catalog: bento */
function renderCatalogBento(categories, products) {
  setContent(`
    <div class="bn-hero">
      <div><h2>ویترین الگوها</h2><p>${fmt(products.length)} محصول در ${fmt(categories.length)} دسته‌بندی</p></div>
      <div class="bn-seg">
        <button class="bn-seg-btn ${catalogTab === 'products' ? 'active' : ''}" data-t="products">محصولات</button>
        <button class="bn-seg-btn ${catalogTab === 'categories' ? 'active' : ''}" data-t="categories">دسته‌بندی‌ها</button>
      </div>
    </div>
    <div id="catalog-body"></div>
  `);
  $$('.bn-seg-btn[data-t]', content()).forEach(b => b.addEventListener('click', () => { catalogTab = b.dataset.t; renderCatalog(); }));

  const body = $('#catalog-body');
  if (catalogTab === 'categories') {
    body.innerHTML = `
      <div class="bn-toolbar" style="justify-content:flex-end"><button class="bn-btn bn-btn-ok" id="add-cat">+ دسته‌بندی جدید</button></div>
      <div class="bn-list">
        ${categories.map((c, i) => `
          <div class="bn-row bn-card-anim" style="animation-delay:${Math.min(i * 25, 220)}ms">
            ${bnAvatar(c.name.trim().charAt(0), i)}
            <div class="bn-row-main"><span class="bn-row-title">${esc(c.name)}</span></div>
            <div class="bn-row-trail">
              ${bnPill(c.is_active ? 'فعال' : 'غیرفعال', c.is_active ? 'ok' : 'no')}
              <button class="bn-btn bn-btn-ghost" data-toggle-cat="${c.id}">${c.is_active ? 'غیرفعال کن' : 'فعال کن'}</button>
              <button class="bn-btn bn-btn-no" data-del-cat="${c.id}">حذف</button>
            </div>
          </div>
        `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>دسته‌بندی‌ای نیست</div>`}
      </div>`;
    $('#add-cat').addEventListener('click', () => openModal('دسته‌بندی جدید', `
      <div class="form-grid"><input class="input" id="cat-name" placeholder="نام دسته‌بندی">
      <button class="btn btn-primary" id="cat-save">ثبت</button></div>`, (b, close) => {
      $('#cat-save', b).addEventListener('click', async () => {
        const name = $('#cat-name', b).value.trim(); if (!name) return;
        try { await apiPost('/categories', { name }); toast('اضافه شد.'); close(); renderCatalog(); } catch (e) { handleErr(e); }
      });
    }));
    $$('[data-toggle-cat]', body).forEach(b => b.addEventListener('click', async () => {
      try { await apiPost(`/categories/${b.dataset.toggleCat}/toggle`); renderCatalog(); } catch (e) { handleErr(e); }
    }));
    $$('[data-del-cat]', body).forEach(b => b.addEventListener('click', async () => {
      if (!confirm('حذف شود؟ (محصولات این دسته هم حذف می‌شوند)')) return;
      try { await apiDelete(`/categories/${b.dataset.delCat}`); toast('حذف شد.'); renderCatalog(); } catch (e) { handleErr(e); }
    }));
    return;
  }

  body.innerHTML = `
    <div class="bn-toolbar" style="justify-content:flex-end"><button class="bn-btn bn-btn-ok" id="add-prod">+ محصول جدید</button></div>
    <div class="bn-card-grid">
      ${products.map((p, i) => `
        <div class="bn-card bn-card-anim" style="animation-delay:${Math.min(i * 30, 260)}ms">
          ${productThumbHtml(p)}
          <div class="bw ${BN_ACCENTS[i % BN_ACCENTS.length]}" style="border-radius:16px;padding:10px 14px;margin-top:8px">
            <span class="bw-value mono" style="font-size:18px">${fmt(p.price)} ت</span>
          </div>
          <div class="bn-row-title" style="font-size:14px">${esc(p.name)}</div>
          <div class="bn-row-sub">${esc(p.category_name)}</div>
          <div style="margin:6px 0 4px">${fileStatusChip(p)}</div>
          ${bnPill(p.is_active ? 'فعال' : 'غیرفعال', p.is_active ? 'ok' : 'no')}
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
            <button class="bn-btn bn-btn-ghost" data-files="${p.id}">📁 فایل‌ها</button>
            <button class="bn-btn bn-btn-ghost" data-edit-prod="${p.id}">ویرایش</button>
            <button class="bn-btn bn-btn-ghost" data-toggle-prod="${p.id}">${p.is_active ? 'غیرفعال' : 'فعال'}</button>
            <button class="bn-btn bn-btn-no" data-del-prod="${p.id}">حذف</button>
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>محصولی نیست</div>`}
    </div>`;

  $('#add-prod').addEventListener('click', () => openProductAddModal(categories));
  wireThumbFallback(body);
  wireProductRowActions(body, products);
}

/* -------------------------------------------------- catalog: brutalist -- */
// الگوها به‌شکل «برچسب قیمت آویزون» (تگ مشکی با سوراخ) و دسته‌بندی‌ها به
// شکل ردیف‌های فهرست ضخیم‌قاب.
function renderCatalogBrutalist(categories, products) {
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>ویترین الگوها</h2>
        <p>${fmt(products.length)} محصول در ${fmt(categories.length)} دسته‌بندی</p>
      </div>
      <div class="bru-seg" role="tablist">
        <button class="bru-seg-btn ${catalogTab === 'products' ? 'active' : ''}" data-t="products">محصولات</button>
        <button class="bru-seg-btn ${catalogTab === 'categories' ? 'active' : ''}" data-t="categories">دسته‌بندی‌ها</button>
      </div>
    </div>
    <div id="catalog-body"></div>
  `);
  $$('.bru-seg-btn[data-t]', content()).forEach(b => b.addEventListener('click', () => { catalogTab = b.dataset.t; renderCatalog(); }));

  const body = $('#catalog-body');
  if (catalogTab === 'categories') {
    body.innerHTML = `
      <div class="bru-toolbar" style="justify-content:flex-end">
        <button class="bru-stamp bru-stamp-ok" id="add-cat" style="--r:-3deg">+ دسته‌بندی جدید</button>
      </div>
      <div class="bru-cat-list">
        ${categories.map((c, i) => `
          <div class="bru-cat-row bru-card-anim" style="animation-delay:${Math.min(i * 30, 250)}ms">
            <span class="bru-cat-name">${esc(c.name)}</span>
            <span class="bru-flag ${c.is_active ? 'bru-flag-ok' : 'bru-flag-no'}">${c.is_active ? 'فعال' : 'غیرفعال'}</span>
            <div class="bru-cat-actions">
              <button class="btn btn-sm" data-toggle-cat="${c.id}">${c.is_active ? 'غیرفعال کن' : 'فعال کن'}</button>
              <button class="btn btn-danger btn-sm" data-del-cat="${c.id}">حذف</button>
            </div>
          </div>
        `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>دسته‌بندی‌ای نیست</div>`}
      </div>`;
    $('#add-cat').addEventListener('click', () => openModal('دسته‌بندی جدید', `
      <div class="form-grid"><input class="input" id="cat-name" placeholder="نام دسته‌بندی">
      <button class="btn btn-primary" id="cat-save">ثبت</button></div>`, (b, close) => {
      $('#cat-save', b).addEventListener('click', async () => {
        const name = $('#cat-name', b).value.trim(); if (!name) return;
        try { await apiPost('/categories', { name }); toast('اضافه شد.'); close(); renderCatalog(); } catch (e) { handleErr(e); }
      });
    }));
    $$('[data-toggle-cat]', body).forEach(b => b.addEventListener('click', async () => {
      try { await apiPost(`/categories/${b.dataset.toggleCat}/toggle`); renderCatalog(); } catch (e) { handleErr(e); }
    }));
    $$('[data-del-cat]', body).forEach(b => b.addEventListener('click', async () => {
      if (!confirm('حذف شود؟ (محصولات این دسته هم حذف می‌شوند)')) return;
      try { await apiDelete(`/categories/${b.dataset.delCat}`); toast('حذف شد.'); renderCatalog(); } catch (e) { handleErr(e); }
    }));
    return;
  }

  body.innerHTML = `
    <div class="bru-toolbar" style="justify-content:flex-end">
      <button class="bru-stamp bru-stamp-ok" id="add-prod" style="--r:-3deg">+ محصول جدید</button>
    </div>
    <div class="bru-product-grid">
      ${products.map((p, i) => `
        <div class="bru-product-card bru-card-anim" style="animation-delay:${Math.min(i * 35, 300)}ms">
          <div class="bru-product-tag">
            <span class="bru-product-tag-hole"></span>
            <span class="bru-product-price mono">${fmt(p.price)} ت</span>
          </div>
          <div class="bru-product-body">
            ${productThumbHtml(p)}
            <div class="bru-product-name">${esc(p.name)}</div>
            <div class="bru-product-cat">${esc(p.category_name)}</div>
            <div class="bru-coupon-row"><span>فایل الگو</span><b>${p.has_files ? '✅ آماده' : '⛔️ ندارد'}</b></div>
            <span class="bru-flag ${p.is_active ? 'bru-flag-ok' : 'bru-flag-no'}" style="align-self:flex-start">${p.is_active ? 'فعال' : 'غیرفعال'}</span>
          </div>
          <div class="bru-coupon-actions" style="flex-wrap:wrap">
            <button class="btn btn-sm" data-files="${p.id}">📁 فایل‌ها</button>
            <button class="btn btn-sm" data-edit-prod="${p.id}">ویرایش</button>
            <button class="btn btn-sm" data-toggle-prod="${p.id}">${p.is_active ? 'غیرفعال' : 'فعال'}</button>
            <button class="btn btn-danger btn-sm" data-del-prod="${p.id}">حذف</button>
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>محصولی نیست</div>`}
    </div>`;

  $('#add-prod').addEventListener('click', () => openProductAddModal(categories));
  wireThumbFallback(body);
  wireProductRowActions(body, products);
}

/* ------------------------------------------------------- catalog: glass -- */

/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* ========================================================== discounts === */
async function renderDiscounts() {
  const codes = await apiGet('/discounts');
  if (loadTheme().theme === 'brutalist') return renderDiscountsBrutalist(codes);
  if (loadTheme().theme === 'bento') return renderDiscountsBento(codes);
  setContent(`
    <div class="toolbar"><button class="btn btn-primary btn-sm" id="add-code">+ کد تخفیف جدید</button></div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>کد</th><th>تخفیف</th><th>سقف استفاده</th><th>مصرف‌شده</th><th>وضعیت</th><th>عملیات</th></tr></thead>
      <tbody>${codes.map(c => `<tr>
        <td class="mono">${esc(c.code)}</td>
        <td>${c.percent ? c.percent + '%' : fmt(c.fixed_amount) + ' تومان'}</td>
        <td class="mono">${c.max_uses ? fmt(c.max_uses) : 'نامحدود'}</td>
        <td class="mono">${fmt(c.used_count)}</td>
        <td>${c.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
        <td><button class="btn btn-sm" data-toggle="${c.id}">${c.is_active ? 'غیرفعال' : 'فعال'}</button>
        <button class="btn btn-danger btn-sm" data-del="${c.id}">حذف</button></td>
      </tr>`).join('') || '<tr><td colspan="6" class="empty-state">کدی ثبت نشده</td></tr>'}</tbody>
    </table></div></div>
  `);
  $('#add-code').addEventListener('click', () => openModal('کد تخفیف جدید', `
    <div class="form-grid">
      <input class="input" id="code-value" placeholder="کد (مثلا SUMMER20)">
      <div class="form-row">
        <input class="input" id="code-percent" type="number" placeholder="درصد تخفیف">
        <input class="input" id="code-fixed" type="number" placeholder="یا مبلغ ثابت">
      </div>
      <input class="input" id="code-maxuses" type="number" placeholder="سقف تعداد استفاده (۰=نامحدود)" value="0">
      <button class="btn btn-primary" id="code-save">ثبت</button>
    </div>`, (b, close) => {
    $('#code-save', b).addEventListener('click', async () => {
      const code = $('#code-value', b).value.trim();
      if (!code) return toast('کد را وارد کن.', true);
      try {
        await apiPost('/discounts', {
          code,
          percent: Number($('#code-percent', b).value) || null,
          fixed_amount: Number($('#code-fixed', b).value) || null,
          max_uses: Number($('#code-maxuses', b).value) || 0,
        });
        toast('کد اضافه شد.'); close(); renderDiscounts();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-toggle]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/discounts/${b.dataset.toggle}/toggle`); renderDiscounts(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('حذف شود؟')) return;
    try { await apiDelete(`/discounts/${b.dataset.del}`); toast('حذف شد.'); renderDiscounts(); } catch (e) { handleErr(e); }
  }));
}

/* ------------------------------------------------------ discounts: bento */
function renderDiscountsBento(codes) {
  setContent(`
    <div class="bn-hero">
      <div><h2>کدهای تخفیف</h2><p>${fmt(codes.length)} کد ثبت‌شده</p></div>
      <button class="bn-btn bn-btn-ok" id="add-code">+ کد جدید</button>
    </div>
    <div class="bn-card-grid">
      ${codes.map((c, i) => `
        <div class="bn-card bn-card-anim" style="animation-delay:${Math.min(i * 30, 260)}ms">
          <div class="bw ${BN_ACCENTS[i % BN_ACCENTS.length]}" style="border-radius:16px;padding:12px 14px">
            <span class="bw-value mono" style="font-size:20px">${c.percent ? c.percent + '%' : fmt(c.fixed_amount) + ' ت'}</span>
          </div>
          <div class="bn-row-title mono" style="font-size:14px">${esc(c.code)}</div>
          <div class="bn-row-sub">سقف: ${c.max_uses ? fmt(c.max_uses) : 'نامحدود'} · مصرف: ${fmt(c.used_count)}</div>
          ${bnPill(c.is_active ? 'فعال' : 'غیرفعال', c.is_active ? 'ok' : 'no')}
          <div style="display:flex;gap:8px;margin-top:6px">
            <button class="bn-btn bn-btn-ghost" data-toggle="${c.id}">${c.is_active ? 'غیرفعال' : 'فعال'}</button>
            <button class="bn-btn bn-btn-no" data-del="${c.id}">حذف</button>
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>کدی ثبت نشده</div>`}
    </div>
  `);
  $('#add-code').addEventListener('click', () => openModal('کد تخفیف جدید', `
    <div class="form-grid">
      <input class="input" id="code-value" placeholder="کد (مثلا SUMMER20)">
      <div class="form-row">
        <input class="input" id="code-percent" type="number" placeholder="درصد تخفیف">
        <input class="input" id="code-fixed" type="number" placeholder="یا مبلغ ثابت">
      </div>
      <input class="input" id="code-maxuses" type="number" placeholder="سقف تعداد استفاده (۰=نامحدود)" value="0">
      <button class="btn btn-primary" id="code-save">ثبت</button>
    </div>`, (b, close) => {
    $('#code-save', b).addEventListener('click', async () => {
      const code = $('#code-value', b).value.trim();
      if (!code) return toast('کد را وارد کن.', true);
      try {
        await apiPost('/discounts', {
          code,
          percent: Number($('#code-percent', b).value) || null,
          fixed_amount: Number($('#code-fixed', b).value) || null,
          max_uses: Number($('#code-maxuses', b).value) || 0,
        });
        toast('کد اضافه شد.'); close(); renderDiscounts();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-toggle]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/discounts/${b.dataset.toggle}/toggle`); renderDiscounts(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('حذف شود؟')) return;
    try { await apiDelete(`/discounts/${b.dataset.del}`); toast('حذف شد.'); renderDiscounts(); } catch (e) { handleErr(e); }
  }));
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* ------------------------------------------------ discounts: brutalist -- */
// کدهای تخفیف به‌شکل «بلیط پانچ‌شده» (کوپن) با خط بریدگی دایره‌ای وسط —
// عدد تخفیف با فونت درشت مثل تگ قیمت.
function renderDiscountsBrutalist(codes) {
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>کدهای تخفیف</h2>
        <p>${fmt(codes.length)} کد ثبت‌شده</p>
      </div>
      <button class="bru-stamp bru-stamp-ok" id="add-code" style="--r:-3deg">+ کد جدید</button>
    </div>

    <div class="bru-coupon-grid">
      ${codes.map((c, i) => `
        <div class="bru-coupon bru-card-anim ${c.is_active ? '' : 'bru-coupon-off'}" style="animation-delay:${Math.min(i * 40, 320)}ms">
          <div class="bru-coupon-value">${c.percent ? c.percent + '%' : fmt(c.fixed_amount) + ' ت'}</div>
          <div class="bru-coupon-cut"></div>
          <div class="bru-coupon-body">
            <div class="bru-coupon-code mono">${esc(c.code)}</div>
            <div class="bru-coupon-row"><span>سقف مصرف</span><b class="mono">${c.max_uses ? fmt(c.max_uses) : 'نامحدود'}</b></div>
            <div class="bru-coupon-row"><span>مصرف‌شده</span><b class="mono">${fmt(c.used_count)}</b></div>
            <span class="bru-flag ${c.is_active ? 'bru-flag-ok' : 'bru-flag-no'}" style="align-self:flex-start">${c.is_active ? 'فعال' : 'غیرفعال'}</span>
          </div>
          <div class="bru-coupon-actions">
            <button class="btn btn-sm" data-toggle="${c.id}">${c.is_active ? 'غیرفعال' : 'فعال'}</button>
            <button class="btn btn-danger btn-sm" data-del="${c.id}">حذف</button>
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>کدی ثبت نشده</div>`}
    </div>
  `);
  $('#add-code').addEventListener('click', () => openModal('کد تخفیف جدید', `
    <div class="form-grid">
      <input class="input" id="code-value" placeholder="کد (مثلا SUMMER20)">
      <div class="form-row">
        <input class="input" id="code-percent" type="number" placeholder="درصد تخفیف">
        <input class="input" id="code-fixed" type="number" placeholder="یا مبلغ ثابت">
      </div>
      <input class="input" id="code-maxuses" type="number" placeholder="سقف تعداد استفاده (۰=نامحدود)" value="0">
      <button class="btn btn-primary" id="code-save">ثبت</button>
    </div>`, (b, close) => {
    $('#code-save', b).addEventListener('click', async () => {
      const code = $('#code-value', b).value.trim();
      if (!code) return toast('کد را وارد کن.', true);
      try {
        await apiPost('/discounts', {
          code,
          percent: Number($('#code-percent', b).value) || null,
          fixed_amount: Number($('#code-fixed', b).value) || null,
          max_uses: Number($('#code-maxuses', b).value) || 0,
        });
        toast('کد اضافه شد.'); close(); renderDiscounts();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-toggle]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/discounts/${b.dataset.toggle}/toggle`); renderDiscounts(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('حذف شود؟')) return;
    try { await apiDelete(`/discounts/${b.dataset.del}`); toast('حذف شد.'); renderDiscounts(); } catch (e) { handleErr(e); }
  }));
}

/* ============================================================= support === */
async function renderSupport() {
  stopSupportPoll();
  const convs = await apiGet('/support/conversations');
  if (loadTheme().theme === 'brutalist') return renderSupportBrutalist(convs);
  if (loadTheme().theme === 'bento') return renderSupportBento(convs);
  setContent(`
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>کاربر</th><th>آخرین پیام</th><th>زمان</th><th></th></tr></thead>
      <tbody>${convs.map(c => `<tr>
        <td>${esc(c.user_name || c.user_username || ('#' + c.user_id))}${c.unread ? ` <span class="badge badge-pending">${c.unread}</span>` : ''}${c.locked_for_me ? ` <span class="badge badge-rejected" title="${esc(c.locked_by || '')}">🔒</span>` : ''}</td>
        <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.last_sender === 'admin' ? '↩ ' : ''}${esc(c.last_message || '')}</td>
        <td class="mono">${fmtDate(c.last_at)}</td>
        <td><button class="btn btn-sm" data-open="${c.user_id}">مشاهده</button></td>
      </tr>`).join('') || '<tr><td colspan="4" class="empty-state">گفتگویی نیست</td></tr>'}</tbody>
    </table></div></div>
  `);
  $$('[data-open]', content()).forEach(b => b.addEventListener('click', () => showSupportChat(Number(b.dataset.open))));
  SUPPORT_POLL_TIMER = setInterval(async () => {
    if (CURRENT_TAB !== 'support') return stopSupportPoll();
    try { const fresh = await apiGet('/support/conversations'); renderSupportRows(fresh); } catch (e) { /* silent */ }
  }, 5000);
}

function renderSupportRows(convs) {
  const tbody = $('table tbody', content());
  if (!tbody) return;
  tbody.innerHTML = convs.map(c => `<tr>
    <td>${esc(c.user_name || c.user_username || ('#' + c.user_id))}${c.unread ? ` <span class="badge badge-pending">${c.unread}</span>` : ''}${c.locked_for_me ? ` <span class="badge badge-rejected" title="${esc(c.locked_by || '')}">🔒</span>` : ''}</td>
    <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.last_sender === 'admin' ? '↩ ' : ''}${esc(c.last_message || '')}</td>
    <td class="mono">${fmtDate(c.last_at)}</td>
    <td><button class="btn btn-sm" data-open="${c.user_id}">مشاهده</button></td>
  </tr>`).join('') || '<tr><td colspan="4" class="empty-state">گفتگویی نیست</td></tr>';
  $$('[data-open]', tbody).forEach(b => b.addEventListener('click', () => showSupportChat(Number(b.dataset.open))));
}

/* ---------------------------------------------------------- support: bento */
function renderSupportBento(convs) {
  setContent(`
    <div class="bn-hero"><div><h2>صندوق پشتیبانی</h2><p>${fmt(convs.length)} گفتگو</p></div></div>
    <div class="bn-list" id="support-inbox-list">${supportInboxRowsHtmlBento(convs)}</div>
  `);
  $$('[data-open]', content()).forEach(b => b.addEventListener('click', () => showSupportChat(Number(b.dataset.open))));
  SUPPORT_POLL_TIMER = setInterval(async () => {
    if (CURRENT_TAB !== 'support') return stopSupportPoll();
    try { const fresh = await apiGet('/support/conversations'); renderSupportRowsBento(fresh); } catch (e) { /* silent */ }
  }, 5000);
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */
function supportInboxRowsHtmlBento(convs) {
  return convs.map((c, i) => `
    <div class="bn-row bn-card-anim" style="animation-delay:${Math.min(i * 25, 220)}ms">
      ${bnAvatar((c.user_name || c.user_username || '؟').trim().charAt(0), i)}
      <div class="bn-row-main">
        <span class="bn-row-title">${esc(c.user_name || c.user_username || ('#' + c.user_id))}${c.locked_for_me ? ' 🔒' : ''}</span>
        <span class="bn-row-sub">${c.last_sender === 'admin' ? '↩ ' : ''}${esc(c.last_message || '')}</span>
      </div>
      <div class="bn-row-trail">
        ${c.unread ? bnPill(c.unread, 'no') : ''}
        <span class="bn-row-sub mono">${fmtDate(c.last_at)}</span>
        <button class="bn-btn bn-btn-ghost" data-open="${c.user_id}">مشاهده</button>
      </div>
    </div>
  `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>گفتگویی نیست</div>`;
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */
function renderSupportRowsBento(convs) {
  const list = $('#support-inbox-list', content());
  if (!list) return;
  list.innerHTML = supportInboxRowsHtmlBento(convs);
  $$('[data-open]', list).forEach(b => b.addEventListener('click', () => showSupportChat(Number(b.dataset.open))));
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* -------------------------------------------------- support: brutalist -- */
// اینباکس گفتگوها به‌شکل ردیف‌های ضخیم با آواتار حرفی و نشان تعداد
// نخوانده مثل مهر گرد قرمز روی گوشه.
function renderSupportBrutalist(convs) {
  setContent(`
    <div class="bru-hero">
      <h2>صندوق پشتیبانی</h2>
      <p>${fmt(convs.length)} گفتگو</p>
    </div>
    <div class="bru-inbox-list" id="support-inbox-list">${supportInboxRowsHtml(convs)}</div>
  `);
  $$('[data-open]', content()).forEach(b => b.addEventListener('click', () => showSupportChat(Number(b.dataset.open))));
  SUPPORT_POLL_TIMER = setInterval(async () => {
    if (CURRENT_TAB !== 'support') return stopSupportPoll();
    try { const fresh = await apiGet('/support/conversations'); renderSupportRowsBrutalist(fresh); } catch (e) { /* silent */ }
  }, 5000);
}
function supportInboxRowsHtml(convs) {
  return convs.map((c, i) => `
    <div class="bru-inbox-row bru-card-anim" style="animation-delay:${Math.min(i * 30, 240)}ms">
      <div class="bru-inbox-avatar mono">${esc((c.user_name || c.user_username || '#').trim().charAt(0).toUpperCase())}</div>
      <div class="bru-inbox-main">
        <div class="bru-inbox-name">${esc(c.user_name || c.user_username || ('#' + c.user_id))}${c.locked_for_me ? ` <span title="${esc(c.locked_by || '')}">🔒</span>` : ''}</div>
        <div class="bru-inbox-msg">${c.last_sender === 'admin' ? '↩ ' : ''}${esc(c.last_message || '')}</div>
      </div>
      <div class="bru-inbox-meta">
        <span class="mono">${fmtDate(c.last_at)}</span>
        ${c.unread ? `<span class="bru-inbox-badge">${c.unread}</span>` : ''}
      </div>
      <button class="btn btn-sm" data-open="${c.user_id}">مشاهده</button>
    </div>
  `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>گفتگویی نیست</div>`;
}
function renderSupportRowsBrutalist(convs) {
  const list = $('#support-inbox-list', content());
  if (!list) return;
  list.innerHTML = supportInboxRowsHtml(convs);
  $$('[data-open]', list).forEach(b => b.addEventListener('click', () => showSupportChat(Number(b.dataset.open))));
}

async function showSupportChat(userId) {
  let lastId = 0;
  let d;
  try {
    d = await apiGet(`/support/${userId}/messages`);
  } catch (e) {
    handleErr(e);
    return;
  }
  lastId = d.messages.length ? d.messages[d.messages.length - 1].id : 0;
  const title = d.user.user_name || d.user.user_username || `#${userId}`;
  const locked = d.user.locked_for_me;
  let pollTimer = null;
  const bubble = m => `<div style="align-self:${m.sender === 'admin' ? 'flex-end' : 'flex-start'};max-width:80%;background:${m.sender === 'admin' ? 'var(--signal-dim)' : 'var(--panel-2)'};padding:8px 12px;border-radius:9px;font-size:13px">
        ${esc(m.message)}<div class="card-sub" style="font-size:10px;margin-top:3px">${fmtDate(m.created_at)}</div>
      </div>`;
  const modal = openModal(`چت با ${esc(title)}`, `
    <div id="sc-log" style="display:flex;flex-direction:column;gap:8px;max-height:320px;overflow-y:auto;margin-bottom:12px">
      ${d.messages.map(bubble).join('') || '<span class="card-sub">پیامی نیست</span>'}
    </div>
    ${locked ? `<div class="card-sub" style="color:var(--danger,#ff6b52);margin-bottom:8px">🔒 این گفتگو در حال حاضر توسط ${esc(d.user.locked_by || 'ادمین دیگری')} پاسخ داده می‌شود.</div>` : ''}
    <div style="display:flex;gap:8px">
      <input class="input" id="sc-input" placeholder="پاسخ..." style="flex:1" ${locked ? 'disabled' : ''}>
      <button class="btn btn-primary" id="sc-send" ${locked ? 'disabled' : ''}>ارسال</button>
    </div>
  `, (body, close) => {
    const log = $('#sc-log', body);
    const input = $('#sc-input', body);
    log.scrollTop = log.scrollHeight;
    const send = async () => {
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      try {
        await apiPost(`/support/${userId}/messages`, { message: text });
        log.insertAdjacentHTML('beforeend', bubble({ sender: 'admin', message: text, created_at: new Date().toISOString() }));
        log.scrollTop = log.scrollHeight;
      } catch (e) { handleErr(e); }
    };
    $('#sc-send', body).addEventListener('click', send);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

    pollTimer = setInterval(async () => {
      try {
        const fresh = await apiGet(`/support/${userId}/messages?since_id=${lastId}`);
        fresh.messages.forEach(m => {
          log.insertAdjacentHTML('beforeend', bubble(m));
          lastId = m.id;
        });
        if (fresh.messages.length) log.scrollTop = log.scrollHeight;
      } catch (e) { /* silent */ }
    }, 4000);
  });
  modal.addEventListener('click', e => { if (e.target === modal) { clearInterval(pollTimer); renderSupport(); } });
}

/* ============================================================= tickets === */
let ticketsStatusFilter = '';
const TICKETS_STATUS_LABEL = { '': 'همه', open: 'باز', answered: 'پاسخ‌داده‌شده', closed: 'بسته' };
async function renderTickets() {
  const tickets = await apiGet(`/tickets${ticketsStatusFilter ? '?status=' + ticketsStatusFilter : ''}`);
  if (loadTheme().theme === 'brutalist') return renderTicketsBrutalist(tickets);
  if (loadTheme().theme === 'bento') return renderTicketsBento(tickets);
  setContent(`
    <div class="tabs">
      ${[['', 'همه'], ['open', 'باز'], ['answered', 'پاسخ‌داده‌شده'], ['closed', 'بسته']].map(([v, l]) => `<button class="tab-btn ${v === ticketsStatusFilter ? 'active' : ''}" data-s="${v}">${l}</button>`).join('')}
    </div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>#</th><th>کاربر</th><th>موضوع</th><th>وضعیت</th><th>آخرین بروزرسانی</th><th></th></tr></thead>
      <tbody>${tickets.map(t => `<tr>
        <td class="mono">#${t.id}</td><td>${esc(t.username || t.user_id)}</td><td>${esc(t.subject)}</td>
        <td>${{ open: '<span class="badge badge-pending">باز</span>', answered: '<span class="badge badge-approved">پاسخ‌داده‌شده</span>', closed: '<span class="badge badge-rejected">بسته</span>' }[t.status] || t.status}</td>
        <td class="mono">${fmtDate(t.updated_at)}</td>
        <td><button class="btn btn-sm" data-open="${t.id}">مشاهده</button></td>
      </tr>`).join('') || '<tr><td colspan="6" class="empty-state">تیکتی نیست</td></tr>'}</tbody>
    </table></div></div>
  `);
  $$('.tab-btn', content()).forEach(b => b.addEventListener('click', () => { ticketsStatusFilter = b.dataset.s; renderTickets(); }));
  $$('[data-open]', content()).forEach(b => b.addEventListener('click', () => showTicket(Number(b.dataset.open))));
}

/* ---------------------------------------------------------- tickets: bento */
function renderTicketsBento(tickets) {
  setContent(`
    <div class="bn-hero">
      <div><h2>تیکت‌های پشتیبانی</h2><p>${fmt(tickets.length)} تیکت در فیلتر «${TICKETS_STATUS_LABEL[ticketsStatusFilter]}»</p></div>
      <div class="bn-seg">${[['', 'همه'], ['open', 'باز'], ['answered', 'پاسخ‌داده‌شده'], ['closed', 'بسته']].map(([v, l]) => `<button class="bn-seg-btn ${v === ticketsStatusFilter ? 'active' : ''}" data-s="${v}">${l}</button>`).join('')}</div>
    </div>
    <div class="bn-list">
      ${tickets.map((t, i) => `
        <div class="bn-row bn-card-anim" style="animation-delay:${Math.min(i * 25, 220)}ms">
          ${bnAvatar((t.username || '؟').trim().charAt(0), i)}
          <div class="bn-row-main">
            <span class="bn-row-title">${esc(t.subject)}</span>
            <span class="bn-row-sub">${esc(t.username || t.user_id)} · ${fmtDate(t.updated_at)}</span>
          </div>
          <div class="bn-row-trail">
            ${bnPill(TICKETS_STATUS_LABEL[t.status] || t.status, t.status === 'open' ? 'pending' : t.status === 'answered' ? 'ok' : 'no')}
            <button class="bn-btn bn-btn-ghost" data-open="${t.id}">مشاهده</button>
          </div>
        </div>
      `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>تیکتی نیست</div>`}
    </div>
  `);
  $$('.bn-seg-btn[data-s]', content()).forEach(b => b.addEventListener('click', () => { ticketsStatusFilter = b.dataset.s; renderTickets(); }));
  $$('[data-open]', content()).forEach(b => b.addEventListener('click', () => showTicket(Number(b.dataset.open))));
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* -------------------------------------------------- tickets: brutalist -- */
// هر تیکت به‌شکل کارت «پرونده‌ی باز» با برچسب وضعیت مثل استیکر گوشه.
function renderTicketsBrutalist(tickets) {
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>تیکت‌های پشتیبانی</h2>
        <p>${fmt(tickets.length)} تیکت در فیلتر «${TICKETS_STATUS_LABEL[ticketsStatusFilter]}»</p>
      </div>
      <div class="bru-seg" role="tablist">
        ${[['', 'همه'], ['open', 'باز'], ['answered', 'پاسخ‌داده‌شده'], ['closed', 'بسته']].map(([v, l]) => `<button class="bru-seg-btn ${v === ticketsStatusFilter ? 'active' : ''}" data-s="${v}">${l}</button>`).join('')}
      </div>
    </div>
    <div class="bru-ticket-grid">
      ${tickets.map((t, i) => `
        <div class="bru-ticket bru-card-anim" style="animation-delay:${Math.min(i * 40, 320)}ms">
          <div class="bru-ticket-stub">
            <span class="bru-ticket-num mono">#${t.id}</span>
            <span class="bru-flag ${t.status === 'open' ? 'bru-flag-pending' : t.status === 'answered' ? 'bru-flag-ok' : 'bru-flag-no'}">${TICKETS_STATUS_LABEL[t.status] || t.status}</span>
          </div>
          <div class="bru-ticket-body">
            <div class="bru-ticket-row"><span>کاربر</span><b>${esc(t.username || t.user_id)}</b></div>
            <div class="bru-ticket-row" style="flex-direction:column;align-items:flex-start;gap:2px"><span>موضوع</span><b style="white-space:normal">${esc(t.subject)}</b></div>
            <div class="bru-ticket-row"><span>بروزرسانی</span><b class="mono">${fmtDate(t.updated_at)}</b></div>
          </div>
          <div class="bru-ticket-actions">
            <button class="btn btn-sm" data-open="${t.id}">مشاهده</button>
          </div>
        </div>
      `).join('') || `<div class="empty-state" style="grid-column:1/-1"><div class="icon">${svg('empty')}</div>تیکتی نیست</div>`}
    </div>
  `);
  $$('.bru-seg-btn[data-s]', content()).forEach(b => b.addEventListener('click', () => { ticketsStatusFilter = b.dataset.s; renderTickets(); }));
  $$('[data-open]', content()).forEach(b => b.addEventListener('click', () => showTicket(Number(b.dataset.open))));
}

async function showTicket(ticketId) {
  const d = await apiGet(`/tickets/${ticketId}/messages`);
  const canAct = hasPerm('tickets');
  openModal(`تیکت: ${esc(d.ticket.subject)}`, `
    <div style="display:flex;flex-direction:column;gap:8px;max-height:280px;overflow-y:auto;margin-bottom:12px">
      ${d.messages.map(m => `<div style="background:${m.sender === 'admin' ? 'var(--signal-dim)' : 'var(--panel-2)'};padding:8px 12px;border-radius:9px;font-size:13px">
        <strong style="font-size:11px;color:var(--text-muted)">${m.sender === 'admin' ? 'ادمین' : 'کاربر'}</strong><br>${esc(m.message)}
      </div>`).join('') || '<span class="card-sub">پیامی نیست</span>'}
    </div>
    ${canAct && d.ticket.status !== 'closed' ? `
      <textarea class="input" id="ticket-reply" rows="2" placeholder="پاسخ..."></textarea>
      <div class="modal-actions">
        <button class="btn btn-primary" id="ticket-send">ارسال پاسخ</button>
        <button class="btn btn-danger" id="ticket-close-btn">بستن تیکت</button>
      </div>` : ''}
  `, (body, close) => {
    const send = $('#ticket-send', body);
    if (send) send.addEventListener('click', async () => {
      const message = $('#ticket-reply', body).value.trim();
      if (!message) return;
      try { await apiPost(`/tickets/${ticketId}/reply`, { message }); toast('پاسخ ارسال شد.'); close(); renderTickets(); } catch (e) { handleErr(e); }
    });
    const closeBtn = $('#ticket-close-btn', body);
    if (closeBtn) closeBtn.addEventListener('click', async () => {
      try { await apiPost(`/tickets/${ticketId}/close`); toast('تیکت بسته شد.'); close(); renderTickets(); } catch (e) { handleErr(e); }
    });
  });
}

/* =========================================================== broadcast === */
/* ------------------------------------------------------ broadcast: bento */
function renderBroadcastBento() {
  setContent(`
    <div class="bn-hero"><div><h2>پیام همگانی</h2><p>ارسال متنی به همه‌ی کاربران غیرمسدود ربات</p></div></div>
    <div class="bn-card" style="max-width:680px">
      <textarea class="bn-search" id="bc-text" rows="7" maxlength="4000" style="width:100%;border-radius:18px;resize:vertical" placeholder="متن پیام را بنویس..."></textarea>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px">
        <span class="mono" id="bc-count" style="font-size:12px;color:var(--text-muted)">۰ / ۴۰۰۰</span>
        <button class="bn-btn bn-btn-ok" id="bc-send" style="padding:10px 22px">ارسال به همه</button>
      </div>
      <div id="bc-result" style="margin-top:16px"></div>
    </div>
  `);
  const ta = $('#bc-text', content());
  ta.addEventListener('input', () => { $('#bc-count', content()).textContent = `${ta.value.length} / 4000`; });

  $('#bc-send', content()).addEventListener('click', () => {
    const text = ta.value.trim();
    if (!text) return toast('متن پیام خالی است.', true);
    openModal('تایید ارسال همگانی', `
      <p style="font-size:13px;line-height:1.9">این پیام برای <strong>همه‌ی کاربران</strong> ربات ارسال می‌شود و قابل بازگشت نیست. مطمئنی؟</p>
      <div style="border-radius:14px;background:var(--surface-2);padding:10px 12px;font-size:13px;white-space:pre-wrap;max-height:160px;overflow-y:auto">${esc(text)}</div>
      <div class="modal-actions">
        <button class="btn btn-primary" id="bc-confirm">بله، ارسال کن</button>
      </div>
    `, (body, close) => {
      $('#bc-confirm', body).addEventListener('click', async () => {
        const btn = $('#bc-confirm', body);
        btn.disabled = true; btn.textContent = 'در حال ارسال...';
        try {
          const res = await apiPost('/broadcast', { message: text });
          close();
          $('#bc-result', content()).innerHTML = `
            <div class="bento-grid" style="grid-auto-rows:minmax(84px,auto)">
              <div class="bw w-blue"><span class="bw-label">کل</span><span class="bw-value mono">${fmt(res.total)}</span></div>
              <div class="bw w-green"><span class="bw-label">موفق</span><span class="bw-value mono">${fmt(res.success)}</span></div>
              <div class="bw w-pink"><span class="bw-label">ناموفق</span><span class="bw-value mono">${fmt(res.failed)}</span></div>
            </div>`;
          ta.value = ''; $('#bc-count', content()).textContent = '۰ / ۴۰۰۰';
          toast('پیام همگانی ارسال شد.');
        } catch (e) { close(); handleErr(e); }
      });
    });
  });
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

async function renderBroadcast() {
  if (loadTheme().theme === 'brutalist') return renderBroadcastBrutalist();
  if (loadTheme().theme === 'bento') return renderBroadcastBento();
  setContent(`
    <div class="card" style="max-width:640px">
      <h3 style="margin:0 0 4px">ارسال پیام همگانی</h3>
      <p class="card-sub" style="margin:0 0 14px">این پیام برای همه‌ی کاربران ربات (غیرمسدود) به‌صورت متنی ارسال می‌شود.</p>
      <textarea class="input" id="bc-text" rows="6" maxlength="4000" placeholder="متن پیام را بنویس..."></textarea>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
        <span class="card-sub" id="bc-count">۰ / ۴۰۰۰</span>
        <button class="btn btn-primary" id="bc-send">ارسال به همه</button>
      </div>
      <div id="bc-result" style="margin-top:14px"></div>
    </div>
  `);
  const ta = $('#bc-text', content());
  ta.addEventListener('input', () => { $('#bc-count', content()).textContent = `${ta.value.length} / 4000`; });

  $('#bc-send', content()).addEventListener('click', () => {
    const text = ta.value.trim();
    if (!text) return toast('متن پیام خالی است.', true);
    openModal('تایید ارسال همگانی', `
      <p style="font-size:13px;line-height:1.9">این پیام برای <strong>همه‌ی کاربران</strong> ربات ارسال می‌شود و قابل بازگشت نیست. مطمئنی؟</p>
      <div style="background:var(--panel-2);padding:10px 12px;border-radius:9px;font-size:13px;white-space:pre-wrap;max-height:160px;overflow-y:auto">${esc(text)}</div>
      <div class="modal-actions">
        <button class="btn btn-primary" id="bc-confirm">بله، ارسال کن</button>
      </div>
    `, (body, close) => {
      $('#bc-confirm', body).addEventListener('click', async () => {
        const btn = $('#bc-confirm', body);
        btn.disabled = true; btn.textContent = 'در حال ارسال...';
        try {
          const res = await apiPost('/broadcast', { message: text });
          close();
          $('#bc-result', content()).innerHTML = `
            <div class="card" style="background:var(--panel-2)">
              📢 ارسال تمام شد — کل: <strong>${res.total}</strong> ·
              موفق: <strong style="color:var(--ok, #3ddc84)">${res.success}</strong> ·
              ناموفق: <strong style="color:var(--danger, #ff6b52)">${res.failed}</strong>
            </div>`;
          ta.value = ''; $('#bc-count', content()).textContent = '۰ / ۴۰۰۰';
          toast('پیام همگانی ارسال شد.');
        } catch (e) { close(); handleErr(e); }
      });
    });
  });
}

/* ------------------------------------------------ broadcast: brutalist -- */
// چیدمان «کنسول بلندگو»: تکست‌ناحیه‌ی درشت با شمارنده‌ی مونو، دکمه‌ی
// مُهر بزرگ، و نتیجه‌ی ارسال به‌شکل سه بلاک آماری مثل داشبورد.
function renderBroadcastBrutalist() {
  setContent(`
    <div class="bru-hero">
      <h2>کنسول پیام همگانی</h2>
      <p>ارسال متنی به همه‌ی کاربران غیرمسدود ربات</p>
    </div>
    <div class="bru-panel" style="max-width:680px">
      <div class="bru-panel-head">متن پیام</div>
      <textarea class="bru-search-input" id="bc-text" rows="7" maxlength="4000" style="width:100%;resize:vertical" placeholder="متن پیام را بنویس..."></textarea>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px">
        <span class="mono" id="bc-count" style="font-weight:800;font-size:12px">۰ / ۴۰۰۰</span>
        <button class="bru-stamp bru-stamp-ok" id="bc-send" style="--r:-3deg">ارسال به همه</button>
      </div>
      <div id="bc-result" style="margin-top:16px"></div>
    </div>
  `);
  const ta = $('#bc-text', content());
  ta.addEventListener('input', () => { $('#bc-count', content()).textContent = `${ta.value.length} / 4000`; });

  $('#bc-send', content()).addEventListener('click', () => {
    const text = ta.value.trim();
    if (!text) return toast('متن پیام خالی است.', true);
    openModal('تایید ارسال همگانی', `
      <p style="font-size:13px;line-height:1.9">این پیام برای <strong>همه‌ی کاربران</strong> ربات ارسال می‌شود و قابل بازگشت نیست. مطمئنی؟</p>
      <div style="border:2.5px solid #000;background:var(--surface-2);padding:10px 12px;font-size:13px;white-space:pre-wrap;max-height:160px;overflow-y:auto">${esc(text)}</div>
      <div class="modal-actions">
        <button class="btn btn-primary" id="bc-confirm">بله، ارسال کن</button>
      </div>
    `, (body, close) => {
      $('#bc-confirm', body).addEventListener('click', async () => {
        const btn = $('#bc-confirm', body);
        btn.disabled = true; btn.textContent = 'در حال ارسال...';
        try {
          const res = await apiPost('/broadcast', { message: text });
          close();
          $('#bc-result', content()).innerHTML = `
            <div class="bru-grid-4" style="grid-template-columns:repeat(3,1fr)">
              <div class="bru-block bru-white"><span class="bru-block-label">کل</span><span class="bru-block-val mono">${fmt(res.total)}</span></div>
              <div class="bru-block bru-yellow"><span class="bru-block-label">موفق</span><span class="bru-block-val mono">${fmt(res.success)}</span></div>
              <div class="bru-block bru-black"><span class="bru-block-label">ناموفق</span><span class="bru-block-val mono">${fmt(res.failed)}</span></div>
            </div>`;
          ta.value = ''; $('#bc-count', content()).textContent = '۰ / ۴۰۰۰';
          toast('پیام همگانی ارسال شد.');
        } catch (e) { close(); handleErr(e); }
      });
    });
  });
}

/* ================================================= sales settings === */
// تنظیمات فروش: رفرال (سه مدل مستقل)، گردونه‌شانس، عضویت اجباری و مخزن
// الگوهای نمونه‌ی رایگان (که دکمه‌ی «الگوی نمونه رایگان» ربات می‌فرستد).

function _swSpan(key, on) {
  return `<span class="switch" data-swkey="${key}" data-on="${on ? '1' : '0'}"><i></i></span>`;
}
function _bindSwitches(root) {
  $$('.switch[data-swkey]', root).forEach(sw => {
    sw.addEventListener('click', () => { sw.dataset.on = sw.dataset.on === '1' ? '0' : '1'; sw.classList.toggle('on'); });
    if (sw.dataset.on === '1') sw.classList.add('on');
  });
}
function _swOn(root, key) { return $(`.switch[data-swkey="${key}"]`, root)?.dataset.on === '1'; }
function _val(root, key) { return $(`[data-fkey="${key}"]`, root)?.value; }
function _num(root, key) { return Number(_val(root, key)) || 0; }

async function renderSalesSettings() {
  const [referral, wheel, forceJoin, products, sampleFiles] = await Promise.all([
    apiGet('/settings/referral'), apiGet('/settings/wheel'), apiGet('/settings/force-join'),
    apiGet('/products'), apiGet('/sample-files'),
  ]);

  const productOptions = (products || []).map(p =>
    `<option value="${p.id}" ${referral.free_config_product_id === p.id ? 'selected' : ''}>${esc(p.name)}${p.is_active ? '' : ' (غیرفعال)'}</option>`
  ).join('');

  const sampleRows = (sampleFiles || []).map(f => `
    <div class="file-row">
      <span class="file-row-icon">🧪</span>
      <span class="file-row-name">الگوی نمونه #${f.id}</span>
      <span class="file-row-size mono">${fmtDate(f.created_at)}</span>
      <span class="file-row-actions">
        <a class="btn btn-ghost btn-sm" href="/api/files/${encodeURIComponent(f.file_id)}" target="_blank" rel="noopener">مشاهده</a>
        <button class="btn btn-danger btn-sm" data-del-sample="${esc(f.file_id)}" title="حذف">🗑</button>
      </span>
    </div>`).join('') || '<span class="card-sub">هنوز الگوی نمونه‌ای آپلود نشده است.</span>';

  setContent(`
    <div class="card">
      <h3>🔗 رفرال — سه مدل مستقل زیرمجموعه‌گیری</h3>

      <div class="card-sub" style="margin:8px 0 4px"><b>① پورسانت درصدی از خرید</b></div>
      <label class="field field-row"><span>فعال</span>${_swSpan('ref_enabled', referral.enabled)}</label>
      <label class="field"><span>درصد پورسانت</span><input class="input" data-fkey="ref_percent" type="number" value="${referral.percent}"></label>
      <label class="field"><span>سقف تعداد نفرات پورسانت‌دار (۰ = نامحدود)</span><input class="input" data-fkey="ref_commission_max" type="number" value="${referral.commission_max_count}"></label>

      <div class="card-sub" style="margin:16px 0 4px"><b>② الگوی رایگان با تعداد دعوت مشخص</b></div>
      <label class="field field-row"><span>فعال</span>${_swSpan('ref_fc_enabled', referral.free_config_enabled)}</label>
      <label class="field"><span>تعداد دعوت لازم</span><input class="input" data-fkey="ref_fc_threshold" type="number" value="${referral.free_config_threshold}"></label>
      <label class="field"><span>محصول جایزه</span>
        <select class="input" data-fkey="ref_fc_product">
          <option value="">— انتخاب کنید —</option>
          ${productOptions}
        </select>
      </label>
      <div class="card-sub">می‌توانید محصولی غیرفعال (که در ویترین فروشگاه نمایش داده نمی‌شود) مخصوص همین جایزه بسازید.</div>

      <div class="card-sub" style="margin:16px 0 4px"><b>③ شارژ ثابت کیف پول به‌ازای هر دعوت</b></div>
      <label class="field field-row"><span>فعال</span>${_swSpan('ref_ib_enabled', referral.invite_bonus_enabled)}</label>
      <label class="field"><span>مبلغ شارژ (تومان)</span><input class="input" data-fkey="ref_ib_amount" type="number" value="${referral.invite_bonus_amount}"></label>
      <label class="field"><span>سقف تعداد دعوت‌های مشمول (۰ = نامحدود)</span><input class="input" data-fkey="ref_ib_max" type="number" value="${referral.invite_bonus_max_count}"></label>

      <button class="btn btn-primary btn-sm" id="save-referral" style="margin-top:12px">ذخیره همه‌ی تنظیمات رفرال</button>
    </div>

    <div class="card">
      <h3>🎰 گردونه‌ی شانس</h3>
      <label class="field field-row"><span>فعال</span>${_swSpan('wheel_enabled', wheel.enabled)}</label>
      <label class="field"><span>درصد برد</span><input class="input" data-fkey="wheel_win_percent" type="number" value="${wheel.win_percent}"></label>
      <label class="field"><span>جوایز (٪ تخفیف، با کاما جدا کن)</span><input class="input" data-fkey="wheel_prizes" type="text" value="${(wheel.prizes || []).join(', ')}"></label>
      <label class="field"><span>اعتبار کد (ساعت)</span><input class="input" data-fkey="wheel_expiry_hours" type="number" value="${wheel.expiry_hours ?? wheel.code_expiry_hours ?? 24}"></label>
      <label class="field"><span>فاصله‌ی بین دو چرخش (ساعت)</span><input class="input" data-fkey="wheel_cooldown_hours" type="number" value="${wheel.cooldown_hours}"></label>
      <button class="btn btn-primary btn-sm" id="save-wheel">ذخیره</button>
    </div>

    <div class="card">
      <h3>🧪 الگوهای نمونه رایگان</h3>
      <div class="card-sub" style="margin-bottom:8px">این فایل‌ها با دکمه‌ی «الگوی نمونه رایگان» ربات برای کاربران ارسال می‌شوند (PDF و سایر اسناد، حداکثر ۵۰ مگابایت).</div>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
        <input type="file" id="sample-file" hidden multiple accept=".pdf,image/*,.zip,.rar,.doc,.docx,.ai,.svg,.pptx">
        <button type="button" class="btn btn-primary btn-sm" id="sample-upload">➕ آپلود الگوی نمونه</button>
        <span class="card-sub" id="sample-progress"></span>
      </div>
      <div id="sample-list">${sampleRows}</div>
    </div>

    <div class="card">
      <h3>📢 عضویت اجباری در کانال</h3>
      <label class="field field-row"><span>فعال</span>${_swSpan('fj_enabled', forceJoin.enabled)}</label>
      <label class="field"><span>آیدی کانال (مثل ‎@my_channel)</span><input class="input" data-fkey="fj_channel" type="text" value="${esc(forceJoin.channel || '')}" style="direction:ltr;text-align:left"></label>
      <button class="btn btn-primary btn-sm" id="save-forcejoin">ذخیره</button>
    </div>
  `);

  const root = content();
  _bindSwitches(root);

  $('#save-referral').addEventListener('click', async () => {
    try {
      await apiPost('/settings/referral', {
        enabled: _swOn(root, 'ref_enabled'),
        percent: _num(root, 'ref_percent'),
        commission_max_count: _num(root, 'ref_commission_max'),
        free_config_enabled: _swOn(root, 'ref_fc_enabled'),
        free_config_threshold: _num(root, 'ref_fc_threshold'),
        free_config_product_id: _val(root, 'ref_fc_product') ? Number(_val(root, 'ref_fc_product')) : null,
        invite_bonus_enabled: _swOn(root, 'ref_ib_enabled'),
        invite_bonus_amount: _num(root, 'ref_ib_amount'),
        invite_bonus_max_count: _num(root, 'ref_ib_max'),
      });
      toast('تنظیمات رفرال ذخیره شد.');
    } catch (e) { handleErr(e); }
  });

  $('#save-wheel').addEventListener('click', async () => {
    const prizes = (_val(root, 'wheel_prizes') || '').split(',').map(s => Number(s.trim())).filter(n => n > 0);
    try {
      await apiPost('/settings/wheel', {
        enabled: _swOn(root, 'wheel_enabled'), win_percent: _num(root, 'wheel_win_percent'),
        prizes, expiry_hours: _num(root, 'wheel_expiry_hours'), cooldown_hours: _num(root, 'wheel_cooldown_hours'),
      });
      toast('تنظیمات گردونه ذخیره شد.');
    } catch (e) { handleErr(e); }
  });

  $('#save-forcejoin').addEventListener('click', async () => {
    try {
      await apiPost('/settings/force-join', { enabled: _swOn(root, 'fj_enabled'), channel: _val(root, 'fj_channel') });
      toast('تنظیمات عضویت اجباری ذخیره شد.');
    } catch (e) { handleErr(e); }
  });

  const sampleInput = $('#sample-file', root);
  $('#sample-upload', root).addEventListener('click', () => sampleInput.click());
  sampleInput.addEventListener('change', async () => {
    const picked = Array.from(sampleInput.files || []);
    if (!picked.length) return;
    const progress = $('#sample-progress', root);
    const btn = $('#sample-upload', root);
    btn.disabled = true;
    let added = 0, duplicates = 0, failed = 0;
    for (let i = 0; i < picked.length; i++) {
      progress.textContent = `⏳ در حال آپلود ${i + 1} از ${picked.length}...`;
      const fd = new FormData();
      fd.append('file', picked[i]);
      try {
        const r = await apiUpload('/sample-files', fd);
        added += r.added || 0; duplicates += r.duplicates || 0;
      } catch (e) { handleErr(e); failed++; }
    }
    btn.disabled = false;
    progress.textContent = '';
    toast(`${added} فایل اضافه شد${duplicates ? ` (${duplicates} تکراری نادیده گرفته شد)` : ''}${failed ? ` — ${failed} ناموفق` : ''}.`);
    renderSalesSettings();
  });
  $$('[data-del-sample]', root).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این الگوی نمونه حذف شود؟')) return;
    try {
      await apiDelete(`/sample-files/${encodeURIComponent(b.dataset.delSample)}`);
      toast('حذف شد.');
      renderSalesSettings();
    } catch (e) { handleErr(e); }
  }));
}
/* ============================================================ settings === */
const SETTINGS_TABS = [
  { key: 'content', label: '📝 محتوا و متن‌ها' },
  { key: 'payment', label: '💳 پرداخت و مالی' },
];
// نکته: تنظیمات رفرال، گردونه‌شانس، عضویت اجباری و الگوهای نمونه‌ی رایگان
// همگی به‌طور کامل‌تر در صفحه‌ی «تنظیمات فروش» هستند؛ اینجا تکرار نمی‌شوند تا
// تنظیمات فروش فقط یک مرجع داشته باشد.

const SETTINGS_GROUPS = [
  // ---------------------------------------------------------- محتوا و متن‌ها
  { tab: 'content', title: 'متن‌های پایه', fields: [
    { key: 'store_name', label: 'نام فروشگاه', type: 'text' },
    { key: 'welcome_text', label: 'متن خوش‌آمدگویی (شروع ربات)', type: 'textarea' },
    { key: 'contact_text', label: 'متن ابتدای بخش ارتباط با پشتیبانی', type: 'textarea' },
    { key: 'after_buy_text', label: 'متن راهنمای پرداخت (بعد از انتخاب الگو)', type: 'textarea' },
  ]},
  { tab: 'content', title: 'دکمه‌های منوی ربات', fields: [
    { key: 'btn_buy', label: 'متن دکمه خرید الگو', type: 'text' },
    { key: 'btn_buy_style', label: 'رنگ دکمه خرید الگو', type: 'color' },
    { key: 'btn_test', label: 'متن دکمه الگوی نمونه رایگان', type: 'text' },
    { key: 'btn_test_style', label: 'رنگ دکمه الگوی نمونه رایگان', type: 'color' },
    { key: 'btn_my_orders', label: 'متن دکمه سفارش‌های من', type: 'text' },
    { key: 'btn_my_orders_style', label: 'رنگ دکمه سفارش‌های من', type: 'color' },
    { key: 'btn_wallet', label: 'متن دکمه کیف پول', type: 'text' },
    { key: 'btn_wallet_style', label: 'رنگ دکمه کیف پول', type: 'color' },
    { key: 'btn_referral', label: 'متن دکمه زیرمجموعه‌گیری', type: 'text' },
    { key: 'btn_referral_style', label: 'رنگ دکمه زیرمجموعه‌گیری', type: 'color' },
    { key: 'btn_wheel', label: 'متن دکمه گردونه شانس', type: 'text' },
    { key: 'btn_wheel_style', label: 'رنگ دکمه گردونه شانس', type: 'color' },
    { key: 'btn_contact', label: 'متن دکمه ارتباط با پشتیبانی', type: 'text' },
    { key: 'btn_contact_style', label: 'رنگ دکمه ارتباط با پشتیبانی', type: 'color' },
    { key: 'btn_admin_panel', label: 'متن دکمه پنل مدیریت (فقط برای ادمین‌ها)', type: 'text' },
    { key: 'btn_admin_panel_style', label: 'رنگ دکمه پنل مدیریت', type: 'color' },
  ]},
  { tab: 'content', title: '🎨 رنگ دکمه‌های مسیر خرید', fields: [
    { key: 'btn_cat_select_style', label: 'رنگ دکمه‌های انتخاب دسته‌بندی', type: 'color' },
    { key: 'btn_product_select_style', label: 'رنگ دکمه‌های انتخاب الگو', type: 'color' },
    { key: 'btn_buy_continue_style', label: 'رنگ دکمه «ادامه و ارسال رسید»', type: 'color' },
    { key: 'btn_enter_code_style', label: 'رنگ دکمه «وارد کردن کد تخفیف»', type: 'color' },
    { key: 'btn_buy_back_style', label: 'رنگ دکمه‌های بازگشت در مسیر خرید', type: 'color' },
  ]},


  // ------------------------------------------------------------ پرداخت و مالی
  { tab: 'payment', title: 'کارت بانکی', fields: [
    { key: 'card_number', label: 'شماره کارت', type: 'text' },
    { key: 'card_holder', label: 'نام صاحب کارت', type: 'text' },
  ]},
];

function settingsFieldHtml(f, settings) {
  const val = settings[f.key] ?? '';
  if (f.type === 'bool') {
    const on = val === '1' || val === 1 || val === true;
    return `
      <label class="field field-row">
        <span>${esc(f.label)}</span>
        <span class="switch" data-key="${f.key}" data-type="bool" data-on="${on ? '1' : '0'}"><i></i></span>
      </label>`;
  }
  if (f.type === 'textarea') {
    return `<label class="field"><span>${esc(f.label)}</span>
      <textarea class="input" rows="3" data-key="${f.key}" data-type="text">${esc(val)}</textarea></label>`;
  }
  if (f.type === 'select') {
    return `<label class="field"><span>${esc(f.label)}</span>
      <select class="input" data-key="${f.key}" data-type="text">
        ${f.options.map(([v, l]) => `<option value="${v}" ${val === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}
      </select></label>`;
  }
  if (f.type === 'color') {
    const cur = ['primary', 'success', 'danger'].includes(val) ? val : '';
    const swatches = [['', 'swatch-default', 'پیش‌فرض (خاکستری)'], ['primary', 'swatch-primary', 'آبی'], ['success', 'swatch-success', 'سبز'], ['danger', 'swatch-danger', 'قرمز']];
    return `<label class="field"><span>${esc(f.label)}</span>
      <div class="color-pick" data-key="${f.key}" data-color="${cur}">
        ${swatches.map(([v, cls, title]) => `<button type="button" class="color-swatch ${cls} ${cur === v ? 'active' : ''}" data-value="${v}" title="${esc(title)}"></button>`).join('')}
      </div></label>`;
  }
  if (f.type === 'image') {
    return `
      <label class="field">
        <span>${esc(f.label)}</span>
        <div class="image-field" data-key="${f.key}">
          ${val ? `<img src="${val}" class="image-field-preview">` : '<span class="card-sub">تصویری تنظیم نشده</span>'}
          <div class="image-field-actions">
            <input type="file" accept="image/*" class="image-field-input" hidden>
            <button type="button" class="btn btn-sm image-field-pick">انتخاب تصویر</button>
            ${val ? '<button type="button" class="btn btn-sm btn-danger image-field-clear">حذف</button>' : ''}
          </div>
          <input type="hidden" data-key="${f.key}" data-type="text" value="${esc(val)}">
        </div>
      </label>`;
  }
  return `<label class="field"><span>${esc(f.label)}</span>
    <input class="input" type="${f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text'}" data-key="${f.key}" data-type="text" value="${esc(val)}"></label>`;
}

let settingsActiveTab = 'content';

function renderSettingsGroups(settings) {
  const seen = new Set();
  return `<div class="settings-accordion" id="settings-accordion">
    ${SETTINGS_GROUPS.map(g => {
      const isFirstInTab = !seen.has(g.tab);
      seen.add(g.tab);
      return `
      <div class="settings-group ${isFirstInTab ? 'open' : ''}" data-settings-tab="${g.tab}" style="${g.tab === settingsActiveTab ? '' : 'display:none'}">
        <button type="button" class="settings-group-head">
          <span>${esc(g.title)}</span>
          <span class="settings-group-arrow">˅</span>
        </button>
        <div class="settings-group-body"><div class="form-grid">
          ${g.fields.map(f => settingsFieldHtml(f, settings)).join('')}
        </div></div>
      </div>`;
    }).join('')}
  </div>`;
}

function settingsTabsHtml() {
  return `<div class="tabs" id="settings-tabs-nav">
    ${SETTINGS_TABS.map(t => `<button type="button" class="tab-btn ${t.key === settingsActiveTab ? 'active' : ''}" data-tab="${t.key}">${t.label}</button>`).join('')}
  </div>`;
}

function switchSettingsTab(tab, root) {
  settingsActiveTab = tab;
  $$('#settings-tabs-nav .tab-btn, #settings-tabs-nav .bru-seg-btn, #settings-tabs-nav .bn-seg-btn', root).forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  $$('[data-settings-tab]', root).forEach(el => { el.style.display = el.dataset.settingsTab === tab ? '' : 'none'; });
}

function bindSettingsGroupEvents(root) {
  $$('.settings-group-head', root).forEach(btn => btn.addEventListener('click', () => {
    btn.parentElement.classList.toggle('open');
  }));
  $$('.switch', root).forEach(sw => sw.addEventListener('click', () => {
    const on = sw.dataset.on !== '1';
    sw.dataset.on = on ? '1' : '0';
  }));
  $$('.color-pick', root).forEach(box => {
    $$('.color-swatch', box).forEach(btn => btn.addEventListener('click', () => {
      box.dataset.color = btn.dataset.value;
      $$('.color-swatch', box).forEach(b => b.classList.toggle('active', b === btn));
    }));
  });
  $$('.image-field', root).forEach(box => {
    const fileInput = $('.image-field-input', box);
    const hidden = $('input[type=hidden]', box);
    $('.image-field-pick', box).addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      const file = fileInput.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => { hidden.value = reader.result; toast('تصویر انتخاب شد؛ برای ثبت روی «ذخیره تغییرات» بزن.'); };
      reader.readAsDataURL(file);
    });
    const clearBtn = $('.image-field-clear', box);
    if (clearBtn) clearBtn.addEventListener('click', () => { hidden.value = ''; box.querySelector('.image-field-preview')?.remove(); toast('تصویر حذف شد؛ برای ثبت روی «ذخیره تغییرات» بزن.'); });
  });
}

async function collectAndSaveSettings(root, btn) {
  const items = [];
  $$('[data-key][data-type]:not(.switch)', root).forEach(el => items.push({ key: el.dataset.key, value: el.value }));
  $$('.switch[data-key]', root).forEach(sw => items.push({ key: sw.dataset.key, value: sw.dataset.on === '1' ? '1' : '0' }));
  $$('.color-pick[data-key]', root).forEach(box => items.push({ key: box.dataset.key, value: box.dataset.color || '' }));
  btn.disabled = true;
  const prevTxt = btn.textContent; btn.textContent = 'در حال ذخیره...';
  try {
    for (const item of items) {
      await apiPost('/settings', item);
    }
    toast('تنظیمات ذخیره شد.');
  } catch (e) {
    handleErr(e);
  } finally {
    btn.disabled = false; btn.textContent = prevTxt;
  }
}

/* ------------------------------------------------------- menu order card - */
let menuOrderItems = [];
let menuOrderDragState = null;
let menuOrderCustomLayout = false; // یعنی کاربر همین حالا چیدمان آزاد (ردیف‌ها) را ویرایش کرده

function computeMenuRowNumbers() {
  let row = 0;
  return menuOrderItems.map((it, idx) => {
    if (idx === 0 || it.break_before !== false) row++;
    return row;
  });
}

function menuOrderRowHtml(item, idx, rowNumbers) {
  const joined = idx > 0 && item.break_before === false;
  const toggle = item.togglable
    ? `<span class="switch" data-order-enabled="${idx}" data-on="${item.enabled ? '1' : '0'}" title="فعال/غیرفعال" style="margin:0 4px"><i></i></span>`
    : '';
  return `
    <div class="menu-order-row${joined ? ' menu-order-joined' : ''}" data-idx="${idx}">
      <span class="menu-order-drag-handle" data-idx="${idx}">⠿</span>
      <span class="chip" style="opacity:.7">ردیف ${rowNumbers[idx]}</span>
      <span class="menu-order-label">${esc(item.label)}${item.admin_only ? ' <span class="card-sub">(فقط ادمین)</span>' : ''}</span>
      ${item.togglable && item.enabled === false ? '<span class="chip" style="color:var(--rose)">غیرفعال</span>' : ''}
      ${toggle}
      <div class="menu-order-arrows">
        ${idx > 0 ? `<button type="button" class="btn btn-sm ${joined ? 'btn-primary' : 'btn-ghost'}" data-order-break="${idx}" title="کنار دکمه‌ی قبلی یا در ردیف جدید">${joined ? '↔ کنار قبلی' : '⤵ ردیف جدید'}</button>` : ''}
        <button type="button" class="btn btn-sm btn-ghost" data-order-up="${idx}" ${idx === 0 ? 'disabled' : ''}>▲</button>
        <button type="button" class="btn btn-sm btn-ghost" data-order-down="${idx}" ${idx === menuOrderItems.length - 1 ? 'disabled' : ''}>▼</button>
      </div>
    </div>`;
}

function renderMenuOrderList() {
  const list = $('#menu-order-list', content());
  if (!list) return;
  const rowNumbers = computeMenuRowNumbers();
  list.innerHTML = menuOrderItems.map((item, idx) => menuOrderRowHtml(item, idx, rowNumbers)).join('');
  $$('[data-order-up]', list).forEach(b => b.addEventListener('click', () => moveMenuOrderItem(Number(b.dataset.orderUp), -1)));
  $$('[data-order-down]', list).forEach(b => b.addEventListener('click', () => moveMenuOrderItem(Number(b.dataset.orderDown), 1)));
  $$('[data-order-break]', list).forEach(b => b.addEventListener('click', () => toggleMenuOrderBreak(Number(b.dataset.orderBreak))));
  $$('.menu-order-drag-handle', list).forEach(h => h.addEventListener('pointerdown', onMenuOrderDragStart));
  $$('[data-order-enabled]', list).forEach(sw => sw.addEventListener('click', () => {
    const idx = Number(sw.dataset.orderEnabled);
    menuOrderItems[idx].enabled = !menuOrderItems[idx].enabled;
    renderMenuOrderList();
  }));
}

function toggleMenuOrderBreak(idx) {
  const item = menuOrderItems[idx];
  if (!item || idx === 0) return;
  // اگر break_before تا حالا مشخص نشده بود (چیدمان قدیمی ستون‌ثابت)، اولین کلیک
  // یعنی «بچسبان به قبلی»؛ بعد از این لحظه چیدمان آزاد رسماً شروع شده.
  item.break_before = item.break_before === false ? true : false;
  menuOrderCustomLayout = true;
  renderMenuOrderList();
}

function moveMenuOrderItem(idx, dir) {
  const newIdx = idx + dir;
  if (newIdx < 0 || newIdx >= menuOrderItems.length) return;
  const tmp = menuOrderItems[idx];
  menuOrderItems[idx] = menuOrderItems[newIdx];
  menuOrderItems[newIdx] = tmp;
  renderMenuOrderList();
}

function onMenuOrderDragStart(e) {
  e.preventDefault();
  const list = $('#menu-order-list', content());
  const rows = $$('.menu-order-row', list);
  const startIdx = Number(e.currentTarget.dataset.idx);
  const row = rows[startIdx];
  row.classList.add('dragging');
  menuOrderDragState = { startIdx, currentIdx: startIdx };

  const onContextMenu = (ctxEvt) => ctxEvt.preventDefault();
  document.body.classList.add('menu-order-dragging-lock');
  document.addEventListener('contextmenu', onContextMenu);

  const onMove = (moveEvt) => {
    if (!menuOrderDragState) return;
    moveEvt.preventDefault();
    const target = document.elementFromPoint(moveEvt.clientX, moveEvt.clientY);
    const overRow = target && target.closest('.menu-order-row');
    rows.forEach(r => r.classList.remove('drag-over'));
    if (overRow && overRow !== row) {
      overRow.classList.add('drag-over');
      menuOrderDragState.currentIdx = Number(overRow.dataset.idx);
    }
  };
  const onUp = () => {
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    document.removeEventListener('contextmenu', onContextMenu);
    document.body.classList.remove('menu-order-dragging-lock');
    if (menuOrderDragState && menuOrderDragState.currentIdx !== menuOrderDragState.startIdx) {
      const { startIdx: s, currentIdx: c } = menuOrderDragState;
      const [moved] = menuOrderItems.splice(s, 1);
      menuOrderItems.splice(c, 0, moved);
    }
    menuOrderDragState = null;
    renderMenuOrderList();
  };
  document.addEventListener('pointermove', onMove, { passive: false });
  document.addEventListener('pointerup', onUp);
}

function menuOrderCardHtml(items) {
  menuOrderItems = items;
  menuOrderCustomLayout = false;
  return `
    <div class="card" style="margin-bottom:18px">
      <div class="card-head">
        <h3>چیدمان دکمه‌های منوی ربات</h3>
        <button class="btn btn-primary btn-sm" id="menu-order-save">ذخیره چیدمان</button>
      </div>
      <span class="card-sub">با دستگیره ⠿ (یا فلش‌ها) ترتیب را جابه‌جا کن؛ با دکمه‌ی «کنار قبلی / ردیف جدید» مشخص کن کدام دکمه‌ها کنار هم و کدام‌ها در ردیف جدا نمایش داده شوند - مثلاً یک دکمه تمام‌عرض بالا و دو دکمه کنار هم پایینش.</span>
      <div id="menu-order-list" style="margin-top:12px"></div>
    </div>`;
}

async function saveMenuOrder() {
  const btn = $('#menu-order-save', content());
  btn.disabled = true;
  const prevTxt = btn.textContent; btn.textContent = 'در حال ذخیره...';
  try {
    const order = menuOrderItems.map(i => i.key);
    const buttons = menuOrderItems.filter(i => i.togglable).map(i => ({ key: i.key, enabled: !!i.enabled }));
    if (menuOrderCustomLayout) {
      // یعنی کاربر همین الان حداقل یک بار چیدمان ردیف‌ها را دستی تغییر داده؛
      // بقیه‌ی آیتم‌هایی که هنوز break_before نامشخص (null) دارند به‌صورت
      // پیش‌فرض «ردیف جدا» در نظر گرفته می‌شوند تا رفتار قابل‌پیش‌بینی بماند.
      const breaks = menuOrderItems.filter((it, idx) => idx > 0 && it.break_before !== false).map(i => i.key);
      await apiPost('/settings/menu-layout', { order, breaks, buttons });
    } else {
      await apiPost('/settings/menu-order', { order, buttons });
    }
    toast('چیدمان منو ذخیره شد.');
  } catch (e) {
    handleErr(e);
  } finally {
    btn.disabled = false; btn.textContent = prevTxt;
  }
}

async function renderSettings() {
  const [settings, menuOrder] = await Promise.all([
    apiGet('/settings'),
    apiGet('/settings/menu-order').catch(() => []),
  ]);
  if (loadTheme().theme === 'brutalist') return renderSettingsBrutalist(settings, menuOrder);
  if (loadTheme().theme === 'bento') return renderSettingsBento(settings, menuOrder);
  setContent(`
    ${settingsTabsHtml()}

    <div data-settings-tab="content" style="${settingsActiveTab === 'content' ? '' : 'display:none'}">
      ${menuOrderCardHtml(menuOrder)}
    </div>

    ${renderSettingsGroups(settings)}

    <div class="settings-save-bar">
      <button class="btn btn-primary btn-block" id="settings-save">ذخیره تغییرات</button>
    </div>
  `);
  $$('#settings-tabs-nav .tab-btn', content()).forEach(btn => btn.addEventListener('click', () => switchSettingsTab(btn.dataset.tab, content())));
  bindSettingsGroupEvents(content());
  renderMenuOrderList();
  $('#menu-order-save').addEventListener('click', saveMenuOrder);
  $('#settings-save').addEventListener('click', () => collectAndSaveSettings(content(), $('#settings-save')));
}

/* ----------------------------------------------------- settings: bento -- */
// تب افقی به سگمنت کپسولی اپلی تبدیل می‌شه؛ بدنه‌ی فرم همون منطق قبلیه،
// فقط با آکاردئون/سوییچ/سواچ گردتر (از طریق CSS اسکوپ‌شده به تم bento).
function renderSettingsBento(settings, menuOrder) {
  setContent(`
    <div class="bn-hero"><div><h2>تنظیمات</h2><p>پیکربندی محتوا و پرداخت فروشگاه</p></div></div>
    <div class="bn-seg" id="settings-tabs-nav" style="margin-bottom:16px">
      ${SETTINGS_TABS.map(t => `<button type="button" class="bn-seg-btn ${t.key === settingsActiveTab ? 'active' : ''}" data-tab="${t.key}">${t.label}</button>`).join('')}
    </div>
    <div data-settings-tab="content" style="${settingsActiveTab === 'content' ? '' : 'display:none'}">
      ${menuOrderCardHtml(menuOrder)}
    </div>
    ${renderSettingsGroups(settings)}
    <div class="settings-save-bar">
      <button class="bn-btn bn-btn-ok btn-block" id="settings-save" style="width:100%;padding:12px">ذخیره تغییرات</button>
    </div>
  `);
  $$('#settings-tabs-nav .bn-seg-btn', content()).forEach(btn => btn.addEventListener('click', () => switchSettingsTab(btn.dataset.tab, content())));
  bindSettingsGroupEvents(content());
  renderMenuOrderList();
  $('#menu-order-save').addEventListener('click', saveMenuOrder);
  $('#settings-save').addEventListener('click', () => collectAndSaveSettings(content(), $('#settings-save')));
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* ------------------------------------------------- settings: brutalist -- */
// ناوبری از تب افقی به سایدبار عمودی تبدیل می‌شه (مثل داشبورد ادمین‌های
// واقعی) — بدنه‌ی فرم‌ها با همون منطق قبلی، فقط قاب/سوییچ/سواچ برutalist.
function renderSettingsBrutalist(settings, menuOrder) {
  setContent(`
    <div class="bru-hero"><h2>تنظیمات</h2><p>پیکربندی محتوا و پرداخت فروشگاه</p></div>
    <div class="bru-settings-layout">
      <nav class="bru-settings-nav" id="settings-tabs-nav">
        ${SETTINGS_TABS.map(t => `<button type="button" class="bru-seg-btn ${t.key === settingsActiveTab ? 'active' : ''}" data-tab="${t.key}">${t.label}</button>`).join('')}
      </nav>
      <div class="bru-settings-content">
        <div data-settings-tab="content" style="${settingsActiveTab === 'content' ? '' : 'display:none'}">
          ${menuOrderCardHtml(menuOrder)}
        </div>
        ${renderSettingsGroups(settings)}
        <div class="settings-save-bar">
          <button class="bru-stamp bru-stamp-ok btn-block" id="settings-save" style="--r:-2deg;width:100%">ذخیره تغییرات</button>
        </div>
      </div>
    </div>
  `);
  $$('#settings-tabs-nav .bru-seg-btn', content()).forEach(btn => btn.addEventListener('click', () => switchSettingsTab(btn.dataset.tab, content())));
  bindSettingsGroupEvents(content());
  renderMenuOrderList();
  $('#menu-order-save').addEventListener('click', saveMenuOrder);
  $('#settings-save').addEventListener('click', () => collectAndSaveSettings(content(), $('#settings-save')));
}

/* ================================================================ logs === */
let logsPage = 1;
let logsFilter = { action: '', record_type: '', record_id: '' };
const RECORD_TYPE_LABEL = {
  order: 'سفارش', topup: 'شارژ کیف پول', user: 'کاربر', category: 'دسته‌بندی', product: 'محصول',
  product_file: 'فایل الگو', discount: 'کد تخفیف', ticket: 'تیکت',
  setting: 'تنظیم', webadmin: 'ادمین پنل',
};
const ACTION_LABEL = {
  backup_create: 'ساخت بکاپ', backup_restore: 'بازیابی بکاپ', broadcast: 'پیام همگانی',
  card_change: 'تغییر شماره کارت', category_add: 'افزودن دسته‌بندی', category_delete: 'حذف دسته‌بندی',
  category_edit: 'ویرایش دسته‌بندی', category_toggle: 'فعال/غیرفعال کردن دسته‌بندی',
  discount_add: 'افزودن کد تخفیف', discount_delete: 'حذف کد تخفیف',
  discount_toggle: 'فعال/غیرفعال کردن کد تخفیف',
  menu_order_change: 'تغییر چیدمان منو',
  order_approve: 'تایید سفارش', order_reject: 'رد سفارش',
  product_add: 'افزودن محصول', product_delete: 'حذف محصول', product_edit: 'ویرایش محصول',
  product_file_add: 'افزودن فایل الگو', product_file_delete: 'حذف فایل الگو',
  product_preview_set: 'تنظیم عکس پیش‌نمایش محصول',
  product_price_edit: 'ویرایش قیمت محصول', product_toggle: 'فعال/غیرفعال کردن محصول',
  sample_file_add: 'افزودن الگوی نمونه', sample_file_delete: 'حذف الگوی نمونه',
  setting_change: 'تغییر تنظیمات', support_reply: 'پاسخ چت زنده',
  ticket_close: 'بستن تیکت', ticket_reply: 'پاسخ تیکت', topup_approve: 'تایید شارژ کیف پول',
  topup_reject: 'رد شارژ کیف پول', user_block: 'مسدودسازی کاربر', user_unblock: 'رفع مسدودی کاربر',
  wallet_adjust: 'تغییر موجودی کیف پول', web_admin_active: 'فعال/غیرفعال کردن ادمین پنل',
  web_admin_add: 'افزودن ادمین پنل', web_admin_delete: 'حذف ادمین پنل', web_admin_permissions: 'تغییر دسترسی‌های ادمین پنل',
};
function actionLabel(a) { return ACTION_LABEL[a] || esc(a); }
function goToLogsFor(recordType, recordId) {
  logsFilter = { action: '', record_type: recordType, record_id: String(recordId) };
  logsPage = 1;
  goTo('logs');
}
/* ---------------------------------------------------- bento helpers ---- */
// اجزای مشترک تم Bento (اپل): پیل رنگی برای وضعیت، آواتار دایره‌ای گرادیانی —
// دقیقاً همون زبان بصری ویجت‌های داشبورد (.bw / .w-*) که برای بقیه‌ی صفحات
// هم استفاده می‌شه تا کل پنل یکدست بمونه.
const BN_ACCENTS = ['w-blue', 'w-green', 'w-orange', 'w-pink', 'w-purple'];
function bnPill(label, kind) { return `<span class="bn-pill bn-pill-${kind}">${label}</span>`; }
function bnAvatar(ch, i) { return `<div class="bn-avatar ${BN_ACCENTS[i % BN_ACCENTS.length]}">${esc(ch)}</div>`; }

const GLASS_COLORS = ['#8B5CF6', '#22D3EE', '#34D399', '#FBBF24', '#FB7185', '#EC4899'];
function glPill(label, kind) { return `<span class="gl-pill gl-pill-${kind}">${label}</span>`; }
function glAvatar(ch, i) { return `<div class="gl-avatar" style="--c:${GLASS_COLORS[i % GLASS_COLORS.length]}">${esc(ch)}</div>`; }

const CYB_COLORS = ['#00FF9C', '#00E5FF', '#FF2E9A', '#C6FF00', '#FF2E5B'];
function cybPill(label, kind) { return `<span class="cyb-pill cyb-pill-${kind}">${label}</span>`; }
function cybAvatar(ch, i) { return `<div class="cyb-avatar" style="--c:${CYB_COLORS[i % CYB_COLORS.length]}">${esc(ch)}</div>`; }

const CLY_COLORS = ['#F97316', '#FB923C', '#FBBF24', '#10B981', '#EC4899', '#06B6D4'];
function clyPill(label, kind) { return `<span class="cly-pill cly-pill-${kind}">${label}</span>`; }
function clyAvatar(ch, i) { return `<div class="cly-avatar" style="--c:${CLY_COLORS[i % CLY_COLORS.length]}">${esc(ch)}</div>`; }

const PPR_COLORS = ['#111827', '#374151', '#065F46', '#92400E', '#991B1B', '#1F2937'];
function pprPill(label, kind) { return `<span class="ppr-pill ppr-pill-${kind}">${label}</span>`; }
function pprAvatar(ch, i) { return `<div class="ppr-avatar" style="--c:${PPR_COLORS[i % PPR_COLORS.length]}">${esc(ch)}</div>`; }

const OBK_COLORS = ['#0AFF6B', '#EDEDED', '#FFB800', '#FF3344'];
function obkPill(label, kind) { return `<span class="obk-pill obk-pill-${kind}">${label}</span>`; }
function obkAvatar(ch, i) { return `<div class="obk-avatar" style="--c:${OBK_COLORS[i % OBK_COLORS.length]}">${esc(ch)}</div>`; }

const WRP_COLORS = ['#7C5CFF', '#3FE0C0', '#FF6F91', '#9A93C9', '#5A3CFF'];
function wrpPill(label, kind) { return `<span class="wrp-pill wrp-pill-${kind}">${label}</span>`; }
function wrpAvatar(ch, i) { return `<div class="wrp-avatar" style="--c:${WRP_COLORS[i % WRP_COLORS.length]}">${esc(ch)}</div>`; }

function historyBtn(recordType, recordId) {
  return hasPerm('system')
    ? `<button class="btn btn-ghost btn-sm" data-history="${recordType}:${recordId}" title="تاریخچه">تاریخچه</button>` : '';
}
async function showRecordHistory(recordType, recordId) {
  const qs = new URLSearchParams({ page: 1, record_type: recordType, record_id: String(recordId) });
  const res = await apiGet(`/admin-logs?${qs.toString()}`);
  openModal(`تاریخچه ${RECORD_TYPE_LABEL[recordType] || esc(recordType)} #${esc(recordId)}`, `
    <div class="table-wrap" style="max-height:60vh;overflow-y:auto">
      <table><thead><tr><th>ادمین</th><th>عملیات</th><th>جزئیات</th><th>تاریخ</th></tr></thead>
      <tbody>${res.items.map(l => `<tr>
        <td class="mono">${l.admin_id}</td><td>${actionLabel(l.action)}</td>
        <td>${esc(l.details)}</td><td class="mono">${fmtDate(l.created_at)}</td>
      </tr>`).join('') || `<tr><td colspan="4" class="empty-state"><div class="icon">${svg('empty')}</div>لاگی ثبت نشده</td></tr>`}</tbody></table>
    </div>
    <button class="btn btn-block" id="rh-full-log" style="margin-top:14px">مشاهده کامل در لاگ سیستم</button>
  `, (body, close) => {
    $('#rh-full-log', body).addEventListener('click', () => { close(); goToLogsFor(recordType, recordId); });
  }, { wide: true });
}
async function renderLogs() {
  const actionsRes = await apiGet('/admin-logs/actions');
  const qs = new URLSearchParams({ page: logsPage });
  if (logsFilter.action) qs.set('action', logsFilter.action);
  if (logsFilter.record_type) qs.set('record_type', logsFilter.record_type);
  if (logsFilter.record_id) qs.set('record_id', logsFilter.record_id);
  const res = await apiGet(`/admin-logs?${qs.toString()}`);
  const pages = Math.max(Math.ceil(res.total / res.limit), 1);
  if (loadTheme().theme === 'brutalist') return renderLogsBrutalist(actionsRes, res, pages);
  if (loadTheme().theme === 'bento') return renderLogsBento(actionsRes, res, pages);
  setContent(`
    <div class="card" style="margin-bottom:14px">
      <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
        <select class="input" id="lf-action">
          <option value="">همه‌ی عملیات</option>
          ${actionsRes.actions.map(a => `<option value="${a}" ${a === logsFilter.action ? 'selected' : ''}>${actionLabel(a)}</option>`).join('')}
        </select>
        <select class="input" id="lf-type">
          <option value="">همه‌ی رکوردها</option>
          ${Object.keys(RECORD_TYPE_LABEL).map(t => `<option value="${t}" ${t === logsFilter.record_type ? 'selected' : ''}>${RECORD_TYPE_LABEL[t]}</option>`).join('')}
        </select>
        <input class="input" id="lf-id" placeholder="شناسه رکورد (مثلاً آیدی سفارش)" value="${esc(logsFilter.record_id)}">
        <button class="btn btn-primary btn-sm" id="lf-apply">اعمال فیلتر</button>
        <button class="btn btn-sm" id="lf-clear">پاک‌کردن</button>
      </div>
    </div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>ادمین</th><th>عملیات</th><th>رکورد</th><th>جزئیات</th><th>تاریخ</th></tr></thead>
      <tbody>${res.items.map(l => `<tr>
        <td class="mono">${l.admin_id}</td><td>${actionLabel(l.action)}</td>
        <td>${l.record_type ? `<span class="chip">${RECORD_TYPE_LABEL[l.record_type] || esc(l.record_type)} #${esc(l.record_id)}</span>` : '—'}</td>
        <td>${esc(l.details)}</td><td class="mono">${fmtDate(l.created_at)}</td>
      </tr>`).join('') || '<tr><td colspan="5" class="empty-state">لاگی ثبت نشده</td></tr>'}</tbody>
    </table></div>
    <div class="pager">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === logsPage ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
    </div>
  `);
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { logsPage = Number(b.dataset.page); renderLogs(); }));
  $('#lf-apply').addEventListener('click', () => {
    logsFilter = { action: $('#lf-action').value, record_type: $('#lf-type').value, record_id: $('#lf-id').value.trim() };
    logsPage = 1; renderLogs();
  });
  $('#lf-clear').addEventListener('click', () => { logsFilter = { action: '', record_type: '', record_id: '' }; logsPage = 1; renderLogs(); });
}

/* ------------------------------------------------------------- logs: bento */
function renderLogsBento(actionsRes, res, pages) {
  setContent(`
    <div class="bn-hero"><div><h2>لاگ سیستم</h2><p>${fmt(res.total)} رکورد ثبت‌شده</p></div></div>
    <div class="bn-card" style="margin-bottom:14px">
      <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
        <select class="input" id="lf-action">
          <option value="">همه‌ی عملیات</option>
          ${actionsRes.actions.map(a => `<option value="${a}" ${a === logsFilter.action ? 'selected' : ''}>${actionLabel(a)}</option>`).join('')}
        </select>
        <select class="input" id="lf-type">
          <option value="">همه‌ی رکوردها</option>
          ${Object.keys(RECORD_TYPE_LABEL).map(t => `<option value="${t}" ${t === logsFilter.record_type ? 'selected' : ''}>${RECORD_TYPE_LABEL[t]}</option>`).join('')}
        </select>
        <input class="input" id="lf-id" placeholder="شناسه رکورد" value="${esc(logsFilter.record_id)}">
        <button class="bn-btn bn-btn-ok" id="lf-apply">اعمال فیلتر</button>
        <button class="bn-btn bn-btn-ghost" id="lf-clear">پاک‌کردن</button>
      </div>
    </div>
    <div class="bn-list">
      ${res.items.map((l, i) => `
        <div class="bn-row bn-card-anim" style="animation-delay:${Math.min(i * 20, 200)}ms">
          ${bnAvatar('#', i)}
          <div class="bn-row-main">
            <span class="bn-row-title">${actionLabel(l.action)}</span>
            <span class="bn-row-sub">ادمین #${l.admin_id}${l.record_type ? ` · ${RECORD_TYPE_LABEL[l.record_type] || esc(l.record_type)} #${esc(l.record_id)}` : ''}${l.details ? ' · ' + esc(l.details) : ''}</span>
          </div>
          <span class="bn-row-sub mono">${fmtDate(l.created_at)}</span>
        </div>
      `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>لاگی ثبت نشده</div>`}
    </div>
    <div class="pager" style="margin-top:16px">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === logsPage ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
  `);
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { logsPage = Number(b.dataset.page); renderLogs(); }));
  $('#lf-apply').addEventListener('click', () => {
    logsFilter = { action: $('#lf-action').value, record_type: $('#lf-type').value, record_id: $('#lf-id').value.trim() };
    logsPage = 1; renderLogs();
  });
  $('#lf-clear').addEventListener('click', () => { logsFilter = { action: '', record_type: '', record_id: '' }; logsPage = 1; renderLogs(); });
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* ---------------------------------------------------- logs: brutalist --- */
// لاگ‌ها به‌شکل نوار زمانی (تایم‌لاین) با خط ضخیم سمت راست، به‌جای جدول.
function renderLogsBrutalist(actionsRes, res, pages) {
  setContent(`
    <div class="bru-hero"><h2>لاگ سیستم</h2><p>${fmt(res.total)} رکورد ثبت‌شده</p></div>
    <div class="bru-panel" style="margin-bottom:16px">
      <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
        <select class="input" id="lf-action">
          <option value="">همه‌ی عملیات</option>
          ${actionsRes.actions.map(a => `<option value="${a}" ${a === logsFilter.action ? 'selected' : ''}>${actionLabel(a)}</option>`).join('')}
        </select>
        <select class="input" id="lf-type">
          <option value="">همه‌ی رکوردها</option>
          ${Object.keys(RECORD_TYPE_LABEL).map(t => `<option value="${t}" ${t === logsFilter.record_type ? 'selected' : ''}>${RECORD_TYPE_LABEL[t]}</option>`).join('')}
        </select>
        <input class="input" id="lf-id" placeholder="شناسه رکورد (مثلاً آیدی سفارش)" value="${esc(logsFilter.record_id)}">
        <button class="bru-stamp bru-stamp-ok" id="lf-apply" style="--r:-2deg">اعمال فیلتر</button>
        <button class="btn btn-sm" id="lf-clear">پاک‌کردن</button>
      </div>
    </div>
    <div class="bru-log-list">
      ${res.items.map((l, i) => `
        <div class="bru-log-row bru-card-anim" style="animation-delay:${Math.min(i * 25, 220)}ms">
          <span class="bru-log-time mono">${fmtDate(l.created_at)}</span>
          <div class="bru-log-main">
            <span class="bru-log-action">${actionLabel(l.action)}</span>
            <span class="bru-log-admin mono">ادمین #${l.admin_id}</span>
            ${l.record_type ? `<span class="chip">${RECORD_TYPE_LABEL[l.record_type] || esc(l.record_type)} #${esc(l.record_id)}</span>` : ''}
          </div>
          ${l.details ? `<div class="bru-log-details">${esc(l.details)}</div>` : ''}
        </div>
      `).join('') || `<div class="empty-state"><div class="icon">${svg('empty')}</div>لاگی ثبت نشده</div>`}
    </div>
    <div class="pager" style="margin-top:16px">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === logsPage ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
  `);
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { logsPage = Number(b.dataset.page); renderLogs(); }));
  $('#lf-apply').addEventListener('click', () => {
    logsFilter = { action: $('#lf-action').value, record_type: $('#lf-type').value, record_id: $('#lf-id').value.trim() };
    logsPage = 1; renderLogs();
  });
  $('#lf-clear').addEventListener('click', () => { logsFilter = { action: '', record_type: '', record_id: '' }; logsPage = 1; renderLogs(); });
}

/* ========================================================== webadmins === */
const PERM_LABEL = {
  orders: 'سفارش‌ها و شارژ کیف پول', users: 'کاربران (بلاک/کیف پول)', catalog: 'محصولات و فایل‌های الگو',
  discounts: 'کدهای تخفیف', tickets: 'تیکت‌ها و چت زنده', broadcast: 'پیام همگانی',
  system: 'سیستم، بکاپ (وضعیت) و لاگ‌ها',
  settings: 'تنظیمات و برندینگ', backup: 'ساخت بکاپ فوری',
};

function permChecklistHtml(idPrefix, selected) {
  return `<div class="chip-row" style="flex-wrap:wrap;gap:6px">${PERM_KEYS.map(p => `
    <label style="display:flex;align-items:center;gap:4px;font-size:12px;background:var(--panel-2);padding:4px 8px;border-radius:7px">
      <input type="checkbox" id="${idPrefix}-${p}" data-perm="${p}" ${selected.includes(p) ? 'checked' : ''}>${PERM_LABEL[p] || p}
    </label>`).join('')}</div>`;
}
function readPermChecklist(root, idPrefix) {
  return PERM_KEYS.filter(p => $(`#${idPrefix}-${p}`, root)?.checked);
}

let PERM_KEYS = [];
async function renderWebAdmins() {
  if (!PERM_KEYS.length) PERM_KEYS = (await apiGet('/web-admins/permissions')).permissions;
  const admins = await apiGet('/web-admins');
  if (loadTheme().theme === 'brutalist') return renderWebAdminsBrutalist(admins);
  if (loadTheme().theme === 'bento') return renderWebAdminsBento(admins);
  setContent(`
    <div class="toolbar"><button class="btn btn-primary btn-sm" id="add-admin">+ کاربر پنل جدید</button></div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>یوزرنیم</th><th>نقش</th><th>مجوزها</th><th>وضعیت</th><th>آخرین ورود</th><th>عملیات</th></tr></thead>
      <tbody>${admins.map(a => `<tr>
        <td>${esc(a.username)}</td>
        <td><span class="badge badge-${a.role}">${ROLE_LABEL[a.role]}</span></td>
        <td>${a.role === 'owner' ? '<span class="card-sub">همه</span>' : `<span class="card-sub">${a.permissions.length ? a.permissions.map(p => PERM_LABEL[p] || p).join('، ') : 'بدون مجوز (فقط مشاهده)'}</span>`}</td>
        <td>${a.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
        <td class="mono">${fmtDate(a.last_login)}</td>
        <td>${a.role === 'owner' ? '<span class="card-sub">مالک</span>' : `
          <button class="btn btn-sm" data-edit-perms="${a.id}">ویرایش مجوزها</button>
          <button class="btn btn-sm" data-toggle-active="${a.id}" data-active="${a.is_active}">${a.is_active ? 'غیرفعال' : 'فعال'}</button>
          <button class="btn btn-danger btn-sm" data-del="${a.id}">حذف</button>`}</td>
      </tr>`).join('')}</tbody>
    </table></div></div>
  `);
  $('#add-admin').addEventListener('click', () => openModal('کاربر پنل جدید', `
    <div class="form-grid">
      <input class="input" id="na-user" placeholder="یوزرنیم">
      <input class="input" id="na-pass" type="password" placeholder="پسورد (حداقل ۸ کاراکتر)">
      <div class="card-sub" style="margin-top:4px">مجوزها:</div>
      ${permChecklistHtml('na', [])}
      <button class="btn btn-primary" id="na-save">ثبت</button>
    </div>`, (body, close) => {
    $('#na-save', body).addEventListener('click', async () => {
      try {
        await apiPost('/web-admins', {
          username: $('#na-user', body).value.trim(), password: $('#na-pass', body).value,
          role: 'admin', permissions: readPermChecklist(body, 'na'),
        });
        toast('کاربر ساخته شد.'); close(); renderWebAdmins();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-edit-perms]', content()).forEach(b => b.addEventListener('click', () => {
    const a = admins.find(x => x.id === Number(b.dataset.editPerms));
    openModal(`مجوزهای ${esc(a.username)}`, `
      ${permChecklistHtml('ep', a.permissions)}
      <button class="btn btn-primary" id="ep-save" style="margin-top:14px">ذخیره</button>
    `, (body, close) => {
      $('#ep-save', body).addEventListener('click', async () => {
        try {
          await apiPost(`/web-admins/${a.id}/permissions`, { permissions: readPermChecklist(body, 'ep') });
          toast('مجوزها به‌روزرسانی شد.'); close(); renderWebAdmins();
        } catch (e) { handleErr(e); }
      });
    });
  }));
  $$('[data-toggle-active]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/web-admins/${b.dataset.toggleActive}/active`, { active: b.dataset.active !== 'true' }); renderWebAdmins(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این حساب حذف شود؟')) return;
    try { await apiDelete(`/web-admins/${b.dataset.del}`); toast('حذف شد.'); renderWebAdmins(); } catch (e) { handleErr(e); }
  }));
}

/* ------------------------------------------------------- webadmins: bento */
function renderWebAdminsBento(admins) {
  setContent(`
    <div class="bn-hero">
      <div><h2>ادمین‌های پنل</h2><p>${fmt(admins.length)} حساب ثبت‌شده</p></div>
      <button class="bn-btn bn-btn-ok" id="add-admin">+ کاربر پنل جدید</button>
    </div>
    <div class="bn-list">
      ${admins.map((a, i) => `
        <div class="bn-row bn-card-anim" style="animation-delay:${Math.min(i * 25, 220)}ms">
          ${bnAvatar(a.username.trim().charAt(0).toUpperCase(), i)}
          <div class="bn-row-main">
            <span class="bn-row-title">${esc(a.username)}</span>
            <span class="bn-row-sub">${ROLE_LABEL[a.role]} · ورود: ${fmtDate(a.last_login)}</span>
          </div>
          <div class="bn-row-trail">
            ${bnPill(a.is_active ? 'فعال' : 'غیرفعال', a.is_active ? 'ok' : 'no')}
            ${a.role !== 'owner' ? `
            <button class="bn-btn bn-btn-ghost" data-edit-perms="${a.id}">مجوزها</button>
            <button class="bn-btn bn-btn-ghost" data-toggle-active="${a.id}" data-active="${a.is_active}">${a.is_active ? 'غیرفعال' : 'فعال'}</button>
            <button class="bn-btn bn-btn-no" data-del="${a.id}">حذف</button>` : ''}
          </div>
        </div>
      `).join('')}
    </div>
  `);
  $('#add-admin').addEventListener('click', () => openModal('کاربر پنل جدید', `
    <div class="form-grid">
      <input class="input" id="na-user" placeholder="یوزرنیم">
      <input class="input" id="na-pass" type="password" placeholder="پسورد (حداقل ۸ کاراکتر)">
      <div class="card-sub" style="margin-top:4px">مجوزها:</div>
      ${permChecklistHtml('na', [])}
      <button class="btn btn-primary" id="na-save">ثبت</button>
    </div>`, (body, close) => {
    $('#na-save', body).addEventListener('click', async () => {
      try {
        await apiPost('/web-admins', {
          username: $('#na-user', body).value.trim(), password: $('#na-pass', body).value,
          role: 'admin', permissions: readPermChecklist(body, 'na'),
        });
        toast('کاربر ساخته شد.'); close(); renderWebAdmins();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-edit-perms]', content()).forEach(b => b.addEventListener('click', () => {
    const a = admins.find(x => x.id === Number(b.dataset.editPerms));
    openModal(`مجوزهای ${esc(a.username)}`, `
      ${permChecklistHtml('ep', a.permissions)}
      <button class="btn btn-primary" id="ep-save" style="margin-top:14px">ذخیره</button>
    `, (body, close) => {
      $('#ep-save', body).addEventListener('click', async () => {
        try {
          await apiPost(`/web-admins/${a.id}/permissions`, { permissions: readPermChecklist(body, 'ep') });
          toast('مجوزها به‌روزرسانی شد.'); close(); renderWebAdmins();
        } catch (e) { handleErr(e); }
      });
    });
  }));
  $$('[data-toggle-active]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/web-admins/${b.dataset.toggleActive}/active`, { active: b.dataset.active !== 'true' }); renderWebAdmins(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این حساب حذف شود؟')) return;
    try { await apiDelete(`/web-admins/${b.dataset.del}`); toast('حذف شد.'); renderWebAdmins(); } catch (e) { handleErr(e); }
  }));
}


/* -------------------------------------------------- cyberpunk --- */

/* -------------------------------------------------- clay --- */

/* -------------------------------------------------- paper --- */

/* -------------------------------------------------- obsidian --- */

/* -------------------------------------------------- warp --- */

/* ------------------------------------------------- webadmins: brutalist - */
// کارت شناسنامه‌ای برای هر ادمین پنل، با برچسب نقش مثل مهر روی پرونده.
function renderWebAdminsBrutalist(admins) {
  setContent(`
    <div class="bru-hero" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap">
      <div>
        <h2>ادمین‌های پنل</h2>
        <p>${fmt(admins.length)} حساب ثبت‌شده</p>
      </div>
      <button class="bru-stamp bru-stamp-ok" id="add-admin" style="--r:-3deg">+ کاربر پنل جدید</button>
    </div>
    <div class="bru-user-grid">
      ${admins.map((a, i) => `
        <div class="bru-user-card bru-card-anim" style="animation-delay:${Math.min(i * 35, 300)}ms;text-align:center">
          <span class="bru-flag ${a.is_active ? 'bru-flag-ok' : 'bru-flag-no'}">${a.is_active ? 'فعال' : 'غیرفعال'}</span>
          <div class="bru-user-avatar mono">${esc(a.username.trim().charAt(0).toUpperCase())}</div>
          <div class="bru-user-name">${esc(a.username)}</div>
          <div class="bru-flag" style="background:var(--primary);margin-top:4px">${ROLE_LABEL[a.role]}</div>
          <div class="bru-user-id mono" style="margin-top:6px">ورود: ${fmtDate(a.last_login)}</div>
          <div class="bru-user-joined" style="max-width:190px">${a.role === 'owner' ? 'دسترسی کامل' : (a.permissions.length ? a.permissions.map(p => PERM_LABEL[p] || p).join('، ') : 'بدون مجوز')}</div>
          ${a.role !== 'owner' ? `
          <div class="bru-user-actions">
            <button class="btn btn-sm" data-edit-perms="${a.id}">مجوزها</button>
            <button class="btn btn-sm" data-toggle-active="${a.id}" data-active="${a.is_active}">${a.is_active ? 'غیرفعال' : 'فعال'}</button>
            <button class="btn btn-danger btn-sm" data-del="${a.id}">حذف</button>
          </div>` : ''}
        </div>
      `).join('')}
    </div>
  `);
  $('#add-admin').addEventListener('click', () => openModal('کاربر پنل جدید', `
    <div class="form-grid">
      <input class="input" id="na-user" placeholder="یوزرنیم">
      <input class="input" id="na-pass" type="password" placeholder="پسورد (حداقل ۸ کاراکتر)">
      <div class="card-sub" style="margin-top:4px">مجوزها:</div>
      ${permChecklistHtml('na', [])}
      <button class="btn btn-primary" id="na-save">ثبت</button>
    </div>`, (body, close) => {
    $('#na-save', body).addEventListener('click', async () => {
      try {
        await apiPost('/web-admins', {
          username: $('#na-user', body).value.trim(), password: $('#na-pass', body).value,
          role: 'admin', permissions: readPermChecklist(body, 'na'),
        });
        toast('کاربر ساخته شد.'); close(); renderWebAdmins();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-edit-perms]', content()).forEach(b => b.addEventListener('click', () => {
    const a = admins.find(x => x.id === Number(b.dataset.editPerms));
    openModal(`مجوزهای ${esc(a.username)}`, `
      ${permChecklistHtml('ep', a.permissions)}
      <button class="btn btn-primary" id="ep-save" style="margin-top:14px">ذخیره</button>
    `, (body, close) => {
      $('#ep-save', body).addEventListener('click', async () => {
        try {
          await apiPost(`/web-admins/${a.id}/permissions`, { permissions: readPermChecklist(body, 'ep') });
          toast('مجوزها به‌روزرسانی شد.'); close(); renderWebAdmins();
        } catch (e) { handleErr(e); }
      });
    });
  }));
  $$('[data-toggle-active]', content()).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/web-admins/${b.dataset.toggleActive}/active`, { active: b.dataset.active !== 'true' }); renderWebAdmins(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این حساب حذف شود؟')) return;
    try { await apiDelete(`/web-admins/${b.dataset.del}`); toast('حذف شد.'); renderWebAdmins(); } catch (e) { handleErr(e); }
  }));
}

/* ============================================================= system === */
async function renderSystem() {
  const jobs = await apiGet('/system/jobs');
  const backupStatus = await apiGet('/system/backup/status');
  const isOwner = ME.role === 'owner';

  setContent(`
    <div class="card" style="margin-bottom:18px">
      <div class="card-head"><h3>بکاپ خودکار دیتابیس</h3></div>
      <p class="card-sub" style="margin-bottom:10px">زمان‌بندی بکاپ خودکار در پردازش بات تنظیم می‌شود و از اینجا قابل تغییر نیست؛ وضعیت آخرین اجرا:</p>
      <div class="chip-row">
        <span class="chip">آخرین اجرا: ${jobs.backup?.last_run ? fmtDate(jobs.backup.last_run) : 'هنوز اجرا نشده'}</span>
      </div>
    </div>

    <div class="card" style="margin-bottom:18px">
      <div class="card-head"><h3>بکاپ دیتابیس</h3></div>
      <div class="chip-row" style="margin-bottom:14px">
        <span class="chip">آخرین بکاپ: ${backupStatus.last_backup_at ? fmtDate(backupStatus.last_backup_at) : 'ثبت نشده'}</span>
        <span class="chip">حجم آخرین بکاپ: ${backupStatus.last_backup_size_mb ?? '—'} مگابایت</span>
        <span class="chip">تعداد نسخه‌های نگه‌داشته‌شده: ${fmt(backupStatus.count)}</span>
      </div>
      ${isOwner ? `
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px">
        <button class="btn btn-primary" id="backup-create-btn">📥 گرفتن بکاپ فوری و ارسال به تلگرام</button>
      </div>
      <div id="backup-create-status"></div>

      <div class="card-head" style="margin-top:10px"><h3>بازیابی از فایل بکاپ</h3></div>
      <p class="card-sub" style="margin-bottom:10px">⚠️ با تایید، کل دیتابیس فعلی با فایل آپلودی جایگزین می‌شود. این کار قابل بازگشت نیست مگر با بکاپ دیگر. قبل از جایگزینی، یک نسخه از وضعیت فعلی خودکار ذخیره می‌شود.</p>
      <input type="file" class="input" id="restore-file" accept=".db,.sqlite,.sqlite3" style="margin-bottom:10px">
      <div id="restore-area"></div>
      ` : `<p class="card-sub">گرفتن بکاپ فوری و بازیابی فقط برای مالک در دسترس است.</p>`}
    </div>
  `);

  if (!isOwner) return;

  $('#backup-create-btn').addEventListener('click', async () => {
    const btn = $('#backup-create-btn');
    const status = $('#backup-create-status', content());
    btn.disabled = true;
    status.innerHTML = '<span class="card-sub">⏳ در حال ساخت و ارسال بکاپ...</span>';
    try {
      const res = await apiPost('/system/backup/create');
      status.innerHTML = `<span class="card-sub">✅ بکاپ (${esc(res.filename)}, ${res.size_mb} مگابایت) ساخته شد و به ${res.sent} ادمین ارسال شد${res.failed ? ` (${res.failed} ناموفق)` : ''}.</span>`;
      toast('بکاپ گرفته شد.');
    } catch (e) {
      status.innerHTML = '';
      handleErr(e);
    } finally {
      btn.disabled = false;
    }
  });

  let restorePendingFile = null;

  function renderRestoreArea() {
    const area = $('#restore-area', content());
    if (!restorePendingFile) {
      area.innerHTML = '';
      return;
    }
    const sizeMb = (restorePendingFile.size / (1024 * 1024)).toFixed(1);
    area.innerHTML = `
      <div class="card" style="margin-top:0;border-color:var(--rose)">
        <p class="card-sub" style="margin:0 0 8px">📦 فایل انتخاب‌شده: ${esc(restorePendingFile.name)} (${sizeMb} مگابایت)</p>
        <p class="card-sub" style="margin:0 0 10px">⚠️ مرحله ۱: این عمل کل دیتابیس فعلی رو با این فایل جایگزین می‌کنه. مطمئنی؟</p>
        <div style="display:flex;gap:8px">
          <button class="btn btn-danger btn-sm" id="restore-step1-btn">بله، ادامه بده</button>
          <button class="btn btn-ghost btn-sm" id="restore-cancel-btn">انصراف</button>
        </div>
      </div>
    `;
    $('#restore-step1-btn', area).addEventListener('click', () => renderRestoreConfirmStep());
    $('#restore-cancel-btn', area).addEventListener('click', cancelRestore);
  }

  function renderRestoreConfirmStep() {
    const area = $('#restore-area', content());
    area.innerHTML = `
      <div class="card" style="margin-top:0;border-color:var(--rose)">
        <p class="card-sub" style="margin:0 0 10px">⚠️ مرحله ۲ (نهایی): برای تایید نهایی، عبارت <strong class="mono">RESTORE</strong> رو دقیقاً تایپ کن.</p>
        <input class="input" id="restore-confirm-input" placeholder="RESTORE" style="margin-bottom:10px">
        <div style="display:flex;gap:8px">
          <button class="btn btn-danger btn-sm" id="restore-final-btn">✅ تایید نهایی و جایگزینی</button>
          <button class="btn btn-ghost btn-sm" id="restore-cancel-btn2">انصراف</button>
        </div>
        <div id="restore-final-status" style="margin-top:10px"></div>
      </div>
    `;
    $('#restore-cancel-btn2', area).addEventListener('click', cancelRestore);
    $('#restore-final-btn', area).addEventListener('click', async () => {
      const phrase = $('#restore-confirm-input', area).value.trim();
      if (phrase.toUpperCase() !== 'RESTORE') {
        $('#restore-final-status', area).innerHTML = '<span class="card-sub" style="color:var(--rose)">عبارت را دقیقاً RESTORE وارد کن.</span>';
        return;
      }
      const statusEl = $('#restore-final-status', area);
      statusEl.innerHTML = '<span class="card-sub">⏳ در حال بازیابی...</span>';
      try {
        const formData = new FormData();
        formData.append('file', restorePendingFile);
        formData.append('confirm_phrase', phrase);
        const res = await fetch('/api/system/backup/restore', { method: 'POST', credentials: 'include', body: formData });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'خطای ناشناخته');
        statusEl.innerHTML = `<span class="card-sub">✅ دیتابیس بازیابی شد. نسخه‌ی قبلی به‌عنوان «${esc(data.pre_restore_backup)}» ذخیره شد. صفحه را رفرش کن.</span>`;
        restorePendingFile = null;
        $('#restore-file').value = '';
      } catch (e) {
        statusEl.innerHTML = `<span class="card-sub" style="color:var(--rose)">${esc(e.message)}</span>`;
      }
    });
  }

  function cancelRestore() {
    restorePendingFile = null;
    $('#restore-file').value = '';
    renderRestoreArea();
  }

  $('#restore-file').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) { restorePendingFile = null; renderRestoreArea(); return; }
    if (!/\.(db|sqlite|sqlite3)$/i.test(file.name)) {
      toast('فایل باید پسوند .db یا .sqlite داشته باشد.', true);
      e.target.value = '';
      return;
    }
    restorePendingFile = file;
    renderRestoreArea();
  });
}

/* ============================================================= account === */
function renderThemeCard(t, cur) {
  const active = t.id === cur.theme;
  const swatchHtml = t.swatch.map(c => `<span style="background:${c}"></span>`).join('');
  return `
    <div class="theme-card ${active ? 'active' : ''} ${t.ready ? '' : 'locked'}" data-theme-id="${t.id}">
      <div class="theme-card-swatch">${swatchHtml}</div>
      <div class="theme-card-body">
        <strong>${esc(t.name)}</strong>
        <span>${esc(t.desc)}</span>
      </div>
      ${active ? '<span class="theme-card-badge">فعال</span>' : (t.ready ? '' : '<span class="theme-card-badge locked">به‌زودی</span>')}
    </div>`;
}

async function renderAccount() {
  const cur = loadTheme();
  const activeMeta = THEMES.find(t => t.id === cur.theme) || THEMES[0];
  setContent(`
    <div class="card" style="margin-bottom:18px">
      <div class="card-head"><h3>تم پنل</h3></div>
      <div class="theme-grid" id="theme-grid">
        ${THEMES.map(t => renderThemeCard(t, cur)).join('')}
      </div>
      <span class="card-sub">این یک ترجیح شخصیه و فقط برای همین مرورگر ذخیره می‌شود؛ روی نمایش پنل برای بقیه‌ی ادمین‌ها اثری ندارد.${activeMeta.supportsMode ? ' سوییچ روشن/تیره از نوار بالا در دسترسه.' : ''}</span>
    </div>

    <div class="card" style="max-width:420px">
      <div class="card-head"><h3>تغییر پسورد</h3></div>
      <div class="form-grid">
        <input class="input" id="acc-cur" type="password" placeholder="پسورد فعلی">
        <input class="input" id="acc-new" type="password" placeholder="پسورد جدید (حداقل ۸ کاراکتر)">
        <button class="btn btn-primary" id="acc-save">تغییر پسورد</button>
      </div>
    </div>
  `);
  $$('.theme-card', content()).forEach(card => card.addEventListener('click', () => {
    const id = card.dataset.themeId;
    const meta = THEMES.find(t => t.id === id);
    if (!meta.ready) { toast('این تم هنوز آماده نیست — به‌زودی اضافه می‌شود.'); return; }
    applyThemeChoice(id);
    renderAccount();
  }));
  $('#acc-save').addEventListener('click', async () => {
    try {
      await apiPost('/me/password', { current_password: $('#acc-cur').value, new_password: $('#acc-new').value });
      toast('پسورد تغییر کرد.');
      $('#acc-cur').value = ''; $('#acc-new').value = '';
    } catch (e) { handleErr(e); }
  });
}

boot();

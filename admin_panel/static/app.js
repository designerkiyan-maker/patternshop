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
    id: 'flat',
    name: 'Fintech Flat',
    desc: 'سایدبار + کارت‌های تخت بنفش، نمودار رادار',
    ready: true,
    supportsMode: true, // این تم حالت روشن/تیره داره
    swatch: ['#7367F0', '#23253A', '#1B1D2C'],
  },
  {
    id: 'bento',
    name: 'Bento Grid',
    desc: 'کارت‌های نامنظم چندسایز مثل ویجت‌های اپل',
    ready: true,
    supportsMode: false,
    swatch: ['#0A84FF', '#30D158', '#FF9F0A'],
  },
  {
    id: 'brutalist',
    name: 'Neo-brutalist',
    desc: 'کادر ضخیم، بی‌سایه، تایپوگرافی بولد',
    ready: true,
    supportsMode: false,
    swatch: ['#FFE600', '#000000', '#FFFFFF'],
  },
  {
    id: 'glass',
    name: 'Glassmorphism',
    desc: 'شیشه‌ای، بلور، لایه‌ای',
    ready: true,
    supportsMode: false,
    swatch: ['#8A9BFF', '#22D3EE', '#0B1020'],
  },
  {
    id: 'cyberpunk',
    name: 'Cyberpunk',
    desc: 'ترمینال هک، اسکن‌لاین، رادار تهدید، نمودار مه‌آلود نئون',
    ready: true,
    supportsMode: false,
    swatch: ['#00FF9C', '#FF2E9A', '#050a08'],
  },
  {
    id: 'clay',
    name: 'Dawn Clay',
    desc: 'خمیریِ گرم، حجیم و دوستانه — کارت‌های بادکرده هلویی',
    ready: true,
    supportsMode: false,
    swatch: ['#F97316', '#FFF7ED', '#FB7185'],
  },
  {
    id: 'paper',
    name: 'Ink Paper',
    desc: 'سرمقاله‌ای مینیمال — کاغذ لوکس، خط مویی و فضای سفید',
    ready: true,
    supportsMode: false,
    swatch: ['#111827', '#FFFBF0', '#9CA3AF'],
  },
  {
    id: 'obsidian',
    name: 'Obsidian Signal',
    desc: 'ترمینال داده متراکم — مشکی AMOLED با سیگنال مونو',
    ready: true,
    supportsMode: false,
    swatch: ['#0AFF6B', '#000000', '#1A1A1A'],
  },
];
const DEFAULT_THEME = 'flat';

function loadTheme() {
  try {
    const t = JSON.parse(localStorage.getItem('sv-theme')) || {};
    return { theme: t.theme || DEFAULT_THEME, mode: t.mode || 'dark' };
  } catch (e) { return { theme: DEFAULT_THEME, mode: 'dark' }; }
}
function applyThemeChoice(themeId, mode) {
  const meta = THEMES.find(t => t.id === themeId) || THEMES[0];
  const finalTheme = meta.ready ? meta.id : DEFAULT_THEME;
  const finalMode = mode || 'dark';
  document.documentElement.setAttribute('data-theme', finalTheme);
  document.documentElement.setAttribute('data-mode', finalMode);
  localStorage.setItem('sv-theme', JSON.stringify({ theme: finalTheme, mode: finalMode }));
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
  resellers: '<rect x="2" y="7" width="20" height="14" rx="2.5"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>',
  panels: '<rect x="2" y="3" width="20" height="7" rx="2"></rect><rect x="2" y="14" width="20" height="7" rx="2"></rect><line x1="6" y1="6.5" x2="6.01" y2="6.5"></line><line x1="6" y1="17.5" x2="6.01" y2="17.5"></line>',
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
// بوم امبیانت شبکه‌ی سیگنال در کارت خوش‌آمدگویی (هاب اتصال VPN)
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
  if (!res.ok) throw new Error(formatApiError(data.detail));
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
  const url = `/api/${kind === 'order' ? 'orders' : 'topups'}/${id}/receipt`;
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
  { key: 'catalog', label: 'محصولات و بانک کانفیگ', icon: 'catalog', role: 'catalog', section: 'محصولات و بازاریابی' },
  { key: 'discounts', label: 'کدهای تخفیف', icon: 'discounts', role: 'discounts', section: 'محصولات و بازاریابی' },
  { key: 'broadcast', label: 'پیام همگانی', icon: 'broadcast', role: 'broadcast', section: 'محصولات و بازاریابی' },

  // شبکه و همکاران
  { key: 'resellers', label: 'نمایندگی‌ها', icon: 'resellers', role: 'resellers', section: 'شبکه و همکاران' },
  { key: 'panels', label: 'پنل‌های VPN', icon: 'panels', role: 'panels', section: 'شبکه و همکاران' },

  // تنظیمات و سیستم — همه‌ی موارد مرتبط با تنظیمات و نگهداری یک‌جا
  { key: 'settings', label: 'تنظیمات و برندینگ', icon: 'settings', role: 'settings', section: 'تنظیمات و سیستم' },
  { key: 'system', label: 'سیستم و نگهداری', icon: 'system', role: 'system', section: 'تنظیمات و سیستم' },
  { key: 'logs', label: 'لاگ فعالیت ادمین‌ها', icon: 'logs', role: 'system', section: 'تنظیمات و سیستم' },
  { key: 'webadmins', label: 'کاربران پنل', icon: 'webadmins', role: 'owner', section: 'تنظیمات و سیستم' },

  // حساب کاربری
  { key: 'account', label: 'حساب من', icon: 'account', role: 'any', section: 'حساب کاربری' },
];
function hasPerm(perm) {
  return ME.role === 'owner' || (ME.permissions || []).includes(perm);
}
function canSee(navRole) {
  if (navRole === 'resellers' && ME.tenant) return false;
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
function tenantParam() {
  return new URLSearchParams(location.search).get('b') || '';
}

async function boot() {
  if (location.pathname === '/setup') return boot_setup();
  try {
    ME = await apiGet('/me');
    showApp();
  } catch (e) {
    showLogin();
  }
}

async function boot_setup() {
  const b = tenantParam();
  const t = new URLSearchParams(location.search).get('t') || '';
  $('#login-screen').hidden = true;
  $('#app').hidden = true;
  $('#setup-screen').hidden = false;
  if (!b || !t) {
    $('#setup-subtitle').textContent = 'لینک ناقص است.';
    $('#setup-form').hidden = true;
    return;
  }
  try {
    const info = await fetch(`/api/setup/info?b=${encodeURIComponent(b)}&t=${encodeURIComponent(t)}`).then(async r => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(formatApiError(data.detail));
      return data;
    });
    $('#setup-subtitle').textContent = info.bot_username
      ? `پنل نمایندگی @${info.bot_username} - یک یوزرنیم و پسورد انتخاب کن`
      : 'یک یوزرنیم و پسورد برای پنل وب خودت انتخاب کن';
  } catch (e) {
    $('#setup-subtitle').textContent = e.message;
    $('#setup-form').hidden = true;
    return;
  }

  $('#setup-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = $('#setup-submit');
    const errBox = $('#setup-error');
    errBox.hidden = true;
    btn.disabled = true; btn.textContent = 'در حال ساخت حساب...';
    try {
      const res = await fetch('/api/setup', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          b, t,
          username: $('#setup-username').value.trim(),
          password: $('#setup-password').value,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(formatApiError(data.detail));
      ME = data;
      history.replaceState(null, '', `/?b=${encodeURIComponent(b)}`);
      $('#setup-screen').hidden = true;
      showApp();
    } catch (e) {
      errBox.textContent = e.message;
      errBox.hidden = false;
    } finally {
      btn.disabled = false; btn.textContent = 'ساخت حساب و ورود';
    }
  });
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
      b: tenantParam(),
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
      case 'resellers': return renderResellers();
      case 'panels': return renderPanels();
      case 'system': return renderSystem();
      case 'settings': return renderSettings();
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

async function renderDashboard() {
  const s = await apiGet('/dashboard');
  let sys = null;
  try { sys = await apiGet('/system/stats'); } catch (e) { /* psutil ممکن است نصب نباشد */ }
  const theme = loadTheme().theme;
  if (theme === 'bento') return renderDashboardBento(s, sys);
  if (theme === 'brutalist') return renderDashboardBrutalist(s, sys);
  if (theme === 'glass') return renderDashboardGlass(s, sys);
  if (theme === 'cyberpunk') return renderDashboardCyberpunk(s, sys);
  if (theme === 'clay') return renderDashboardClay(s, sys);
  if (theme === 'paper') return renderDashboardPaper(s, sys);
  if (theme === 'obsidian') return renderDashboardObsidian(s, sys);
  return renderDashboardFlat(s, sys);
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
function renderDashboardGlass(s, sys) {
  const glassColors = ['#8B5CF6', '#22D3EE', '#34D399', '#FBBF24', '#FB7185', '#EC4899'];
  const resHtml = sys ? `
    <div class="res-grid">
      ${resRingHtml(sys.cpu.percent, 'var(--violet)', 'پردازنده (CPU)', `${sys.cpu.cores} هسته`)}
      ${resRingHtml(sys.ram.percent, 'var(--amber)', 'حافظه رم (RAM)', `${sys.ram.used_gb} از ${sys.ram.total_gb} گیگابایت`)}
      ${resRingHtml(sys.disk.percent, 'var(--cyan)', 'فضای دیسک', `${sys.disk.used_gb} از ${sys.disk.total_gb} گیگابایت`)}
    </div>` : '';
  const eqBars = s.daily_series.map((d, i) => {
    const max = Math.max(...s.daily_series.map(x => x.revenue), 1);
    return `<i data-h="${Math.max((d.revenue / max) * 100, 6)}" title="${d.date}: ${fmt(d.revenue)} تومان" style="--c:${glassColors[i % glassColors.length]}"></i>`;
  }).join('');

  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const dials = [
    { label: 'نرخ تبدیل', pct: s.conversion_rate, color: '#22D3EE' },
    { label: 'سلامت سرور', pct: sys ? Math.max(0, 100 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 3) : 80, color: '#34D399' },
    { label: 'نسبت تیکت', pct: s.active_configs ? Math.min(Math.round((s.open_tickets / s.active_configs) * 100), 100) : 0, color: '#FB7185' },
  ];
  const dialHtml = dials.map(d => {
    const c = 2 * Math.PI * 40;
    const off = c - Math.max(0, Math.min(100, d.pct)) / 100 * c;
    return `
    <div class="glass-dial">
      <svg viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="8"/>
        <circle cx="50" cy="50" r="40" fill="none" stroke="${d.color}" stroke-width="8" stroke-linecap="round"
          stroke-dasharray="${c}" stroke-dashoffset="${c}" data-final="${off}" transform="rotate(-90 50 50)"
          class="glass-dial-seg" style="filter:drop-shadow(0 0 6px ${d.color}aa)"/>
      </svg>
      <div class="glass-dial-center"><span class="mono">${fmt(Math.round(d.pct))}٪</span></div>
      <span class="glass-dial-label">${d.label}</span>
    </div>`;
  }).join('');

  const catData = s.category_breakdown.map(c => ({ label: c.name, value: c.revenue }));
  const totalCat = catData.reduce((a, b) => a + b.value, 0);
  const donut = donutSegments(90, 90, 68, catData, glassColors, 20);
  const catLegend = s.category_breakdown.map((c, i) => `
    <span class="glass-legend-item"><i style="background:${glassColors[i % glassColors.length]}"></i>${esc(c.name)}<b class="mono">${fmt(c.revenue)}</b></span>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  const prodRows = s.top_products.map((p, i) => `
    <div class="glass-row">
      <span class="glass-row-badge" style="--c:${glassColors[i % glassColors.length]}">${i + 1}</span>
      <span class="glass-row-name">${esc(p.name)}</span>
      <span class="glass-row-val mono">${fmt(p.orders)} فروش</span>
    </div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  setContent(`
    <div class="hero">
      <div class="hero-text">
        <h2>${greetingByHour()}، ${esc(ME.username)} ✨</h2>
        <p>وضعیت فروشگاه در ${s.start_date} تا ${s.end_date}</p>
      </div>
      <div class="hero-net"><canvas id="hero-net-canvas"></canvas></div>
    </div>

    ${resHtml}
    <div class="grid grid-4">
      <div class="card glass-stat">
        <span class="glass-stat-label">درآمد (۱۴ روز)</span>
        <span class="value mono" data-count="${s.revenue}">۰</span>
        <span class="glass-stat-tag ${deltaUp ? 'up' : 'down'}">${deltaUp ? '▲' : '▼'} ${Math.abs(s.revenue_change_pct ?? 0)}٪</span>
      </div>
      <div class="card glass-stat">
        <span class="glass-stat-label">سفارش تایید شده</span>
        <span class="value mono" data-count="${s.approved}">۰</span>
      </div>
      <div class="card glass-stat">
        <span class="glass-stat-label">کاربران کل</span>
        <span class="value mono" data-count="${s.total_users}">۰</span>
      </div>
      <div class="card glass-stat">
        <span class="glass-stat-label">کانفیگ فعال</span>
        <span class="value mono" data-count="${s.active_configs}">۰</span>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h3>روند فروش روزانه</h3><span class="card-sub">${s.start_date} تا ${s.end_date}</span></div>
      <div class="glass-eq">${eqBars}</div>
    </div>

    <div class="grid grid-2" style="margin-top:16px; align-items:stretch">
      <div class="card">
        <div class="card-head"><h3>شاخص‌های کلیدی</h3></div>
        <div class="glass-dials">${dialHtml}</div>
      </div>
      <div class="card">
        <div class="card-head"><h3>تفکیک درآمد</h3></div>
        <div class="glass-donut-wrap">
          <svg viewBox="0 0 180 180">${donut}</svg>
          <div class="glass-donut-center"><span class="mono">${fmt(totalCat)}</span><small>مجموع</small></div>
        </div>
        <div class="glass-legend">${catLegend}</div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h3>پرفروش‌ترین محصولات</h3></div>
      ${prodRows}
    </div>

    <div style="margin-top:16px">${serverMapCardHtml()}</div>
  `);

  const root = content();
  $$('.value[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  drawHeroNet($('#hero-net-canvas', root));
  requestAnimationFrame(() => setTimeout(() => {
    $$('.glass-eq i[data-h]', root).forEach(b => { b.style.height = b.dataset.h + '%'; });
    $$('.glass-dial-seg', root).forEach(seg => {
      seg.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(.16,1,.3,1)';
      seg.style.strokeDashoffset = seg.dataset.final;
    });
  }, 60));
  mountServerMap();
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
  const cpColors = ['#00FF9C', '#FF2E9A', '#39FF14', '#00E5FF', '#FF5F5F'];
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const trend = cyberSmoothPath(s.daily_series.map(d => d.revenue), 300, 110, 8);

  const blips = Array.from({ length: 6 }, (_, i) => {
    const ang = (i / 6) * Math.PI * 2 + 0.4;
    const rr = 30 + (i % 3) * 10;
    return `<circle class="cp-radar-blip" cx="${60 + Math.cos(ang) * rr}" cy="${60 + Math.sin(ang) * rr}" r="2" style="animation-delay:${i * .4}s"/>`;
  }).join('');

  const resHtml = sys ? `
    <div class="cp-panel" style="margin-top:16px">
      <div class="cp-panel-head"><span>&gt; منابع سرور</span><span class="cp-cursor"></span></div>
      <div class="cp-res-grid">
        <div class="cp-res-item"><span>CPU</span><div class="cp-res-track"><span class="cp-res-fill" data-w="${sys.cpu.percent}" style="background:#00FF9C;box-shadow:0 0 8px #00FF9C"></span></div><b class="mono">${sys.cpu.percent}٪</b></div>
        <div class="cp-res-item"><span>RAM</span><div class="cp-res-track"><span class="cp-res-fill" data-w="${sys.ram.percent}" style="background:#FF2E9A;box-shadow:0 0 8px #FF2E9A"></span></div><b class="mono">${sys.ram.percent}٪</b></div>
        <div class="cp-res-item"><span>DISK</span><div class="cp-res-track"><span class="cp-res-fill" data-w="${sys.disk.percent}" style="background:#00E5FF;box-shadow:0 0 8px #00E5FF"></span></div><b class="mono">${sys.disk.percent}٪</b></div>
      </div>
    </div>` : '';

  const gauges = [
    { label: 'نرخ تبدیل', pct: s.conversion_rate, color: '#00FF9C' },
    { label: 'سلامت سرور', pct: sys ? Math.max(0, 100 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 3) : 80, color: '#00E5FF' },
    { label: 'ریسک تیکت', pct: s.active_configs ? Math.min(Math.round((s.open_tickets / s.active_configs) * 100), 100) : 0, color: '#FF2E9A' },
  ];
  const gaugeHtml = gauges.map(g => `
    <div class="cp-gauge">
      <svg viewBox="0 0 100 100">${cyberArc(50, 50, 40, g.pct, g.color, 7)}</svg>
      <div class="cp-gauge-val mono">${fmt(Math.round(g.pct))}<small>٪</small></div>
      <span class="cp-gauge-label">${g.label}</span>
    </div>`).join('');

  const maxCat = Math.max(...s.category_breakdown.map(c => c.revenue), 1);
  const barsHtml = s.category_breakdown.map((c, i) => `
    <div class="cp-bar-row">
      <span class="cp-bar-name">${esc(c.name)}</span>
      <div class="cp-bar-track"><span class="cp-bar-fill" data-w="${(c.revenue / maxCat) * 100}" style="--c:${cpColors[i % cpColors.length]}"></span></div>
      <b class="mono cp-bar-val">${fmt(c.revenue)}</b>
    </div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  const logHtml = s.top_products.map((p, i) => `
    <div class="cp-log-row">
      <span class="mono cp-log-idx">[${String(i + 1).padStart(2, '0')}]</span>
      <span class="cp-log-name">${esc(p.name)}</span>
      <span class="mono cp-log-val">${fmt(p.orders)} فروش</span>
    </div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  setContent(`
    <div class="cp-hero">
      <div class="cp-hero-text">
        <span class="cp-tag">// SYSTEM_ONLINE :: ${s.start_date} → ${s.end_date}</span>
        <h2 class="cp-glitch" data-text="${greetingByHour()}، ${esc(ME.username)}">${greetingByHour()}، ${esc(ME.username)}</h2>
        <p>وضعیت شبکه فروش تحت پایش قرار دارد</p>
      </div>
      <div class="cp-radar">
        <svg viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" class="cp-radar-ring"/>
          <circle cx="60" cy="60" r="34" class="cp-radar-ring"/>
          <circle cx="60" cy="60" r="16" class="cp-radar-ring"/>
          <line x1="60" y1="8" x2="60" y2="112" class="cp-radar-cross"/>
          <line x1="8" y1="60" x2="112" y2="60" class="cp-radar-cross"/>
          ${blips}
          <line x1="60" y1="60" x2="60" y2="8" class="cp-radar-sweep"/>
        </svg>
        <span class="cp-radar-label">SCAN</span>
      </div>
    </div>

    <div class="grid grid-4">
      <div class="cp-panel cp-stat">
        <span class="cp-stat-label">&gt; درآمد (۱۴ روز)</span>
        <span class="cp-stat-val mono" data-count="${s.revenue}">۰</span>
        <span class="cp-stat-tag ${deltaUp ? 'up' : 'down'}">${deltaUp ? '▲' : '▼'} ${Math.abs(s.revenue_change_pct ?? 0)}٪</span>
      </div>
      <div class="cp-panel cp-stat">
        <span class="cp-stat-label">&gt; سفارش تایید شده</span>
        <span class="cp-stat-val mono" data-count="${s.approved}">۰</span>
      </div>
      <div class="cp-panel cp-stat">
        <span class="cp-stat-label">&gt; کاربران کل</span>
        <span class="cp-stat-val mono" data-count="${s.total_users}">۰</span>
      </div>
      <div class="cp-panel cp-stat">
        <span class="cp-stat-label">&gt; کانفیگ فعال</span>
        <span class="cp-stat-val mono" data-count="${s.active_configs}">۰</span>
      </div>
    </div>

    <div class="cp-panel cp-chart-panel" style="margin-top:16px">
      <div class="cp-panel-head"><span>&gt; روند فروش روزانه</span><span class="cp-cursor"></span></div>
      <div class="cp-chart-wrap">
        <svg viewBox="0 0 300 110" preserveAspectRatio="none" class="cp-fog-svg">
          <defs>
            <filter id="cpFog1" x="-30%" y="-60%" width="160%" height="220%">
              <feGaussianBlur stdDeviation="7"/>
            </filter>
            <filter id="cpFog2" x="-30%" y="-60%" width="160%" height="220%">
              <feGaussianBlur stdDeviation="14"/>
            </filter>
            <linearGradient id="cpFogFillG" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#00FF9C" stop-opacity=".55"/>
              <stop offset="100%" stop-color="#00FF9C" stop-opacity="0"/>
            </linearGradient>
            <linearGradient id="cpFogFillP" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#FF2E9A" stop-opacity=".4"/>
              <stop offset="100%" stop-color="#FF2E9A" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <path d="${trend.area}" fill="url(#cpFogFillP)" filter="url(#cpFog2)" transform="translate(0,4)"/>
          <path d="${trend.area}" fill="url(#cpFogFillG)" filter="url(#cpFog1)"/>
          <path d="${trend.line}" fill="none" stroke="#00FF9C" stroke-width="1.6" style="filter:drop-shadow(0 0 6px #00FF9C)"/>
        </svg>
        <div class="cp-scanline"></div>
      </div>
    </div>

    <div class="grid grid-2" style="margin-top:16px; align-items:stretch">
      <div class="cp-panel">
        <div class="cp-panel-head"><span>&gt; شاخص‌های کلیدی</span><span class="cp-cursor"></span></div>
        <div class="cp-gauges">${gaugeHtml}</div>
      </div>
      <div class="cp-panel">
        <div class="cp-panel-head"><span>&gt; تفکیک درآمد</span><span class="cp-cursor"></span></div>
        <div class="cp-bars">${barsHtml}</div>
      </div>
    </div>

    <div class="cp-panel" style="margin-top:16px">
      <div class="cp-panel-head"><span>&gt; پرفروش‌ترین محصولات</span><span class="cp-cursor"></span></div>
      <div class="cp-log">${logHtml}</div>
    </div>

    ${resHtml}

    <div style="margin-top:16px">${serverMapCardHtml()}</div>
  `);

  const root = content();
  $$('.cp-stat-val[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  requestAnimationFrame(() => setTimeout(() => {
    $$('.cp-gauge-seg', root).forEach(seg => {
      seg.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.16,1,.3,1)';
      seg.style.strokeDashoffset = seg.dataset.final;
    });
    $$('.cp-res-fill[data-w], .cp-bar-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
  }, 60));
  mountServerMap();
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
    { label: 'نسبت تیکت باز', pct: s.active_configs ? Math.min(Math.round((s.open_tickets / s.active_configs) * 100), 100) : 0, color: '#FF3B3B' },
    { label: 'ظرفیت کانفیگ', pct: Math.min(Math.round((s.active_configs / Math.max(s.total_users, 1)) * 100), 100), color: '#FF3EA5' },
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
      <p>${s.start_date} تا ${s.end_date}</p>
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
        <span class="bru-block-label">کانفیگ فعال / تیکت باز</span>
        <span class="bru-block-val mono" data-count="${s.active_configs}">۰</span>
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

    <div style="margin-top:16px">${serverMapCardHtml()}</div>
  `);

  const root = content();
  $$('.bru-block-val[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  requestAnimationFrame(() => setTimeout(() => {
    $$('.bru-bar[data-h]', root).forEach(b => { b.style.height = b.dataset.h + '%'; });
    $$('.bru-metric-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
    $$('.bru-res-fill[data-w]', root).forEach(b => { b.style.width = b.dataset.w + '%'; });
  }, 60));
  mountServerMap();
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
    { pct: s.active_configs ? Math.min(Math.round((s.open_tickets / s.active_configs) * 100), 100) : 0, color: 'var(--rose)', label: 'تیکت' },
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
        <span class="bw-label">کانفیگ فعال</span>
        <span class="bw-value mono" data-count="${s.active_configs}">۰</span>
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

    ${serverMapCardHtml()}
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
  mountServerMap();
}

/* ----------------------------------------------------- dashboard: flat --- */
async function renderDashboardFlat(s, sys) {
  const maxRev = Math.max(...s.daily_series.map(d => d.revenue), 1);
  const spark = s.daily_series.map(d => `<i data-h="${Math.max((d.revenue / maxRev) * 100, 3)}" title="${d.date}: ${fmt(d.revenue)} تومان"></i>`).join('');
  const deltaCls = (s.revenue_change_pct ?? 0) >= 0 ? 'up' : 'down';
  const deltaSign = (s.revenue_change_pct ?? 0) >= 0 ? '▲' : '▼';
  const ticketRatio = s.active_configs ? Math.min(Math.round((s.open_tickets / s.active_configs) * 100), 100) : 0;

  const resHtml = sys ? `
    <div class="res-grid">
      ${resRingHtml(sys.cpu.percent, 'var(--violet)', 'پردازنده (CPU)', `${sys.cpu.cores} هسته`)}
      ${resRingHtml(sys.ram.percent, 'var(--amber)', 'حافظه رم (RAM)', `${sys.ram.used_gb} از ${sys.ram.total_gb} گیگابایت`)}
      ${resRingHtml(sys.disk.percent, 'var(--cyan)', 'فضای دیسک', `${sys.disk.used_gb} از ${sys.disk.total_gb} گیگابایت`)}
    </div>` : '';

  // امتیاز سلامت سیستم = میانگین معکوس مصرف CPU/RAM/دیسک
  const healthPct = sys ? Math.round(100 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 3) : null;
  const healthLabel = healthPct === null ? '—' : healthPct >= 80 ? 'سالم' : healthPct >= 50 ? 'قابل‌قبول' : 'نیازمند بررسی';
  const healthColor = healthPct === null ? 'var(--text-muted)' : healthPct >= 80 ? 'var(--emerald)' : healthPct >= 50 ? 'var(--amber)' : 'var(--rose)';

  // نوارهای تفکیک درآمد (از category_breakdown واقعی)
  const maxCatRev = Math.max(...s.category_breakdown.map(c => c.revenue), 1);
  const catColors = ['var(--violet)', 'var(--cyan)', 'var(--emerald)', 'var(--amber)', 'var(--rose)', 'var(--fuchsia)'];
  const catBars = s.category_breakdown.map((c, i) => `
    <div class="bar-row">
      <span class="bar-name">${esc(c.name)}</span>
      <span class="bar-track"><span class="bar-fill" data-w="${(c.revenue / maxCatRev) * 100}" style="background:${catColors[i % catColors.length]}"></span></span>
      <span class="bar-val">${fmt(c.revenue)} (${fmt(c.orders)})</span>
    </div>`).join('') || '<span class="card-sub">داده‌ای برای این بازه نیست</span>';

  // لیدربورد پرفروش‌ترین محصولات (از top_products واقعی)
  const maxProdRev = Math.max(...s.top_products.map(p => p.revenue), 1);
  const prodBars = s.top_products.map((p, i) => `
    <div class="bar-row">
      <span class="bar-name">${esc(p.name)}</span>
      <span class="bar-track"><span class="bar-fill" data-w="${(p.revenue / maxProdRev) * 100}" style="background:${catColors[i % catColors.length]}"></span></span>
      <span class="bar-val">${fmt(p.orders)} فروش</span>
    </div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';

  // مقادیر رادار (۰..۱) از شاخص‌های واقعی داشبورد و سرور
  const radarAxes = ['فروش', 'رضایت مشتری', 'سلامت سرور', 'ظرفیت', 'رشد'];
  const radarValues = [
    Math.max(0, Math.min(s.conversion_rate / 100, 1)),
    1 - Math.min(s.open_tickets / Math.max(s.active_configs, 1), 1),
    sys ? Math.max(0, Math.min(1 - (sys.cpu.percent + sys.ram.percent + sys.disk.percent) / 300, 1)) : 0.8,
    Math.max(0, Math.min(s.active_configs / Math.max(s.total_users, 1), 1)),
    Math.max(0, Math.min((s.revenue_change_pct ?? 0) / 100 + 0.5, 1)),
  ];

  setContent(`
    ${resHtml}
    <div class="hero">
      <div class="hero-text">
        <h2>${greetingByHour()}، ${esc(ME.username)} 👋</h2>
        <p>وضعیت فروشگاه در ${s.start_date} تا ${s.end_date} — همه چیز آنلاین و در حال گزارش‌دهی زنده است.</p>
      </div>
      <div class="hero-net"><canvas id="hero-net-canvas"></canvas></div>
    </div>

    <div class="grid grid-4">
      <div class="card stat-card">
        <div class="stat-top">
          <span class="stat-icon stat-icon-1">${svg('revenue')}</span>
          <span class="delta ${deltaCls} mono">${deltaSign} ${Math.abs(s.revenue_change_pct ?? 0)}%</span>
        </div>
        <span class="value mono" data-count="${s.revenue}">۰</span>
        <span class="label">درآمد (۱۴ روز اخیر)</span>
      </div>
      <div class="card stat-card">
        <div class="stat-top">
          <span class="stat-icon stat-icon-2">${svg('check')}</span>
          <div class="ring" style="--ring-a:var(--cyan)" data-pct="${s.conversion_rate}"><span>${s.conversion_rate}٪</span></div>
        </div>
        <span class="value mono" data-count="${s.approved}">۰</span>
        <span class="label">سفارش‌های تایید شده · نرخ تبدیل</span>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span class="stat-icon stat-icon-3">${svg('users')}</span></div>
        <span class="value mono" data-count="${s.total_users}">۰</span>
        <span class="label">کاربران کل</span>
        <span class="card-sub">${fmt(s.new_users)} کاربر جدید در این بازه</span>
      </div>
      <div class="card stat-card">
        <div class="stat-top">
          <span class="stat-icon stat-icon-4">${svg('tickets')}</span>
          <div class="ring" style="--ring-a:var(--rose)" data-pct="${ticketRatio}"><span>${fmt(s.open_tickets)}</span></div>
        </div>
        <span class="value mono" data-count="${s.active_configs}">۰</span>
        <span class="label">کانفیگ فعال · تیکت باز</span>
      </div>
    </div>

    <div class="bento" style="margin-top:18px">
      <div class="card span-4 rows-2">
        <div class="card-head"><h3>روند فروش روزانه</h3><span class="card-sub">${s.start_date} تا ${s.end_date}</span></div>
        <div class="spark" style="flex:1">${spark}</div>
      </div>

      ${sys ? `
      <div class="card span-2 rows-2">
        <div class="card-head"><h3>امتیاز سلامت سیستم</h3></div>
        <div class="gauge-wrap">
          <svg viewBox="0 0 150 150">
            <circle cx="75" cy="75" r="64" fill="none" stroke="var(--border)" stroke-width="11"/>
            <circle id="gaugeRing" cx="75" cy="75" r="64" fill="none" stroke="${healthColor}" stroke-width="11" stroke-linecap="round"/>
          </svg>
          <div class="gauge-center"><div class="v mono">${healthPct}٪</div><div class="l">${healthLabel}</div></div>
        </div>
      </div>` : `
      <div class="card span-2 rows-2">
        <div class="card-head"><h3>رادار عملکرد</h3></div>
        <div class="radar-wrap"><svg id="radarChart" viewBox="0 0 220 190"></svg></div>
      </div>`}

      <div class="card ${sys ? 'span-3' : 'span-4'}">
        <div class="card-head"><h3>تفکیک درآمد</h3></div>
        <div class="chip-row" style="margin-bottom:10px"><span class="chip">مستقیم: ${fmt(s.direct_revenue)}</span><span class="chip">رفرال: ${fmt(s.referral_revenue)}</span></div>
        ${catBars}
      </div>

      ${sys ? `
      <div class="card span-3">
        <div class="card-head"><h3>رادار عملکرد</h3></div>
        <div class="radar-wrap"><svg id="radarChart" viewBox="0 0 220 190"></svg></div>
      </div>` : ''}

      <div class="card span-3">
        <div class="card-head"><h3>پرفروش‌ترین محصولات</h3></div>
        ${prodBars}
      </div>
    </div>

    ${serverMapCardHtml()}
  `);

  const root = content();
  $$('.value[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  activateRings(root);
  activateBars(root);
  activateBarFills(root);
  drawRadar(root, radarAxes, radarValues, '#8B5CF6');
  if (sys) activateGauge(root, healthPct);
  drawHeroNet($('#hero-net-canvas', root));
  mountServerMap();
}


/* ------------------------------------------------------ dashboard: clay --- */
function renderDashboardClay(s, sys){
  const clayColors = ['#F97316','#FB923C','#FBBF24','#10B981','#EC4899','#06B6D4'];
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const maxRev = Math.max(...s.daily_series.map(d=>d.revenue),1);
  const bars = s.daily_series.map((d,i)=>`<div class="clay-bar" data-h="${Math.max((d.revenue/maxRev)*100,6)}" title="${d.date}: ${fmt(d.revenue)}" style="background:${clayColors[i%clayColors.length]}"></div>`).join('');
  const totalCat = s.category_breakdown.reduce((a,b)=>a+b.revenue,0)||1;
  const donut = donutSegments(70,70,52, s.category_breakdown.map(c=>({value:c.revenue})), clayColors, 16);
  const legend = s.category_breakdown.map((c,i)=>`<span class="clay-legend-item"><i style="background:${clayColors[i%clayColors.length]}"></i>${esc(c.name)}<b class="mono">${fmt(c.revenue)}</b></span>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';
  const prodRows = s.top_products.map((p,i)=>`<div class="clay-row"><span class="clay-row-num" style="background:${clayColors[i%clayColors.length]}">${i+1}</span><span class="clay-row-name">${esc(p.name)}</span><span class="mono" style="font-size:12px;color:var(--text-muted)">${fmt(p.orders)} فروش</span></div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';
  const resHtml = sys ? `<div class="clay-res-grid" style="margin-bottom:16px"><div class="clay-res-card" style="background:#FFF7ED"><span class="clay-stat-label">CPU</span><b class="mono" style="font-size:20px">${sys.cpu.percent}٪</b><span class="clay-res-track"><span class="clay-res-fill" data-w="${sys.cpu.percent}" style="background:#F97316"></span></span><span style="font-size:11px;color:var(--text-muted)">${sys.cpu.cores} هسته</span></div><div class="clay-res-card" style="background:#FFFBEB"><span class="clay-stat-label">RAM</span><b class="mono" style="font-size:20px">${sys.ram.percent}٪</b><span class="clay-res-track"><span class="clay-res-fill" data-w="${sys.ram.percent}" style="background:#F59E0B"></span></span><span style="font-size:11px;color:var(--text-muted)">${sys.ram.used_gb}/${sys.ram.total_gb} گیگ</span></div><div class="clay-res-card" style="background:#ECFDF5"><span class="clay-stat-label">DISK</span><b class="mono" style="font-size:20px">${sys.disk.percent}٪</b><span class="clay-res-track"><span class="clay-res-fill" data-w="${sys.disk.percent}" style="background:#10B981"></span></span><span style="font-size:11px;color:var(--text-muted)">${sys.disk.used_gb}/${sys.disk.total_gb} گیگ</span></div></div>` : '';
  setContent(`
    <div class="clay-hero"><div><h2>${greetingByHour()}، ${esc(ME.username)} ☀️</h2><p>${s.start_date} تا ${s.end_date} — روزی گرم و پر از فروش!</p></div><div class="clay-hero-orb"></div></div>
    ${resHtml}
    <div class="grid grid-4">
      <div class="card clay-stat"><span class="clay-stat-label">درآمد ۱۴ روز</span><span class="clay-stat-val mono" data-count="${s.revenue}">۰</span><span class="clay-pill ${deltaUp?'up':'down'}">${deltaUp?'▲':'▼'} ${Math.abs(s.revenue_change_pct??0)}٪</span></div>
      <div class="card clay-stat"><span class="clay-stat-label">سفارش تایید شده</span><span class="clay-stat-val mono" data-count="${s.approved}">۰</span></div>
      <div class="card clay-stat"><span class="clay-stat-label">کاربران کل</span><span class="clay-stat-val mono" data-count="${s.total_users}">۰</span><span style="font-size:11px;color:var(--text-muted)">${fmt(s.new_users)} جدید</span></div>
      <div class="card clay-stat"><span class="clay-stat-label">کانفیگ فعال</span><span class="clay-stat-val mono" data-count="${s.active_configs}">۰</span></div>
    </div>
    <div class="card" style="margin-top:16px"><div class="clay-card-head">روند فروش روزانه</div><div class="clay-bars">${bars}</div></div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="card"><div class="clay-card-head">تفکیک درآمد</div><div class="clay-donut-wrap"><svg viewBox="0 0 140 140">${donut}</svg><div class="clay-legend">${legend}</div></div></div>
      <div class="card"><div class="clay-card-head">پرفروش‌ترین‌ها</div>${prodRows}</div>
    </div>
    <div style="margin-top:16px">${serverMapCardHtml()}</div>
  `);
  const root2 = content();
  $$('.clay-stat-val[data-count]',root2).forEach(el=>animateCount(el,Number(el.dataset.count)));
  requestAnimationFrame(()=>setTimeout(()=>{
    $$('.clay-bar[data-h]',root2).forEach(b=>{ b.style.height=b.dataset.h+'%'; });
    $$('.clay-res-fill[data-w]',root2).forEach(b=>{ b.style.width=b.dataset.w+'%'; });
  },60));
  mountServerMap();
}

/* ----------------------------------------------------- dashboard: paper --- */
function renderDashboardPaper(s, sys){
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const maxRev = Math.max(...s.daily_series.map(d=>d.revenue),1);
  const spark = s.daily_series.map(d=>`<i data-h="${Math.max((d.revenue/maxRev)*100,4)}" title="${d.date}: ${fmt(d.revenue)}"></i>`).join('');
  const maxCat = Math.max(...s.category_breakdown.map(c=>c.revenue),1);
  const catRows = s.category_breakdown.map(c=>`<div class="paper-row"><span class="paper-row-name">${esc(c.name)}</span><span class="paper-row-bar"><span class="paper-row-fill" data-w="${(c.revenue/maxCat)*100}"></span></span><b class="mono" style="font-size:11.5px">${fmt(c.revenue)}</b></div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';
  const prodRows = s.top_products.map(p=>`<div class="paper-row"><span class="paper-row-name">${esc(p.name)}</span><span class="mono" style="font-size:11.5px;color:var(--text-muted)">${fmt(p.orders)} فروش</span></div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';
  const resHtml = sys ? `<div class="paper-res-grid" style="margin-bottom:16px"><div class="paper-res-card"><span class="paper-res-label">CPU</span><span class="paper-res-val mono">${sys.cpu.percent}٪</span><span style="font-size:11px;color:var(--text-muted)">${sys.cpu.cores} هسته</span></div><div class="paper-res-card"><span class="paper-res-label">RAM</span><span class="paper-res-val mono">${sys.ram.percent}٪</span><span style="font-size:11px;color:var(--text-muted)">${sys.ram.used_gb}/${sys.ram.total_gb} گیگ</span></div><div class="paper-res-card"><span class="paper-res-label">DISK</span><span class="paper-res-val mono">${sys.disk.percent}٪</span><span style="font-size:11px;color:var(--text-muted)">${sys.disk.used_gb}/${sys.disk.total_gb} گیگ</span></div></div>` : '';
  setContent(`
    <div class="paper-hero"><h2>${greetingByHour()}، ${esc(ME.username)}</h2><p>گزارش فروش ${s.start_date} تا ${s.end_date}</p><div class="paper-hero-meta"><span>${fmt(s.revenue)} تومان درآمد</span><span>·</span><span>${fmt(s.approved)} سفارش</span><span>·</span><span>${fmt(s.total_users)} کاربر</span></div><div class="paper-hero-rule"></div></div>
    ${resHtml}
    <div class="paper-stats">
      <div class="paper-stat"><span class="paper-stat-label">درآمد ۱۴ روز</span><span class="paper-stat-val mono" data-count="${s.revenue}">۰</span><span class="paper-delta ${deltaUp?'up':'down'}">${deltaUp?'▲':'▼'} ${Math.abs(s.revenue_change_pct??0)}٪ نسبت به قبل</span></div>
      <div class="paper-stat"><span class="paper-stat-label">سفارش تایید شده</span><span class="paper-stat-val mono" data-count="${s.approved}">۰</span><span class="paper-stat-sub">${s.conversion_rate}٪ نرخ تبدیل</span></div>
      <div class="paper-stat"><span class="paper-stat-label">کاربران کل</span><span class="paper-stat-val mono" data-count="${s.total_users}">۰</span><span class="paper-stat-sub">${fmt(s.new_users)} جدید در این بازه</span></div>
      <div class="paper-stat"><span class="paper-stat-label">کانفیگ فعال</span><span class="paper-stat-val mono" data-count="${s.active_configs}">۰</span><span class="paper-stat-sub">${fmt(s.open_tickets)} تیکت باز</span></div>
    </div>
    <div class="paper-panel" style="margin-top:16px"><div class="paper-panel-head">روند فروش روزانه — ${s.start_date} تا ${s.end_date}</div><div class="paper-spark">${spark}</div></div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="paper-panel"><div class="paper-panel-head">تفکیک درآمد</div>${catRows}</div>
      <div class="paper-panel"><div class="paper-panel-head">پرفروش‌ترین محصولات</div>${prodRows}</div>
    </div>
    <div style="margin-top:16px">${serverMapCardHtml()}</div>
  `);
  const root2 = content();
  $$('.paper-stat-val[data-count]',root2).forEach(el=>animateCount(el,Number(el.dataset.count)));
  requestAnimationFrame(()=>setTimeout(()=>{
    $$('.paper-spark i[data-h]',root2).forEach(b=>{ b.style.height=b.dataset.h+'%'; });
    $$('.paper-row-fill[data-w]',root2).forEach(b=>{ b.style.width=b.dataset.w+'%'; });
  },60));
  mountServerMap();
}

/* -------------------------------------------------- dashboard: obsidian --- */
function renderDashboardObsidian(s, sys){
  const deltaUp = (s.revenue_change_pct ?? 0) >= 0;
  const maxRev = Math.max(...s.daily_series.map(d=>d.revenue),1);
  const bars = s.daily_series.map(d=>`<div class="obs-bar" data-h="${Math.max((d.revenue/maxRev)*100,4)}" title="${d.date}: ${fmt(d.revenue)}"></div>`).join('');
  const meters = [
    {label:'نرخ تبدیل', pct:s.conversion_rate},
    {label:'سلامت سرور', pct: sys ? Math.max(0,100-(sys.cpu.percent+sys.ram.percent+sys.disk.percent)/3) : 80},
    {label:'تیکت باز', pct: s.active_configs ? Math.min(Math.round((s.open_tickets/s.active_configs)*100),100) : 0},
  ];
  const meterHtml = meters.map(m=>`<div class="obs-meter"><span class="obs-meter-label">${m.label}</span><span class="obs-meter-track"><span class="obs-meter-fill" data-w="${m.pct}" style="background:var(--emerald)"></span></span><span class="obs-meter-val mono">${fmt(Math.round(m.pct))}٪</span></div>`).join('');
  const prodRows = s.top_products.map((p,i)=>`<tr><td class="mono" style="color:var(--emerald)">${String(i+1).padStart(2,'0')}</td><td>${esc(p.name)}</td><td class="mono">${fmt(p.orders)}</td></tr>`).join('') || `<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">داده‌ای نیست</td></tr>`;
  const catRows = s.category_breakdown.map(c=>`<div class="obs-meter"><span class="obs-meter-label">${esc(c.name)}</span><span class="obs-meter-track"><span class="obs-meter-fill" data-w="${(c.revenue/Math.max(...s.category_breakdown.map(x=>x.revenue),1))*100}" style="background:var(--text-muted)"></span></span><b class="mono" style="font-size:11px">${fmt(c.revenue)}</b></div>`).join('') || '<span class="card-sub">داده‌ای نیست</span>';
  const resHtml = sys ? `<div class="obs-res-grid" style="margin-bottom:14px"><div class="obs-res-card"><span class="obs-res-label">CPU</span><span class="obs-res-val mono">${sys.cpu.percent}٪</span><span class="obs-meter-track"><span class="obs-meter-fill" data-w="${sys.cpu.percent}" style="background:var(--emerald)"></span></span><span class="mono" style="font-size:10.5px;color:var(--text-muted)">${sys.cpu.cores} cores</span></div><div class="obs-res-card"><span class="obs-res-label">RAM</span><span class="obs-res-val mono">${sys.ram.percent}٪</span><span class="obs-meter-track"><span class="obs-meter-fill" data-w="${sys.ram.percent}" style="background:var(--amber)"></span></span><span class="mono" style="font-size:10.5px;color:var(--text-muted)">${sys.ram.used_gb}/${sys.ram.total_gb} GB</span></div><div class="obs-res-card"><span class="obs-res-label">DISK</span><span class="obs-res-val mono">${sys.disk.percent}٪</span><span class="obs-meter-track"><span class="obs-meter-fill" data-w="${sys.disk.percent}" style="background:var(--text-muted)"></span></span><span class="mono" style="font-size:10.5px;color:var(--text-muted)">${sys.disk.used_gb}/${sys.disk.total_gb} GB</span></div></div>` : '';
  setContent(`
    <div class="obs-hero"><div><span class="obs-hero-tag">● SYSTEM ONLINE — ${s.start_date} → ${s.end_date}</span><h2>${greetingByHour()}، ${esc(ME.username)}</h2><p>${fmt(s.revenue)} تومان · ${fmt(s.approved)} سفارش · ${fmt(s.total_users)} کاربر</p></div></div>
    ${resHtml}
    <div class="obs-grid4">
      <div class="obs-stat accent"><span class="obs-stat-label">Revenue / 14d</span><span class="obs-stat-val mono" data-count="${s.revenue}">۰</span><span class="obs-stat-sub" style="color:${deltaUp?'var(--emerald)':'var(--rose)'}">${deltaUp?'▲':'▼'} ${Math.abs(s.revenue_change_pct??0)}%</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Approved</span><span class="obs-stat-val mono" data-count="${s.approved}">۰</span><span class="obs-stat-sub">${s.conversion_rate}% conv</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Users</span><span class="obs-stat-val mono" data-count="${s.total_users}">۰</span><span class="obs-stat-sub">+${fmt(s.new_users)} new</span></div>
      <div class="obs-stat"><span class="obs-stat-label">Active / Open</span><span class="obs-stat-val mono" data-count="${s.active_configs}">۰</span><span class="obs-stat-sub">${fmt(s.open_tickets)} open tickets</span></div>
    </div>
    <div class="obs-panel" style="margin-top:14px"><div class="obs-panel-head">Daily Revenue</div><div class="obs-bars">${bars}</div></div>
    <div class="grid grid-2" style="margin-top:14px">
      <div class="obs-panel"><div class="obs-panel-head">Key Metrics</div>${meterHtml}</div>
      <div class="obs-panel"><div class="obs-panel-head">Revenue Breakdown</div>${catRows}</div>
    </div>
    <div class="obs-panel" style="margin-top:14px"><div class="obs-panel-head">Top Products</div><table class="obs-table"><thead><tr><th>#</th><th>نام</th><th>فروش</th></tr></thead><tbody>${prodRows}</tbody></table></div>
    <div style="margin-top:14px">${serverMapCardHtml()}</div>
  `);
  const root2 = content();
  $$('.obs-stat-val[data-count]',root2).forEach(el=>animateCount(el,Number(el.dataset.count)));
  requestAnimationFrame(()=>setTimeout(()=>{
    $$('.obs-bar[data-h]',root2).forEach(b=>{ b.style.height=b.dataset.h+'%'; });
    $$('.obs-meter-fill[data-w], .obs-res-card .obs-meter-fill[data-w]',root2).forEach(b=>{ b.style.width=b.dataset.w+'%'; });
  },60));
  mountServerMap();
}
/* ====================================================== world map === */
// ویجت مشترک «نقشه‌ی جهانی سرورها» — در هر ۵ تم از طریق کلاس عمومی .card
// (که هرکدام از تم‌ها استایل خودش را رویش اعمال می‌کند) و متغیرهای CSS
// رنگ تم فعلی (--primary/--emerald/--rose/...) نمایش داده می‌شود؛ یعنی
// یک پیاده‌سازی، هم‌رنگ با هر پنج تم.

// نسخه‌ی واقعی نقشه (خطوط ساحلی) دیگر مستقیماً از CDNهای خارجی گرفته
// نمی‌شود — چون اگر مرورگر ادمین به آن دامنه‌ها دسترسی نداشته باشد (فیلتر/
// قطعی)، دانلود ساکت fail می‌شد و فقط گرید خالی می‌ماند. حالا خودِ سرور
// پنل یک‌بار این کار را می‌کند (و روی دیسک cache می‌کند) و ما فقط از
// endpoint خودمان (هم‌مبدأ، بدون نیاز به هیچ CDN) می‌خوانیم. نتیجه هم در
// localStorage کش می‌شود تا در بازدیدهای بعدی اصلاً نیازی به فراخوانی
// مجدد نباشد.
const SV_MAP_CACHE_KEY = 'sv_map_real_v3';
let SV_REAL = null;
let SV_REAL_PROMISE = null;

async function svEnsureRealMap() {
  if (SV_REAL) return SV_REAL;
  if (SV_REAL_PROMISE) return SV_REAL_PROMISE;
  SV_REAL_PROMISE = (async () => {
    // اول کش محلی را امتحان کن — سریع و بدون نیاز به درخواست جدید
    try {
      const cached = localStorage.getItem(SV_MAP_CACHE_KEY);
      if (cached) {
        SV_REAL = JSON.parse(cached);
        return SV_REAL;
      }
    } catch (e) { /* کش خراب/در دسترس نیست — بی‌اهمیت */ }

    try {
      const data = await apiGet('/dashboard/world-map');
      if (!data || !data.ok || !data.land_path) return null;
      SV_REAL = { landPathD: data.land_path };
      try { localStorage.setItem(SV_MAP_CACHE_KEY, JSON.stringify(SV_REAL)); } catch (e) { /* بی‌اهمیت */ }
      return SV_REAL;
    } catch (e) {
      return null; // اتصال به پنل خودمان هم ناموفق بود — همان گرید ساده باقی می‌ماند
    }
  })();
  return SV_REAL_PROMISE;
}

// معادل خطیِ d3.geoEquirectangular().fitSize([1000, 500], {type:'Sphere'})
// است، پس چه نقشه‌ی دقیق لود شده باشد چه نه، پین‌ها دقیقاً روی همان
// تصویربرداری خطوط ساحلی می‌افتند.
function svProject(lat, lon) {
  const x = (Number(lon) + 180) / 360 * 1000;
  const y = (90 - Number(lat)) / 180 * 500;
  return [x, y];
}

function svMapGraticule() {
  let out = '';
  for (let x = 0; x <= 1000; x += 100) out += `<line x1="${x}" y1="0" x2="${x}" y2="500" class="${x === 500 ? 'sv-map-meridian' : ''}"></line>`;
  for (let y = 0; y <= 500; y += 62.5) out += `<line x1="0" y1="${y.toFixed(1)}" x2="1000" y2="${y.toFixed(1)}" class="${Math.abs(y - 250) < 1 ? 'sv-map-equator' : ''}"></line>`;
  return out;
}

// تا وقتی نقشه‌ی دقیق (از CDN یا کش) لود نشده، بک‌گراند فقط همان گرید
// عرض/طول جغرافیایی (svMapGraticule) است — بدون هیچ چندضلعی تقریبی؛ به
// محض آماده‌شدن svEnsureRealMap، خطوط ساحلی واقعی جای‌گزین می‌شوند.
function svMapLandPaths() {
  return '';
}

function svFlagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐';
  try { return String.fromCodePoint(...[...cc.toUpperCase()].map(c => 127397 + c.charCodeAt(0))); }
  catch (e) { return '🌐'; }
}

const SV_STATUS_LABEL = { online: 'آنلاین', offline: 'آفلاین', unknown: 'نامشخص' };

function serverMapCardHtml() {
  return `
  <div class="card sv-map-card">
    <div class="card-head sv-map-head">
      <h3>🗺️ نقشه‌ی جهانی سرورها</h3>
      <div class="sv-map-actions">
        <span class="sv-map-updated" id="sv-map-updated"></span>
        <button class="btn btn-sm" id="sv-map-refresh-btn" hidden>↻ اسکن مجدد</button>
      </div>
    </div>
    <p class="card-sub">لینک ساب مادر را وارد کن تا کانفیگ‌هایش بر اساس IP سرور روی نقشه مشخص شوند.</p>
    <div class="sv-map-linkrow">
      <input type="text" id="sv-map-link-input" class="input" dir="ltr" placeholder="https://example.com/sub/xxxxx">
      <button class="btn btn-primary btn-sm" id="sv-map-scan-btn">بررسی و رسم نقشه</button>
    </div>
    <div class="sv-map-stats" id="sv-map-stats"></div>
    <div class="sv-map-wrap" id="sv-map-wrap">
      <svg id="sv-map-svg" viewBox="0 0 1000 500" preserveAspectRatio="xMidYMid meet">
        <g class="sv-map-grid">${svMapGraticule()}</g>
        <g class="sv-map-land">${svMapLandPaths()}</g>
        <g class="sv-map-markers" id="sv-map-markers"></g>
      </svg>
      <div class="sv-map-tooltip" id="sv-map-tooltip" hidden></div>
      <div class="sv-map-empty" id="sv-map-empty" hidden>هنوز لینک ساب مادری ثبت نشده — یکی وارد کن و «بررسی و رسم نقشه» را بزن.</div>
      <div class="sv-map-loading" id="sv-map-loading" hidden><span class="sv-map-spinner"></span>در حال دریافت و جئولوکیت کانفیگ‌ها…</div>
    </div>
    <div class="sv-map-legend">
      <span><i class="dot online"></i>آنلاین</span>
      <span><i class="dot offline"></i>آفلاین</span>
      <span><i class="dot unknown"></i>نامشخص</span>
    </div>
    <div class="sv-map-list" id="sv-map-list"></div>
  </div>`;
}

function svTooltipHtml(s) {
  const protoBadges = (s.protocols || []).map(p => `<span class="chip">${esc(p.name)}</span>`).join(' ');
  const ipLine = s.ip || 'نامشخص';
  const srcNote = s.source === 'label+geoip'
    ? '🏷️📡 نام کانفیگ + موقعیت دقیق IP (هر دو هم‌راستا)'
    : s.source === 'label'
      ? '🏷️ بر اساس نام کانفیگ (سرور پشت CDN است، مختصات تقریبی مرکز کشور)'
      : '📡 بر اساس موقعیت واقعی IP';
  return `
    <div class="sv-tt-head">${svFlagEmoji(s.country_code)} <b>${esc(s.city || s.country || '—')}</b><span class="sv-tt-country">${esc(s.country || '')}</span></div>
    <div class="sv-tt-name">${esc(s.remark || '—')}</div>
    <div class="sv-tt-ip mono">${esc(ipLine)}</div>
    <div class="sv-tt-row">وضعیت: <b class="sv-tt-status-${s.status}">${SV_STATUS_LABEL[s.status] || 'نامشخص'}</b></div>
    <div class="sv-tt-protocols">${protoBadges}</div>
    <div class="sv-tt-source">${srcNote}</div>`;
}

function svShowTooltip(s) {
  const root = content();
  const wrap = $('#sv-map-wrap', root);
  const tip = $('#sv-map-tooltip', root);
  const svgEl = $('#sv-map-svg', root);
  if (!wrap || !tip || !svgEl || s.lat == null || s.lon == null) return;
  const [vx, vy] = svProject(s.lat, s.lon);
  const svgRect = svgEl.getBoundingClientRect();
  const wrapRect = wrap.getBoundingClientRect();
  const px = (svgRect.left - wrapRect.left) + vx * (svgRect.width / 1000);
  const py = (svgRect.top - wrapRect.top) + vy * (svgRect.height / 500);
  tip.innerHTML = svTooltipHtml(s);
  tip.hidden = false;
  tip.style.left = Math.max(4, Math.min(px + 14, wrapRect.width - 236)) + 'px';
  tip.style.top = Math.max(4, Math.min(py + 14, wrapRect.height - 110)) + 'px';
}
function svHideTooltip() {
  const tip = $('#sv-map-tooltip', content());
  if (tip) tip.hidden = true;
}

// چون هر کانفیگ حالا پین جدای خودش را دارد، ممکن است چند کانفیگ دقیقاً
// روی یک سرور (همان lat/lon) باشند — بدون این تابع دقیقاً روی هم می‌افتند
// و فقط بالایی‌شان قابل کلیک می‌ماند. این تابع پین‌های هم‌مکان را به‌صورت
// یک دایره‌ی کوچک دور نقطه‌ی اصلی پخش می‌کند تا همه جدا و کلیک‌پذیر بمانند.
function svSpreadOverlapping(points) {
  const buckets = new Map();
  points.forEach((p, i) => {
    const key = p.x.toFixed(1) + ',' + p.y.toFixed(1);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(i);
  });
  const out = points.map(p => ({ x: p.x, y: p.y }));
  buckets.forEach(idxs => {
    if (idxs.length < 2) return;
    const spread = Math.min(3 + idxs.length * 0.6, 9);
    idxs.forEach((idx, j) => {
      const angle = (2 * Math.PI * j) / idxs.length;
      out[idx].x += Math.cos(angle) * spread;
      out[idx].y += Math.sin(angle) * spread;
    });
  });
  return out;
}

function svRenderMarkers(servers) {
  const root = content();
  const g = $('#sv-map-markers', root);
  if (!g) return;
  const positions = servers.map(s => (s.lat != null && s.lon != null) ? (([x, y]) => ({ x, y }))(svProject(s.lat, s.lon)) : null);
  const spread = svSpreadOverlapping(positions.map(p => p || { x: -9999, y: -9999 }));
  const r = 6; // چون هر پین حالا دقیقاً یک کانفیگ است، اندازه‌ی ثابت (بدون وزن‌دهی به تعداد) واضح‌تر است
  g.innerHTML = servers.map((s, i) => {
    if (!positions[i]) return '';
    const { x, y } = spread[i];
    const st = SV_STATUS_LABEL[s.status] ? s.status : 'unknown';
    return `<g class="sv-map-pin ${st}" data-idx="${i}" tabindex="0">
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(r + 6).toFixed(1)}" class="sv-map-pulse"></circle>
      <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}" class="sv-map-dot"></circle>
    </g>`;
  }).join('');
  $$('.sv-map-pin', g).forEach(el => {
    const s = servers[+el.dataset.idx];
    el.addEventListener('mouseenter', () => svShowTooltip(s));
    el.addEventListener('click', () => svShowTooltip(s));
    el.addEventListener('mouseleave', svHideTooltip);
  });
}

function svStatsHtml(data) {
  return `
    <span class="chip">🖥️ ${fmt(data.total_servers)} سرور</span>
    <span class="chip">🌍 ${fmt(data.total_countries)} کشور</span>
    <span class="chip">⚙️ ${fmt(data.total_configs)} کانفیگ</span>`;
}

function svServerListHtml(servers) {
  return servers.map((s, i) => `
    <div class="sv-map-list-row" data-idx="${i}">
      <i class="dot ${SV_STATUS_LABEL[s.status] ? s.status : 'unknown'}"></i>
      <span class="sv-ml-flag">${svFlagEmoji(s.country_code)}</span>
      <span class="sv-ml-name">${esc(s.remark || s.city || s.country || '—')}<small>${esc(s.country || '')}</small></span>
      <span class="sv-ml-ip mono">${esc(s.ip || '—')}</span>
      <span class="sv-ml-count mono">${esc((s.protocols && s.protocols[0] && s.protocols[0].name) || '')}</span>
    </div>`).join('');
}

function svFmtTime(ts) {
  if (!ts) return '';
  try { return 'آخرین اسکن: ' + new Date(ts * 1000).toLocaleString('fa-IR'); } catch (e) { return ''; }
}

async function mountServerMap() {
  const root = content();
  const card = $('.sv-map-card', root);
  if (!card) return;

  const input = $('#sv-map-link-input', root);
  const scanBtn = $('#sv-map-scan-btn', root);
  const refreshBtn = $('#sv-map-refresh-btn', root);
  const loadingEl = $('#sv-map-loading', root);
  const emptyEl = $('#sv-map-empty', root);
  const updatedEl = $('#sv-map-updated', root);
  let currentServers = [];

  // نسخه‌ی دقیق نقشه را در پس‌زمینه بارگیری کن و به‌محض آماده‌شدن جای‌گزین
  // خطوط تقریبی/گرید کن — بدون این‌که منتظرش بمانیم.
  svEnsureRealMap().then(real => {
    if (!real) return;
    const r = content();
    if (!$('.sv-map-card', r)) return; // کاربر جابه‌جا شده
    const landG = $('#sv-map-wrap .sv-map-land', r);
    if (landG) landG.innerHTML = `<path d="${real.landPathD}" class="sv-map-land-poly"></path>`;
    if (currentServers.length) svRenderMarkers(currentServers);
  });

  const paint = (data) => {
    if (!$('.sv-map-card', content())) return; // کاربر به تب دیگری رفته
    if (!data || !data.ok) {
      $('#sv-map-stats', root).innerHTML = '';
      svRenderMarkers([]);
      $('#sv-map-list', root).innerHTML = '';
      if (data && data.error === 'no_link') { if (emptyEl) emptyEl.hidden = false; }
      else if (data && data.error) toast(data.error, true);
      return;
    }
    currentServers = data.servers || [];
    if (emptyEl) emptyEl.hidden = true;
    $('#sv-map-stats', root).innerHTML = svStatsHtml(data);
    svRenderMarkers(currentServers);
    $('#sv-map-list', root).innerHTML = svServerListHtml(currentServers);
    $$('.sv-map-list-row', root).forEach(row => row.addEventListener('click', () => svShowTooltip(currentServers[+row.dataset.idx])));
    if (updatedEl) updatedEl.textContent = svFmtTime(data.generated_at);
    if (refreshBtn) refreshBtn.hidden = false;
  };

  const doScan = async (refresh) => {
    if (loadingEl) loadingEl.hidden = false;
    if (emptyEl) emptyEl.hidden = true;
    try {
      const data = await apiGet(`/dashboard/servers-map${refresh ? '?refresh=1' : ''}`);
      paint(data);
    } catch (e) { handleErr(e); }
    finally { if (loadingEl) loadingEl.hidden = true; }
  };

  try {
    const s = await apiGet('/settings/master-sub');
    if (!$('.sv-map-card', content())) return;
    if (input) input.value = s.link || '';
    if (s.link) { if (refreshBtn) refreshBtn.hidden = false; await doScan(false); }
    else if (emptyEl) emptyEl.hidden = false;
  } catch (e) { /* بی‌اهمیت — کاربر می‌تواند دستی لینک بدهد */ }

  if (scanBtn) scanBtn.addEventListener('click', async () => {
    const link = (input.value || '').trim();
    if (!link) { toast('لینک ساب را وارد کن', true); return; }
    scanBtn.disabled = true;
    try {
      await apiPost('/settings/master-sub', { link });
      await doScan(true);
      toast('نقشه به‌روزرسانی شد.');
    } catch (e) { handleErr(e); }
    finally { scanBtn.disabled = false; }
  });

  if (refreshBtn) refreshBtn.addEventListener('click', () => doScan(true));
}

/* ============================================================ orders === */
let ordersStatus = 'pending';
async function renderOrders() {
  const canAct = hasPerm('orders');
  const orders = await apiGet(`/orders?status=${ordersStatus}`);
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
            <td>${esc(o.product_name)}</td>
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
    try { await apiPost(`/orders/${b.dataset.approve}/approve`); toast('سفارش تایید شد.'); renderOrders(); }
    catch (e) { handleErr(e); b.disabled = false; }
  }));
  $$('[data-reject]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('سفارش رد شود؟')) return;
    try { await apiPost(`/orders/${b.dataset.reject}/reject`); toast('سفارش رد شد.'); renderOrders(); }
    catch (e) { handleErr(e); }
  }));
}

/* ============================================================ topups === */
let topupsStatus = 'pending';
async function renderTopups() {
  const canAct = hasPerm('orders');
  const topups = await apiGet(`/topups?status=${topupsStatus}`);
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

/* ============================================================= users === */
let usersState = { q: '', status: 'all', page: 1 };
async function renderUsers() {
  const res = await apiGet(`/users?q=${encodeURIComponent(usersState.q)}&status=${usersState.status}&page=${usersState.page}`);
  const pages = Math.max(Math.ceil(res.total / res.limit), 1);
  setContent(`
    <div class="toolbar">
      <input class="input" id="user-search" placeholder="جستجو (آیدی، یوزرنیم، نام)..." value="${esc(usersState.q)}">
      <select class="input" id="user-status">
        ${[['all', 'همه'], ['active', 'فعال'], ['expired', 'منقضی'], ['blocked', 'مسدود']].map(([v, l]) => `<option value="${v}" ${v === usersState.status ? 'selected' : ''}>${l}</option>`).join('')}
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
    { label: 'تست دریافتی', val: u.test_used ? 'بله' : 'خیر' },
  ];
  if (d.is_reseller) statCards.push({ label: 'اعتبار نمایندگی', val: `${fmt(d.reseller_credit)} گیگ` });
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
async function renderCatalog() {
  const [categories, products] = await Promise.all([apiGet('/categories'), apiGet('/products')]);
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
    <div class="card"><div class="table-wrap"><table><thead><tr><th>نام</th><th>دسته</th><th>قیمت</th><th>موجودی</th><th>وضعیت</th><th>عملیات</th></tr></thead>
    <tbody>${products.map(p => `<tr>
      <td>${esc(p.name)}</td><td>${esc(p.category_name)}</td><td class="mono">${fmt(p.price)}</td>
      <td class="mono">${p.is_auto_provision ? '<span class="chip">خودکار</span>' : fmt(p.stock)}</td>
      <td>${p.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
      <td>
        ${!p.is_auto_provision ? `<button class="btn btn-sm" data-configs="${p.id}">بانک کانفیگ</button>` : ''}
        <button class="btn btn-sm" data-toggle-prod="${p.id}">${p.is_active ? 'غیرفعال' : 'فعال'}</button>
        <button class="btn btn-danger btn-sm" data-del-prod="${p.id}">حذف</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="6" class="empty-state">محصولی نیست</td></tr>'}</tbody></table></div></div>`;

  $('#add-prod').addEventListener('click', () => openModal('محصول جدید', `
    <div class="form-grid">
      <select class="input" id="prod-cat">${categories.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select>
      <input class="input" id="prod-name" placeholder="نام محصول">
      <div class="form-row"><input class="input" id="prod-price" type="number" placeholder="قیمت (تومان)">
      <input class="input" id="prod-duration" type="number" placeholder="مدت (روز)" value="30"></div>
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
          description: $('#prod-desc', b).value, duration_days: Number($('#prod-duration', b).value) || 30,
        });
        toast('محصول اضافه شد.'); close(); renderCatalog();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-toggle-prod]', body).forEach(b => b.addEventListener('click', async () => {
    try { await apiPost(`/products/${b.dataset.toggleProd}/toggle`); renderCatalog(); } catch (e) { handleErr(e); }
  }));
  $$('[data-del-prod]', body).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('این محصول حذف شود؟')) return;
    try { await apiDelete(`/products/${b.dataset.delProd}`); toast('حذف شد.'); renderCatalog(); } catch (e) { handleErr(e); }
  }));
  $$('[data-configs]', body).forEach(b => b.addEventListener('click', () => showConfigBank(Number(b.dataset.configs))));
}

async function showConfigBank(productId) {
  const res = await apiGet(`/products/${productId}/configs`);
  const configs = res.items || [];
  const usedCount = res.used_count || 0;
  openModal('بانک کانفیگ', `
    <div class="cfg-stats">
      <div class="cfg-stat"><span>لینک‌های آزاد</span><b class="mono">${fmt(configs.length)}</b></div>
      <div class="cfg-stat"><span>تحویل‌شده</span><b class="mono">${fmt(usedCount)}</b></div>
      <div class="cfg-stat"><span>مجموع</span><b class="mono">${fmt(configs.length + usedCount)}</b></div>
    </div>
    <label class="field" style="margin-top:16px">
      <span>افزودن لینک جدید</span>
      <textarea class="input" id="new-links" rows="6" placeholder="هر خط یک لینک کانفیگ..."></textarea>
    </label>
    <button class="btn btn-primary btn-block" id="add-links" style="margin-top:10px">افزودن لینک‌ها</button>
    <h4 class="cfg-list-title">لینک‌های آزاد (${configs.length})</h4>
    <div class="table-wrap cfg-table-wrap">
      <table><tbody>${configs.map(c => `<tr>
        <td class="mono cfg-link-cell">${esc(c.link)}</td>
        <td class="cfg-actions"><button class="btn btn-ghost btn-sm" data-copy-cfg="${esc(c.link)}">کپی</button><button class="btn btn-danger btn-sm" data-del-cfg="${c.id}">حذف</button></td>
      </tr>`).join('') || `<tr><td colspan="2" class="empty-state"><div class="icon">${svg('empty')}</div>خالی است</td></tr>`}</tbody></table>
    </div>
  `, (body, close) => {
    $('#add-links', body).addEventListener('click', async () => {
      const links = $('#new-links', body).value;
      if (!links.trim()) return;
      try {
        const r = await apiPost(`/products/${productId}/configs`, { links });
        toast(`${r.added} لینک اضافه شد${r.duplicates ? ` (${r.duplicates} تکراری نادیده گرفته شد)` : ''}.`);
        close(); showConfigBank(productId);
      } catch (e) { handleErr(e); }
    });
    $$('[data-copy-cfg]', body).forEach(b => b.addEventListener('click', () => {
      navigator.clipboard?.writeText(b.dataset.copyCfg).then(() => toast('کپی شد.'));
    }));
    $$('[data-del-cfg]', body).forEach(b => b.addEventListener('click', async () => {
      try { await apiDelete(`/configs/${b.dataset.delCfg}`); close(); showConfigBank(productId); } catch (e) { handleErr(e); }
    }));
  }, { wide: true });
}

/* ========================================================== discounts === */
async function renderDiscounts() {
  const codes = await apiGet('/discounts');
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

/* ============================================================= support === */
async function renderSupport() {
  stopSupportPoll();
  const convs = await apiGet('/support/conversations');
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

async function showSupportChat(userId) {
  let lastId = 0;
  const d = await apiGet(`/support/${userId}/messages`);
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
async function renderTickets() {
  const tickets = await apiGet(`/tickets${ticketsStatusFilter ? '?status=' + ticketsStatusFilter : ''}`);
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
async function renderBroadcast() {
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

/* =========================================================== resellers === */
async function renderResellers() {
  const [resellers, cohort] = await Promise.all([
    apiGet('/resellers'),
    apiGet('/resellers/analytics/cohort').catch(() => null),
  ]);

  const cohortHtml = cohort ? renderResellerCohortBlock(cohort) : '';

  setContent(`
    ${cohortHtml}
    <div class="card"><div class="card-head"><h3>لیست نمایندگی‌ها</h3></div><div class="table-wrap"><table>
      <thead><tr><th>آیدی</th><th>یوزرنیم</th><th>اعتبار (گیگ)</th><th>وضعیت</th><th>عملیات</th></tr></thead>
      <tbody>${resellers.map(r => `<tr>
        <td class="mono">${r.telegram_id}</td><td>${esc(r.username || '—')}</td>
        <td class="mono">${fmt(r.reseller_credit_gb)}</td>
        <td>${r.is_reseller ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
        <td><button class="btn btn-sm" data-credit="${r.telegram_id}">تنظیم اعتبار</button></td>
      </tr>`).join('') || '<tr><td colspan="5" class="empty-state">نماینده‌ای ثبت نشده</td></tr>'}</tbody>
    </table></div></div>
  `);
  $$('[data-credit]', content()).forEach(b => b.addEventListener('click', () => openModal('تنظیم اعتبار حجمی', `
    <div class="form-grid">
      <input class="input" id="credit-delta" type="number" placeholder="مقدار (گیگ، منفی=کسر)">
      <input class="input" id="credit-reason" placeholder="دلیل (اختیاری)">
      <button class="btn btn-primary" id="credit-save">ثبت</button>
    </div>`, (body, close) => {
    $('#credit-save', body).addEventListener('click', async () => {
      const delta_gb = Number($('#credit-delta', body).value);
      if (!delta_gb) return;
      try {
        await apiPost(`/resellers/${b.dataset.credit}/credit`, { delta_gb, reason: $('#credit-reason', body).value });
        toast('اعتبار به‌روزرسانی شد.'); close(); renderResellers();
      } catch (e) { handleErr(e); }
    });
  })));

  if (cohort) {
    activateRings(content());
    $$('[data-toggle-churn]', content()).forEach(el => el.addEventListener('click', () => {
      const box = $('#churn-list-box', content());
      box.style.display = box.style.display === 'none' ? '' : 'none';
    }));
  }
}

function renderResellerCohortBlock(data) {
  const c = data.churn;
  const months = data.cohorts;
  const allMonths = months.length ? months[months.length - 1].retention.map(r => r.month) : [];

  const heatRows = months.map(co => {
    const cells = co.retention.map(r => {
      const pct = r.pct;
      const alpha = Math.max(0.08, Math.min(1, pct / 100));
      return `<td class="mono" style="text-align:center;background:rgba(139,92,246,${alpha.toFixed(2)});border-radius:6px">
        ${co.size ? `${pct}٪<div style="font-size:10px;opacity:.75">${fmt(r.active)}</div>` : '—'}
      </td>`;
    }).join('');
    const pad = allMonths.length - co.retention.length;
    return `<tr><td class="mono">${co.cohort_month}</td><td class="mono">${fmt(co.size)}</td>${cells}${'<td></td>'.repeat(Math.max(0, pad))}</tr>`;
  }).join('');

  const churnRows = c.list.slice(0, 30).map(u => `
    <tr>
      <td class="mono">${u.telegram_id}</td><td>${esc(u.username || '—')}</td>
      <td class="mono">${fmt(u.credit_gb)}</td>
      <td class="mono">${u.last_activity ? fmtDate(u.last_activity) : 'هیچ‌وقت'}</td>
      <td class="mono">${fmt(u.days_inactive)} روز</td>
    </tr>`).join('') || '<tr><td colspan="5" class="empty-state">نماینده‌ی ریزش‌کرده‌ای نیست 🎉</td></tr>';

  return `
    <div class="grid grid-4">
      <div class="card stat-card">
        <div class="stat-top"><span class="stat-icon stat-icon-1">${svg('resellers')}</span></div>
        <span class="value mono">${fmt(c.total)}</span>
        <span class="label">کل نمایندگان فعلی</span>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span class="stat-icon stat-icon-2">${svg('check')}</span></div>
        <span class="value mono">${fmt(c.active)}</span>
        <span class="label">فعال (${fmt(c.inactivity_days)} روز اخیر)</span>
      </div>
      <div class="card stat-card" data-toggle-churn style="cursor:pointer">
        <div class="stat-top">
          <span class="stat-icon stat-icon-4">${svg('tickets')}</span>
          <div class="ring" style="--ring-a:var(--rose)" data-pct="${c.churn_rate}"><span>${c.churn_rate}٪</span></div>
        </div>
        <span class="value mono">${fmt(c.churned)}</span>
        <span class="label">ریزش‌کرده (churn) — برای لیست کلیک کنید</span>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span class="stat-icon stat-icon-3">${svg('users')}</span></div>
        <span class="value mono">${fmt(months.reduce((a, m) => a + m.size, 0))}</span>
        <span class="label">مجموع نماینده‌های ${fmt(months.length)} ماه اخیر</span>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3>کوهورت نگهداشت ماهانه نمایندگان</h3>
        <span class="card-sub">هر ردیف یک کوهورت (ماه فعال‌سازی) — درصد نماینده‌های همان کوهورت که در هر ماه بعد هم فعالیت (شارژ/مصرف) داشته‌اند.</span>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>ماه کوهورت</th><th>تعداد</th>${allMonths.map((m, i) => `<th class="mono">M${i}</th>`).join('')}</tr></thead>
        <tbody>${heatRows || '<tr><td colspan="2" class="empty-state">داده‌ای نیست</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="card" id="churn-list-box" style="display:none">
      <div class="card-head"><h3>نماینده‌های در آستانه‌ی ریزش / ریزش‌کرده</h3></div>
      <div class="table-wrap"><table>
        <thead><tr><th>آیدی</th><th>یوزرنیم</th><th>اعتبار (گیگ)</th><th>آخرین فعالیت</th><th>مدت بی‌فعالیتی</th></tr></thead>
        <tbody>${churnRows}</tbody>
      </table></div>
    </div>
  `;
}

/* ============================================================== panels === */
async function renderPanels() {
  const servers = await apiGet('/panel-servers');
  setContent(`
    <div class="toolbar"><button class="btn btn-primary btn-sm" id="add-panel">+ پنل جدید</button></div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>نام</th><th>نوع</th><th>آدرس</th><th>وضعیت</th><th>عملیات</th></tr></thead>
      <tbody>${servers.map(s => `<tr>
        <td>${esc(s.name)}</td><td>${esc(s.type_label)}</td><td class="mono" style="direction:ltr;text-align:right">${esc(s.api_url)}</td>
        <td>${s.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
        <td><button class="btn btn-sm" data-test="${s.id}">تست اتصال</button>
        <button class="btn btn-danger btn-sm" data-del="${s.id}">حذف</button></td>
      </tr>`).join('') || '<tr><td colspan="5" class="empty-state">پنلی ثبت نشده</td></tr>'}</tbody>
    </table></div></div>
  `);
  $('#add-panel').addEventListener('click', () => openModal('پنل جدید', `
    <div class="form-grid">
      <input class="input" id="p-name" placeholder="نام (مثلا سرور آلمان)">
      <select class="input" id="p-type"><option value="pasarguard">PasarGuard</option><option value="3xui">3X-UI</option></select>
      <input class="input" id="p-url" placeholder="آدرس پنل (https://...)">
      <div class="form-row"><input class="input" id="p-user" placeholder="یوزرنیم"><input class="input" id="p-pass" type="password" placeholder="پسورد"></div>
      <button class="btn btn-primary" id="p-save">ثبت</button>
    </div>`, (body, close) => {
    $('#p-save', body).addEventListener('click', async () => {
      const name = $('#p-name', body).value.trim(), api_url = $('#p-url', body).value.trim();
      if (!name || !api_url) return toast('نام و آدرس الزامی است.', true);
      try {
        await apiPost('/panel-servers', {
          name, panel_type: $('#p-type', body).value, api_url,
          api_username: $('#p-user', body).value, api_password: $('#p-pass', body).value,
        });
        toast('پنل اضافه شد.'); close(); renderPanels();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-test]', content()).forEach(b => b.addEventListener('click', async () => {
    b.textContent = 'در حال تست...'; b.disabled = true;
    try {
      const r = await apiPost(`/panel-servers/${b.dataset.test}/test`);
      toast(r.ok ? 'اتصال موفق بود.' : (r.error || 'اتصال ناموفق بود.'), !r.ok);
    } catch (e) { handleErr(e); }
    finally { b.textContent = 'تست اتصال'; b.disabled = false; }
  }));
  $$('[data-del]', content()).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('حذف شود؟')) return;
    try { await apiDelete(`/panel-servers/${b.dataset.del}`); toast('حذف شد.'); renderPanels(); } catch (e) { handleErr(e); }
  }));
}

/* ============================================================ settings === */
const RATE_SOURCE_LABEL = { tgju: 'tgju.org', nobitex: 'نوبیتکس', wallex: 'والکس', coingecko: 'CoinGecko (جهانی)', manual: 'دستی (تنظیم‌شده در پنل)' };

function rateCardHtml(r) {
  const rateTxt = r.rate ? `${fmt(r.rate)} تومان` : '—';
  const sourceTxt = r.source ? (RATE_SOURCE_LABEL[r.source] || r.source) : '—';
  const errTxt = !r.ok
    ? `<span class="card-sub" style="color:var(--rose)">دریافت زنده ناموفق بود؛ ${r.rate ? 'مقدار کش قدیمی نمایش داده شده.' : 'مقداری در کش نیست.'} (${esc(r.error || '')})</span>`
    : (r.source === 'manual'
        ? `<span class="card-sub" style="color:var(--amber, #f5a623)">⚠️ همه‌ی منابع زنده شکست خوردند؛ نرخ دستی تنظیم‌شده در پایین همین صفحه موقتاً استفاده شد.</span>`
        : '');
  return `
    <div class="card" style="margin-bottom:18px" id="rate-card">
      <div class="card-head">
        <h3>نرخ ارز (دلار به تومان)</h3>
        <button class="btn btn-sm" id="rate-refresh">🔄 رفرش کش</button>
      </div>
      <div class="chip-row">
        <span class="chip mono">نرخ فعلی: ${rateTxt}</span>
        <span class="chip">منبع: ${sourceTxt}</span>
        <span class="chip mono">آخرین بروزرسانی: ${fmtDate(r.updated_at)}</span>
      </div>
      ${errTxt}
    </div>`;
}

const SETTINGS_TABS = [
  { key: 'content', label: '📝 محتوا و متن‌ها' },
  { key: 'payment', label: '💳 پرداخت و مالی' },
  { key: 'campaign', label: '🎯 کمپین و مشارکت' },
  { key: 'services', label: '⚙️ سرویس‌های ویژه' },
];

const SETTINGS_GROUPS = [
  // ---------------------------------------------------------- محتوا و متن‌ها
  { tab: 'content', title: 'متن‌های پایه', fields: [
    { key: 'store_name', label: 'نام فروشگاه', type: 'text' },
    { key: 'welcome_text', label: 'متن خوش‌آمدگویی (شروع ربات)', type: 'textarea' },
    { key: 'contact_text', label: 'متن ابتدای بخش ارتباط با پشتیبانی', type: 'textarea' },
    { key: 'after_buy_text', label: 'متن راهنمای پرداخت (بعد از انتخاب محصول)', type: 'textarea' },
  ]},
  { tab: 'content', title: 'دکمه‌های منوی ربات', fields: [
    { key: 'btn_buy', label: 'متن دکمه خرید کانفیگ', type: 'text' },
    { key: 'btn_buy_style', label: 'رنگ دکمه خرید کانفیگ', type: 'color' },
    { key: 'btn_test', label: 'متن دکمه کانفیگ تست', type: 'text' },
    { key: 'btn_test_style', label: 'رنگ دکمه کانفیگ تست', type: 'color' },
    { key: 'test_enabled', label: 'نمایش دکمه کانفیگ تست', type: 'bool' },
    { key: 'btn_my_orders', label: 'متن دکمه سفارش‌های من', type: 'text' },
    { key: 'btn_my_orders_style', label: 'رنگ دکمه سفارش‌های من', type: 'color' },
    { key: 'btn_wallet', label: 'متن دکمه کیف پول', type: 'text' },
    { key: 'btn_wallet_style', label: 'رنگ دکمه کیف پول', type: 'color' },
    { key: 'btn_referral', label: 'متن دکمه زیرمجموعه‌گیری', type: 'text' },
    { key: 'btn_referral_style', label: 'رنگ دکمه زیرمجموعه‌گیری', type: 'color' },
    { key: 'referral_enabled', label: 'نمایش دکمه زیرمجموعه‌گیری', type: 'bool' },
    { key: 'btn_wheel', label: 'متن دکمه گردونه شانس', type: 'text' },
    { key: 'btn_wheel_style', label: 'رنگ دکمه گردونه شانس', type: 'color' },
    { key: 'wheel_enabled', label: 'نمایش دکمه گردونه شانس', type: 'bool' },
    { key: 'btn_contact', label: 'متن دکمه ارتباط با پشتیبانی', type: 'text' },
    { key: 'btn_contact_style', label: 'رنگ دکمه ارتباط با پشتیبانی', type: 'color' },
    { key: 'btn_reseller_panel', label: 'متن دکمه پنل نمایندگی (فقط برای نماینده‌ها)', type: 'text' },
    { key: 'btn_reseller_panel_style', label: 'رنگ دکمه پنل نمایندگی', type: 'color' },
    { key: 'btn_reseller_request', label: 'متن دکمه درخواست نمایندگی سطح ۲', type: 'text' },
    { key: 'btn_reseller_request_style', label: 'رنگ دکمه درخواست نمایندگی سطح ۲', type: 'color' },
    { key: 'btn_admin_panel', label: 'متن دکمه پنل مدیریت (فقط برای ادمین‌ها)', type: 'text' },
    { key: 'btn_admin_panel_style', label: 'رنگ دکمه پنل مدیریت', type: 'color' },
  ]},
  { tab: 'content', title: '🎨 رنگ دکمه‌های مسیر خرید', fields: [
    { key: 'btn_cat_select_style', label: 'رنگ دکمه‌های انتخاب دسته‌بندی', type: 'color' },
    { key: 'btn_product_select_style', label: 'رنگ دکمه‌های انتخاب محصول', type: 'color' },
    { key: 'btn_buy_continue_style', label: 'رنگ دکمه «ادامه و ارسال رسید»', type: 'color' },
    { key: 'btn_enter_code_style', label: 'رنگ دکمه «وارد کردن کد تخفیف»', type: 'color' },
    { key: 'btn_buy_back_style', label: 'رنگ دکمه‌های بازگشت در مسیر خرید', type: 'color' },
  ]},


  // ------------------------------------------------------------ پرداخت و مالی
  { tab: 'payment', title: 'کارت بانکی', fields: [
    { key: 'card_number', label: 'شماره کارت', type: 'text' },
    { key: 'card_holder', label: 'نام صاحب کارت', type: 'text' },
  ]},
  { tab: 'payment', title: 'پرداخت کریپتو (Plisio)', fields: [
    { key: 'crypto_payment_enabled', label: 'فعال بودن پرداخت کریپتو', type: 'bool' },
    { key: 'plisio_api_key', label: 'کلید API درگاه Plisio', type: 'password' },
  ]},
  { tab: 'payment', title: 'موجودی و نرخ ارز پشتیبان', fields: [
    { key: 'low_stock_threshold', label: 'آستانه هشدار موجودی کم', type: 'number' },
    { key: 'manual_usd_rate_toman', label: 'نرخ دلار دستی (پشتیبان — فقط وقتی همه‌ی منابع زنده شکست بخورند استفاده می‌شود)', type: 'number' },
  ]},

  // -------------------------------------------------------- کمپین و مشارکت
  { tab: 'campaign', title: 'عضویت اجباری کانال', fields: [
    { key: 'force_join_enabled', label: 'فعال بودن عضویت اجباری', type: 'bool' },
    { key: 'force_join_channel', label: 'آیدی کانال (مثلاً ‎@mychannel)', type: 'text' },
  ]},
  { tab: 'campaign', title: 'زیرمجموعه‌گیری (رفرال)', fields: [
    { key: 'referral_percent', label: 'درصد پورسانت رفرال', type: 'number' },
  ]},
  { tab: 'campaign', title: 'گردونه شانس', fields: [
    { key: 'wheel_win_percent', label: 'درصد احتمال برد در هر چرخش', type: 'number' },
    { key: 'wheel_prizes', label: 'درصدهای تخفیف ممکن (با کاما جدا کنید، مثلاً 10,20,30,50)', type: 'text' },
    { key: 'wheel_code_expiry_hours', label: 'اعتبار کد جایزه پس از برد (ساعت)', type: 'number' },
    { key: 'wheel_cooldown_hours', label: 'فاصله مجاز بین دو چرخش هر کاربر (ساعت)', type: 'number' },
  ]},
  { tab: 'campaign', title: 'یادآوری تمدید سرویس', fields: [
    { key: 'renewal_reminder_enabled', label: 'فعال بودن یادآوری', type: 'bool' },
    { key: 'renewal_reminder_days_before', label: 'چند روز قبل از انقضا یادآوری ارسال شود', type: 'number' },
    { key: 'renewal_discount_percent', label: 'درصد تخفیف کد تشویقی تمدید', type: 'number' },
    { key: 'renewal_discount_expiry_hours', label: 'اعتبار کد تشویقی تمدید (ساعت)', type: 'number' },
  ]},
  { tab: 'campaign', title: 'یادآوری اتمام حجم', fields: [
    { key: 'volume_reminder_enabled', label: 'فعال بودن یادآوری', type: 'bool' },
    { key: 'volume_reminder_mode', label: 'مبنای هشدار', type: 'select', options: [['percent', 'بر اساس درصد مصرف'], ['gb', 'بر اساس حجم باقی‌مانده']] },
    { key: 'volume_reminder_percent', label: 'درصد مصرف برای هشدار (حالت درصد)', type: 'number' },
    { key: 'volume_reminder_gb_left', label: 'حجم باقی‌مانده برای هشدار — گیگ (حالت حجم)', type: 'number' },
    { key: 'volume_discount_percent', label: 'درصد تخفیف کد تشویقی اتمام حجم', type: 'number' },
    { key: 'volume_discount_expiry_hours', label: 'اعتبار کد تشویقی اتمام حجم (ساعت)', type: 'number' },
  ]},

  // ------------------------------------------------------ سرویس‌های ویژه
  { tab: 'services', title: 'کانفیگ تست رایگان', fields: [
    { key: 'test_config_panel_volume_gb', label: 'حجم کانفیگ تست (گیگابایت)', type: 'number' },
    { key: 'test_config_panel_duration_days', label: 'مدت اعتبار کانفیگ تست (روز)', type: 'number' },
  ]},
  { tab: 'services', title: 'کانفیگ شخصی/سفارشی', fields: [
    { key: 'custom_config_enabled', label: 'فعال بودن ساخت کانفیگ شخصی', type: 'bool' },
    { key: 'custom_config_min_gb', label: 'حداقل حجم مجاز (گیگ)', type: 'number' },
    { key: 'custom_config_max_gb', label: 'حداکثر حجم مجاز (گیگ)', type: 'number' },
    { key: 'custom_config_duration_days', label: 'مدت اعتبار (روز)', type: 'number' },
    { key: 'btn_custom_config', label: 'متن دکمه ساخت کانفیگ شخصی', type: 'text' },
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
  $$('#settings-tabs-nav .tab-btn', root).forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
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

function menuOrderRowHtml(item, idx) {
  return `
    <div class="menu-order-row" data-idx="${idx}">
      <span class="menu-order-drag-handle" data-idx="${idx}">⠿</span>
      <span class="menu-order-label">${esc(item.label)}${item.admin_only ? ' <span class="card-sub">(فقط ادمین)</span>' : ''}</span>
      ${item.enabled === false ? '<span class="chip" style="color:var(--rose)">غیرفعال</span>' : ''}
      <div class="menu-order-arrows">
        <button type="button" class="btn btn-sm btn-ghost" data-order-up="${idx}" ${idx === 0 ? 'disabled' : ''}>▲</button>
        <button type="button" class="btn btn-sm btn-ghost" data-order-down="${idx}" ${idx === menuOrderItems.length - 1 ? 'disabled' : ''}>▼</button>
      </div>
    </div>`;
}

function renderMenuOrderList() {
  const list = $('#menu-order-list', content());
  if (!list) return;
  list.innerHTML = menuOrderItems.map((item, idx) => menuOrderRowHtml(item, idx)).join('');
  $$('[data-order-up]', list).forEach(b => b.addEventListener('click', () => moveMenuOrderItem(Number(b.dataset.orderUp), -1)));
  $$('[data-order-down]', list).forEach(b => b.addEventListener('click', () => moveMenuOrderItem(Number(b.dataset.orderDown), 1)));
  $$('.menu-order-drag-handle', list).forEach(h => h.addEventListener('pointerdown', onMenuOrderDragStart));
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

  const onMove = (moveEvt) => {
    if (!menuOrderDragState) return;
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
    if (menuOrderDragState && menuOrderDragState.currentIdx !== menuOrderDragState.startIdx) {
      const { startIdx: s, currentIdx: c } = menuOrderDragState;
      const [moved] = menuOrderItems.splice(s, 1);
      menuOrderItems.splice(c, 0, moved);
    }
    menuOrderDragState = null;
    renderMenuOrderList();
  };
  document.addEventListener('pointermove', onMove);
  document.addEventListener('pointerup', onUp);
}

function menuOrderCardHtml(items) {
  menuOrderItems = items;
  return `
    <div class="card" style="margin-bottom:18px">
      <div class="card-head">
        <h3>ترتیب دکمه‌های منوی ربات</h3>
        <button class="btn btn-primary btn-sm" id="menu-order-save">ذخیره ترتیب</button>
      </div>
      <span class="card-sub">با گرفتن دستگیره ⠿ (یا فلش‌ها) ترتیب نمایش دکمه‌های منوی اصلی ربات را جابه‌جا کن.</span>
      <div id="menu-order-list" style="margin-top:12px"></div>
    </div>`;
}

async function saveMenuOrder() {
  const btn = $('#menu-order-save', content());
  btn.disabled = true;
  const prevTxt = btn.textContent; btn.textContent = 'در حال ذخیره...';
  try {
    await apiPost('/settings/menu-order', { order: menuOrderItems.map(i => i.key) });
    toast('ترتیب منو ذخیره شد.');
  } catch (e) {
    handleErr(e);
  } finally {
    btn.disabled = false; btn.textContent = prevTxt;
  }
}

async function renderSettings() {
  const [settings, rate, menuOrder] = await Promise.all([
    apiGet('/settings'),
    apiGet('/exchange-rate').catch(e => ({ ok: false, rate: null, source: null, updated_at: null, error: e.message })),
    apiGet('/settings/menu-order').catch(() => []),
  ]);
  setContent(`
    ${settingsTabsHtml()}

    <div data-settings-tab="content" style="${settingsActiveTab === 'content' ? '' : 'display:none'}">
      ${menuOrderCardHtml(menuOrder)}
    </div>

    <div data-settings-tab="payment" style="${settingsActiveTab === 'payment' ? '' : 'display:none'}">
      ${rateCardHtml(rate)}
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
  $('#rate-refresh').addEventListener('click', async () => {
    const btn = $('#rate-refresh');
    btn.disabled = true; btn.textContent = 'در حال دریافت...';
    try {
      await apiPost('/exchange-rate/refresh');
      toast('نرخ بروزرسانی شد.');
    } catch (e) {
      handleErr(e);
    } finally {
      renderSettings();
    }
  });
}

/* ================================================================ logs === */
let logsPage = 1;
let logsFilter = { action: '', record_type: '', record_id: '' };
const RECORD_TYPE_LABEL = {
  order: 'سفارش', topup: 'شارژ کیف پول', user: 'کاربر', category: 'دسته‌بندی', product: 'محصول',
  config: 'کانفیگ', discount: 'کد تخفیف', ticket: 'تیکت', reseller: 'نماینده', panel: 'پنل VPN',
  setting: 'تنظیم', webadmin: 'ادمین پنل',
};
const ACTION_LABEL = {
  admin_add: 'افزودن ادمین', admin_remove: 'حذف ادمین', admin_role_change: 'تغییر نقش ادمین',
  backup_create: 'ساخت بکاپ', backup_restore: 'بازیابی بکاپ', broadcast: 'پیام همگانی',
  card_change: 'تغییر شماره کارت', category_add: 'افزودن دسته‌بندی', category_delete: 'حذف دسته‌بندی',
  category_edit: 'ویرایش دسته‌بندی', category_toggle: 'فعال/غیرفعال کردن دسته‌بندی',
  config_delete: 'حذف کانفیگ', configs_add: 'افزودن کانفیگ', custom_config_approve: 'تایید کانفیگ سفارشی',
  custom_config_toggle: 'فعال/غیرفعال کردن کانفیگ سفارشی', discount_add: 'افزودن کد تخفیف',
  discount_delete: 'حذف کد تخفیف', discount_toggle: 'فعال/غیرفعال کردن کد تخفیف',
  exchange_rate_refresh: 'بروزرسانی نرخ ارز', menu_order_change: 'تغییر ترتیب منو',
  order_approve: 'تایید سفارش', order_reject: 'رد سفارش', orphan_db_file_delete: 'حذف فایل بلااستفاده',
  panel_add: 'افزودن پنل VPN', panel_delete: 'حذف پنل VPN', panel_server_add: 'افزودن سرور پنل',
  panel_server_delete: 'حذف سرور پنل', panel_server_template_update: 'ویرایش قالب سرور پنل',
  panel_server_usage_toggle: 'فعال/غیرفعال کردن مصرف سرور', plisio_key_change: 'تغییر کلید Plisio',
  pricing_tier_add: 'افزودن رده قیمتی', pricing_tier_delete: 'حذف رده قیمتی', product_add: 'افزودن محصول',
  product_delete: 'حذف محصول', product_edit: 'ویرایش محصول', product_price_edit: 'ویرایش قیمت محصول',
  product_toggle: 'فعال/غیرفعال کردن محصول', reseller_credit_adjust: 'تغییر اعتبار نماینده',
  reseller_credit_toggle: 'فعال/غیرفعال کردن اعتبار نماینده', reseller_orphan_purge: 'پاکسازی نمایندگان بلااستفاده',
  reseller_panel_set: 'تنظیم پنل نماینده', reseller_request_admin_cancel: 'لغو درخواست نمایندگی',
  reseller_request_payment_approve: 'تایید پرداخت نمایندگی', reseller_request_quote: 'ثبت مبلغ درخواست نمایندگی',
  reseller_request_reject: 'رد درخواست نمایندگی', reseller_status_toggle: 'فعال/غیرفعال کردن نماینده',
  reset_test_configs: 'ریست کانفیگ‌های تست', setting_change: 'تغییر تنظیمات', support_reply: 'پاسخ پشتیبانی',
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

/* ========================================================== webadmins === */
const PERM_LABEL = {
  orders: 'سفارش‌ها و شارژ کیف پول', users: 'کاربران (بلاک/کیف پول)', catalog: 'محصولات و بانک کانفیگ',
  discounts: 'کدهای تخفیف', tickets: 'تیکت‌ها و چت زنده', broadcast: 'پیام همگانی',
  resellers: 'نمایندگی‌ها', panels: 'پنل‌های VPN و نرخ ارز', system: 'سیستم، بکاپ (وضعیت) و لاگ‌ها',
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

/* ============================================================= system === */
async function renderSystem() {
  const jobs = await apiGet('/system/jobs');
  const r = jobs.renewal;
  const stockRows = jobs.stock;
  const lowCount = stockRows.filter(p => p.low).length;
  const backupStatus = await apiGet('/system/backup/status');
  const isOwner = ME.role === 'owner';

  setContent(`
    <div class="card" style="margin-bottom:18px">
      <div class="card-head"><h3>یادآوری‌های تمدید/حجم</h3></div>
      <p class="card-sub" style="margin-bottom:10px">این بخش فقط وضعیت آخرین اجرا را نشان می‌دهد؛ زمان‌بندی اجرا (هر ۱ ساعت) از کد بات کنترل می‌شود و از اینجا قابل تغییر نیست.</p>
      <div class="chip-row">
        <span class="chip">آخرین اجرا: ${r.last_run ? fmtDate(r.last_run) : 'هنوز اجرا نشده'}</span>
        <span class="chip">یادآوری تاریخ ارسال‌شده: ${fmt(r.last_date_sent)}</span>
        <span class="chip">یادآوری حجم ارسال‌شده: ${fmt(r.last_volume_sent)}</span>
      </div>
    </div>

    <div class="card" style="margin-bottom:18px">
      <div class="card-head">
        <h3>وضعیت لحظه‌ای موجودی محصولات</h3>
        <span class="card-sub">${lowCount ? `${lowCount} محصول زیر آستانه هشدار` : 'همه محصولات موجودی کافی دارند'}</span>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>محصول</th><th>موجودی</th><th>آستانه هشدار</th><th>وضعیت</th></tr></thead>
        <tbody>${stockRows.map(p => `<tr>
          <td>${esc(p.name)}</td>
          <td class="mono">${fmt(p.stock)}</td>
          <td class="mono">${fmt(p.threshold)}</td>
          <td>${p.low
            ? `<span class="badge badge-rejected">کم${p.alerted ? ' · هشدار ارسال شد' : ''}</span>`
            : '<span class="badge badge-approved">کافی</span>'}</td>
        </tr>`).join('') || `<tr><td colspan="4" class="empty-state"><div class="icon">${svg('empty')}</div>محصولی برای نمایش نیست</td></tr>`}</tbody>
      </table></div>
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
      ${activeMeta.supportsMode ? `
      <div class="card-head" style="margin-top:16px">
        <h3 style="font-size:13.5px">حالت نمایش</h3>
        <div class="mode-toggle" id="mode-toggle">
          <button data-mode="light" class="${cur.mode === 'light' ? 'active' : ''}">☀️ روشن</button>
          <button data-mode="dark" class="${cur.mode === 'dark' ? 'active' : ''}">🌙 تیره</button>
        </div>
      </div>` : ''}
      <span class="card-sub">این یک ترجیح شخصیه و فقط برای همین مرورگر ذخیره می‌شود؛ روی نمایش پنل برای بقیه‌ی ادمین‌ها اثری ندارد.</span>
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
    applyThemeChoice(id, loadTheme().mode);
    renderAccount();
  }));
  $$('#mode-toggle button', content()).forEach(btn => btn.addEventListener('click', () => {
    applyThemeChoice(loadTheme().theme, btn.dataset.mode);
    $$('#mode-toggle button', content()).forEach(b => b.classList.toggle('active', b === btn));
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

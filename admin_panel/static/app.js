'use strict';

/* ============================================================ state === */
let ME = null;
let CURRENT_TAB = 'dashboard';
let SUPPORT_POLL_TIMER = null;
function stopSupportPoll() { if (SUPPORT_POLL_TIMER) { clearInterval(SUPPORT_POLL_TIMER); SUPPORT_POLL_TIMER = null; } }

/* ============================================================= theme === */
const THEMES = [
  { id: '6', name: 'سایبرپانک // NEXUS', desc: 'پیش‌فرض جدید — رادار زنده، گلیچ، شبکه‌ی نئونی', colors: ['#ff2e88', '#21e6c1', '#ffb020'] },
  { id: '1', name: 'فلت کورپوریت', desc: 'ساده، تمیز، اداری', colors: ['#0f6e5f', '#1f7ae0', '#c78a10'] },
  { id: '2', name: 'نئون گلس', desc: 'طرح کلاسیک ShopVPN', colors: ['#8B5CF6', '#EC4899', '#22D3EE'] },
  { id: '3', name: 'ترمینال عملیاتی', desc: 'مونوسپیس، حس اتاق سرور', colors: ['#3ddc84', '#ff6b52', '#e0b23c'] },
  { id: '4', name: 'بنتوی نرم', desc: 'گرم، گرد، صمیمی', colors: ['#d97757', '#5b8a72', '#c99a3a'] },
  { id: '5', name: 'پالس شبکه', desc: 'HUD تیره، درخشش نئونی، حس اتاق کنترل', colors: ['#00e5ff', '#7c5cff', '#ff4fd8'] },
];
function loadTheme() {
  try { return JSON.parse(localStorage.getItem('sv-theme')) || { style: '6', mode: 'dark' }; }
  catch (e) { return { style: '6', mode: 'dark' }; }
}
function applyTheme(style, mode) {
  document.documentElement.setAttribute('data-style', style);
  document.documentElement.setAttribute('data-mode', mode);
  localStorage.setItem('sv-theme', JSON.stringify({ style, mode }));
}
applyTheme(loadTheme().style, loadTheme().mode);

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
  if (!res.ok) throw new Error(data.detail || 'خطای ناشناخته');
  return data;
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

/* ============================================================ modal === */
function openModal(title, bodyHtml, onMount) {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `<div class="modal"><h3>${title}</h3><div class="modal-body">${bodyHtml}</div></div>`;
  backdrop.addEventListener('click', e => { if (e.target === backdrop) backdrop.remove(); });
  document.body.appendChild(backdrop);
  if (onMount) onMount(backdrop.querySelector('.modal-body'), () => backdrop.remove());
  return backdrop;
}

/* ============================================================== nav === */
const NAV = [
  { key: 'dashboard', label: 'داشبورد', icon: 'dashboard', role: 'any' },
  { key: 'orders', label: 'سفارش‌ها', icon: 'orders', role: 'any' },
  { key: 'topups', label: 'شارژ کیف پول', icon: 'topups', role: 'any' },
  { key: 'users', label: 'کاربران', icon: 'users', role: 'any' },
  { key: 'catalog', label: 'محصولات و بانک کانفیگ', icon: 'catalog', role: 'senior' },
  { key: 'discounts', label: 'کدهای تخفیف', icon: 'discounts', role: 'senior' },
  { key: 'tickets', label: 'تیکت‌ها', icon: 'tickets', role: 'any' },
  { key: 'support', label: 'چت زنده', icon: 'support', role: 'any' },
  { key: 'broadcast', label: 'پیام همگانی', icon: 'broadcast', role: 'full' },
  { key: 'resellers', label: 'نمایندگی‌ها', icon: 'resellers', role: 'senior' },
  { key: 'panels', label: 'پنل‌های VPN', icon: 'panels', role: 'senior' },
  { key: 'system', label: 'سیستم و نگهداری', icon: 'logs', role: 'senior' },
  { key: 'settings', label: 'تنظیمات و برندینگ', icon: 'settings', role: 'senior' },
  { key: 'logs', label: 'لاگ فعالیت ادمین‌ها', icon: 'logs', role: 'senior' },
  { key: 'webadmins', label: 'کاربران پنل', icon: 'webadmins', role: 'owner' },
  { key: 'account', label: 'حساب من', icon: 'account', role: 'any' },
];
const FULL_ROLES = ['owner', 'admin', 'mid'];
const SENIOR_ROLES = ['owner', 'admin'];
function canSee(navRole) {
  if (navRole === 'any') return true;
  if (navRole === 'full') return FULL_ROLES.includes(ME.role);
  if (navRole === 'senior') return SENIOR_ROLES.includes(ME.role);
  if (navRole === 'owner') return ME.role === 'owner';
  return false;
}
const ROLE_LABEL = { owner: 'مالک', admin: 'مدیر کامل', mid: 'ادمین میانی', support: 'پشتیبان' };

function renderNav() {
  const el = $('#nav-tunnel');
  const CYCLE = ['nav-c1', 'nav-c2', 'nav-c3', 'nav-c4'];
  el.innerHTML = NAV.filter(n => canSee(n.role)).map((n, i) => `
    <div class="nav-item ${CYCLE[i % 4]} ${n.key === CURRENT_TAB ? 'active' : ''}" data-tab="${n.key}">
      <span class="nav-icon">${svg(n.icon)}</span><span>${n.label}</span>
    </div>`).join('');
  $$('.nav-item', el).forEach(item => item.addEventListener('click', () => { goTo(item.dataset.tab); closeSidebar(); }));
}

function goTo(tab) {
  stopSupportPoll();
  CURRENT_TAB = tab;
  renderNav();
  $('#page-title').textContent = NAV.find(n => n.key === tab)?.label || '';
  renderPage(tab);
}

/* ============================================================= boot === */
async function boot() {
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
  goTo('dashboard');
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
  `);

  const root = content();
  $$('.value[data-count]', root).forEach(el => animateCount(el, Number(el.dataset.count)));
  activateRings(root);
  activateBars(root);
  activateBarFills(root);
  drawRadar(root, radarAxes, radarValues, '#8B5CF6');
  if (sys) activateGauge(root, healthPct);
  drawHeroNet($('#hero-net-canvas', root));
}

/* ============================================================ orders === */
let ordersStatus = 'pending';
async function renderOrders() {
  const canAct = FULL_ROLES.includes(ME.role);
  const orders = await apiGet(`/orders?status=${ordersStatus}`);
  setContent(`
    <div class="tabs">
      ${['pending', 'approved', 'rejected'].map(s => `<button class="tab-btn ${s === ordersStatus ? 'active' : ''}" data-status="${s}">${{ pending: 'در انتظار', approved: 'تایید شده', rejected: 'رد شده' }[s]}</button>`).join('')}
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>#</th><th>کاربر</th><th>محصول</th><th>تعداد</th><th>مبلغ</th><th>تاریخ</th>${canAct && ordersStatus === 'pending' ? '<th>عملیات</th>' : ''}</tr></thead>
        <tbody>
          ${orders.map(o => `<tr>
            <td class="mono">#${o.id}</td>
            <td>${esc(o.username || o.user_id)}</td>
            <td>${esc(o.product_name)}</td>
            <td class="mono">${fmt(o.quantity || 1)}</td>
            <td class="mono">${fmt(o.final_price ?? o.base_price)}</td>
            <td class="mono">${fmtDate(o.created_at)}</td>
            ${canAct && ordersStatus === 'pending' ? `<td>
              <button class="btn btn-primary btn-sm" data-approve="${o.id}">تایید</button>
              <button class="btn btn-danger btn-sm" data-reject="${o.id}">رد</button>
            </td>` : ''}
          </tr>`).join('') || `<tr><td colspan="7" class="empty-state"><div class="icon">${svg('empty')}</div>سفارشی در این وضعیت نیست</td></tr>`}
        </tbody>
      </table></div>
    </div>
  `);
  $$('.tab-btn', content()).forEach(b => b.addEventListener('click', () => { ordersStatus = b.dataset.status; renderOrders(); }));
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
  const canAct = FULL_ROLES.includes(ME.role);
  const topups = await apiGet(`/topups?status=${topupsStatus}`);
  setContent(`
    <div class="tabs">
      ${['pending', 'approved', 'rejected'].map(s => `<button class="tab-btn ${s === topupsStatus ? 'active' : ''}" data-status="${s}">${{ pending: 'در انتظار', approved: 'تایید شده', rejected: 'رد شده' }[s]}</button>`).join('')}
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>#</th><th>کاربر</th><th>مبلغ</th><th>تاریخ</th>${canAct && topupsStatus === 'pending' ? '<th>عملیات</th>' : ''}</tr></thead>
        <tbody>${topups.map(t => `<tr>
          <td class="mono">#${t.id}</td><td>${esc(t.username || t.user_id)}</td>
          <td class="mono">${fmt(t.amount)}</td><td class="mono">${fmtDate(t.created_at)}</td>
          ${canAct && topupsStatus === 'pending' ? `<td>
            <button class="btn btn-primary btn-sm" data-approve="${t.id}">تایید</button>
            <button class="btn btn-danger btn-sm" data-reject="${t.id}">رد</button>
          </td>` : ''}
        </tr>`).join('') || `<tr><td colspan="5" class="empty-state"><div class="icon">${svg('empty')}</div>درخواستی در این وضعیت نیست</td></tr>`}</tbody>
      </table></div>
    </div>
  `);
  $$('.tab-btn', content()).forEach(b => b.addEventListener('click', () => { topupsStatus = b.dataset.status; renderTopups(); }));
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
            ${FULL_ROLES.includes(ME.role) ? (u.is_blocked
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
  const isSenior = SENIOR_ROLES.includes(ME.role);
  openModal(`کاربر ${esc(d.user.username || tgId)}`, `
    <div class="chip-row" style="margin-bottom:14px">
      <span class="chip">کیف پول: ${fmt(d.user.referral_credit)} تومان</span>
      <span class="chip">زیرمجموعه‌ها: ${fmt(d.referral.count)}</span>
      ${d.is_reseller ? `<span class="chip">اعتبار نمایندگی: ${fmt(d.reseller_credit)} گیگ</span>` : ''}
    </div>
    ${isSenior ? `<div class="form-row" style="margin-bottom:14px">
      <input class="input" id="wallet-delta" type="number" placeholder="مبلغ (مثبت=افزایش، منفی=کاهش)">
      <button class="btn btn-primary" id="wallet-submit">اعمال</button>
    </div>` : ''}
    <h4 style="font-size:13px;margin:10px 0">سفارش‌های اخیر</h4>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>محصول</th><th>مبلغ</th><th>وضعیت</th></tr></thead>
    <tbody>${d.orders.slice(0, 10).map(o => `<tr><td class="mono">#${o.id}</td><td>${esc(o.product_name || '-')}</td><td class="mono">${fmt(o.final_price)}</td><td>${o.status}</td></tr>`).join('') || '<tr><td colspan="4" class="empty-state">سفارشی نیست</td></tr>'}</tbody></table></div>
  `, (body, close) => {
    const submitBtn = $('#wallet-submit', body);
    if (submitBtn) submitBtn.addEventListener('click', async () => {
      const delta = Number($('#wallet-delta', body).value);
      if (!delta) return;
      try { await apiPost(`/users/${tgId}/wallet`, { delta }); toast('کیف پول به‌روزرسانی شد.'); close(); }
      catch (e) { handleErr(e); }
    });
  });
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
  const configs = await apiGet(`/products/${productId}/configs`);
  openModal('بانک کانفیگ', `
    <textarea class="input" id="new-links" rows="4" placeholder="هر خط یک لینک کانفیگ..."></textarea>
    <button class="btn btn-primary btn-block" id="add-links" style="margin-top:10px">افزودن لینک‌ها</button>
    <h4 style="font-size:13px;margin:16px 0 8px">لینک‌های آزاد (${configs.length})</h4>
    <div class="table-wrap" style="max-height:220px;overflow-y:auto">
      <table><tbody>${configs.map(c => `<tr><td style="font-size:11px;word-break:break-all">${esc(c.link)}</td><td><button class="btn btn-danger btn-sm" data-del-cfg="${c.id}">حذف</button></td></tr>`).join('') || '<tr><td class="empty-state">خالی است</td></tr>'}</tbody></table>
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
    $$('[data-del-cfg]', body).forEach(b => b.addEventListener('click', async () => {
      try { await apiDelete(`/configs/${b.dataset.delCfg}`); close(); showConfigBank(productId); } catch (e) { handleErr(e); }
    }));
  });
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
  const canAct = FULL_ROLES.includes(ME.role);
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
  const resellers = await apiGet('/resellers');
  setContent(`
    <div class="card"><div class="table-wrap"><table>
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
async function renderSettings() {
  const settings = await apiGet('/settings');
  const fields = [
    ['shop_name', 'نام فروشگاه'],
    ['miniapp_banner_text', 'متن بنر Mini App'],
    ['low_stock_threshold', 'آستانه هشدار موجودی کم'],
    ['referral_percent', 'درصد پورسانت رفرال'],
  ];
  const cur = loadTheme();
  setContent(`
    <div class="card" style="margin-bottom:18px">
      <div class="card-head">
        <h3>ظاهر پنل</h3>
        <div class="mode-toggle" id="mode-toggle">
          <button data-mode="light" class="${cur.mode === 'light' ? 'active' : ''}">☀️ روشن</button>
          <button data-mode="dark" class="${cur.mode === 'dark' ? 'active' : ''}">🌙 تیره</button>
        </div>
      </div>
      <div class="theme-grid" id="theme-grid">
        ${THEMES.map(t => `
          <div class="theme-opt ${cur.style === t.id ? 'active' : ''}" data-style="${t.id}">
            <div class="swatch">${t.colors.map(c => `<i style="background:${c}"></i>`).join('')}</div>
            <strong>${esc(t.name)}</strong>
            <span>${esc(t.desc)}</span>
          </div>`).join('')}
      </div>
      <span class="card-sub">هر وقت خواستی می‌تونی طرح یا حالت روشن/تیره رو عوض کنی؛ فقط برای همین مرورگر ذخیره می‌شود.</span>
    </div>

    <div class="card"><div class="form-grid">
      ${fields.map(([key, label]) => `
        <label class="field"><span>${label}</span>
          <input class="input" data-key="${key}" value="${esc(settings[key] || '')}">
        </label>`).join('')}
      <button class="btn btn-primary" id="settings-save">ذخیره تغییرات</button>
    </div></div>
  `);
  $$('.theme-opt', content()).forEach(el => el.addEventListener('click', () => {
    applyTheme(el.dataset.style, loadTheme().mode);
    $$('.theme-opt', content()).forEach(o => o.classList.toggle('active', o === el));
  }));
  $$('#mode-toggle button', content()).forEach(btn => btn.addEventListener('click', () => {
    applyTheme(loadTheme().style, btn.dataset.mode);
    $$('#mode-toggle button', content()).forEach(b => b.classList.toggle('active', b === btn));
  }));
  $('#settings-save').addEventListener('click', async () => {
    try {
      for (const inp of $$('[data-key]', content())) {
        await apiPost('/settings', { key: inp.dataset.key, value: inp.value });
      }
      toast('تنظیمات ذخیره شد.');
    } catch (e) { handleErr(e); }
  });
}

/* ================================================================ logs === */
let logsPage = 1;
async function renderLogs() {
  const res = await apiGet(`/admin-logs?page=${logsPage}`);
  const pages = Math.max(Math.ceil(res.total / res.limit), 1);
  setContent(`
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>ادمین</th><th>عملیات</th><th>جزئیات</th><th>تاریخ</th></tr></thead>
      <tbody>${res.items.map(l => `<tr><td class="mono">${l.admin_id}</td><td>${esc(l.action)}</td><td>${esc(l.details)}</td><td class="mono">${fmtDate(l.created_at)}</td></tr>`).join('') || '<tr><td colspan="4" class="empty-state">لاگی ثبت نشده</td></tr>'}</tbody>
    </table></div>
    <div class="pager">${Array.from({ length: pages }, (_, i) => i + 1).map(p => `<button class="btn btn-sm ${p === logsPage ? 'btn-primary' : ''}" data-page="${p}">${p}</button>`).join('')}</div>
    </div>
  `);
  $$('[data-page]', content()).forEach(b => b.addEventListener('click', () => { logsPage = Number(b.dataset.page); renderLogs(); }));
}

/* ========================================================== webadmins === */
async function renderWebAdmins() {
  const admins = await apiGet('/web-admins');
  setContent(`
    <div class="toolbar"><button class="btn btn-primary btn-sm" id="add-admin">+ کاربر پنل جدید</button></div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>یوزرنیم</th><th>نقش</th><th>وضعیت</th><th>آخرین ورود</th><th>عملیات</th></tr></thead>
      <tbody>${admins.map(a => `<tr>
        <td>${esc(a.username)}</td>
        <td><span class="badge badge-${a.role}">${ROLE_LABEL[a.role]}</span></td>
        <td>${a.is_active ? '<span class="badge badge-approved">فعال</span>' : '<span class="badge badge-rejected">غیرفعال</span>'}</td>
        <td class="mono">${fmtDate(a.last_login)}</td>
        <td>${a.role === 'owner' ? '<span class="card-sub">مالک</span>' : `
          <select class="input" data-role="${a.id}" style="width:auto;display:inline-block">
            ${['admin', 'mid', 'support'].map(r => `<option value="${r}" ${r === a.role ? 'selected' : ''}>${ROLE_LABEL[r]}</option>`).join('')}
          </select>
          <button class="btn btn-sm" data-toggle-active="${a.id}" data-active="${a.is_active}">${a.is_active ? 'غیرفعال' : 'فعال'}</button>
          <button class="btn btn-danger btn-sm" data-del="${a.id}">حذف</button>`}</td>
      </tr>`).join('')}</tbody>
    </table></div></div>
  `);
  $('#add-admin').addEventListener('click', () => openModal('کاربر پنل جدید', `
    <div class="form-grid">
      <input class="input" id="na-user" placeholder="یوزرنیم">
      <input class="input" id="na-pass" type="password" placeholder="پسورد (حداقل ۸ کاراکتر)">
      <select class="input" id="na-role">${['admin', 'mid', 'support'].map(r => `<option value="${r}">${ROLE_LABEL[r]}</option>`).join('')}</select>
      <button class="btn btn-primary" id="na-save">ثبت</button>
    </div>`, (body, close) => {
    $('#na-save', body).addEventListener('click', async () => {
      try {
        await apiPost('/web-admins', { username: $('#na-user', body).value.trim(), password: $('#na-pass', body).value, role: $('#na-role', body).value });
        toast('کاربر ساخته شد.'); close(); renderWebAdmins();
      } catch (e) { handleErr(e); }
    });
  }));
  $$('[data-role]', content()).forEach(sel => sel.addEventListener('change', async () => {
    try { await apiPost(`/web-admins/${sel.dataset.role}/role`, { role: sel.value }); toast('نقش تغییر کرد.'); } catch (e) { handleErr(e); renderWebAdmins(); }
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

    <div class="card">
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
  `);
}

/* ============================================================= account === */
async function renderAccount() {
  setContent(`
    <div class="card" style="max-width:420px">
      <div class="card-head"><h3>تغییر پسورد</h3></div>
      <div class="form-grid">
        <input class="input" id="acc-cur" type="password" placeholder="پسورد فعلی">
        <input class="input" id="acc-new" type="password" placeholder="پسورد جدید (حداقل ۸ کاراکتر)">
        <button class="btn btn-primary" id="acc-save">تغییر پسورد</button>
      </div>
    </div>
  `);
  $('#acc-save').addEventListener('click', async () => {
    try {
      await apiPost('/me/password', { current_password: $('#acc-cur').value, new_password: $('#acc-new').value });
      toast('پسورد تغییر کرد.');
      $('#acc-cur').value = ''; $('#acc-new').value = '';
    } catch (e) { handleErr(e); }
  });
}

boot();

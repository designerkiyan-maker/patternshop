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
  if (navRole === 'any') return true;
  if (navRole === 'owner') return ME.role === 'owner';
  return hasPerm(navRole);
}
const ROLE_LABEL = { owner: 'مالک', admin: 'مدیر کامل', mid: 'ادمین میانی', support: 'پشتیبان' };

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
    html += `
    <div class="nav-item ${CYCLE[i % 4]} ${n.key === CURRENT_TAB ? 'active' : ''}" data-tab="${n.key}">
      <span class="nav-icon">${svg(n.icon)}</span><span>${n.label}</span>
    </div>`;
  });
  el.innerHTML = html;
  $$('.nav-item', el).forEach(item => item.addEventListener('click', () => { goTo(item.dataset.tab); closeSidebar(); }));
}

function goTo(tab) {
  stopSupportPoll();
  CURRENT_TAB = tab;
  renderNav();
  $('#page-title').textContent = NAV.find(n => n.key === tab)?.label || '';
  renderPage(tab);
}

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-history]');
  if (!btn) return;
  const [recordType, recordId] = btn.dataset.history.split(':');
  $$('.modal-backdrop').forEach(m => m.remove());
  goToLogsFor(recordType, recordId);
});

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
  const canAct = hasPerm('orders');
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
            <td class="mono">#${o.id} ${historyBtn('order', o.id)}</td>
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
  const canAct = hasPerm('orders');
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
  openModal(`کاربر ${esc(d.user.username || tgId)}`, `
    <div class="chip-row" style="margin-bottom:14px">
      <span class="chip">کیف پول: ${fmt(d.user.referral_credit)} تومان</span>
      <span class="chip">زیرمجموعه‌ها: ${fmt(d.referral.count)}</span>
      ${d.is_reseller ? `<span class="chip">اعتبار نمایندگی: ${fmt(d.reseller_credit)} گیگ</span>` : ''}
      ${historyBtn('user', tgId)}
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
    { key: 'btn_test', label: 'متن دکمه کانفیگ تست', type: 'text' },
    { key: 'test_enabled', label: 'نمایش دکمه کانفیگ تست', type: 'bool' },
    { key: 'btn_my_orders', label: 'متن دکمه سفارش‌های من', type: 'text' },
    { key: 'btn_wallet', label: 'متن دکمه کیف پول', type: 'text' },
    { key: 'btn_referral', label: 'متن دکمه زیرمجموعه‌گیری', type: 'text' },
    { key: 'btn_wheel', label: 'متن دکمه گردونه شانس', type: 'text' },
    { key: 'btn_contact', label: 'متن دکمه ارتباط با پشتیبانی', type: 'text' },
    { key: 'btn_admin_panel', label: 'متن دکمه پنل مدیریت (فقط برای ادمین‌ها)', type: 'text' },
  ]},
  { tab: 'content', title: 'برندینگ و Mini App', fields: [
    { key: 'miniapp_banner_text', label: 'متن بنر Mini App', type: 'text' },
    { key: 'header_image_data', label: 'تصویر هدر / لوگو', type: 'image' },
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
    { key: 'referral_enabled', label: 'فعال بودن سیستم رفرال', type: 'bool' },
    { key: 'referral_percent', label: 'درصد پورسانت رفرال', type: 'number' },
  ]},
  { tab: 'campaign', title: 'گردونه شانس', fields: [
    { key: 'wheel_enabled', label: 'فعال بودن گردونه شانس', type: 'bool' },
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
  $$('[data-key][data-type]', root).forEach(el => items.push({ key: el.dataset.key, value: el.value }));
  $$('.switch[data-key]', root).forEach(sw => items.push({ key: sw.dataset.key, value: sw.dataset.on === '1' ? '1' : '0' }));
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
function goToLogsFor(recordType, recordId) {
  logsFilter = { action: '', record_type: recordType, record_id: String(recordId) };
  logsPage = 1;
  goTo('logs');
}
function historyBtn(recordType, recordId) {
  return hasPerm('system')
    ? `<button class="btn btn-ghost btn-sm" data-history="${recordType}:${recordId}" title="تاریخچه">تاریخچه</button>` : '';
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
          ${actionsRes.actions.map(a => `<option value="${a}" ${a === logsFilter.action ? 'selected' : ''}>${esc(a)}</option>`).join('')}
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
        <td class="mono">${l.admin_id}</td><td>${esc(l.action)}</td>
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
async function renderAccount() {
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
  $$('.theme-opt', content()).forEach(el => el.addEventListener('click', () => {
    applyTheme(el.dataset.style, loadTheme().mode);
    $$('.theme-opt', content()).forEach(o => o.classList.toggle('active', o === el));
  }));
  $$('#mode-toggle button', content()).forEach(btn => btn.addEventListener('click', () => {
    applyTheme(loadTheme().style, btn.dataset.mode);
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

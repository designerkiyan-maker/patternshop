const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
try { tg.setHeaderColor("#0a0e17"); tg.setBackgroundColor("#0a0e17"); } catch (e) {}

const initData = tg.initData; // برای هدر X-Init-Data به بک‌اند فرستاده می‌شود
const content = document.getElementById("content");

// ---------------------------------------------------------------------------
// تبدیل میلادی به شمسی (فقط برای نمایش؛ منطق داخلی همچنان میلادی/ISO است)
// ---------------------------------------------------------------------------
function gregorianToJalali(gy, gm, gd) {
  const g_d_m = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const j_d_m = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
  const div = (a, b) => Math.floor(a / b);

  const gy2 = gy - 1600, gm2 = gm - 1, gd2 = gd - 1;
  let g_day_no = 365 * gy2 + div(gy2 + 3, 4) - div(gy2 + 99, 100) + div(gy2 + 399, 400);
  for (let i = 0; i < gm2; i++) g_day_no += g_d_m[i];
  if (gm2 > 1 && ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0)) g_day_no += 1;
  g_day_no += gd2;

  let j_day_no = g_day_no - 79;
  const j_np = div(j_day_no, 12053);
  j_day_no %= 12053;

  let jy = 979 + 33 * j_np + 4 * div(j_day_no, 1461);
  j_day_no %= 1461;

  if (j_day_no >= 366) {
    jy += div(j_day_no - 1, 365);
    j_day_no = (j_day_no - 1) % 365;
  }

  let jm = 12, jd = j_day_no + 1;
  for (let i = 0; i < 11; i++) {
    if (j_day_no < j_d_m[i]) { jm = i + 1; jd = j_day_no + 1; break; }
    j_day_no -= j_d_m[i];
  }
  return [jy, jm, jd];
}

function toJalaliStr(value, withTime = false) {
  if (!value) return "-";
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return String(value);
  const [jy, jm, jd] = gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  const pad = (n) => String(n).padStart(2, "0");
  let out = `${jy}/${pad(jm)}/${pad(jd)}`;
  if (withTime) out += ` - ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return out;
}

function notify(message) {
  if (tg.showAlert) tg.showAlert(message);
  else alert(message);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Init-Data": initData, ...(options.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "خطا" }));
    if (res.status === 403 && err.detail && err.detail.code === "force_join") {
      showForceJoinGate(err.detail);
      throw new Error(err.detail.message || "برای ادامه باید در کانال عضو شوید.");
    }
    const msg = typeof err.detail === "string" ? err.detail : (err.detail && err.detail.message) || "خطای ناشناخته";
    throw new Error(msg);
  }
  return res.json();
}

// صفحه‌ی عضویت اجباری در کانال - هم‌تراز با force_join.py در ربات اصلی
// که قبل از هر اکشنی (خرید/تاپ‌آپ/گردونه) عضویت را چک می‌کند.
function showForceJoinGate(info) {
  const overlay = document.createElement("div");
  overlay.className = "force-join-overlay";
  overlay.innerHTML = `
    <div class="card" style="max-width:320px;text-align:center">
      <h3><span class="ic">📢</span>عضویت در کانال الزامی است</h3>
      <p style="margin:10px 0">برای استفاده از این بخش، ابتدا باید در کانال زیر عضو شوید:</p>
      <a class="btn" href="${info.join_link}" target="_blank" style="text-decoration:none;display:block;margin-bottom:8px">📢 عضویت در کانال</a>
      <button class="btn outline" id="force-join-recheck-btn">✅ بررسی مجدد عضویت</button>
      <button class="btn outline small" id="force-join-close-btn" style="margin-top:8px">بستن</button>
    </div>
  `;
  document.body.appendChild(overlay);
  document.getElementById("force-join-close-btn").onclick = () => overlay.remove();
  document.getElementById("force-join-recheck-btn").onclick = async () => {
    try {
      const status = await api("/api/force-join-status");
      if (!status.required || status.member) {
        notify("✅ عضویت شما تایید شد.");
        overlay.remove();
      } else {
        notify("هنوز عضو کانال نشده‌اید.");
      }
    } catch (e) { /* از خود force-join-status هیچ‌وقت force_join throw نمی‌کند */ }
  };
}

// آپلود فایل (مولتی‌پارت) - بدون Content-Type دستی تا مرورگر boundary را ست کند
async function apiUpload(path, formData) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "X-Init-Data": initData },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "خطا" }));
    throw new Error(err.detail || "خطای ناشناخته");
  }
  return res.json();
}

function fmt(n) {
  return Number(n).toLocaleString("fa-IR");
}

function formatCardNumber(raw) {
  const digits = String(raw || "").replace(/\D/g, "");
  if (digits.length < 8) return raw || "----";
  return digits.replace(/(.{4})/g, "$1 ").trim();
}

function escHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function skeleton(rows = 3) {
  return `<div class="skeleton-block">${'<div class="skel"></div>'.repeat(rows)}</div>`;
}

function errorState(message) {
  return `<div class="state-msg error"><span class="ic">⚠</span>${message}</div>`;
}

// ---------------------------------------------------------------------------
// استایل‌های حداقلی برای گرید الگوها و فایل‌های دانلود — هم‌راستا با متغیرهای
// تم در style.css (کلاس‌های شیشه‌ای موجود پوشش‌دهنده‌ی کارت با تصویر نیستند).
// ---------------------------------------------------------------------------
const extraStyle = document.createElement("style");
extraStyle.textContent = `
.pattern-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.pattern-card {
  background: var(--glass); border: 1px solid var(--glass-brd);
  border-radius: var(--radius-md); overflow: hidden; cursor: pointer;
  backdrop-filter: blur(10px); transition: transform .12s ease;
}
.pattern-card:active { transform: scale(.97); }
.pattern-card.disabled { opacity: .55; cursor: not-allowed; }
.product-thumb { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; background: var(--glass-2); }
.product-thumb-ph {
  width: 100%; aspect-ratio: 1 / 1; display: flex; align-items: center; justify-content: center;
  font-size: 36px; background: var(--glass-2); border-bottom: 1px solid var(--glass-brd);
}
.pattern-card-body { padding: 10px 12px 12px; }
.pattern-badge-row { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-top: 8px; }
.pattern-hero { border-radius: var(--radius-md); }
.order-row { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.order-row.expandable { cursor: pointer; }
.order-files {
  margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-soft);
  display: flex; flex-direction: column; gap: 6px;
}
.chat-bubble.incoming {
  align-self: flex-end;
  background: var(--glass-2); border: 1px solid var(--glass-brd);
  color: var(--text); border-bottom-left-radius: 4px;
}
`;
document.head.appendChild(extraStyle);

// ---------------------------------------------------------------------------
// دریافت باینری با هدر احراز هویت (پیش‌نمایش الگو / دانلود فایل‌ها)
// ---------------------------------------------------------------------------
async function fetchBlob(path) {
  const res = await fetch(path, { headers: { "X-Init-Data": initData } });
  if (!res.ok) throw new Error("خطا در دریافت فایل");
  return res.blob();
}

// کش پیش‌نمایش‌ها: با هر ورود دوباره به فروشگاه باطل می‌شود
const previewCache = new Map(); // productId -> objectURL

function revokePreviewCache() {
  previewCache.forEach((url) => { try { URL.revokeObjectURL(url); } catch (e) {} });
  previewCache.clear();
}

function loadProductPreview(img, productId) {
  const cached = previewCache.get(productId);
  if (cached) { img.src = cached; return; }
  fetchBlob(`/api/products/${productId}/preview`)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      previewCache.set(productId, url);
      if (img.isConnected) img.src = url;
    })
    .catch(() => {
      if (img.isConnected) {
        // اگر پیش‌نمایش در دسترس نبود، جای‌نگهدار را نشان بده
        const ph = document.createElement("div");
        ph.className = "product-thumb-ph";
        ph.textContent = "🧵";
        img.replaceWith(ph);
      }
    });
}

async function downloadBlobAsFile(path, filename) {
  const blob = await fetchBlob(path);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  try { a.remove(); } catch (e) {}
  setTimeout(() => { try { URL.revokeObjectURL(url); } catch (e) {} }, 10000);
}

// ---------------------------------------------------------------------------
// الگوی نمونه رایگان (داخل تب فروشگاه)
// ---------------------------------------------------------------------------
let sampleClaimed = false;

function sampleCardHtml() {
  return `
    <div class="card" id="sample-card">
      <h3><span class="ic">🧪</span>الگوی نمونه رایگان</h3>
      <p class="hint-text">قبل از خرید، کیفیت و نحوه‌ی اجرای الگوها را با یک نمونه‌ی رایگان امتحان کن.</p>
      <div id="sample-body">
        ${sampleClaimed
          ? `<button class="btn" id="sample-download-btn" style="margin-top:0">📥 دانلود الگوی نمونه</button>`
          : `<button class="btn" id="sample-get-btn">دریافت الگوی نمونه رایگان</button>`}
      </div>
    </div>
  `;
}

function wireSampleDownload(root) {
  const dl = root && root.querySelector("#sample-download-btn");
  if (!dl) return;
  dl.onclick = async () => {
    dl.disabled = true;
    try {
      await downloadBlobAsFile("/api/sample/file", "pattern-sample.pdf");
    } catch (e) {
      notify("خطا در دانلود: " + e.message);
    }
    dl.disabled = false;
  };
}

function wireSampleCard(root) {
  const getBtn = root.querySelector("#sample-get-btn");
  if (getBtn) getBtn.onclick = async () => {
    getBtn.disabled = true;
    getBtn.textContent = "در حال دریافت...";
    try {
      const r = await api("/api/sample", { method: "POST" });
      sampleClaimed = true;
      tg.HapticFeedback.notificationOccurred("success");
      const body = document.getElementById("sample-body");
      if (body) {
        body.innerHTML = `<button class="btn" id="sample-download-btn" style="margin-top:0">📥 دانلود الگوی نمونه</button>`;
        wireSampleDownload(body);
      }
    } catch (e) {
      // پیام فارسی سرور (مثلاً «شما قبلاً نمونه را دریافت کرده‌اید»)
      notify(e.message);
      getBtn.disabled = false;
      getBtn.textContent = "دریافت الگوی نمونه رایگان";
    }
  };
  wireSampleDownload(root);
}

// ---------------------------------------------------------------------------
// تب پشتیبانی (چت)
// ---------------------------------------------------------------------------

let supportPollTimer = null;
let supportLastId = 0;
let supportSection = "chat"; // chat | tickets
let ticketView = { level: "list" }; // list | thread

function renderSupport() {
  content.innerHTML = `
    <div class="segmented" id="support-section-tabs">
      <button class="seg-btn ${supportSection === "chat" ? "active" : ""}" data-section="chat">گفتگوی زنده</button>
      <button class="seg-btn ${supportSection === "tickets" ? "active" : ""}" data-section="tickets">تیکت‌ها</button>
    </div>
    <div id="support-section-body"></div>
  `;
  document.querySelectorAll("#support-section-tabs .seg-btn").forEach((b) => {
    b.onclick = () => {
      clearInterval(supportPollTimer);
      supportSection = b.dataset.section;
      if (supportSection === "tickets") ticketView = { level: "list" };
      renderSupport();
    };
  });
  if (supportSection === "chat") renderSupportChat();
  else renderTicketsSection();
}

function renderSupportChat() {
  const body = document.getElementById("support-section-body");
  body.innerHTML = `
    <div class="chat-wrap">
      <div class="chat-messages" id="chat-messages">${skeleton(2)}</div>
      <form class="chat-input-row" id="chat-form">
        <input type="text" id="chat-input" placeholder="پیام خود را بنویسید..." autocomplete="off" />
        <button type="submit" class="chat-send-btn" aria-label="ارسال">
          <svg viewBox="0 0 24 24" fill="none"><path d="M4 12 20 4l-6 16-3-7-7-1Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
        </button>
      </form>
    </div>
  `;

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    appendChatMessage({ sender: "user", message: text, created_at: new Date().toISOString() }, true);
    try {
      await api("/api/support/messages", { method: "POST", body: JSON.stringify({ message: text }) });
    } catch (e2) {
      notify("خطا: " + e2.message);
    }
  };

  supportLastId = 0;
  document.getElementById("chat-messages").innerHTML = "";
  loadSupportMessages(true);
  clearInterval(supportPollTimer);
  supportPollTimer = setInterval(() => loadSupportMessages(false), 4000);
}

async function loadSupportMessages(initial) {
  try {
    const msgs = await api(`/api/support/messages?since_id=${supportLastId}`);
    if (initial && msgs.length === 0) {
      document.getElementById("chat-messages").innerHTML =
        `<div class="state-msg"><span class="ic">💬</span>سوالی دارید؟ همینجا بنویسید تا پشتیبانی پاسخ دهد.</div>`;
    }
    msgs.forEach((m) => appendChatMessage(m, false));
  } catch (e) {
    // در پس‌زمینه صامت (ارور نمایش داده نمی‌شود تا مزاحم تایپ کاربر نشود)
  }
}

function appendChatMessage(m, isOptimistic) {
  const box = document.getElementById("chat-messages");
  if (!box) return;
  if (box.querySelector(".state-msg")) box.innerHTML = "";
  if (m.id) supportLastId = Math.max(supportLastId, m.id);
  const time = new Date(m.created_at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${m.sender === "user" ? "mine" : "incoming"}`;
  bubble.innerHTML = `<div class="chat-text"></div><div class="chat-time">${time}</div>`;
  bubble.querySelector(".chat-text").textContent = m.message;
  box.appendChild(bubble);
  box.scrollTop = box.scrollHeight;
}

// ---------------------------------------------------------------------------
// تیکت‌ها (بخش دوم تب پشتیبانی)
// ---------------------------------------------------------------------------

const TICKET_STATUS_LABEL = { open: "🟡 در انتظار پاسخ", answered: "🟢 پاسخ داده‌شده", closed: "⚪️ بسته‌شده" };

async function renderTicketsSection() {
  const body = document.getElementById("support-section-body");
  body.innerHTML = skeleton(2);
  try {
    if (ticketView.level === "list") await renderTicketsList(body);
    else await renderTicketThread(body);
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

async function renderTicketsList(body) {
  const tickets = await api("/api/tickets");
  body.innerHTML = `
    <div class="card">
      ${tickets.length === 0 ? `<div class="hint-text" style="margin:0">هنوز تیکتی ثبت نکرده‌ای.</div>` : tickets.map((t) => `
        <div class="order-block" data-open-ticket="${t.id}" style="cursor:pointer">
          <div class="stat-row">
            <span>${escHtml(t.subject)}</span>
            <span class="hint-text" style="margin:0">${TICKET_STATUS_LABEL[t.status] || t.status}</span>
          </div>
        </div>
      `).join("")}
    </div>
    <button class="btn" id="new-ticket-btn">🎫 ثبت تیکت جدید</button>
    <div class="card" id="new-ticket-form" style="display:none;margin-top:12px">
      <input class="input" id="new-ticket-subject" type="text" placeholder="موضوع تیکت" style="direction:rtl;text-align:right;font-family:var(--font-body);margin-bottom:8px" />
      <textarea class="input" id="new-ticket-message" rows="4" placeholder="توضیح مشکل یا سوال خود را بنویس..." style="direction:rtl;text-align:right;font-family:var(--font-body)"></textarea>
      <button class="btn" id="new-ticket-submit" style="margin-top:8px">ارسال تیکت</button>
    </div>
  `;
  body.querySelectorAll("[data-open-ticket]").forEach((el) => {
    el.onclick = () => {
      ticketView = { level: "thread", ticketId: Number(el.dataset.openTicket) };
      renderTicketsSection();
    };
  });
  document.getElementById("new-ticket-btn").onclick = () => {
    document.getElementById("new-ticket-form").style.display = "";
  };
  document.getElementById("new-ticket-submit").onclick = async () => {
    const subject = document.getElementById("new-ticket-subject").value.trim();
    const message = document.getElementById("new-ticket-message").value.trim();
    if (!subject || !message) { notify("موضوع و متن پیام الزامی است."); return; }
    try {
      const t = await api("/api/tickets", { method: "POST", body: JSON.stringify({ subject, message }) });
      tg.HapticFeedback.notificationOccurred("success");
      ticketView = { level: "thread", ticketId: t.id };
      renderTicketsSection();
    } catch (e) { notify(e.message); }
  };
}

let ticketThreadLastId = 0;

async function renderTicketThread(body) {
  const { ticketId } = ticketView;
  const data = await api(`/api/tickets/${ticketId}/messages`);
  const { ticket, messages } = data;
  ticketThreadLastId = messages.length ? messages[messages.length - 1].id : 0;
  const closed = ticket.status === "closed";
  body.innerHTML = `
    <button class="btn outline small" id="back-to-tickets" style="width:auto;margin-bottom:12px">→ بازگشت به لیست تیکت‌ها</button>
    <div class="eyebrow" style="margin-top:0">${escHtml(ticket.subject)} <span class="hint-text" style="margin-right:6px">${TICKET_STATUS_LABEL[ticket.status] || ""}</span></div>
    <div class="chat-wrap">
      <div class="chat-messages" id="ticket-messages"></div>
      ${closed
        ? `<p class="hint-text" style="text-align:center">این تیکت بسته شده است.</p>`
        : `<form class="chat-input-row" id="ticket-form">
            <input type="text" id="ticket-input" placeholder="پاسخ خود را بنویسید..." autocomplete="off" />
            <button type="submit" class="chat-send-btn" aria-label="ارسال">
              <svg viewBox="0 0 24 24" fill="none"><path d="M4 12 20 4l-6 16-3-7-7-1Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
            </button>
          </form>
          <button class="btn outline small" id="close-ticket-btn" style="width:auto;margin-top:8px">بستن این تیکت</button>`}
    </div>
  `;
  document.getElementById("back-to-tickets").onclick = () => {
    ticketView = { level: "list" };
    renderTicketsSection();
  };
  const box = document.getElementById("ticket-messages");
  if (messages.length === 0) {
    box.innerHTML = `<div class="state-msg"><span class="ic">🎫</span>پیامی هنوز ثبت نشده.</div>`;
  }
  messages.forEach((m) => {
    if (box.querySelector(".state-msg")) box.innerHTML = "";
    const time = new Date(m.created_at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${m.sender === "user" ? "mine" : "incoming"}`;
    bubble.innerHTML = `<div class="chat-text"></div><div class="chat-time">${time}</div>`;
    bubble.querySelector(".chat-text").textContent = m.message;
    box.appendChild(bubble);
  });
  box.scrollTop = box.scrollHeight;

  if (!closed) {
    const form = document.getElementById("ticket-form");
    const input = document.getElementById("ticket-input");
    form.onsubmit = async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      const time = new Date().toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
      const bubble = document.createElement("div");
      bubble.className = "chat-bubble mine";
      bubble.innerHTML = `<div class="chat-text"></div><div class="chat-time">${time}</div>`;
      bubble.querySelector(".chat-text").textContent = text;
      box.appendChild(bubble);
      box.scrollTop = box.scrollHeight;
      try {
        await api(`/api/tickets/${ticketId}/messages`, { method: "POST", body: JSON.stringify({ message: text }) });
      } catch (e2) {
        notify("خطا: " + e2.message);
      }
    };
    document.getElementById("close-ticket-btn").onclick = async () => {
      if (!confirm("این تیکت بسته شود؟")) return;
      try {
        await api(`/api/tickets/${ticketId}/close`, { method: "POST" });
        renderTicketsSection();
      } catch (e) { notify(e.message); }
    };
  }
}

// ---------------------------------------------------------------------------
// تب خانه
// ---------------------------------------------------------------------------
// آیکون‌های خطی (outline) برای گرید دسترسی سریع — هم‌راستا با آیکون‌های نوار پایین
const ICON_STORE = `<svg viewBox="0 0 24 24" fill="none"><path d="M4 8h16l-1.2 10.2a2 2 0 0 1-2 1.8H7.2a2 2 0 0 1-2-1.8L4 8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M8 8V6a4 4 0 0 1 8 0v2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
const ICON_SHIELD = `<svg viewBox="0 0 24 24" fill="none"><path d="M12 2 4 6v6c0 5 3.4 8.7 8 10 4.6-1.3 8-5 8-10V6l-8-4Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9.5 12.2 11.3 14l3.2-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const ICON_WALLET = `<svg viewBox="0 0 24 24" fill="none"><rect x="3.5" y="6" width="17" height="12.5" rx="2.2" stroke="currentColor" stroke-width="1.8"/><path d="M3.5 10h17" stroke="currentColor" stroke-width="1.8"/><circle cx="16.5" cy="14.2" r="1.3" fill="currentColor"/></svg>`;
const ICON_PROFILE = `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="3.4" stroke="currentColor" stroke-width="1.8"/><path d="M5 19.5c0-3.6 3.1-6.2 7-6.2s7 2.6 7 6.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
const ICON_SUPPORT = `<svg viewBox="0 0 24 24" fill="none"><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7A2.5 2.5 0 0 1 17.5 16H10l-4 3.5V16H6.5A2.5 2.5 0 0 1 4 13.5v-7Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>`;
const ICON_REFERRAL = `<svg viewBox="0 0 24 24" fill="none"><circle cx="9" cy="8.5" r="2.7" stroke="currentColor" stroke-width="1.8"/><path d="M4 19c0-3 2.3-5 5-5s5 2 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="17" cy="7.5" r="2.1" stroke="currentColor" stroke-width="1.8"/><path d="M15.5 13c2.2.3 3.8 2 3.8 4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;

function setHeaderWallet(amount) {
  const el = document.getElementById("header-wallet-amount");
  if (el) el.textContent = `${fmt(amount)} تومان`;
}

function promoSlides({ referralLink }) {
  const slides = [];
  if (referralLink) {
    slides.push({
      bg: "linear-gradient(120deg, #0d1420, #142845 55%, #1c3f6e)",
      icon: "🤝",
      title: "دوستاتو دعوت کن",
      sub: "با دعوت از دوستان، اعتبار رایگان به کیف پولت اضافه کن.",
      cta: "مشاهده لینک دعوت",
      nav: "referral",
    });
  }
  slides.push({
    bg: "linear-gradient(120deg, #0d1a12, #123a20 55%, #17532c)",
    icon: "🧵",
    title: "الگوهای خیاطی حرفه‌ای!",
    sub: "الگوی مورد نظرت رو انتخاب کن و همین حالا دانلودش کن!",
    cta: "شروع خرید",
    nav: "store",
  });
  return slides;
}

function renderPromoCarousel(slides) {
  return `
    <div class="promo-carousel">
      <div class="promo-track" id="promo-track">
        ${slides.map((s) => `
          <div class="promo-slide" data-nav="${s.nav}" style="--promo-bg:${s.bg}">
            <div class="promo-slide-body">
              <div class="promo-slide-title">${s.title}</div>
              <div class="promo-slide-sub">${s.sub}</div>
              <div class="promo-slide-cta">‹ ${s.cta}</div>
            </div>
            <div class="promo-slide-icon">${s.icon}</div>
          </div>
        `).join("")}
      </div>
      ${slides.length > 1 ? `<div class="promo-dots">${slides.map((_, i) => `<span class="${i === 0 ? "active" : ""}"></span>`).join("")}</div>` : ""}
    </div>
  `;
}

function wirePromoCarousel(root) {
  const track = root.querySelector("#promo-track");
  if (!track) return;
  track.querySelectorAll(".promo-slide[data-nav]").forEach((el) => {
    el.onclick = () => switchTab(el.dataset.nav);
  });
  const dots = root.querySelectorAll(".promo-dots span");
  if (!dots.length) return;
  track.addEventListener("scroll", () => {
    const idx = Math.round(track.scrollLeft / track.clientWidth);
    dots.forEach((d, i) => d.classList.toggle("active", i === idx));
  }, { passive: true });
}

async function renderHome() {
  content.innerHTML = skeleton(3);
  try {
    const [me, orders, referral] = await Promise.all([
      api("/api/me"),
      api("/api/orders"),
      api("/api/referral").catch(() => null),
    ]);
    setHeaderWallet(me.wallet_credit);
    const slides = promoSlides({ referralLink: referral && referral.link });

    content.innerHTML = `
      <div class="home-greet">
        <h1>👋 سلام ${me.first_name}</h1>
        <p>خوش آمدی</p>
      </div>

      ${renderPromoCarousel(slides)}

      <div class="eyebrow">دسترسی سریع</div>
      <div class="quick-grid">
        <div class="quick-item" data-nav="store"><span class="q-label">خرید الگو</span><span class="q-ic">${ICON_STORE}</span></div>
        <div class="quick-item" data-nav="orders"><span class="q-label">الگوهای من</span><span class="q-ic">${ICON_SHIELD}</span></div>
        <div class="quick-item" data-nav="wallet"><span class="q-label">کیف پول</span><span class="q-ic">${ICON_WALLET}</span></div>
        <div class="quick-item" data-nav="profile"><span class="q-label">حساب کاربری</span><span class="q-ic">${ICON_PROFILE}</span></div>
        <div class="quick-item full" data-nav="support"><span class="q-label">پشتیبانی</span><span class="q-ic">${ICON_SUPPORT}</span></div>
      </div>

      <div class="eyebrow">سفارش‌های اخیر</div>
      ${orders.length === 0
        ? `<div class="card"><div class="state-msg"><span class="ic">◌</span>هنوز الگویی خریداری نکرده‌اید.<br><span style="font-size:11.5px">از فروشگاه یک الگو انتخاب کنید تا اینجا نمایش داده شود.</span></div></div>`
        : `<div class="card">${orders.slice(0, 3).map(orderRowHtml).join("")}</div>
           <div class="list-row" data-nav="orders" style="cursor:pointer">
             <div class="list-row-main"><span class="list-row-title">مشاهده همه‌ی سفارش‌ها</span></div>
             <span class="list-row-chev">‹</span>
           </div>`}
    `;
    content.querySelectorAll(".quick-item[data-nav], .list-row[data-nav]").forEach((el) => {
      el.onclick = () => switchTab(el.dataset.nav);
    });
    wirePromoCarousel(content);
    wireOrderExpand(content);
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب پروفایل
// ---------------------------------------------------------------------------
async function renderProfile() {
  content.innerHTML = skeleton(3);
  try {
    const [me, orders, referral] = await Promise.all([
      api("/api/me"),
      api("/api/orders"),
      api("/api/referral").catch(() => ({ enabled: true })),
    ]);
    setHeaderWallet(me.wallet_credit);
    const deliveredCount = orders.filter((o) => o.status === "approved").length;

    const tgUser = (tg.initDataUnsafe && tg.initDataUnsafe.user) || {};
    const username = me.username || tgUser.username || "";
    const photoUrl = tgUser.photo_url || "";
    const initial = (me.first_name || "؟").trim().charAt(0).toUpperCase();

    content.innerHTML = `
      <div class="card profile-hero">
        <div class="profile-avatar-wrap">
          <div class="profile-avatar">${photoUrl ? `<img src="${photoUrl}" alt="" />` : initial}</div>
        </div>
        <div class="profile-name">${me.first_name || ""}</div>
        ${username ? `<div class="profile-meta-row" id="copy-username"><span>📋</span>@${escHtml(username)}</div>` : ""}
        <div class="profile-meta-row" id="copy-userid"><span>📋</span>شناسه: ${me.telegram_id}</div>

        <div class="profile-info-grid">
          <div class="stat-card"><div class="stat-num">${fmt(deliveredCount)}</div><div class="stat-label">الگوی خریداری‌شده</div></div>
          <div class="stat-card"><div class="stat-num">${fmt(me.wallet_credit)}</div><div class="stat-label">موجودی کیف پول</div></div>
          <div class="profile-info-row"><span>تاریخ عضویت</span><b>${me.joined_at ? toJalaliStr(me.joined_at) : "-"}</b></div>
        </div>
      </div>

      <div class="card">
        <div class="list-row" data-nav="wallet">
          <div class="list-row-main">
            <div class="list-row-ic line">${ICON_WALLET}</div>
            <div class="list-row-text"><div class="list-row-title">کیف پول و افزایش موجودی</div></div>
          </div>
          <span class="list-row-chev">‹</span>
        </div>
        <div class="list-row" data-nav="orders">
          <div class="list-row-main">
            <div class="list-row-ic line">${ICON_SHIELD}</div>
            <div class="list-row-text"><div class="list-row-title">الگوهای من</div></div>
          </div>
          <span class="list-row-chev">‹</span>
        </div>
        ${referral.enabled ? `
        <div class="list-row" data-nav="referral">
          <div class="list-row-main">
            <div class="list-row-ic line">${ICON_REFERRAL}</div>
            <div class="list-row-text"><div class="list-row-title">زیرمجموعه‌گیری</div></div>
          </div>
          <span class="list-row-chev">‹</span>
        </div>` : ""}
        <div class="list-row" data-nav="support">
          <div class="list-row-main">
            <div class="list-row-ic line">${ICON_SUPPORT}</div>
            <div class="list-row-text"><div class="list-row-title">پشتیبانی</div></div>
          </div>
          <span class="list-row-chev">‹</span>
        </div>
      </div>
    `;
    content.querySelectorAll(".list-row[data-nav]").forEach((el) => {
      el.onclick = () => switchTab(el.dataset.nav);
    });
    const cu = document.getElementById("copy-username");
    if (cu) cu.onclick = (e) => { e.stopPropagation(); navigator.clipboard.writeText("@" + username); tg.HapticFeedback.notificationOccurred("success"); notify("کپی شد."); };
    const ci = document.getElementById("copy-userid");
    if (ci) ci.onclick = (e) => { e.stopPropagation(); navigator.clipboard.writeText(String(me.telegram_id)); tg.HapticFeedback.notificationOccurred("success"); notify("کپی شد."); };
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب زیرمجموعه‌گیری
// ---------------------------------------------------------------------------

async function renderReferral() {
  content.innerHTML = skeleton(1);
  try {
    const r = await api("/api/referral");
    if (!r.enabled) {
      content.innerHTML = `<div class="state-msg"><span class="ic">◌</span>زیرمجموعه‌گیری در حال حاضر غیرفعال است.</div>`;
      return;
    }
    content.innerHTML = `
      ${referralCard(r)}
    `;
    const copyBtn = document.getElementById("copy-referral-btn");
    if (copyBtn) copyBtn.onclick = () => {
      navigator.clipboard.writeText(r.link);
      tg.HapticFeedback.notificationOccurred("success");
      notify("لینک دعوت کپی شد.");
    };
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

function referralCard(r) {
  const rows = [];
  if (r.commission_enabled) {
    const cap = r.commission_max_count > 0 ? ` (تا ${fmt(r.commission_max_count)} نفر)` : "";
    rows.push(`<div class="stat-row"><span>پورسانت خرید الگو</span><b>${r.percent}٪ از اولین خرید${cap}</b></div>`);
  }
  if (r.free_config_enabled) {
    rows.push(`<div class="stat-row"><span>الگوی رایگان</span><b>با دعوت ${fmt(r.free_config_threshold)} نفر</b></div>`);
  }
  if (r.invite_bonus_enabled) {
    const cap = r.invite_bonus_max_count > 0 ? ` (تا ${fmt(r.invite_bonus_max_count)} دعوت)` : "";
    rows.push(`<div class="stat-row"><span>شارژ به‌ازای دعوت</span><b>${fmt(r.invite_bonus_amount)} تومان${cap}</b></div>`);
  }
  return `
    <div class="eyebrow">زیرمجموعه‌گیری</div>
    <div class="card">
      <h3><span class="ic">🤝</span>دعوت از دوستان</h3>
      ${rows.join("")}
      <div class="stat-row"><span>تعداد زیرمجموعه‌ها</span><b>${fmt(r.count)}</b></div>
      <div class="stat-row"><span>اعتبار کسب‌شده</span><b>${fmt(r.credit)} تومان</b></div>
      ${r.link ? `
      <div class="link-box" style="margin-top:8px">${r.link}</div>
      <button class="btn small outline" id="copy-referral-btn" data-link="${r.link}" style="width:100%;margin-top:8px">📋 کپی لینک دعوت</button>
      ` : ""}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// کارت بانکی + آپلود رسید (مشترک بین «شارژ کیف پول» و «پرداخت سفارش»)
// ---------------------------------------------------------------------------
function renderReceiptCard(box, { amount, cardNumber, cardHolder, sendReceipt, successText, accept = "image/*", chooseLabel }) {
  box.innerHTML = `
    <h3><span class="ic">💳</span>واریز و ارسال رسید</h3>
    <div class="bank-card">
      <div class="bank-card-top">
        <div class="bank-card-chip"></div>
        <div class="bank-card-brand">SHOP PAY</div>
      </div>
      <div class="bank-card-number">${formatCardNumber(cardNumber)}</div>
      <div class="bank-card-bottom">
        <div>
          <div class="bank-card-holder-label">به نام</div>
          <div class="bank-card-holder">${cardHolder || "---"}</div>
        </div>
        <div class="bank-card-amount">${fmt(amount)} تومان</div>
      </div>
    </div>
    <button class="copy-chip" id="copy-card-btn" style="width:100%;margin-bottom:12px">📋 کپی شماره کارت</button>

    <label class="receipt-upload" id="receipt-drop">
      <span class="ic">🧾</span>
      <span id="receipt-label">${chooseLabel || "مبلغ را واریز کن و عکس رسید را همینجا انتخاب کن"}</span>
      <input type="file" id="receipt-file" accept="${accept}" />
    </label>
    <img id="receipt-preview" class="receipt-preview" style="display:none" />
    <button class="btn" id="send-receipt-btn" disabled>ارسال رسید برای تایید</button>
  `;

  box.querySelector("#copy-card-btn").onclick = () => {
    navigator.clipboard.writeText(String(cardNumber).replace(/\s/g, ""));
    tg.HapticFeedback.notificationOccurred("success");
  };

  const fileInput = box.querySelector("#receipt-file");
  const preview = box.querySelector("#receipt-preview");
  const drop = box.querySelector("#receipt-drop");
  const sendBtn = box.querySelector("#send-receipt-btn");

  fileInput.onchange = () => {
    const file = fileInput.files[0];
    if (!file) return;
    drop.classList.add("has-file");
    const isPdf = (file.type || "").includes("pdf");
    box.querySelector("#receipt-label").textContent = isPdf ? "✅ فایل رسید انتخاب شد" : "✅ عکس رسید انتخاب شد";
    if (isPdf) {
      preview.removeAttribute("src");
      preview.style.display = "none";
    } else {
      preview.src = URL.createObjectURL(file);
      preview.style.display = "block";
    }
    sendBtn.disabled = false;
  };

  sendBtn.onclick = async () => {
    const file = fileInput.files[0];
    if (!file) return;
    sendBtn.disabled = true;
    sendBtn.textContent = "در حال ارسال...";
    try {
      await sendReceipt(file);
      tg.HapticFeedback.notificationOccurred("success");
      box.innerHTML = `<div class="state-msg"><span class="ic">✅</span>${successText}</div>`;
    } catch (e) {
      notify("خطا: " + e.message);
      sendBtn.disabled = false;
      sendBtn.textContent = "ارسال رسید برای تایید";
    }
  };
}

// ---------------------------------------------------------------------------
// تب فروشگاه (الگوها)
// ---------------------------------------------------------------------------
let storeCategoryView = null; // null = لیست دسته‌بندی‌ها، وگرنه شناسه دسته‌بندی انتخاب‌شده
let catalogProductsById = {};

function enterStoreTab() {
  storeCategoryView = null;
  revokePreviewCache(); // با هر ورود دوباره، پیش‌نمایش‌ها از نو گرفته می‌شوند
  renderStore();
}

function productCardHtml(p) {
  const available = p.available !== false;
  return `
    <div class="pattern-card ${available ? "" : "disabled"}" data-product-id="${p.id}">
      ${p.has_preview
        ? `<img class="product-thumb" alt="" loading="lazy" />`
        : `<div class="product-thumb-ph">🧵</div>`}
      <div class="pattern-card-body">
        <div class="product-name">${escHtml(p.name)}</div>
        <div class="price">${fmt(p.price)} <span style="font-family:var(--font-body);font-size:10.5px">تومان</span></div>
        <div class="pattern-badge-row">
          <span class="badge ${available ? "approved" : "rejected"}">${available ? "✅ موجود" : "⛔️ ناموجود"}</span>
        </div>
      </div>
    </div>
  `;
}

async function renderStore() {
  content.innerHTML = skeleton(4);
  try {
    const categories = await api("/api/catalog");
    if (categories.length === 0) {
      content.innerHTML = `<div class="state-msg"><span class="ic">◌</span>در حال حاضر الگویی موجود نیست.</div>`;
      return;
    }
    categories.forEach((c) => c.products.forEach((p) => { catalogProductsById[p.id] = p; }));

    if (storeCategoryView == null) {
      content.innerHTML = `
        <div class="eyebrow">یک دسته را انتخاب کنید</div>
        ${sampleCardHtml()}
        ${categories.map((c) => `
          <div class="list-row" data-cat="${c.id}" style="cursor:pointer">
            <div class="list-row-main">
              <div class="list-row-ic">🧵</div>
              <div class="list-row-text">
                <span class="list-row-title">${escHtml(c.name)}</span>
                <span class="list-row-sub">${c.products.length} الگو</span>
              </div>
            </div>
            <span class="list-row-chev">‹</span>
          </div>
        `).join("")}
      `;
      content.querySelectorAll(".list-row[data-cat]").forEach((el) => {
        el.onclick = () => { storeCategoryView = parseInt(el.dataset.cat, 10); renderStore(); };
      });
      wireSampleCard(content);
      return;
    }

    const cat = categories.find((c) => c.id === storeCategoryView);
    if (!cat) { storeCategoryView = null; return renderStore(); }
    content.innerHTML = `
      <div class="list-row" id="store-back-row" style="cursor:pointer">
        <div class="list-row-main">
          <span class="list-row-ic">‹</span>
          <div class="list-row-text"><span class="list-row-title">بازگشت به دسته‌بندی‌ها</span></div>
        </div>
      </div>
      <div class="eyebrow">${escHtml(cat.name)}</div>
      <div class="pattern-grid">
        ${cat.products.map(productCardHtml).join("")}
      </div>
    `;
    document.getElementById("store-back-row").onclick = () => { storeCategoryView = null; renderStore(); };
    content.querySelectorAll(".pattern-card[data-product-id]").forEach((el) => {
      const productId = Number(el.dataset.productId);
      const img = el.querySelector("img.product-thumb");
      if (img) loadProductPreview(img, productId);
      el.onclick = () => {
        if (el.classList.contains("disabled")) return;
        openProductDetail(productId);
      };
    });
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

async function openProductDetail(productId) {
  content.innerHTML = skeleton(3);
  try {
    const p = catalogProductsById[productId] || await api(`/api/products/${productId}`);
    const available = p.available !== false;
    content.innerHTML = `
      <button class="btn outline small" id="back-to-store-btn" style="width:auto;margin-bottom:12px">→ بازگشت به فروشگاه</button>
      <div class="card">
        ${p.has_preview
          ? `<img class="product-thumb pattern-hero" alt="" />`
          : `<div class="product-thumb-ph">🧵</div>`}
        <h3 style="margin-top:12px"><span class="ic">🧵</span>${escHtml(p.name)}</h3>
        <div class="pattern-badge-row">
          <span class="badge ${available ? "approved" : "rejected"}">${available ? "✅ موجود" : "⛔️ ناموجود"}</span>
          <span class="price" style="margin:0">${fmt(p.price)} تومان</span>
        </div>
        ${p.description ? `<p class="hint-text" style="white-space:pre-wrap">${escHtml(p.description)}</p>` : ""}
        ${available ? `
        <input class="input" id="purchase-discount-code" type="text" placeholder="کد تخفیف (اختیاری)"
          style="direction:ltr;text-align:left;margin-top:10px" />
        <button class="btn" id="buy-btn" style="margin-top:10px">🛍 خرید الگو</button>
        ` : `<div class="state-msg" style="margin-top:10px"><span class="ic">⛔️</span>این الگو در حال حاضر ناموجود است.</div>`}
      </div>
    `;
    document.getElementById("back-to-store-btn").onclick = renderStore;
    const img = content.querySelector("img.product-thumb");
    if (img) loadProductPreview(img, p.id);
    const buyBtn = document.getElementById("buy-btn");
    if (buyBtn) {
      buyBtn.onclick = () => {
        const code = document.getElementById("purchase-discount-code").value.trim();
        buyProduct(p.id, code || null);
      };
    }
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// خرید الگو + پرداخت کارت‌به‌کارت
// ---------------------------------------------------------------------------
async function buyProduct(productId, code) {
  const btn = document.getElementById("buy-btn");
  if (btn) { btn.disabled = true; btn.textContent = "در حال ثبت سفارش..."; }
  try {
    const result = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, discount_code: code || null }),
    });
    if (result.status === "approved") {
      tg.HapticFeedback.notificationOccurred("success");
      renderOrderSuccess(result);
    } else {
      renderOrderPendingPayment(result);
    }
  } catch (e) {
    notify("خطا: " + e.message);
    if (btn) { btn.disabled = false; btn.textContent = "🛍 خرید الگو"; }
  }
}

function renderOrderSuccess(result) {
  const files = result.files || [];
  content.innerHTML = `
    <div class="card" style="text-align:center">
      <h3><span class="ic">✅</span>خرید شما تکمیل شد!</h3>
      <p class="hint-text">الگوی شما آماده‌ی دانلود است:</p>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${files.length === 0
          ? `<div class="hint-text">فایل(های) الگو از بخش «الگوهای من» قابل دانلود است.</div>`
          : files.map((f, i) => `
            <button class="btn" style="margin-top:0" data-dl-order="${result.order_id}" data-dl-rec="${f.record_id}" data-dl-n="${i + 1}">📥 دانلود الگو${files.length > 1 ? " " + fmt(i + 1) : ""}</button>
          `).join("")}
      </div>
      <button class="btn outline" id="back-to-store-btn" style="margin-top:10px">بازگشت به فروشگاه</button>
    </div>
  `;
  wireOrderDownloadButtons(content);
  document.getElementById("back-to-store-btn").onclick = renderStore;
}

function renderOrderPendingPayment(result) {
  const breakdown = [];
  if (result.discount_amount > 0) {
    breakdown.push(`<div class="stat-row"><span>تخفیف</span><b>${fmt(result.discount_amount)} تومان</b></div>`);
  }
  if (result.wallet_used > 0) {
    breakdown.push(`<div class="stat-row"><span>کسر از کیف پول</span><b>${fmt(result.wallet_used)} تومان</b></div>`);
  }
  content.innerHTML = `
    <button class="btn outline small" id="back-to-store-btn" style="width:auto;margin-bottom:12px">→ بازگشت به فروشگاه</button>
    <div class="eyebrow">پرداخت سفارش</div>
    ${breakdown.length ? `<div class="card">${breakdown.join("")}</div>` : ""}
    <div class="card" id="order-payment-card"></div>
  `;
  document.getElementById("back-to-store-btn").onclick = renderStore;
  renderReceiptCard(document.getElementById("order-payment-card"), {
    amount: result.final_price,
    cardNumber: result.card_number,
    cardHolder: result.card_holder,
    accept: "image/*,application/pdf",
    chooseLabel: "مبلغ را واریز کن و عکس یا فایل رسید را همینجا انتخاب کن",
    successText: "رسید شما ارسال شد و در انتظار تایید ادمین است.",
    sendReceipt: async (file) => {
      const fd = new FormData();
      fd.append("file", file);
      await apiUpload(`/api/orders/${result.order_id}/receipt`, fd);
    },
  });
}

// ---------------------------------------------------------------------------
// تب سفارش‌های من
// ---------------------------------------------------------------------------
const ORDER_STATUS_BADGE = {
  pending: { cls: "pending", label: "⏳ در انتظار تایید" },
  approved: { cls: "approved", label: "✅ تحویل شده" },
  rejected: { cls: "rejected", label: "❌ رد شده" },
};

const orderFilesCache = new Map(); // orderId -> html دکمه‌های دانلود

function orderRowHtml(o) {
  const st = ORDER_STATUS_BADGE[o.status] || { cls: "", label: o.status };
  const canDownload = o.status === "approved" && (o.file_count || 0) > 0;
  return `
    <div class="order-block">
      <div class="order-row ${canDownload ? "expandable" : ""}" ${canDownload ? `data-order-toggle="${o.id}"` : ""}>
        <div>
          <div class="product-name">${escHtml(o.product_name)}</div>
          <div class="hint-text" style="margin:2px 0 0">${o.created_at ? toJalaliStr(o.created_at, true) : "-"}</div>
        </div>
        <div style="text-align:left">
          <span class="badge ${st.cls}">${st.label}</span>
          ${o.final_price != null ? `<div class="hint-text" style="margin:4px 0 0">${fmt(o.final_price)} تومان</div>` : ""}
        </div>
      </div>
      ${canDownload ? `<div class="order-files" id="order-files-${o.id}" style="display:none"></div>` : ""}
    </div>
  `;
}

function fileButtonsHtml(orderId, files) {
  return files.map((f, i) => `
    <button class="btn small outline" style="width:100%"
      data-dl-order="${orderId}" data-dl-rec="${f.record_id}" data-dl-n="${i + 1}">
      📥 دانلود الگو${files.length > 1 ? " " + fmt(i + 1) : ""}
    </button>
  `).join("");
}

async function toggleOrderFiles(orderId) {
  const box = document.getElementById(`order-files-${orderId}`);
  if (!box) return;
  if (box.style.display !== "none") { box.style.display = "none"; return; }
  box.style.display = "";
  if (orderFilesCache.has(orderId)) {
    box.innerHTML = orderFilesCache.get(orderId);
    wireOrderDownloadButtons(box);
    return;
  }
  box.innerHTML = skeleton(1);
  try {
    const detail = await api(`/api/orders/${orderId}`);
    const files = detail.files || [];
    const html = files.length === 0
      ? `<div class="hint-text" style="margin:0">فایلی برای این سفارش ثبت نشده است.</div>`
      : fileButtonsHtml(orderId, files);
    orderFilesCache.set(orderId, html);
    box.innerHTML = html;
    wireOrderDownloadButtons(box);
  } catch (e) {
    box.innerHTML = `<div class="hint-text" style="margin:0">${escHtml(e.message)}</div>`;
  }
}

function wireOrderExpand(root) {
  root.querySelectorAll("[data-order-toggle]").forEach((el) => {
    el.onclick = () => toggleOrderFiles(Number(el.dataset.orderToggle));
  });
}

function wireOrderDownloadButtons(root) {
  root.querySelectorAll("[data-dl-order]").forEach((btn) => {
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        await downloadBlobAsFile(
          `/api/orders/${btn.dataset.dlOrder}/files/${btn.dataset.dlRec}`,
          `pattern-${btn.dataset.dlOrder}-${btn.dataset.dlN}.pdf`
        );
      } catch (e) {
        notify("خطا در دانلود: " + e.message);
      }
      btn.disabled = false;
    };
  });
}

async function renderOrders() {
  content.innerHTML = skeleton(3);
  try {
    const orders = await api("/api/orders");
    content.innerHTML = `
      <div class="eyebrow">سفارش‌های من</div>
      ${orders.length === 0
        ? `<div class="state-msg"><span class="ic">◌</span>هنوز سفارشی ثبت نکرده‌اید.<br><span style="font-size:11.5px">از فروشگاه یک الگو انتخاب کنید.</span></div>`
        : `<div class="card">${orders.map(orderRowHtml).join("")}</div>`}
    `;
    wireOrderExpand(content);
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب گردونه شانس -> دستگاه جکپات با ۳ رول
// ---------------------------------------------------------------------------
const SLOT_SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"];
const JACKPOT_SYMBOL = "💎";

async function renderWheel() {
  content.innerHTML = skeleton(1);
  try {
    const status = await api("/api/wheel");
    if (!status.enabled) {
      content.innerHTML = `<div class="state-msg"><span class="ic">◌</span>گردونه شانس غیرفعال است.</div>`;
      return;
    }
    content.innerHTML = `
      <div class="jackpot">
        <div class="jackpot-title"><span class="bulb"></span>جکپات شانس<span class="bulb"></span></div>
        <div class="marquee">${'<span class="lamp"></span>'.repeat(10)}</div>
        <div class="reels">
          <div class="reel" id="reel-0"><span class="reel-symbol">🍒</span></div>
          <div class="reel" id="reel-1"><span class="reel-symbol">⭐</span></div>
          <div class="reel" id="reel-2"><span class="reel-symbol">🔔</span></div>
        </div>
        <button class="spin-cta" id="spin-btn" ${status.can_spin ? "" : "disabled"}>
          ${status.can_spin ? "بکش! 🎰" : `⏳ ${status.remaining_hours} ساعت`}
        </button>
        <div id="jackpot-result"></div>
      </div>
    `;
    if (status.can_spin) {
      document.getElementById("spin-btn").onclick = spinWheel;
    }
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

function randomSymbol() {
  return SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)];
}

async function spinWheel() {
  const btn = document.getElementById("spin-btn");
  const reels = [0, 1, 2].map((i) => document.getElementById(`reel-${i}`));
  const resultBox = document.getElementById("jackpot-result");
  btn.disabled = true;
  resultBox.innerHTML = "";
  reels.forEach((r) => {
    r.classList.add("spinning");
    r.classList.remove("win");
  });

  const spinIntervals = reels.map((r) =>
    setInterval(() => { r.querySelector(".reel-symbol").textContent = randomSymbol(); }, 70)
  );

  let apiResult, apiError;
  try {
    apiResult = await api("/api/wheel/spin", { method: "POST" });
  } catch (e) {
    apiError = e;
  }

  // رول‌ها یکی‌یکی با فاصله می‌ایستند، شبیه دستگاه واقعی
  const stopDelays = [1400, 1900, 2400];
  reels.forEach((r, i) => {
    setTimeout(() => {
      clearInterval(spinIntervals[i]);
      r.classList.remove("spinning");
      const finalSymbol = apiResult && apiResult.won ? JACKPOT_SYMBOL : randomSymbol();
      r.querySelector(".reel-symbol").textContent = finalSymbol;
      if (i === 2) {
        if (apiError) {
          resultBox.innerHTML = `<div class="jackpot-result lose">خطا: ${apiError.message}</div>`;
          btn.disabled = false;
          return;
        }
        tg.HapticFeedback.notificationOccurred(apiResult.won ? "success" : "error");
        if (apiResult.won) {
          reels.forEach((rr) => rr.classList.add("win"));
          resultBox.innerHTML = `
            <div class="jackpot-result win">
              🎉 جکپات بردی! کد تخفیف ${apiResult.percent}٪
              <div class="code">${apiResult.code}</div>
            </div>`;
        } else {
          resultBox.innerHTML = `<div class="jackpot-result lose">😔 امروز شانس نبود، فردا دوباره امتحان کن!</div>`;
        }
        renderWheel_refreshButtonOnly();
      }
    }, stopDelays[i]);
  });
}

// بعد از نتیجه، فقط وضعیت دکمه را بدون پاک‌کردن نتیجه به‌روزرسانی می‌کند
async function renderWheel_refreshButtonOnly() {
  try {
    const status = await api("/api/wheel");
    const btn = document.getElementById("spin-btn");
    if (!btn) return;
    btn.disabled = !status.can_spin;
    btn.textContent = status.can_spin ? "بکش! 🎰" : `⏳ ${status.remaining_hours} ساعت`;
    if (status.can_spin) btn.onclick = spinWheel;
  } catch (e) {}
}

// ---------------------------------------------------------------------------
// تب کیف پول
// ---------------------------------------------------------------------------
async function renderWallet() {
  content.innerHTML = skeleton(2);
  try {
    const me = await api("/api/me");
    setHeaderWallet(me.wallet_credit);
    content.innerHTML = `
      <div class="eyebrow">کیف پول</div>
      <div class="card">
        <h3><span class="ic">👛</span>موجودی فعلی</h3>
        <div class="stat-row"><span>قابل استفاده برای خرید الگو</span><b>${fmt(me.wallet_credit)} تومان</b></div>
      </div>
      <div class="eyebrow">شارژ کیف پول</div>
      <div class="card" id="topup-card">
        <input id="topup-amount" class="input" type="number" placeholder="مبلغ به تومان" />
        <button class="btn" id="topup-btn">ثبت درخواست شارژ</button>
      </div>
    `;
    document.getElementById("topup-btn").onclick = async () => {
      const amount = parseInt(document.getElementById("topup-amount").value, 10);
      if (!amount || amount < 1000) return notify("حداقل مبلغ ۱۰۰۰ تومان است.");
      const btn = document.getElementById("topup-btn");
      btn.disabled = true;
      try {
        const r = await api("/api/wallet/topup-request", { method: "POST", body: JSON.stringify({ amount }) });
        renderTopupPaymentStep(r.topup_id, amount, r.card_number, r.card_holder);
      } catch (e) {
        notify("خطا: " + e.message);
        btn.disabled = false;
      }
    };
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

function renderTopupPaymentStep(topupId, amount, cardNumber, cardHolder) {
  const box = document.getElementById("topup-card");
  renderReceiptCard(box, {
    amount, cardNumber, cardHolder,
    successText: "رسید ارسال شد. پس از تایید ادمین، کیف پول شما شارژ می‌شود.",
    sendReceipt: async (file) => {
      const fd = new FormData();
      fd.append("topup_id", topupId);
      fd.append("photo", file);
      await apiUpload("/api/wallet/topup-receipt", fd);
    },
  });
}

// ---------------------------------------------------------------------------
// ناوبری تب‌ها
// ---------------------------------------------------------------------------
const tabs = {
  home: renderHome,
  store: enterStoreTab,
  services: renderOrders, // سازگار با برچسب قدیمی نوار پایین
  orders: renderOrders,
  profile: renderProfile,
  wheel: renderWheel,
  referral: renderReferral,
  support: renderSupport,
  wallet: renderWallet,
};

function switchTab(name) {
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  if (name !== "support") clearInterval(supportPollTimer);
  content.classList.remove("fade-in");
  void content.offsetWidth; // ری‌استارت انیمیشن
  (tabs[name] || renderHome)();
  content.classList.add("fade-in");
}

document.querySelectorAll("#tabbar button").forEach((b) => b.onclick = () => switchTab(b.dataset.tab));

const headerWalletBtn = document.getElementById("header-wallet-btn");
if (headerWalletBtn) headerWalletBtn.onclick = () => switchTab("wallet");

switchTab("home");

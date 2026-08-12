const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
try { tg.setHeaderColor("#0a0e17"); tg.setBackgroundColor("#0a0e17"); } catch (e) {}

const initData = tg.initData; // برای هدر X-Init-Data به بک‌اند فرستاده می‌شود
const content = document.getElementById("content");
const greeting = document.getElementById("greeting");

// شناسه‌ی نماینده (اگر مینی‌اپ از یک بات نمایندگی باز شده باشد) - از URL خوانده می‌شود
// و به تمام درخواست‌های API اضافه می‌شود تا سرور دیتابیس/توکن درست را انتخاب کند.
const TENANT_ID = new URLSearchParams(window.location.search).get("b") || "";

function withTenant(path) {
  if (!TENANT_ID) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}b=${encodeURIComponent(TENANT_ID)}`;
}

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

function toJalaliMonthDay(value) {
  if (!value) return "-";
  const d = value instanceof Date ? value : new Date(value);
  if (isNaN(d.getTime())) return String(value);
  const [, jm, jd] = gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(jm)}/${pad(jd)}`;
}

function jalaliToGregorian(jy, jm, jd) {
  const j_d_m = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
  const g_d_m = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const div = (a, b) => Math.floor(a / b);

  const jy2 = jy - 979, jm2 = jm - 1, jd2 = jd - 1;
  let j_day_no = 365 * jy2 + div(jy2, 33) * 8 + div((jy2 % 33) + 3, 4);
  for (let i = 0; i < jm2; i++) j_day_no += j_d_m[i];
  j_day_no += jd2;

  let g_day_no = j_day_no + 79;

  let gy = 1600 + 400 * div(g_day_no, 146097);
  g_day_no %= 146097;

  if (g_day_no >= 36525) {
    g_day_no -= 1;
    gy += 100 * div(g_day_no, 36524);
    g_day_no %= 36524;
    if (g_day_no >= 365) g_day_no += 1;
  }

  gy += 4 * div(g_day_no, 1461);
  g_day_no %= 1461;

  if (g_day_no >= 366) {
    g_day_no -= 1;
    gy += div(g_day_no, 365);
    g_day_no %= 365;
  }

  let gm = 1, gd = g_day_no + 1;
  let days = g_day_no;
  for (let i = 0; i < 12; i++) {
    const dim = g_d_m[i] + (i === 1 && ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0) ? 1 : 0);
    if (days < dim) { gm = i + 1; gd = days + 1; break; }
    days -= dim;
  }
  return [gy, gm, gd];
}

function jalaliToISO(jy, jm, jd) {
  const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd);
  const pad = (n) => String(n).padStart(2, "0");
  return `${gy}-${pad(gm)}-${pad(gd)}`;
}

function isoToJalaliYMD(iso) {
  const d = new Date(iso);
  return gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

function jalaliDateSelectHtml(idPrefix, jy, jm, jd) {
  const dayOptions = Array.from({ length: 31 }, (_, i) => i + 1)
    .map((d) => `<option value="${d}" ${d === jd ? "selected" : ""}>${d}</option>`).join("");
  const monthOptions = JALALI_MONTH_NAMES
    .map((name, i) => `<option value="${i + 1}" ${i + 1 === jm ? "selected" : ""}>${name}</option>`).join("");
  const yearOptions = Array.from({ length: 6 }, (_, i) => jy - 4 + i)
    .map((y) => `<option value="${y}" ${y === jy ? "selected" : ""}>${y}</option>`).join("");
  return `
    <select class="input" id="${idPrefix}-d" style="flex:0 0 25%;padding:8px 4px">${dayOptions}</select>
    <select class="input" id="${idPrefix}-m" style="flex:0 0 38%;padding:8px 4px">${monthOptions}</select>
    <select class="input" id="${idPrefix}-y" style="flex:0 0 30%;padding:8px 4px">${yearOptions}</select>
  `;
}

const JALALI_MONTH_NAMES = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

function notify(message) {
  if (tg.showAlert) tg.showAlert(message);
  else alert(message);
}

async function api(path, options = {}) {
  const res = await fetch(withTenant(path), {
    ...options,
    headers: { "Content-Type": "application/json", "X-Init-Data": initData, ...(options.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "خطا" }));
    throw new Error(err.detail || "خطای ناشناخته");
  }
  return res.json();
}

// آپلود فایل (مولتی‌پارت) - بدون Content-Type دستی تا مرورگر boundary را ست کند
async function apiUpload(path, formData) {
  const res = await fetch(withTenant(path), {
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

function skeleton(rows = 3) {
  return `<div class="skeleton-block">${'<div class="skel"></div>'.repeat(rows)}</div>`;
}

function errorState(message) {
  return `<div class="state-msg error"><span class="ic">⚠</span>${message}</div>`;
}

// ---------------------------------------------------------------------------
// تب کانفیگ تست
// ---------------------------------------------------------------------------

async function renderTestConfig() {
  content.innerHTML = skeleton(1);
  try {
    const status = await api("/api/test-config");
    content.innerHTML = `
      <div class="eyebrow">کانفیگ تست</div>
      <div class="card" id="test-config-card">
        <h3><span class="ic">🧪</span>کانفیگ تست رایگان</h3>
        <p class="hint-text">یک کانفیگ محدود و رایگان برای امتحان کیفیت سرویس، فقط یک‌بار برای هر کاربر.</p>
        ${testConfigBody(status)}
      </div>
    `;
    const btn = document.getElementById("test-config-btn");
    if (btn) btn.onclick = () => claimTestConfig(btn);
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

function testConfigBody(status) {
  if (!status.enabled) return `<div class="state-msg"><span class="ic">◌</span>در حال حاضر کانفیگ تست غیرفعال است.</div>`;
  if (status.used) {
    if (!status.link) return `<div class="state-msg"><span class="ic">✅</span>شما کانفیگ تست خود را قبلاً دریافت کرده‌اید.</div>`;
    return `
      <div class="state-msg" style="padding:0 0 10px"><span class="ic">✅</span>کانفیگ تست شما</div>
      <div class="link-box">${status.link}</div>
      <div class="qr-row">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(status.link)}" width="96" height="96" alt="QR" />
        <button class="btn small outline" onclick="navigator.clipboard.writeText('${status.link}');tg.HapticFeedback.notificationOccurred('success')">📋 کپی لینک</button>
      </div>
    `;
  }
  if (status.available <= 0) return `<div class="state-msg"><span class="ic">◌</span>موجودی کانفیگ تست تمام شده است.</div>`;
  return `<button class="btn" id="test-config-btn">دریافت کانفیگ تست رایگان</button>`;
}

async function claimTestConfig(btn) {
  btn.disabled = true;
  btn.textContent = "در حال دریافت...";
  try {
    const r = await api("/api/test-config/claim", { method: "POST" });
    const card = document.getElementById("test-config-card");
    card.innerHTML = `
      <h3><span class="ic">🧪</span>کانفیگ تست رایگان</h3>
      <div class="link-box">${r.link}</div>
      <div class="qr-row">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(r.link)}" width="96" height="96" alt="QR" />
        <button class="btn small outline" onclick="navigator.clipboard.writeText('${r.link}');tg.HapticFeedback.notificationOccurred('success')">📋 کپی لینک</button>
      </div>
    `;
    tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    notify("خطا: " + e.message);
    btn.disabled = false;
    btn.textContent = "دریافت کانفیگ تست رایگان";
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
      <div class="eyebrow">زیرمجموعه‌گیری</div>
      <div class="card">
        <h3><span class="ic">🤝</span>دعوت از دوستان</h3>
        <p class="hint-text">دوستانتان را با لینک زیر دعوت کنید و از اولین خریدشان پورسانت بگیرید.</p>
        <div class="stat-row"><span>پورسانت شما</span><b>${r.percent}٪ از اولین خرید</b></div>
        <div class="stat-row"><span>تعداد زیرمجموعه‌ها</span><b>${fmt(r.count)}</b></div>
        <div class="stat-row"><span>اعتبار کسب‌شده</span><b>${fmt(r.credit)} تومان</b></div>
        ${r.link ? `
        <div class="link-box" style="margin-top:8px">${r.link}</div>
        <button class="btn small outline" id="copy-referral-btn" style="width:100%;margin-top:8px">📋 کپی لینک دعوت</button>
        ` : ""}
      </div>
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
  bubble.className = `chat-bubble ${m.sender === "user" ? "mine" : "admin"}`;
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
        <div class="admin-list-row" data-open-ticket="${t.id}" style="cursor:pointer">
          <div class="admin-list-row-main">
            <span>${t.subject}</span>
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
    <div class="eyebrow" style="margin-top:0">${ticket.subject} <span class="hint-text" style="margin-right:6px">${TICKET_STATUS_LABEL[ticket.status] || ""}</span></div>
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
    bubble.className = `chat-bubble ${m.sender === "user" ? "mine" : "admin"}`;
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
async function renderHome() {
  content.innerHTML = skeleton(3);
  try {
    const [me, orders, expiring] = await Promise.all([
      api("/api/me"),
      api("/api/orders"),
      api("/api/expiring").catch(() => []),
    ]);
    greeting.textContent = `سلام ${me.first_name} 👋`;
    const active = orders.filter((o) => o.status === "approved");

    const adminTabBtn = document.getElementById("admin-tab-btn");
    if (adminTabBtn) adminTabBtn.style.display = me.is_admin ? "" : "none";

    content.innerHTML = `
      ${expiring.length > 0 ? expiringBanner(expiring) : ""}

      <div class="eyebrow">وضعیت حساب</div>
      <div class="card">
        <h3><span class="ic">◆</span>خلاصه</h3>
        <div class="stat-row"><span>👛 موجودی کیف پول</span><b>${fmt(me.wallet_credit)} تومان</b></div>
        <div class="stat-row"><span>👥 زیرمجموعه‌ها</span><b>${fmt(me.referral_count)}</b></div>
        <div class="stat-row"><span>📦 تعداد سفارش</span><b>${fmt(me.orders_count)}</b></div>
      </div>

      <div class="eyebrow">سرویس‌های فعال</div>
      <div class="card">
        ${active.length === 0
          ? `<div class="state-msg"><span class="ic">◌</span>سرویس فعالی ندارید.</div>`
          : active.map(orderCard).join("")}
      </div>
    `;
    active.filter((o) => o.link).forEach((o) => loadSubInfo(o.id, o.link));
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

function expiringBanner(items) {
  const rows = items.map((it) => {
    const d = new Date(it.expires_at);
    const days = Math.max(0, Math.ceil((d - new Date()) / 86400000));
    return `<div class="expiring-row">
      <span>📦 ${it.product_name}</span>
      <b>${days === 0 ? "امروز منقضی می‌شود" : `${days} روز مانده`}</b>
    </div>`;
  }).join("");
  return `
    <div class="banner banner-warn">
      <div class="banner-title"><span class="ic">⏰</span>سرویس‌های نزدیک به انقضا</div>
      ${rows}
      <div class="banner-hint">برای تمدید به بخش «فروشگاه» بروید.</div>
    </div>
  `;
}

function testConfigCard(status) {
  if (!status.enabled) return "";
  let body;
  if (status.used) {
    body = `<div class="state-msg"><span class="ic">✅</span>شما کانفیگ تست خود را دریافت کرده‌اید.</div>`;
  } else if (status.available <= 0) {
    body = `<div class="state-msg"><span class="ic">◌</span>موجودی کانفیگ تست تمام شده است.</div>`;
  } else {
    body = `<button class="btn" id="test-config-btn">دریافت کانفیگ تست رایگان</button>`;
  }
  return `
    <div class="eyebrow">کانفیگ تست</div>
    <div class="card" id="test-config-card">
      <h3><span class="ic">🧪</span>کانفیگ تست رایگان</h3>
      ${body}
    </div>
  `;
}

async function claimTestConfig(btn) {
  btn.disabled = true;
  btn.textContent = "در حال دریافت...";
  try {
    const r = await api("/api/test-config/claim", { method: "POST" });
    const card = document.getElementById("test-config-card");
    card.innerHTML = `
      <h3><span class="ic">🧪</span>کانفیگ تست رایگان</h3>
      <div class="link-box">${r.link}</div>
      <div class="qr-row">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(r.link)}" width="96" height="96" alt="QR" />
        <button class="btn small outline" onclick="navigator.clipboard.writeText('${r.link}');tg.HapticFeedback.notificationOccurred('success')">📋 کپی لینک</button>
      </div>
    `;
    tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    notify("خطا: " + e.message);
    btn.disabled = false;
    btn.textContent = "دریافت کانفیگ تست رایگان";
  }
}

function referralCard(r) {
  return `
    <div class="eyebrow">زیرمجموعه‌گیری</div>
    <div class="card">
      <h3><span class="ic">🤝</span>دعوت از دوستان</h3>
      <div class="stat-row"><span>پورسانت شما</span><b>${r.percent}٪ از اولین خرید</b></div>
      <div class="stat-row"><span>تعداد زیرمجموعه‌ها</span><b>${fmt(r.count)}</b></div>
      <div class="stat-row"><span>اعتبار کسب‌شده</span><b>${fmt(r.credit)} تومان</b></div>
      ${r.link ? `
      <div class="link-box" style="margin-top:8px">${r.link}</div>
      <button class="btn small outline" id="copy-referral-btn" data-link="${r.link}" style="width:100%;margin-top:8px">📋 کپی لینک دعوت</button>
      ` : ""}
    </div>
  `;
}

function orderCard(o) {
  const exp = o.expires_at ? toJalaliStr(o.expires_at) : "نامحدود";
  return `
    <div class="order-block">
      <div class="stat-row"><span>${o.product_name}</span><span class="badge approved">فعال تا ${exp}</span></div>
      ${o.link ? `
      <div class="sub-info" id="sub-info-${o.id}"><div class="sub-info-loading">در حال دریافت اطلاعات مصرف...</div></div>
      <div class="link-box">${o.link}</div>
      <div class="qr-row">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(o.link)}" width="96" height="96" alt="QR" />
        <button class="btn small outline" onclick="navigator.clipboard.writeText('${o.link}');tg.HapticFeedback.notificationOccurred('success')">📋 کپی لینک</button>
      </div>` : ""}
    </div>
  `;
}

function fmtGB(bytes) {
  return (bytes / (1024 ** 3)).toFixed(2);
}

async function loadSubInfo(orderId, link) {
  const box = document.getElementById(`sub-info-${orderId}`);
  if (!box) return;
  try {
    const info = await api(`/api/sub-info?link=${encodeURIComponent(link)}`);
    if (!box.isConnected) return;
    if (!info.ok) {
      box.innerHTML = `<div class="sub-info-error">⚠️ اطلاعات مصرف در دسترس نیست</div>`;
      return;
    }
    const used = info.upload + info.download;
    const total = info.total;
    let usageHtml;
    if (total > 0) {
      const percent = Math.min(100, Math.round((used / total) * 100));
      const remaining = Math.max(0, total - used);
      usageHtml = `
        <div class="sub-info-row"><span>مصرف</span><b>${fmtGB(used)} از ${fmtGB(total)} گیگابایت</b></div>
        <div class="progress-track"><div class="progress-fill" style="width:${percent}%"></div></div>
        <div class="sub-info-row"><span>باقی‌مانده</span><b>${fmtGB(remaining)} گیگابایت</b></div>
      `;
    } else {
      usageHtml = `<div class="sub-info-row"><span>مصرف</span><b>${fmtGB(used)} گیگابایت (نامحدود)</b></div>`;
    }
    let expiryHtml = `<div class="sub-info-row"><span>انقضا</span><b>نامحدود</b></div>`;
    if (info.expire) {
      const expDate = new Date(info.expire * 1000);
      const daysLeft = Math.max(0, Math.ceil((expDate - new Date()) / 86400000));
      expiryHtml = `<div class="sub-info-row"><span>انقضا</span><b>${toJalaliStr(expDate)} (${daysLeft} روز مانده)</b></div>`;
    }
    box.innerHTML = usageHtml + expiryHtml;
  } catch (e) {
    if (box.isConnected) box.innerHTML = `<div class="sub-info-error">⚠️ اطلاعات مصرف در دسترس نیست</div>`;
  }
}

// ---------------------------------------------------------------------------
// کارت بانکی + آپلود رسید (مشترک بین «شارژ کیف پول» و «پرداخت سفارش»)
// ---------------------------------------------------------------------------
function renderReceiptCard(box, { amount, cardNumber, cardHolder, sendReceipt, successText }) {
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
      <span id="receipt-label">مبلغ را واریز کن و عکس رسید را همینجا انتخاب کن</span>
      <input type="file" id="receipt-file" accept="image/*" />
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
    box.querySelector("#receipt-label").textContent = "✅ عکس رسید انتخاب شد";
    preview.src = URL.createObjectURL(file);
    preview.style.display = "block";
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
// تب فروشگاه
// ---------------------------------------------------------------------------
async function renderStore() {
  content.innerHTML = skeleton(4);
  try {
    const categories = await api("/api/catalog");
    if (categories.length === 0) {
      content.innerHTML = `<div class="state-msg"><span class="ic">◌</span>در حال حاضر محصولی موجود نیست.</div>`;
      return;
    }
    content.innerHTML = categories.map((c) => `
      <div class="card">
        <h3><span class="ic">▣</span>${c.name}</h3>
        ${c.products.map((p) => `
          <div class="product">
            <div>
              <div class="product-name">${p.name}</div>
              <div class="price">${fmt(p.price)} تومان</div>
            </div>
            <button class="btn small" ${p.stock <= 0 ? "disabled" : ""}
              onclick="buyProduct(${p.id}, ${p.price})">
              ${p.stock <= 0 ? "ناموجود" : "خرید"}
            </button>
          </div>
        `).join("")}
      </div>
    `).join("");
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}

async function buyProduct(productId) {
  const code = prompt("کد تخفیف دارید؟ (اختیاری - خالی بگذارید و تایید کنید)");
  try {
    const result = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, discount_code: code || null }),
    });
    if (result.status === "approved") {
      tg.HapticFeedback.notificationOccurred("success");
      notify("✅ خرید تایید شد! از تب خانه لینک را ببینید.");
      switchTab("home");
    } else {
      content.innerHTML = `
        <button class="btn outline small" id="back-to-store-btn" style="width:auto;margin-bottom:12px">→ بازگشت به فروشگاه</button>
        <div class="eyebrow">پرداخت سفارش</div>
        <div class="card" id="order-payment-card"></div>
      `;
      document.getElementById("back-to-store-btn").onclick = renderStore;
      renderReceiptCard(document.getElementById("order-payment-card"), {
        amount: result.final_price,
        cardNumber: result.card_number,
        cardHolder: result.card_holder,
        successText: "رسید ارسال شد. پس از تایید ادمین، کانفیگ از تب خانه در دسترس شما خواهد بود.",
        sendReceipt: async (file) => {
          const fd = new FormData();
          fd.append("photo", file);
          await apiUpload(`/api/orders/${result.order_id}/receipt`, fd);
        },
      });
    }
  } catch (e) {
    notify("خطا: " + e.message);
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
    content.innerHTML = `
      <div class="eyebrow">کیف پول</div>
      <div class="card">
        <h3><span class="ic">👛</span>موجودی فعلی</h3>
        <div class="stat-row"><span>قابل استفاده برای خرید</span><b>${fmt(me.wallet_credit)} تومان</b></div>
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
// تب مدیریت (فقط ادمین) - چیدمان دکمه‌های منوی اصلی
// ---------------------------------------------------------------------------

let adminMenuItems = [];

const STYLE_OPTIONS = [
  { value: "", label: "⚪️ پیش‌فرض" },
  { value: "primary", label: "🔵 آبی" },
  { value: "success", label: "🟢 سبز" },
  { value: "danger", label: "🔴 قرمز" },
];

let adminSection = "stats"; // stats | menu | branding | catalog | tickets | sales | users | resellers
let adminCatalogView = { level: "categories" }; // categories | products | configs
let adminTicketView = { level: "list" }; // list | thread

const ADMIN_TABS = [
  { key: "stats", label: "آمار", fullOnly: true },
  { key: "menu", label: "چیدمان منو", fullOnly: true },
  { key: "branding", label: "برندینگ", fullOnly: true },
  { key: "catalog", label: "محصولات", fullOnly: true },
  { key: "users", label: "مدیریت کاربران", fullOnly: false },
  { key: "sales", label: "فروش", fullOnly: true },
  { key: "tickets", label: "تیکت‌ها", fullOnly: false },
  { key: "adminlog", label: "لاگ ادمین", fullOnly: true },
  { key: "backup", label: "بکاپ", fullOnly: true, ownerOnly: true },
];

async function renderAdmin() {
  const isMainBot = !TENANT_ID;

  let adminRole = "admin";
  try {
    const check = await api("/api/admin/check");
    adminRole = check.admin_role || "admin";
  } catch (e) {
    // در صورت خطا محتاطانه فرض می‌کنیم دسترسی کامل نیست
  }
  const isSupport = adminRole === "support";
  const isOwner = adminRole === "owner";
  const visibleTabs = ADMIN_TABS.filter((t) => (!isSupport || !t.fullOnly) && (!t.ownerOnly || isOwner));
  if (isSupport && !visibleTabs.some((t) => t.key === adminSection)) {
    adminSection = visibleTabs[0].key;
  }

  const prevTabsEl = document.getElementById("admin-section-tabs");
  const prevScrollLeft = prevTabsEl ? prevTabsEl.scrollLeft : 0;
  content.innerHTML = `
    ${isSupport ? `<div class="banner" style="margin-bottom:10px"><div class="banner-title"><span class="ic">🎧</span>نقش شما: پشتیبان (دسترسی محدود)</div></div>` : ""}
    <div class="segmented" id="admin-section-tabs">
      ${visibleTabs.map((t) => `<button class="seg-btn ${adminSection === t.key ? "active" : ""}" data-section="${t.key}">${t.label}</button>`).join("")}
      ${(!isSupport && isMainBot) ? `<button class="seg-btn ${adminSection === "resellers" ? "active" : ""}" data-section="resellers">نمایندگی‌ها</button>` : ""}
    </div>
    <div id="admin-section-body">${skeleton(4)}</div>
  `;
  const newTabsEl = document.getElementById("admin-section-tabs");
  if (newTabsEl) {
    newTabsEl.scrollLeft = prevScrollLeft;
    const activeBtn = newTabsEl.querySelector(".seg-btn.active");
    if (activeBtn) activeBtn.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  document.querySelectorAll("#admin-section-tabs .seg-btn").forEach((b) => {
    b.onclick = () => {
      adminSection = b.dataset.section;
      if (adminSection === "catalog") adminCatalogView = { level: "categories" };
      if (adminSection === "tickets") adminTicketView = { level: "list" };
      if (adminSection === "users") adminUserView = { level: "list", filter: "all", query: "" };
      renderAdmin();
    };
  });
  if (adminSection === "stats") await renderAdminStatsSection();
  else if (adminSection === "menu") await renderAdminMenuSection();
  else if (adminSection === "branding") await renderAdminBrandingSection();
  else if (adminSection === "catalog") await renderAdminCatalogSection();
  else if (adminSection === "users") await renderAdminUsersSection();
  else if (adminSection === "sales") await renderAdminSalesSection();
  else if (adminSection === "tickets") await renderAdminTicketsSection();
  else if (adminSection === "adminlog") await renderAdminLogSection();
  else if (adminSection === "resellers" && isMainBot && !isSupport) await renderAdminResellersSection();
  else if (adminSection === "backup") await renderAdminBackupSection();
}

// ---------------------------------------------------------------------------
// تب مدیریت > آمار (داشبورد)
// ---------------------------------------------------------------------------

let adminStatsRange = { preset: 14, startDate: "", endDate: "" };

function _statsRangeDates() {
  if (adminStatsRange.startDate && adminStatsRange.endDate) {
    return { start: adminStatsRange.startDate, end: adminStatsRange.endDate };
  }
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (adminStatsRange.preset - 1));
  const toISO = (d) => d.toISOString().slice(0, 10);
  return { start: toISO(start), end: toISO(end) };
}

function _changeBadge(pct) {
  if (pct === null || pct === undefined) return `<span class="hint-text" style="margin:0">—</span>`;
  const up = pct >= 0;
  const color = up ? "var(--cyan)" : "var(--danger)";
  const arrow = up ? "▲" : "▼";
  return `<span style="color:${color};font-weight:700;font-size:12px">${arrow} ${Math.abs(pct)}٪</span>`;
}

async function renderAdminStatsSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(4);
  try {
    const { start, end } = _statsRangeDates();
    const s = await api(`/api/admin/dashboard?start_date=${start}&end_date=${end}`);
    const maxRevenue = Math.max(...s.daily_series.map((d) => d.revenue), 1);
    const presets = [7, 14, 30, 90];
    const [sJy, sJm, sJd] = isoToJalaliYMD(start);
    const [eJy, eJm, eJd] = isoToJalaliYMD(end);

    body.innerHTML = `
      <div class="card">
        <div class="segmented" style="margin-bottom:10px">
          ${presets.map((p) => `<button class="seg-btn ${!adminStatsRange.startDate && adminStatsRange.preset === p ? "active" : ""}" data-stats-preset="${p}">${p} روز اخیر</button>`).join("")}
        </div>
        <p class="hint-text" style="margin:0 0 4px">از تاریخ</p>
        <div style="display:flex;gap:4px;margin-bottom:10px">
          ${jalaliDateSelectHtml("stats-start", sJy, sJm, sJd)}
        </div>
        <p class="hint-text" style="margin:0 0 4px">تا تاریخ</p>
        <div style="display:flex;gap:4px">
          ${jalaliDateSelectHtml("stats-end", eJy, eJm, eJd)}
        </div>
        <button class="btn small outline" id="stats-apply-range" style="width:auto;margin-top:10px">اعمال بازه‌ی دلخواه</button>
        <p class="hint-text">بازه‌ی نمایش‌داده‌شده: ${toJalaliStr(s.start_date)} تا ${toJalaliStr(s.end_date)}</p>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">💰 درآمد این بازه</div>
        <div class="stat-row"><span>مبلغ</span><b>${fmt(s.revenue)} تومان</b></div>
        <div class="stat-row"><span>نسبت به بازه‌ی قبل</span>${_changeBadge(s.revenue_change_pct)}</div>
      </div>

      <div class="stat-grid">
        <div class="stat-card"><span class="stat-num">${fmt(s.total_users)}</span><span class="stat-label">کل کاربران</span></div>
        <div class="stat-card"><span class="stat-num">+${fmt(s.new_users)}</span><span class="stat-label">کاربر جدید این بازه</span></div>
        <div class="stat-card"><span class="stat-num">${fmt(s.approved)}</span><span class="stat-label">سفارش تاییدشده</span></div>
        <div class="stat-card"><span class="stat-num">${fmt(s.pending)}</span><span class="stat-label">سفارش در انتظار</span></div>
        <div class="stat-card"><span class="stat-num">${fmt(s.rejected)}</span><span class="stat-label">سفارش ردشده</span></div>
        <div class="stat-card"><span class="stat-num">${s.conversion_rate}٪</span><span class="stat-label">نرخ تبدیل</span></div>
        <div class="stat-card"><span class="stat-num">${fmt(s.aov)}</span><span class="stat-label">میانگین سبد خرید (تومان)</span></div>
        <div class="stat-card"><span class="stat-num">${fmt(s.active_configs)}</span><span class="stat-label">کانفیگ فعال</span></div>
        <div class="stat-card"><span class="stat-num">${fmt(s.open_tickets)}</span><span class="stat-label">تیکت باز</span></div>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">📈 روند درآمد در بازه</div>
        <div class="bar-chart">
          ${s.daily_series.map((d) => `
            <div class="bar-chart-col">
              <div class="bar-chart-bar" style="height:${Math.max((d.revenue / maxRevenue) * 100, 3)}%" title="${fmt(d.revenue)} تومان"></div>
              <span class="bar-chart-label">${toJalaliMonthDay(d.date)}</span>
            </div>
          `).join("")}
        </div>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🗂 تفکیک درآمد بر اساس دسته‌بندی</div>
        ${s.category_breakdown.length === 0 ? `<div class="hint-text" style="margin:0">فروشی در این بازه ثبت نشده.</div>` : s.category_breakdown.map((c) => `
          <div class="admin-list-row">
            <div class="admin-list-row-main">
              <span>${escHtml(c.name)}</span>
              <span class="hint-text" style="margin:0">${c.orders} سفارش</span>
            </div>
            <div class="admin-list-row-actions"><b>${fmt(c.revenue)} تومان</b></div>
          </div>
        `).join("")}
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🤝 رفرال در مقابل خرید مستقیم</div>
        <div class="stat-row"><span>از طریق رفرال</span><b>${fmt(s.referral_revenue)} تومان</b></div>
        <div class="stat-row"><span>خرید مستقیم</span><b>${fmt(s.direct_revenue)} تومان</b></div>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🏆 پرفروش‌ترین محصولات این بازه</div>
        ${s.top_products.length === 0 ? `<div class="hint-text" style="margin:0">هنوز فروشی ثبت نشده.</div>` : s.top_products.map((p, i) => `
          <div class="admin-list-row">
            <div class="admin-list-row-main">
              <span>${i + 1}. ${escHtml(p.name)}</span>
              <span class="hint-text" style="margin:0">${p.orders} فروش · ${fmt(p.revenue)} تومان</span>
            </div>
          </div>
        `).join("")}
      </div>

      <a class="btn outline small" style="width:auto;display:inline-block;text-decoration:none;text-align:center" href="${withTenant(`/api/admin/orders/export?start_date=${s.start_date}&end_date=${s.end_date}`)}" target="_blank">📤 خروجی اکسل سفارش‌های این بازه (CSV)</a>
    `;

    body.querySelectorAll("[data-stats-preset]").forEach((el) => {
      el.onclick = () => {
        adminStatsRange = { preset: Number(el.dataset.statsPreset), startDate: "", endDate: "" };
        renderAdminStatsSection();
      };
    });
    document.getElementById("stats-apply-range").onclick = () => {
      const sJyv = Number(document.getElementById("stats-start-y").value);
      const sJmv = Number(document.getElementById("stats-start-m").value);
      const sJdv = Number(document.getElementById("stats-start-d").value);
      const eJyv = Number(document.getElementById("stats-end-y").value);
      const eJmv = Number(document.getElementById("stats-end-m").value);
      const eJdv = Number(document.getElementById("stats-end-d").value);
      const sd = jalaliToISO(sJyv, sJmv, sJdv);
      const ed = jalaliToISO(eJyv, eJmv, eJdv);
      if (sd > ed) { notify("تاریخ شروع باید قبل از تاریخ پایان باشد."); return; }
      adminStatsRange = { preset: 0, startDate: sd, endDate: ed };
      renderAdminStatsSection();
    };
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب مدیریت > چیدمان منو
// ---------------------------------------------------------------------------

async function renderAdminMenuSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(3);
  try {
    const menu = await api("/api/admin/menu");
    adminMenuItems = menu;
    body.innerHTML = `
      <p class="hint-text">ترتیب، متن، رنگ و فعال/غیرفعال بودن دکمه‌های منوی اصلی بات را از اینجا مدیریت کن. با فلش‌ها جای دکمه‌ها را جابه‌جا کن.</p>
      <div class="card" id="admin-menu-list"></div>
      <button class="btn" id="admin-menu-save">💾 ذخیره تغییرات</button>
    `;
    renderAdminMenuList();
    document.getElementById("admin-menu-save").onclick = saveAdminMenu;
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب مدیریت > برندینگ (نام فروشگاه / بنر / عکس هدر / تم مینی‌اپ)
// ---------------------------------------------------------------------------

async function renderAdminBrandingSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(3);
  try {
    const branding = await api("/api/admin/settings/branding");
    body.innerHTML = `
      <div class="card">
        <div class="eyebrow" style="margin-top:0">🎨 برندینگ مینی‌اپ</div>
        <p class="hint-text">نام و متن بالای صفحه‌ی مینی‌اپ (بنر) همینجا قابل تغییره.</p>
        <label class="field-label">نام فروشگاه (بالای صفحه، کنار آیکون ⚡)</label>
        <input class="input" id="brand-store-name" type="text" placeholder="مثال: SHOP VPN" value="${branding.store_name.replace(/"/g, "&quot;")}" style="direction:rtl;text-align:right;font-family:var(--font-body);margin-bottom:10px" />
        <label class="field-label">متن بنر (زیر نام کاربر، مثلاً یک شعار کوتاه)</label>
        <input class="input" id="brand-banner-text" type="text" placeholder="مثال: اتصال امن و پایدار برقرار است" value="${branding.banner_text.replace(/"/g, "&quot;")}" style="direction:rtl;text-align:right;font-family:var(--font-body);margin-bottom:4px" />
        <div class="field-error" id="brand-error"></div>
        <button class="btn" id="brand-save" style="margin-top:8px">💾 ذخیره برندینگ</button>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🖼 عکس بالای صفحه (به‌جای خورشید)</div>
        <p class="hint-text">می‌تونی به‌جای انیمیشن خورشید بالای مینی‌اپ، یک عکس/لوگوی دلخواه بذاری.</p>
        <div id="header-logo-preview" style="margin-bottom:10px">
          ${branding.header_image ? `<img src="${branding.header_image}" style="width:88px;height:88px;border-radius:50%;object-fit:cover;border:2px solid var(--glass-brd)" />` : `<span class="hint-text" style="margin:0">فعلاً عکسی تنظیم نشده؛ همون خورشید انیمیشنی نمایش داده می‌شه.</span>`}
        </div>
        <input type="file" accept="image/*" id="header-logo-file" style="margin-bottom:10px" />
        <div class="field-error" id="header-logo-error"></div>
        <div style="display:flex;gap:8px;margin-top:4px">
          <button class="btn" id="header-logo-save">💾 آپلود عکس</button>
          ${branding.header_image ? `<button class="btn outline danger" id="header-logo-reset">🗑 بازگشت به خورشید</button>` : ""}
        </div>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🎨 تم مینی‌اپ</div>
        <p class="hint-text">یکی از تم‌های آماده رو برای رنگ‌بندی کل مینی‌اپ انتخاب کن.</p>
        <select class="input" id="theme-select" style="margin-bottom:10px">
          ${branding.themes.map((t) => `<option value="${t.id}" ${t.id === branding.theme ? "selected" : ""}>${t.label}</option>`).join("")}
        </select>
        <div class="field-error" id="theme-error"></div>
        <button class="btn" id="theme-save">💾 اعمال تم</button>
      </div>
    `;

    document.getElementById("brand-save").onclick = async () => {
      const errBox = document.getElementById("brand-error");
      errBox.textContent = "";
      const storeName = document.getElementById("brand-store-name").value.trim();
      const bannerText = document.getElementById("brand-banner-text").value.trim();
      if (!storeName || !bannerText) { errBox.textContent = "هر دو کادر باید پر باشند."; return; }
      try {
        await api("/api/admin/settings/branding", {
          method: "POST",
          body: JSON.stringify({ store_name: storeName, banner_text: bannerText }),
        });
        tg.HapticFeedback.notificationOccurred("success");
        notify("برندینگ ذخیره شد. برای دیدن تغییر، صفحه را دوباره باز کن.");
      } catch (e) { errBox.textContent = e.message; }
    };

    document.getElementById("header-logo-save").onclick = async () => {
      const errBox = document.getElementById("header-logo-error");
      errBox.textContent = "";
      const fileInput = document.getElementById("header-logo-file");
      const file = fileInput.files && fileInput.files[0];
      if (!file) { errBox.textContent = "ابتدا یک عکس انتخاب کن."; return; }
      const fd = new FormData();
      fd.append("photo", file);
      try {
        await apiUpload("/api/admin/settings/header-image", fd);
        tg.HapticFeedback.notificationOccurred("success");
        notify("عکس بالای صفحه ذخیره شد. برای دیدن تغییر، صفحه را دوباره باز کن.");
        renderAdminBrandingSection();
      } catch (e) { errBox.textContent = e.message; }
    };

    const resetBtn = document.getElementById("header-logo-reset");
    if (resetBtn) {
      resetBtn.onclick = async () => {
        if (!confirm("عکس سفارشی حذف و به خورشید انیمیشنی پیش‌فرض برگردد؟")) return;
        try {
          await api("/api/admin/settings/header-image", { method: "DELETE" });
          tg.HapticFeedback.notificationOccurred("success");
          renderAdminBrandingSection();
        } catch (e) { notify(e.message); }
      };
    }

    document.getElementById("theme-save").onclick = async () => {
      const errBox = document.getElementById("theme-error");
      errBox.textContent = "";
      const theme = document.getElementById("theme-select").value;
      try {
        await api("/api/admin/settings/theme", { method: "POST", body: JSON.stringify({ theme }) });
        tg.HapticFeedback.notificationOccurred("success");
        notify("تم ذخیره شد. برای دیدن تغییر، صفحه را دوباره باز کن.");
      } catch (e) { errBox.textContent = e.message; }
    };
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

function renderAdminMenuList() {
  const list = document.getElementById("admin-menu-list");
  list.innerHTML = adminMenuItems.map((item, idx) => adminMenuRow(item, idx)).join("");
  adminMenuItems.forEach((item, idx) => {
    const upBtn = document.getElementById(`menu-up-${idx}`);
    const downBtn = document.getElementById(`menu-down-${idx}`);
    if (upBtn) upBtn.onclick = () => moveMenuItem(idx, -1);
    if (downBtn) downBtn.onclick = () => moveMenuItem(idx, 1);
  });
}

function adminMenuRow(item, idx) {
  const styleSelect = item.has_style
    ? `<select class="input menu-style-input" data-idx="${idx}">
        ${STYLE_OPTIONS.map((o) => `<option value="${o.value}" ${o.value === (item.style || "") ? "selected" : ""}>${o.label}</option>`).join("")}
      </select>`
    : "";
  const textInput = item.has_text
    ? `<input class="input menu-text-input" data-idx="${idx}" type="text" value="${(item.text || "").replace(/"/g, "&quot;")}" placeholder="متن دکمه" />`
    : `<div class="hint-text" style="margin:0">${item.label} (بدون متن قابل‌ویرایش)</div>`;
  const toggle = item.togglable
    ? `<label class="menu-toggle">
        <input type="checkbox" class="menu-enabled-input" data-idx="${idx}" ${item.enabled ? "checked" : ""} />
        <span>فعال</span>
      </label>`
    : "";
  return `
    <div class="menu-row" data-idx="${idx}">
      <div class="menu-row-top">
        <span class="menu-row-label">${item.label}${item.admin_only ? " (فقط ادمین)" : ""}</span>
        <div class="menu-row-arrows">
          <button type="button" class="btn small outline" id="menu-up-${idx}" ${idx === 0 ? "disabled" : ""}>▲</button>
          <button type="button" class="btn small outline" id="menu-down-${idx}" ${idx === adminMenuItems.length - 1 ? "disabled" : ""}>▼</button>
        </div>
      </div>
      <div class="menu-row-body">
        ${textInput}
        ${styleSelect}
        ${toggle}
      </div>
    </div>
  `;
}

function collectMenuEdits() {
  document.querySelectorAll(".menu-text-input").forEach((el) => {
    adminMenuItems[Number(el.dataset.idx)].text = el.value;
  });
  document.querySelectorAll(".menu-style-input").forEach((el) => {
    adminMenuItems[Number(el.dataset.idx)].style = el.value;
  });
  document.querySelectorAll(".menu-enabled-input").forEach((el) => {
    adminMenuItems[Number(el.dataset.idx)].enabled = el.checked;
  });
}

function moveMenuItem(idx, dir) {
  collectMenuEdits();
  const newIdx = idx + dir;
  if (newIdx < 0 || newIdx >= adminMenuItems.length) return;
  const tmp = adminMenuItems[idx];
  adminMenuItems[idx] = adminMenuItems[newIdx];
  adminMenuItems[newIdx] = tmp;
  renderAdminMenuList();
}

async function saveAdminMenu() {
  collectMenuEdits();
  const saveBtn = document.getElementById("admin-menu-save");
  saveBtn.disabled = true;
  saveBtn.textContent = "در حال ذخیره...";
  try {
    await api("/api/admin/menu", {
      method: "POST",
      body: JSON.stringify({
        order: adminMenuItems.map((i) => i.key),
        buttons: adminMenuItems.map((i) => ({ key: i.key, text: i.text, style: i.style, enabled: i.enabled })),
      }),
    });
    tg.HapticFeedback.notificationOccurred("success");
    notify("چیدمان منو با موفقیت ذخیره شد. برای دیدن تغییرات، بات را دوباره در تلگرام باز کن.");
  } catch (e) {
    notify(e.message);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "💾 ذخیره تغییرات";
  }
}

// ---------------------------------------------------------------------------
// تب مدیریت > محصولات (دسته‌بندی‌ها / محصولات / بانک کانفیگ)
// ---------------------------------------------------------------------------

async function renderAdminCatalogSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(3);
  try {
    if (adminCatalogView.level === "categories") {
      await renderAdminCategories(body);
    } else if (adminCatalogView.level === "products") {
      await renderAdminProducts(body);
    } else if (adminCatalogView.level === "configs") {
      await renderAdminConfigs(body);
    }
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

async function renderAdminCategories(body) {
  const cats = await api("/api/admin/categories");
  body.innerHTML = `
    <div class="card">
      ${cats.length === 0 ? `<div class="hint-text" style="margin:0">هنوز دسته‌بندی‌ای ثبت نشده.</div>` : cats.map((c) => `
        <div class="admin-list-row">
          <div class="admin-list-row-main" data-open-cat="${c.id}" data-cat-name="${(c.name || "").replace(/"/g, "&quot;")}">
            <span>${c.name}</span>
            <span class="hint-text" style="margin:0">${c.product_count} محصول ${c.is_active ? "" : "· غیرفعال"}</span>
          </div>
          <div class="admin-list-row-actions">
            <button class="btn small outline" data-edit-cat="${c.id}">✏️</button>
            <button class="btn small outline" data-toggle-cat="${c.id}">${c.is_active ? "⛔️" : "✅"}</button>
            <button class="btn small outline danger" data-del-cat="${c.id}">🗑️</button>
          </div>
        </div>
      `).join("")}
    </div>
    <div class="card">
      <div class="eyebrow" style="margin-top:0">افزودن دسته‌بندی جدید</div>
      <input class="input" id="new-cat-name" type="text" placeholder="نام دسته‌بندی" style="direction:rtl;text-align:right;font-family:var(--font-body)" />
      <button class="btn" id="new-cat-save" style="margin-top:8px">➕ افزودن</button>
    </div>
  `;
  body.querySelectorAll("[data-open-cat]").forEach((el) => {
    el.onclick = () => {
      adminCatalogView = { level: "products", categoryId: Number(el.dataset.openCat), categoryName: el.dataset.catName };
      renderAdmin();
    };
  });
  body.querySelectorAll("[data-edit-cat]").forEach((el) => {
    el.onclick = async () => {
      const cat = cats.find((c) => c.id === Number(el.dataset.editCat));
      const name = prompt("نام جدید دسته‌بندی:", cat.name);
      if (!name || !name.trim()) return;
      try {
        await api(`/api/admin/categories/${cat.id}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  body.querySelectorAll("[data-toggle-cat]").forEach((el) => {
    el.onclick = async () => {
      try {
        await api(`/api/admin/categories/${el.dataset.toggleCat}/toggle`, { method: "POST" });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  body.querySelectorAll("[data-del-cat]").forEach((el) => {
    el.onclick = async () => {
      if (!confirm("حذف این دسته‌بندی و همه‌ی محصولاتش؟ این کار برگشت‌ناپذیر است.")) return;
      try {
        await api(`/api/admin/categories/${el.dataset.delCat}`, { method: "DELETE" });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  document.getElementById("new-cat-save").onclick = async () => {
    const input = document.getElementById("new-cat-name");
    if (!input.value.trim()) return;
    try {
      await api("/api/admin/categories", { method: "POST", body: JSON.stringify({ name: input.value.trim() }) });
      renderAdmin();
    } catch (e) { notify(e.message); }
  };
}

async function renderAdminProducts(body) {
  const { categoryId, categoryName } = adminCatalogView;
  const products = await api(`/api/admin/categories/${categoryId}/products`);
  body.innerHTML = `
    <button class="btn outline small" id="back-to-cats" style="width:auto;margin-bottom:12px">→ بازگشت به دسته‌بندی‌ها</button>
    <div class="eyebrow" style="margin-top:0">محصولات «${categoryName}»</div>
    <div class="card">
      ${products.length === 0 ? `<div class="hint-text" style="margin:0">هنوز محصولی در این دسته ثبت نشده.</div>` : products.map((p) => `
        <div class="admin-list-row">
          <div class="admin-list-row-main" data-open-prod="${p.id}" data-prod-name="${(p.name || "").replace(/"/g, "&quot;")}">
            <span>${p.name}</span>
            <span class="hint-text" style="margin:0">${fmt(p.price)} تومان · موجودی: ${p.stock} ${p.is_active ? "" : "· غیرفعال"}</span>
          </div>
          <div class="admin-list-row-actions">
            <button class="btn small outline" data-edit-prod="${p.id}">✏️</button>
            <button class="btn small outline" data-toggle-prod="${p.id}">${p.is_active ? "⛔️" : "✅"}</button>
            <button class="btn small outline danger" data-del-prod="${p.id}">🗑️</button>
          </div>
        </div>
      `).join("")}
    </div>
    <div class="card">
      <div class="eyebrow" style="margin-top:0">افزودن محصول جدید</div>
      <input class="input" id="new-prod-name" type="text" placeholder="نام محصول" style="direction:rtl;text-align:right;font-family:var(--font-body);margin-bottom:8px" />
      <input class="input" id="new-prod-price" type="number" placeholder="قیمت (تومان)" style="margin-bottom:8px" />
      <input class="input" id="new-prod-duration" type="number" placeholder="مدت اعتبار (روز)" value="30" style="margin-bottom:8px" />
      <input class="input" id="new-prod-desc" type="text" placeholder="توضیحات (اختیاری)" style="direction:rtl;text-align:right;font-family:var(--font-body);margin-bottom:8px" />
      <button class="btn" id="new-prod-save">➕ افزودن محصول</button>
    </div>
  `;
  document.getElementById("back-to-cats").onclick = () => {
    adminCatalogView = { level: "categories" };
    renderAdmin();
  };
  body.querySelectorAll("[data-open-prod]").forEach((el) => {
    el.onclick = () => {
      adminCatalogView = {
        level: "configs", productId: Number(el.dataset.openProd), productName: el.dataset.prodName,
        categoryId, categoryName,
      };
      renderAdmin();
    };
  });
  body.querySelectorAll("[data-edit-prod]").forEach((el) => {
    el.onclick = async () => {
      const p = products.find((x) => x.id === Number(el.dataset.editProd));
      const name = prompt("نام محصول:", p.name);
      if (name === null) return;
      const price = prompt("قیمت (تومان):", p.price);
      if (price === null) return;
      const duration = prompt("مدت اعتبار (روز):", p.duration_days);
      if (duration === null) return;
      try {
        await api(`/api/admin/products/${p.id}`, {
          method: "PATCH",
          body: JSON.stringify({ name: name.trim() || undefined, price: Number(price), duration_days: Number(duration) }),
        });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  body.querySelectorAll("[data-toggle-prod]").forEach((el) => {
    el.onclick = async () => {
      try {
        await api(`/api/admin/products/${el.dataset.toggleProd}/toggle`, { method: "POST" });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  body.querySelectorAll("[data-del-prod]").forEach((el) => {
    el.onclick = async () => {
      if (!confirm("حذف این محصول و بانک کانفیگ‌هایش؟ این کار برگشت‌ناپذیر است.")) return;
      try {
        await api(`/api/admin/products/${el.dataset.delProd}`, { method: "DELETE" });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  document.getElementById("new-prod-save").onclick = async () => {
    const name = document.getElementById("new-prod-name").value.trim();
    const price = Number(document.getElementById("new-prod-price").value);
    const duration = Number(document.getElementById("new-prod-duration").value) || 30;
    const desc = document.getElementById("new-prod-desc").value.trim();
    if (!name || !price) { notify("نام و قیمت الزامی است."); return; }
    try {
      await api("/api/admin/products", {
        method: "POST",
        body: JSON.stringify({ category_id: categoryId, name, price, duration_days: duration, description: desc }),
      });
      renderAdmin();
    } catch (e) { notify(e.message); }
  };
}

async function renderAdminConfigs(body) {
  const { productId, productName, categoryId, categoryName } = adminCatalogView;
  const configs = await api(`/api/admin/products/${productId}/configs`);
  body.innerHTML = `
    <button class="btn outline small" id="back-to-prods" style="width:auto;margin-bottom:12px">→ بازگشت به محصولات «${categoryName}»</button>
    <div class="eyebrow" style="margin-top:0">بانک کانفیگ «${productName}»</div>
    <div class="card">
      <div class="eyebrow" style="margin-top:0">🎲 دریافت کانفیگ رندوم</div>
      <p class="hint-text">یکی از کانفیگ‌های آزاد این محصول به‌صورت تصادفی برداشته و به تو اختصاص داده می‌شود (از انبار کم می‌شود).</p>
      <button class="btn outline" id="take-random-cfg-btn">🎲 دریافت یک کانفیگ رندوم</button>
      <div id="random-cfg-result"></div>
    </div>
    <div class="card">
      <p class="hint-text" id="cfg-stock-count" style="margin:0 0 10px">موجودی فعلی: ${configs.length} کانفیگ استفاده‌نشده</p>
      <div id="cfg-list-box">
      ${configs.length === 0 ? `<div class="hint-text" style="margin:0">کانفیگی در انبار نیست.</div>` : configs.map((c) => `
        <div class="admin-list-row">
          <div class="admin-list-row-main" style="direction:ltr;text-align:left;font-family:var(--font-mono);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.link}</div>
          <div class="admin-list-row-actions">
            <button class="btn small outline danger" data-del-cfg="${c.id}">🗑️</button>
          </div>
        </div>
      `).join("")}
      </div>
    </div>
    <div class="card">
      <div class="eyebrow" style="margin-top:0">افزودن دسته‌ای کانفیگ</div>
      <p class="hint-text">هر خط یک لینک کانفیگ (vmess/vless/...) وارد کن.</p>
      <textarea class="input" id="new-configs-bulk" rows="5" style="direction:ltr;text-align:left;resize:vertical"></textarea>
      <button class="btn" id="new-configs-save" style="margin-top:8px">➕ افزودن به انبار</button>
    </div>
  `;
  document.getElementById("back-to-prods").onclick = () => {
    adminCatalogView = { level: "products", categoryId, categoryName };
    renderAdmin();
  };
  document.getElementById("take-random-cfg-btn").onclick = async () => {
    const resultBox = document.getElementById("random-cfg-result");
    try {
      const res = await api(`/api/admin/products/${productId}/take-random-config`, { method: "POST" });
      tg.HapticFeedback.notificationOccurred("success");
      resultBox.innerHTML = `
        <div class="hint-text" style="margin:10px 0 4px">کانفیگ دریافت‌شده (این مورد از انبار کم شد):</div>
        <div class="input" style="direction:ltr;text-align:left;word-break:break-all;user-select:all">${res.link}</div>
      `;
      // به‌جای رفرش کامل صفحه (که نتیجه‌ی بالا را پاک می‌کند)، فقط لیست و شمارنده را به‌روزرسانی می‌کنیم
      const idx = configs.findIndex((c) => c.id === res.id);
      if (idx !== -1) configs.splice(idx, 1);
      const listBox = document.getElementById("cfg-list-box");
      listBox.innerHTML = configs.length === 0
        ? `<div class="hint-text" style="margin:0">کانفیگی در انبار نیست.</div>`
        : configs.map((c) => `
            <div class="admin-list-row">
              <div class="admin-list-row-main" style="direction:ltr;text-align:left;font-family:var(--font-mono);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.link}</div>
              <div class="admin-list-row-actions">
                <button class="btn small outline danger" data-del-cfg="${c.id}">🗑️</button>
              </div>
            </div>
          `).join("");
      listBox.querySelectorAll("[data-del-cfg]").forEach((el) => {
        el.onclick = async () => {
          if (!confirm("این کانفیگ حذف شود؟")) return;
          try {
            await api(`/api/admin/configs/${el.dataset.delCfg}`, { method: "DELETE" });
            renderAdmin();
          } catch (e2) { notify(e2.message); }
        };
      });
      document.getElementById("cfg-stock-count").textContent = `موجودی فعلی: ${configs.length} کانفیگ استفاده‌نشده`;
    } catch (e) {
      resultBox.innerHTML = `<div class="field-error" style="margin-top:10px">${e.message}</div>`;
    }
  };
  body.querySelectorAll("[data-del-cfg]").forEach((el) => {
    el.onclick = async () => {
      if (!confirm("این کانفیگ حذف شود؟")) return;
      try {
        await api(`/api/admin/configs/${el.dataset.delCfg}`, { method: "DELETE" });
        renderAdmin();
      } catch (e) { notify(e.message); }
    };
  });
  document.getElementById("new-configs-save").onclick = async () => {
    const raw = document.getElementById("new-configs-bulk").value;
    const links = raw.split("\n").map((l) => l.trim()).filter(Boolean);
    if (links.length === 0) { notify("هیچ لینکی وارد نشده."); return; }
    try {
      const res = await api(`/api/admin/products/${productId}/configs`, { method: "POST", body: JSON.stringify({ links }) });
      tg.HapticFeedback.notificationOccurred("success");
      notify(`${res.added} کانفیگ اضافه شد.`);
      renderAdmin();
    } catch (e) { notify(e.message); }
  };
}

// ---------------------------------------------------------------------------
// تب مدیریت > مدیریت کاربران (کیف‌پول و در آینده امکانات بیشتر)
// ---------------------------------------------------------------------------

let adminUserView = { level: "list", filter: "all", query: "" };
const USER_STATUS_LABEL = { active: "فعال", expired: "منقضی‌شده", blocked: "بلاک‌شده", none: "بدون سرویس" };
const USER_STATUS_BADGE_CLASS = { active: "approved", expired: "pending", blocked: "rejected", none: "" };

function escHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function renderAdminUsersSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(3);
  try {
    if (adminUserView.level === "list") await renderAdminUsersList(body);
    else await renderAdminUserDetail(body);
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

async function renderAdminUsersList(body) {
  const filter = adminUserView.filter || "all";
  const query = adminUserView.query || "";
  const data = await api(`/api/admin/users?query=${encodeURIComponent(query)}&status=${filter}&limit=50&offset=0`);

  const filters = [
    { k: "all", label: "همه" },
    { k: "active", label: "فعال" },
    { k: "expired", label: "منقضی‌شده" },
    { k: "blocked", label: "بلاک‌شده" },
  ];

  body.innerHTML = `
    <div class="card">
      <div class="eyebrow" style="margin-top:0">📢 پیام گروهی به کاربران منقضی‌شده</div>
      <textarea class="input" id="broadcast-expired-text" rows="2" placeholder="متن پیام تشویق به تمدید..." style="margin-bottom:8px;resize:vertical"></textarea>
      <button class="btn outline small" id="broadcast-expired-btn" style="width:auto">ارسال به همه‌ی کاربران منقضی‌شده</button>
    </div>

    <div class="card">
      <input class="input" id="user-search-input" type="text" placeholder="جستجو با آیدی عددی، یوزرنیم یا نام..." value="${escHtml(query)}" style="margin-bottom:10px" />
      <div class="segmented" style="margin-bottom:0">
        ${filters.map((f) => `<button class="seg-btn ${filter === f.k ? "active" : ""}" data-user-filter="${f.k}">${f.label}</button>`).join("")}
      </div>
    </div>

    <div class="card">
      ${data.users.length === 0
        ? `<div class="state-msg"><span class="ic">👤</span>کاربری پیدا نشد.</div>`
        : data.users.map((u) => `
        <div class="admin-list-row" data-open-user="${u.telegram_id}" style="cursor:pointer">
          <div class="admin-list-row-main">
            <span>${escHtml(u.first_name || "بدون نام")}${u.username ? " (@" + escHtml(u.username) + ")" : ""}</span>
            <span class="hint-text" style="margin:0">🆔 ${u.telegram_id} · 👛 ${fmt(u.wallet_credit)} تومان</span>
          </div>
          <div class="admin-list-row-actions">
            <span class="badge ${USER_STATUS_BADGE_CLASS[u.status]}">${USER_STATUS_LABEL[u.status]}</span>
          </div>
        </div>
      `).join("")}
    </div>
    ${data.total > data.users.length ? `<p class="hint-text" style="text-align:center">${data.users.length} از ${data.total} کاربر نمایش داده شد؛ برای محدودکردن نتایج جستجو کنید.</p>` : ""}
  `;

  document.getElementById("user-search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      adminUserView = { ...adminUserView, query: e.target.value.trim() };
      renderAdminUsersSection();
    }
  });
  body.querySelectorAll("[data-user-filter]").forEach((el) => {
    el.onclick = () => {
      adminUserView = { ...adminUserView, filter: el.dataset.userFilter };
      renderAdminUsersSection();
    };
  });
  body.querySelectorAll("[data-open-user]").forEach((el) => {
    el.onclick = () => {
      adminUserView = { level: "detail", telegramId: Number(el.dataset.openUser), returnTo: adminUserView };
      renderAdminUsersSection();
    };
  });
  document.getElementById("broadcast-expired-btn").onclick = async () => {
    const text = document.getElementById("broadcast-expired-text").value.trim();
    if (!text) { notify("متن پیام را وارد کن."); return; }
    if (!confirm("این پیام برای همه‌ی کاربران منقضی‌شده ارسال می‌شود. ادامه؟")) return;
    try {
      const res = await api("/api/admin/users/broadcast-expired", { method: "POST", body: JSON.stringify({ text }) });
      tg.HapticFeedback.notificationOccurred("success");
      notify(`ارسال شد. موفق: ${res.success} از ${res.total}`);
      document.getElementById("broadcast-expired-text").value = "";
    } catch (e) { notify("⚠️ " + e.message); }
  };
}

async function renderAdminUserDetail(body) {
  const { telegramId } = adminUserView;
  const u = await api(`/api/admin/users/${telegramId}`);

  const statusLine = `<span class="badge ${USER_STATUS_BADGE_CLASS[u.status]}">${USER_STATUS_LABEL[u.status]}</span>`;

  const ordersHtml = u.orders.length === 0
    ? `<div class="hint-text" style="margin:0">هیچ سفارشی ثبت نکرده.</div>`
    : u.orders.map((o) => `
      <div class="admin-list-row">
        <div class="admin-list-row-main">
          <span>${escHtml(o.product_name || "نامشخص")} — ${fmt(o.final_price ?? o.base_price ?? 0)} تومان</span>
          <span class="hint-text" style="margin:0">#${o.id} · ${o.created_at ? toJalaliStr(o.created_at, true) : ""}${o.config_link ? " · دارای کانفیگ" : ""}</span>
        </div>
        <div class="admin-list-row-actions">
          <span class="badge ${o.status === "approved" ? "approved" : o.status === "pending" ? "pending" : "rejected"}">${o.status === "approved" ? "تاییدشده" : o.status === "pending" ? "در انتظار" : "ردشده"}</span>
        </div>
      </div>
    `).join("");

  const topupsHtml = u.topups.length === 0
    ? `<div class="hint-text" style="margin:0">هیچ شارژ کیف‌پولی ثبت نکرده.</div>`
    : u.topups.map((t) => `
      <div class="admin-list-row">
        <div class="admin-list-row-main">
          <span>${fmt(t.amount)} تومان</span>
          <span class="hint-text" style="margin:0">${t.created_at ? toJalaliStr(t.created_at, true) : ""}</span>
        </div>
        <div class="admin-list-row-actions">
          <span class="badge ${t.status === "approved" ? "approved" : t.status === "pending" ? "pending" : "rejected"}">${t.status === "approved" ? "تاییدشده" : t.status === "pending" ? "در انتظار" : "ردشده"}</span>
        </div>
      </div>
    `).join("");

  body.innerHTML = `
    <button class="btn outline small" id="back-to-user-list" style="width:auto;margin-bottom:12px">→ بازگشت به لیست کاربران</button>

    <div class="card">
      <div class="eyebrow" style="margin-top:0">${escHtml(u.first_name || "بدون نام")}${u.username ? " (@" + escHtml(u.username) + ")" : ""}</div>
      <div class="stat-row"><span>🆔 آیدی عددی</span><span>${u.telegram_id}</span></div>
      <div class="stat-row"><span>📅 تاریخ عضویت</span><span>${u.joined_at ? toJalaliStr(u.joined_at) : "---"}</span></div>
      <div class="stat-row"><span>👛 موجودی کیف‌پول</span><span>${fmt(u.wallet_credit)} تومان</span></div>
      <div class="stat-row"><span>وضعیت سرویس</span>${statusLine}</div>
      <button class="btn ${u.is_blocked ? "" : "outline"} small" id="toggle-block-btn" style="width:auto;margin-top:10px">
        ${u.is_blocked ? "✅ رفع بلاک کاربر" : "⛔️ بلاک‌کردن کاربر"}
      </button>
    </div>

    <div class="card">
      <div class="eyebrow" style="margin-top:0">✏️ تغییر موجودی کیف‌پول</div>
      <input class="input" id="detail-wallet-amount" type="number" placeholder="مثال: 50000 یا -20000" style="margin-bottom:8px" />
      <button class="btn small" id="detail-wallet-save" style="width:auto">💾 اعمال تغییر</button>
    </div>

    <div class="card">
      <div class="eyebrow" style="margin-top:0">✉️ ارسال پیام مستقیم</div>
      <textarea class="input" id="detail-message-text" rows="2" placeholder="متن پیام..." style="margin-bottom:8px;resize:vertical"></textarea>
      <button class="btn small" id="detail-message-send" style="width:auto">ارسال پیام</button>
    </div>

    <div class="eyebrow">🧾 تاریخچه سفارش‌ها</div>
    <div class="card">${ordersHtml}</div>

    <div class="eyebrow">💳 تاریخچه شارژ کیف‌پول</div>
    <div class="card">${topupsHtml}</div>
  `;

  document.getElementById("back-to-user-list").onclick = () => {
    adminUserView = adminUserView.returnTo || { level: "list", filter: "all", query: "" };
    renderAdminUsersSection();
  };

  document.getElementById("toggle-block-btn").onclick = async () => {
    const willBlock = !u.is_blocked;
    if (willBlock && !confirm("این کاربر بلاک شود؟ دیگر نمی‌تواند از بات یا فروشگاه استفاده کند.")) return;
    try {
      await api(`/api/admin/users/${telegramId}/block`, { method: "POST", body: JSON.stringify({ blocked: willBlock }) });
      tg.HapticFeedback.notificationOccurred("success");
      notify(willBlock ? "کاربر بلاک شد." : "بلاک کاربر برداشته شد.");
      renderAdminUsersSection();
    } catch (e) { notify("⚠️ " + e.message); }
  };

  document.getElementById("detail-wallet-save").onclick = async () => {
    const amountRaw = document.getElementById("detail-wallet-amount").value.trim();
    const amount = Number(amountRaw);
    if (!amountRaw || isNaN(amount) || amount === 0) { notify("مبلغ باید عددی غیرصفر باشد."); return; }
    try {
      const res = await api("/api/admin/wallet/adjust", {
        method: "POST",
        body: JSON.stringify({ telegram_id: telegramId, amount }),
      });
      tg.HapticFeedback.notificationOccurred("success");
      notify(`موجودی به ${fmt(res.new_balance)} تومان تغییر کرد.`);
      renderAdminUsersSection();
    } catch (e) { notify("⚠️ " + e.message); }
  };

  document.getElementById("detail-message-send").onclick = async () => {
    const text = document.getElementById("detail-message-text").value.trim();
    if (!text) { notify("متن پیام را وارد کن."); return; }
    try {
      await api(`/api/admin/users/${telegramId}/message`, { method: "POST", body: JSON.stringify({ text }) });
      tg.HapticFeedback.notificationOccurred("success");
      notify("پیام ارسال شد.");
      document.getElementById("detail-message-text").value = "";
    } catch (e) { notify("⚠️ " + e.message); }
  };
}

// ---------------------------------------------------------------------------
// تب مدیریت > لاگ فعالیت ادمین
// ---------------------------------------------------------------------------

const ADMIN_ACTION_LABELS = {
  wallet_adjust: "✏️ تغییر موجودی کیف‌پول",
  product_price_edit: "💲 ویرایش قیمت محصول",
  order_approve: "✅ تایید سفارش",
  order_reject: "❌ رد سفارش",
  topup_approve: "✅ تایید شارژ کیف‌پول",
  topup_reject: "❌ رد شارژ کیف‌پول",
  admin_add: "➕ افزودن ادمین",
  admin_remove: "➖ حذف ادمین",
  admin_role_change: "🔄 تغییر نقش ادمین",
  card_change: "💳 تغییر شماره کارت",
  backup_create: "🗄 دریافت بکاپ",
  backup_restore: "♻️ بازیابی بکاپ",
  category_add: "📂 افزودن دسته‌بندی",
  category_toggle: "📂 تغییر وضعیت دسته‌بندی",
  category_delete: "🗑 حذف دسته‌بندی",
  product_add: "📦 افزودن محصول",
  product_toggle: "📦 تغییر وضعیت محصول",
  product_delete: "🗑 حذف محصول",
  discount_add: "🎟 افزودن کد تخفیف",
  discount_toggle: "🎟 تغییر وضعیت کد تخفیف",
  discount_delete: "🗑 حذف کد تخفیف",
  broadcast: "📢 ارسال پیام همگانی",
};

let adminLogSelectedId = "";

function _renderAdminLogRows(logs) {
  if (logs.length === 0) return `<div class="hint-text" style="margin:0">هنوز رخدادی برای این ادمین ثبت نشده.</div>`;
  return logs.map((l) => `
    <div class="admin-list-row">
      <div class="admin-list-row-main">
        <span>${ADMIN_ACTION_LABELS[l.action] || l.action}</span>
        <span class="hint-text" style="margin:0">${escHtml(l.details)}</span>
        <span class="hint-text" style="margin:0">👤 ${escHtml(l.admin_name)} (${l.admin_id}) · ${toJalaliStr(l.created_at, true)}</span>
      </div>
    </div>
  `).join("");
}

async function searchAdminLogById() {
  const input = document.getElementById("adminlog-id-input");
  const resultsBox = document.getElementById("adminlog-results");
  const id = (input.value || "").trim();
  if (!id || !/^\d+$/.test(id)) {
    resultsBox.innerHTML = `<div class="hint-text" style="margin:0">لطفاً آیدی عددی ادمین را وارد کن.</div>`;
    return;
  }
  adminLogSelectedId = id;
  resultsBox.innerHTML = skeleton(3);
  try {
    const data = await api(`/api/admin/logs?limit=100&offset=0&admin_id=${id}`);
    resultsBox.innerHTML = `
      <div class="card" style="margin-top:10px">
        ${_renderAdminLogRows(data.logs)}
      </div>
      ${data.total > data.logs.length ? `<p class="hint-text" style="text-align:center">${data.logs.length} از ${data.total} رخداد نمایش داده شد.</p>` : ""}
    `;
  } catch (e) {
    resultsBox.innerHTML = errorState(e.message);
  }
}

async function renderAdminLogSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(4);
  try {
    const adminsData = await api("/api/admin/logs/admins");
    const admins = adminsData.admins || [];
    body.innerHTML = `
      <div class="card">
        <div class="eyebrow" style="margin-top:0">📜 لاگ فعالیت ادمین</div>
        <p class="hint-text">تایید/رد سفارش و شارژ کیف‌پول، تغییر موجودی، مدیریت ادمین‌ها، محصولات، بکاپ و سایر اقدامات هر ادمین اینجا با آیدی عددی همان ادمین ثبت و نمایش داده می‌شود.</p>
        <div style="display:flex;gap:6px;margin-top:8px">
          <input type="text" inputmode="numeric" id="adminlog-id-input" placeholder="آیدی عددی ادمین را وارد کن" value="${escHtml(adminLogSelectedId)}" style="flex:1" />
          <button class="btn small" id="adminlog-search-btn" style="width:auto">جستجو</button>
        </div>
        ${admins.length ? `
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
            ${admins.map((a) => `<button class="btn small outline adminlog-chip" data-admin-id="${a.telegram_id}" style="width:auto">${escHtml(a.name) || a.telegram_id} (${a.telegram_id})</button>`).join("")}
          </div>
        ` : ""}
      </div>
      <div id="adminlog-results">
        ${adminLogSelectedId ? "" : `<div class="card"><div class="hint-text" style="margin:0">برای مشاهده‌ی لاگ، آیدی عددی یک ادمین را وارد کن یا از لیست بالا انتخاب کن.</div></div>`}
      </div>
    `;
    document.getElementById("adminlog-search-btn").addEventListener("click", searchAdminLogById);
    document.getElementById("adminlog-id-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") searchAdminLogById();
    });
    document.querySelectorAll(".adminlog-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.getElementById("adminlog-id-input").value = btn.dataset.adminId;
        searchAdminLogById();
      });
    });
    if (adminLogSelectedId) await searchAdminLogById();
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب مدیریت > بکاپ و بازیابی (فقط مالک اصلی)
// ---------------------------------------------------------------------------

async function downloadAdminBackup() {
  const btn = document.getElementById("admin-backup-create-btn");
  const status = document.getElementById("admin-backup-status");
  if (btn) btn.disabled = true;
  status.innerHTML = `<span class="hint-text">⏳ در حال آماده‌سازی و ارسال بکاپ به چت بات...</span>`;
  try {
    const result = await api("/api/admin/backup/create", { method: "POST" });
    status.innerHTML = `<span class="hint-text">✅ بکاپ (${escHtml(result.filename)}) به چت بات ارسال شد. برای دریافت فایل، چت بات خودت را در تلگرام باز کن.</span>`;
  } catch (e) {
    status.innerHTML = errorState(e.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function uploadAdminRestore(file) {
  const status = document.getElementById("admin-restore-status");
  if (!file) return;
  if (!/\.(db|sqlite|sqlite3)$/i.test(file.name)) {
    status.innerHTML = errorState("فایل باید پسوند .db یا .sqlite داشته باشد.");
    return;
  }
  if (!confirm(
    "⚠️ با این کار کل دیتابیس فعلی با این فایل جایگزین می‌شود.\n" +
    "یک نسخه از وضعیت فعلی هم قبلش ذخیره می‌شود، ولی این عملیات نباید بی‌دقت انجام شود.\n\n" +
    "مطمئنی می‌خواهی ادامه بدهی؟"
  )) return;

  status.innerHTML = `<span class="hint-text">⏳ در حال بازیابی...</span>`;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const result = await apiUpload("/api/admin/backup/restore", formData);
    status.innerHTML = `<span class="hint-text">✅ دیتابیس با موفقیت بازیابی شد. نسخه‌ی قبلی هم به‌عنوان «${escHtml(result.pre_restore_backup)}» کنار دیتابیس ذخیره شد. صفحه را رفرش کن.</span>`;
  } catch (e) {
    status.innerHTML = errorState(e.message);
  }
}

async function renderAdminBackupSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = `
    <div class="card">
      <div class="eyebrow" style="margin-top:0">📥 دریافت بکاپ فوری</div>
      <p class="hint-text">یک نسخه‌ی کامل از دیتابیس فعلی همین الان ساخته و دانلود می‌شود.</p>
      <button class="btn" id="admin-backup-create-btn">📥 دریافت بکاپ فوری</button>
      <div id="admin-backup-status" style="margin-top:10px"></div>
    </div>
    <div class="card">
      <div class="eyebrow" style="margin-top:0">♻️ بازیابی از فایل بکاپ</div>
      <p class="hint-text">⚠️ با آپلود یک فایل بکاپ (.db)، دیتابیس فعلی کامل با آن جایگزین می‌شود. این کار قابل بازگشت نیست مگر با بکاپ دیگری. قبل از جایگزینی، یک نسخه‌ی ایمن از وضعیت فعلی هم خودکار ذخیره می‌شود.</p>
      <input type="file" id="admin-restore-file" accept=".db,.sqlite,.sqlite3" style="margin-bottom:10px" />
      <div id="admin-restore-status"></div>
    </div>
  `;
  document.getElementById("admin-backup-create-btn").onclick = downloadAdminBackup;
  document.getElementById("admin-restore-file").onchange = (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    uploadAdminRestore(file);
  };
}

// ---------------------------------------------------------------------------
// تب مدیریت > فروش (رفرال / گردونه شانس / یادآوری تمدید / کدهای تخفیف)
// ---------------------------------------------------------------------------

async function renderAdminSalesSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(4);
  try {
    const [referral, wheel, renewal, discounts] = await Promise.all([
      api("/api/admin/settings/referral"),
      api("/api/admin/settings/wheel"),
      api("/api/admin/settings/renewal"),
      api("/api/admin/discounts"),
    ]);

    body.innerHTML = `
      <div class="card">
        <div class="eyebrow" style="margin-top:0">🤝 زیرمجموعه‌گیری (رفرال)</div>
        <p class="hint-text">وقتی کاربری با لینک دعوت یکی دیگه وارد بشه و خرید کنه، درصدی از خریدش به‌عنوان اعتبار کیف‌پول به دعوت‌کننده تعلق می‌گیره.</p>
        <div class="field-switch-row">
          <span>سیستم رفرال فعال باشد</span>
          <label class="switch"><input type="checkbox" id="ref-enabled" ${referral.enabled ? "checked" : ""} /><span class="switch-slider"></span></label>
        </div>
        <label class="field-label">درصد پاداش دعوت‌کننده از هر خرید زیرمجموعه (۰ تا ۱۰۰)</label>
        <input class="input" id="ref-percent" type="number" placeholder="مثال: 10" value="${referral.percent}" style="margin-bottom:4px" />
        <div class="field-error" id="ref-error"></div>
        <button class="btn" id="ref-save" style="margin-top:8px">💾 ذخیره</button>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🎡 گردونه شانس</div>
        <p class="hint-text">کاربرها با گردوندن این چرخ، شانس بردن کد تخفیف دارن.</p>
        <div class="field-switch-row">
          <span>گردونه شانس فعال باشد</span>
          <label class="switch"><input type="checkbox" id="wheel-enabled" ${wheel.enabled ? "checked" : ""} /><span class="switch-slider"></span></label>
        </div>
        <label class="field-label">احتمال برد در هر چرخش (درصد از ۰ تا ۱۰۰)</label>
        <input class="input" id="wheel-win-percent" type="number" placeholder="مثال: 30" value="${wheel.win_percent}" style="margin-bottom:10px" />
        <label class="field-label">لیست درصد جوایز، با کاما جدا شود</label>
        <input class="input" id="wheel-prizes" type="text" placeholder="مثال: 10,20,30,50" value="${wheel.prizes.join(",")}" style="margin-bottom:10px" />
        <label class="field-label">مدت اعتبار کد جایزه پس از برد (ساعت)</label>
        <input class="input" id="wheel-expiry" type="number" placeholder="مثال: 24" value="${wheel.expiry_hours}" style="margin-bottom:10px" />
        <label class="field-label">حداقل فاصله‌ی زمانی بین دو چرخش هر کاربر (ساعت)</label>
        <input class="input" id="wheel-cooldown" type="number" placeholder="مثال: 24" value="${wheel.cooldown_hours}" style="margin-bottom:4px" />
        <div class="field-error" id="wheel-error"></div>
        <button class="btn" id="wheel-save" style="margin-top:8px">💾 ذخیره</button>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">⏰ یادآوری تمدید سرویس</div>
        <p class="hint-text">چند روز مانده به اتمام سرویس، به کاربر پیام یادآوری همراه با کد تخفیف تشویقی برای تمدید فرستاده می‌شود.</p>
        <div class="field-switch-row">
          <span>یادآوری تمدید فعال باشد</span>
          <label class="switch"><input type="checkbox" id="ren-enabled" ${renewal.enabled ? "checked" : ""} /><span class="switch-slider"></span></label>
        </div>
        <label class="field-label">چند روز مانده به پایان سرویس، یادآوری ارسال شود</label>
        <input class="input" id="ren-days" type="number" placeholder="مثال: 5" value="${renewal.days_before}" style="margin-bottom:10px" />
        <label class="field-label">درصد تخفیف کد تشویقی تمدید (۰ تا ۱۰۰)</label>
        <input class="input" id="ren-percent" type="number" placeholder="مثال: 20" value="${renewal.discount_percent}" style="margin-bottom:10px" />
        <label class="field-label">مدت اعتبار کد تشویقی (ساعت)</label>
        <input class="input" id="ren-expiry" type="number" placeholder="مثال: 24" value="${renewal.discount_expiry_hours}" style="margin-bottom:4px" />
        <div class="field-error" id="ren-error"></div>
        <button class="btn" id="ren-save" style="margin-top:8px">💾 ذخیره</button>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🏷️ کدهای تخفیف</div>
        <div id="discounts-list">
          ${discounts.length === 0 ? `<div class="hint-text" style="margin:0">هنوز کد تخفیفی ثبت نشده.</div>` : discounts.map((d) => `
            <div class="admin-list-row">
              <div class="admin-list-row-main">
                <span style="direction:ltr">${d.code}</span>
                <span class="hint-text" style="margin:0">
                  ${d.percent ? `${d.percent}٪` : `${fmt(d.fixed_amount)} تومان`} ·
                  استفاده: ${d.used_count}${d.max_uses ? "/" + d.max_uses : " (نامحدود)"}
                  ${d.is_active ? "" : "· غیرفعال"}
                </span>
              </div>
              <div class="admin-list-row-actions">
                <button class="btn small outline" data-toggle-disc="${d.id}">${d.is_active ? "⛔️" : "✅"}</button>
                <button class="btn small outline danger" data-del-disc="${d.id}">🗑️</button>
              </div>
            </div>
          `).join("")}
        </div>
        <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--glass-brd)">
          <div class="eyebrow">افزودن کد تخفیف جدید</div>
          <label class="field-label">کد تخفیف (حروف/عدد انگلیسی، مثال: SUMMER25)</label>
          <input class="input" id="new-disc-code" type="text" placeholder="SUMMER25" style="margin-bottom:10px;direction:ltr;text-align:left" />
          <label class="field-label">درصد تخفیف (اگر می‌خوای درصدی باشه)</label>
          <input class="input" id="new-disc-percent" type="number" placeholder="مثال: 25" style="margin-bottom:10px" />
          <label class="field-label">یا مبلغ ثابت تخفیف به تومان (فقط یکی از این دو را پر کن)</label>
          <input class="input" id="new-disc-fixed" type="number" placeholder="مثال: 50000" style="margin-bottom:10px" />
          <label class="field-label">حداکثر تعداد دفعات استفاده (۰ یعنی نامحدود)</label>
          <input class="input" id="new-disc-maxuses" type="number" placeholder="0" value="0" style="margin-bottom:4px" />
          <div class="field-error" id="new-disc-error"></div>
          <button class="btn" id="new-disc-save" style="margin-top:8px">➕ افزودن کد تخفیف</button>
        </div>
      </div>
    `;

    document.getElementById("ref-save").onclick = async () => {
      const errBox = document.getElementById("ref-error");
      errBox.textContent = "";
      const percentRaw = document.getElementById("ref-percent").value.trim();
      if (percentRaw === "") { errBox.textContent = "درصد پاداش را وارد کن."; return; }
      const percent = Number(percentRaw);
      if (isNaN(percent) || percent < 0 || percent > 100) { errBox.textContent = "درصد باید عددی بین ۰ تا ۱۰۰ باشد."; return; }
      try {
        await api("/api/admin/settings/referral", {
          method: "POST",
          body: JSON.stringify({ enabled: document.getElementById("ref-enabled").checked, percent }),
        });
        tg.HapticFeedback.notificationOccurred("success");
        notify("تنظیمات رفرال ذخیره شد.");
      } catch (e) { errBox.textContent = e.message; }
    };

    document.getElementById("wheel-save").onclick = async () => {
      const errBox = document.getElementById("wheel-error");
      errBox.textContent = "";
      const winRaw = document.getElementById("wheel-win-percent").value.trim();
      const prizesRaw = document.getElementById("wheel-prizes").value.trim();
      const expiryRaw = document.getElementById("wheel-expiry").value.trim();
      const cooldownRaw = document.getElementById("wheel-cooldown").value.trim();
      if (!winRaw || !prizesRaw || !expiryRaw || !cooldownRaw) { errBox.textContent = "همه‌ی کادرها باید پر شوند."; return; }
      const winPercent = Number(winRaw);
      const prizes = prizesRaw.split(",").map((p) => Number(p.trim())).filter((p) => p > 0);
      const expiry = Number(expiryRaw);
      const cooldown = Number(cooldownRaw);
      if (isNaN(winPercent) || winPercent < 0 || winPercent > 100) { errBox.textContent = "احتمال برد باید عددی بین ۰ تا ۱۰۰ باشد."; return; }
      if (prizes.length === 0) { errBox.textContent = "حداقل یک جایزه‌ی معتبر وارد کن."; return; }
      if (isNaN(expiry) || expiry <= 0) { errBox.textContent = "اعتبار کد جایزه باید عددی بزرگ‌تر از صفر باشد."; return; }
      if (isNaN(cooldown) || cooldown <= 0) { errBox.textContent = "فاصله‌ی بین چرخش‌ها باید عددی بزرگ‌تر از صفر باشد."; return; }
      try {
        await api("/api/admin/settings/wheel", {
          method: "POST",
          body: JSON.stringify({
            enabled: document.getElementById("wheel-enabled").checked,
            win_percent: winPercent, prizes, expiry_hours: expiry, cooldown_hours: cooldown,
          }),
        });
        tg.HapticFeedback.notificationOccurred("success");
        notify("تنظیمات گردونه شانس ذخیره شد.");
      } catch (e) { errBox.textContent = e.message; }
    };

    document.getElementById("ren-save").onclick = async () => {
      const errBox = document.getElementById("ren-error");
      errBox.textContent = "";
      const daysRaw = document.getElementById("ren-days").value.trim();
      const percentRaw = document.getElementById("ren-percent").value.trim();
      const expiryRaw = document.getElementById("ren-expiry").value.trim();
      if (!daysRaw || !percentRaw || !expiryRaw) { errBox.textContent = "همه‌ی کادرها باید پر شوند."; return; }
      const days = Number(daysRaw), percent = Number(percentRaw), expiry = Number(expiryRaw);
      if (isNaN(days) || days <= 0) { errBox.textContent = "تعداد روز باید عددی بزرگ‌تر از صفر باشد."; return; }
      if (isNaN(percent) || percent < 0 || percent > 100) { errBox.textContent = "درصد تخفیف باید عددی بین ۰ تا ۱۰۰ باشد."; return; }
      if (isNaN(expiry) || expiry <= 0) { errBox.textContent = "اعتبار کد باید عددی بزرگ‌تر از صفر باشد."; return; }
      try {
        await api("/api/admin/settings/renewal", {
          method: "POST",
          body: JSON.stringify({
            enabled: document.getElementById("ren-enabled").checked,
            days_before: days, discount_percent: percent, discount_expiry_hours: expiry,
          }),
        });
        tg.HapticFeedback.notificationOccurred("success");
        notify("تنظیمات یادآوری تمدید ذخیره شد.");
      } catch (e) { errBox.textContent = e.message; }
    };

    body.querySelectorAll("[data-toggle-disc]").forEach((el) => {
      el.onclick = async () => {
        try {
          await api(`/api/admin/discounts/${el.dataset.toggleDisc}/toggle`, { method: "POST" });
          renderAdminSalesSection();
        } catch (e) { notify(e.message); }
      };
    });
    body.querySelectorAll("[data-del-disc]").forEach((el) => {
      el.onclick = async () => {
        if (!confirm("این کد تخفیف حذف شود؟")) return;
        try {
          await api(`/api/admin/discounts/${el.dataset.delDisc}`, { method: "DELETE" });
          renderAdminSalesSection();
        } catch (e) { notify(e.message); }
      };
    });
    document.getElementById("new-disc-save").onclick = async () => {
      const errBox = document.getElementById("new-disc-error");
      errBox.textContent = "";
      const code = document.getElementById("new-disc-code").value.trim();
      const percentVal = document.getElementById("new-disc-percent").value.trim();
      const fixedVal = document.getElementById("new-disc-fixed").value.trim();
      const maxUses = Number(document.getElementById("new-disc-maxuses").value) || 0;
      if (!code) { errBox.textContent = "کد تخفیف را وارد کن."; return; }
      if (!percentVal && !fixedVal) { errBox.textContent = "باید یکی از دو کادر درصد یا مبلغ ثابت را پر کنی."; return; }
      if (percentVal && fixedVal) { errBox.textContent = "فقط یکی از دو کادر درصد یا مبلغ ثابت را پر کن، نه هردو."; return; }
      try {
        await api("/api/admin/discounts", {
          method: "POST",
          body: JSON.stringify({
            code, percent: percentVal ? Number(percentVal) : null,
            fixed_amount: fixedVal ? Number(fixedVal) : null, max_uses: maxUses,
          }),
        });
        tg.HapticFeedback.notificationOccurred("success");
        renderAdminSalesSection();
      } catch (e) { errBox.textContent = e.message; }
    };
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

// ---------------------------------------------------------------------------
// تب مدیریت > تیکت‌ها
// ---------------------------------------------------------------------------

async function renderAdminTicketsSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(3);
  try {
    if (adminTicketView.level === "list") await renderAdminTicketsList(body);
    else await renderAdminTicketThread(body);
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}

async function renderAdminTicketsList(body) {
  const tickets = await api("/api/admin/tickets");
  body.innerHTML = `
    <div class="card">
      ${tickets.length === 0 ? `<div class="hint-text" style="margin:0">هیچ تیکتی ثبت نشده.</div>` : tickets.map((t) => `
        <div class="admin-list-row" data-open-admin-ticket="${t.id}" style="cursor:pointer">
          <div class="admin-list-row-main">
            <span>${t.subject}</span>
            <span class="hint-text" style="margin:0">${t.user_name || "کاربر"} (@${t.user_username || "---"}) · ${TICKET_STATUS_LABEL[t.status] || t.status}</span>
          </div>
        </div>
      `).join("")}
    </div>
  `;
  body.querySelectorAll("[data-open-admin-ticket]").forEach((el) => {
    el.onclick = () => {
      adminTicketView = { level: "thread", ticketId: Number(el.dataset.openAdminTicket) };
      renderAdminTicketsSection();
    };
  });
}

async function renderAdminTicketThread(body) {
  const { ticketId } = adminTicketView;
  const data = await api(`/api/admin/tickets/${ticketId}/messages`);
  const { ticket, messages } = data;
  const closed = ticket.status === "closed";
  body.innerHTML = `
    <button class="btn outline small" id="back-to-admin-tickets" style="width:auto;margin-bottom:12px">→ بازگشت به لیست تیکت‌ها</button>
    <div class="eyebrow" style="margin-top:0">${ticket.subject}</div>
    <p class="hint-text">${ticket.user_name || "کاربر"} (@${ticket.user_username || "---"}) · شناسه: ${ticket.user_id} · ${TICKET_STATUS_LABEL[ticket.status] || ""}</p>
    <div class="chat-wrap">
      <div class="chat-messages" id="admin-ticket-messages"></div>
      ${closed
        ? `<p class="hint-text" style="text-align:center">این تیکت بسته شده است.</p>`
        : `<form class="chat-input-row" id="admin-ticket-form">
            <input type="text" id="admin-ticket-input" placeholder="پاسخ خود را بنویسید..." autocomplete="off" />
            <button type="submit" class="chat-send-btn" aria-label="ارسال">
              <svg viewBox="0 0 24 24" fill="none"><path d="M4 12 20 4l-6 16-3-7-7-1Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
            </button>
          </form>
          <button class="btn outline small" id="admin-close-ticket-btn" style="width:auto;margin-top:8px">بستن این تیکت</button>`}
    </div>
  `;
  document.getElementById("back-to-admin-tickets").onclick = () => {
    adminTicketView = { level: "list" };
    renderAdminTicketsSection();
  };
  const box = document.getElementById("admin-ticket-messages");
  if (messages.length === 0) {
    box.innerHTML = `<div class="state-msg"><span class="ic">🎫</span>پیامی هنوز ثبت نشده.</div>`;
  }
  messages.forEach((m) => {
    if (box.querySelector(".state-msg")) box.innerHTML = "";
    const time = new Date(m.created_at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${m.sender === "admin" ? "mine" : "admin"}`;
    bubble.innerHTML = `<div class="chat-text"></div><div class="chat-time">${time}</div>`;
    bubble.querySelector(".chat-text").textContent = m.message;
    box.appendChild(bubble);
  });
  box.scrollTop = box.scrollHeight;

  if (!closed) {
    const form = document.getElementById("admin-ticket-form");
    const input = document.getElementById("admin-ticket-input");
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
        await api(`/api/admin/tickets/${ticketId}/messages`, { method: "POST", body: JSON.stringify({ message: text }) });
      } catch (e2) {
        notify("خطا: " + e2.message);
      }
    };
    document.getElementById("admin-close-ticket-btn").onclick = async () => {
      if (!confirm("این تیکت بسته شود؟")) return;
      try {
        await api(`/api/admin/tickets/${ticketId}/close`, { method: "POST" });
        renderAdminTicketsSection();
      } catch (e) { notify(e.message); }
    };
  }
}

// ---------------------------------------------------------------------------
// تب مدیریت > نمایندگی‌ها (فقط بات اصلی)
// ---------------------------------------------------------------------------

async function renderAdminResellersSection() {
  const body = document.getElementById("admin-section-body");
  body.innerHTML = skeleton(3);
  try {
    const resellers = await api("/api/admin/resellers");
    body.innerHTML = `
      <p class="hint-text">تغییرات فعال/غیرفعال‌کردن یا حذف، حداکثر تا ۱۰ ثانیه دیگر روی بات واقعی اعمال می‌شود.</p>
      <div class="card">
        ${resellers.length === 0 ? `<div class="hint-text" style="margin:0">هنوز نماینده‌ای ثبت نشده.</div>` : resellers.map((r) => `
          <div class="admin-list-row">
            <div class="admin-list-row-main">
              <span>@${r.bot_username}</span>
              <span class="hint-text" style="margin:0">${r.owner_name || "بدون نام"} · شناسه: ${r.owner_telegram_id} ${r.is_active ? "" : "· غیرفعال"}</span>
            </div>
            <div class="admin-list-row-actions">
              <button class="btn small outline" data-edit-res="${r.id}">✏️</button>
              <button class="btn small outline" data-toggle-res="${r.id}">${r.is_active ? "⛔️" : "✅"}</button>
              <button class="btn small outline danger" data-del-res="${r.id}">🗑️</button>
            </div>
          </div>
        `).join("")}
      </div>
      <div class="card">
        <div class="eyebrow" style="margin-top:0">افزودن نماینده‌ی جدید</div>
        <input class="input" id="new-res-token" type="text" placeholder="توکن بات (از BotFather)" style="margin-bottom:8px" />
        <button class="btn outline" id="new-res-validate">🔎 بررسی توکن</button>
        <div id="new-res-step2" style="display:none;margin-top:10px">
          <p class="hint-text" id="new-res-username-line"></p>
          <input class="input" id="new-res-owner-id" type="number" placeholder="آیدی عددی نماینده" style="margin-bottom:8px" />
          <input class="input" id="new-res-owner-name" type="text" placeholder="نام نماینده (برای نمایش)" style="direction:rtl;text-align:right;font-family:var(--font-body);margin-bottom:8px" />
          <button class="btn" id="new-res-save">➕ افزودن نماینده</button>
        </div>
      </div>
    `;
    body.querySelectorAll("[data-edit-res]").forEach((el) => {
      el.onclick = async () => {
        const r = resellers.find((x) => x.id === Number(el.dataset.editRes));
        const ownerId = prompt("آیدی عددی نماینده:", r.owner_telegram_id);
        if (ownerId === null || !ownerId.trim()) return;
        const ownerName = prompt("نام نماینده:", r.owner_name || "");
        if (ownerName === null) return;
        try {
          await api(`/api/admin/resellers/${r.id}`, {
            method: "PATCH",
            body: JSON.stringify({ owner_telegram_id: Number(ownerId), owner_name: ownerName.trim() }),
          });
          renderAdmin();
        } catch (e) { notify(e.message); }
      };
    });
    body.querySelectorAll("[data-toggle-res]").forEach((el) => {
      el.onclick = async () => {
        try {
          const res = await api(`/api/admin/resellers/${el.dataset.toggleRes}/toggle`, { method: "POST" });
          notify(res.note || "وضعیت تغییر کرد.");
          renderAdmin();
        } catch (e) { notify(e.message); }
      };
    });
    body.querySelectorAll("[data-del-res]").forEach((el) => {
      el.onclick = async () => {
        const purge = confirm("همراه با حذف نماینده، فایل دیتابیسش هم برای همیشه پاک شود؟\n(تایید = بله پاک شود / لغو = فقط حذف از لیست، فایل نگه داشته شود)");
        try {
          const res = await api(`/api/admin/resellers/${el.dataset.delRes}?purge_db=${purge}`, { method: "DELETE" });
          notify((res.db_purged ? "نماینده حذف و دیتابیسش پاک شد. " : "نماینده حذف شد (دیتابیس نگه داشته شد). ") + (res.note || ""));
          renderAdmin();
        } catch (e) { notify(e.message); }
      };
    });
    document.getElementById("new-res-validate").onclick = async () => {
      const token = document.getElementById("new-res-token").value.trim();
      if (!token) { notify("توکن را وارد کن."); return; }
      try {
        const res = await api("/api/admin/resellers/validate", { method: "POST", body: JSON.stringify({ token }) });
        document.getElementById("new-res-step2").style.display = "";
        document.getElementById("new-res-username-line").textContent = `✅ توکن معتبر است: @${res.username}`;
        document.getElementById("new-res-save").onclick = async () => {
          const ownerId = Number(document.getElementById("new-res-owner-id").value);
          const ownerName = document.getElementById("new-res-owner-name").value.trim();
          if (!ownerId) { notify("آیدی عددی نماینده الزامی است."); return; }
          try {
            const createRes = await api("/api/admin/resellers", {
              method: "POST",
              body: JSON.stringify({ token, username: res.username, owner_telegram_id: ownerId, owner_name: ownerName }),
            });
            tg.HapticFeedback.notificationOccurred("success");
            notify(createRes.note || "نماینده اضافه شد.");
            renderAdmin();
          } catch (e) { notify(e.message); }
        };
      } catch (e) { notify(e.message); }
    };
  } catch (e) {
    body.innerHTML = errorState(e.message);
  }
}


const tabs = {
  home: renderHome,
  store: renderStore,
  test: renderTestConfig,
  wheel: renderWheel,
  referral: renderReferral,
  support: renderSupport,
  wallet: renderWallet,
  admin: renderAdmin,
};

function switchTab(name) {
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  if (name !== "support") clearInterval(supportPollTimer);
  content.classList.remove("fade-in");
  void content.offsetWidth; // ری‌استارت انیمیشن
  tabs[name]();
  content.classList.add("fade-in");
}

document.querySelectorAll("#tabbar button").forEach((b) => b.onclick = () => switchTab(b.dataset.tab));

switchTab("home");

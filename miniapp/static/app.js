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
  const exp = o.expires_at ? o.expires_at.slice(0, 10) : "نامحدود";
  return `
    <div class="order-block">
      <div class="stat-row"><span>${o.product_name}</span><span class="badge approved">فعال تا ${exp}</span></div>
      ${o.link ? `
      <div class="link-box">${o.link}</div>
      <div class="qr-row">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(o.link)}" width="96" height="96" alt="QR" />
        <button class="btn small outline" onclick="navigator.clipboard.writeText('${o.link}');tg.HapticFeedback.notificationOccurred('success')">📋 کپی لینک</button>
      </div>` : ""}
    </div>
  `;
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

let adminSection = "menu"; // menu | catalog | tickets | sales | resellers
let adminCatalogView = { level: "categories" }; // categories | products | configs
let adminTicketView = { level: "list" }; // list | thread

async function renderAdmin() {
  const isMainBot = !TENANT_ID;
  content.innerHTML = `
    <div class="segmented" id="admin-section-tabs">
      <button class="seg-btn ${adminSection === "menu" ? "active" : ""}" data-section="menu">چیدمان منو</button>
      <button class="seg-btn ${adminSection === "catalog" ? "active" : ""}" data-section="catalog">محصولات</button>
      <button class="seg-btn ${adminSection === "sales" ? "active" : ""}" data-section="sales">فروش</button>
      <button class="seg-btn ${adminSection === "tickets" ? "active" : ""}" data-section="tickets">تیکت‌ها</button>
      ${isMainBot ? `<button class="seg-btn ${adminSection === "resellers" ? "active" : ""}" data-section="resellers">نمایندگی‌ها</button>` : ""}
    </div>
    <div id="admin-section-body">${skeleton(4)}</div>
  `;
  document.querySelectorAll("#admin-section-tabs .seg-btn").forEach((b) => {
    b.onclick = () => {
      adminSection = b.dataset.section;
      if (adminSection === "catalog") adminCatalogView = { level: "categories" };
      if (adminSection === "tickets") adminTicketView = { level: "list" };
      renderAdmin();
    };
  });
  if (adminSection === "menu") await renderAdminMenuSection();
  else if (adminSection === "catalog") await renderAdminCatalogSection();
  else if (adminSection === "sales") await renderAdminSalesSection();
  else if (adminSection === "tickets") await renderAdminTicketsSection();
  else if (adminSection === "resellers" && isMainBot) await renderAdminResellersSection();
}

async function renderAdminMenuSection() {
  const body = document.getElementById("admin-section-body");
  try {
    adminMenuItems = await api("/api/admin/menu");
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
    <p class="hint-text">موجودی فعلی: ${configs.length} کانفیگ استفاده‌نشده</p>
    <div class="card">
      ${configs.length === 0 ? `<div class="hint-text" style="margin:0">کانفیگی در انبار نیست.</div>` : configs.map((c) => `
        <div class="admin-list-row">
          <div class="admin-list-row-main" style="direction:ltr;text-align:left;font-family:var(--font-mono);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${c.link}</div>
          <div class="admin-list-row-actions">
            <button class="btn small outline danger" data-del-cfg="${c.id}">🗑️</button>
          </div>
        </div>
      `).join("")}
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
        <label class="menu-toggle" style="margin-bottom:10px">
          <input type="checkbox" id="ref-enabled" ${referral.enabled ? "checked" : ""} /><span>فعال باشد</span>
        </label>
        <input class="input" id="ref-percent" type="number" placeholder="درصد پاداش دعوت‌کننده" value="${referral.percent}" style="margin-bottom:8px" />
        <button class="btn" id="ref-save">💾 ذخیره</button>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">🎡 گردونه شانس</div>
        <label class="menu-toggle" style="margin-bottom:10px">
          <input type="checkbox" id="wheel-enabled" ${wheel.enabled ? "checked" : ""} /><span>فعال باشد</span>
        </label>
        <input class="input" id="wheel-win-percent" type="number" placeholder="احتمال برد (٪)" value="${wheel.win_percent}" style="margin-bottom:8px" />
        <input class="input" id="wheel-prizes" type="text" placeholder="جوایز با کاما (مثال: 10,20,30,50)" value="${wheel.prizes.join(",")}" style="margin-bottom:8px" />
        <input class="input" id="wheel-expiry" type="number" placeholder="اعتبار کد جایزه (ساعت)" value="${wheel.expiry_hours}" style="margin-bottom:8px" />
        <input class="input" id="wheel-cooldown" type="number" placeholder="فاصله بین دو چرخش (ساعت)" value="${wheel.cooldown_hours}" style="margin-bottom:8px" />
        <button class="btn" id="wheel-save">💾 ذخیره</button>
      </div>

      <div class="card">
        <div class="eyebrow" style="margin-top:0">⏰ یادآوری تمدید سرویس</div>
        <label class="menu-toggle" style="margin-bottom:10px">
          <input type="checkbox" id="ren-enabled" ${renewal.enabled ? "checked" : ""} /><span>فعال باشد</span>
        </label>
        <input class="input" id="ren-days" type="number" placeholder="چند روز قبل از اتمام یادآوری شود" value="${renewal.days_before}" style="margin-bottom:8px" />
        <input class="input" id="ren-percent" type="number" placeholder="درصد تخفیف کد تشویقی" value="${renewal.discount_percent}" style="margin-bottom:8px" />
        <input class="input" id="ren-expiry" type="number" placeholder="اعتبار کد تشویقی (ساعت)" value="${renewal.discount_expiry_hours}" style="margin-bottom:8px" />
        <button class="btn" id="ren-save">💾 ذخیره</button>
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
        <div style="margin-top:12px">
          <input class="input" id="new-disc-code" type="text" placeholder="کد تخفیف (مثال: SUMMER25)" style="margin-bottom:8px;direction:ltr;text-align:left" />
          <input class="input" id="new-disc-percent" type="number" placeholder="درصد تخفیف (یا مبلغ ثابت را پر کن)" style="margin-bottom:8px" />
          <input class="input" id="new-disc-fixed" type="number" placeholder="مبلغ ثابت تخفیف - تومان (اختیاری)" style="margin-bottom:8px" />
          <input class="input" id="new-disc-maxuses" type="number" placeholder="حداکثر تعداد استفاده (۰ = نامحدود)" value="0" style="margin-bottom:8px" />
          <button class="btn" id="new-disc-save">➕ افزودن کد تخفیف</button>
        </div>
      </div>
    `;

    document.getElementById("ref-save").onclick = async () => {
      try {
        await api("/api/admin/settings/referral", {
          method: "POST",
          body: JSON.stringify({
            enabled: document.getElementById("ref-enabled").checked,
            percent: Number(document.getElementById("ref-percent").value),
          }),
        });
        notify("تنظیمات رفرال ذخیره شد.");
      } catch (e) { notify(e.message); }
    };

    document.getElementById("wheel-save").onclick = async () => {
      const prizes = document.getElementById("wheel-prizes").value.split(",").map((p) => Number(p.trim())).filter((p) => p > 0);
      try {
        await api("/api/admin/settings/wheel", {
          method: "POST",
          body: JSON.stringify({
            enabled: document.getElementById("wheel-enabled").checked,
            win_percent: Number(document.getElementById("wheel-win-percent").value),
            prizes,
            expiry_hours: Number(document.getElementById("wheel-expiry").value),
            cooldown_hours: Number(document.getElementById("wheel-cooldown").value),
          }),
        });
        notify("تنظیمات گردونه شانس ذخیره شد.");
      } catch (e) { notify(e.message); }
    };

    document.getElementById("ren-save").onclick = async () => {
      try {
        await api("/api/admin/settings/renewal", {
          method: "POST",
          body: JSON.stringify({
            enabled: document.getElementById("ren-enabled").checked,
            days_before: Number(document.getElementById("ren-days").value),
            discount_percent: Number(document.getElementById("ren-percent").value),
            discount_expiry_hours: Number(document.getElementById("ren-expiry").value),
          }),
        });
        notify("تنظیمات یادآوری تمدید ذخیره شد.");
      } catch (e) { notify(e.message); }
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
      const code = document.getElementById("new-disc-code").value.trim();
      const percentVal = document.getElementById("new-disc-percent").value;
      const fixedVal = document.getElementById("new-disc-fixed").value;
      const maxUses = Number(document.getElementById("new-disc-maxuses").value) || 0;
      if (!code) { notify("کد تخفیف را وارد کن."); return; }
      if (!percentVal && !fixedVal) { notify("درصد یا مبلغ ثابت را وارد کن."); return; }
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
      } catch (e) { notify(e.message); }
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

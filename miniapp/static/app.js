const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
try { tg.setHeaderColor("#0a0e17"); tg.setBackgroundColor("#0a0e17"); } catch (e) {}

const initData = tg.initData; // برای هدر X-Init-Data به بک‌اند فرستاده می‌شود
const content = document.getElementById("content");
const greeting = document.getElementById("greeting");

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
    throw new Error(err.detail || "خطای ناشناخته");
  }
  return res.json();
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

function skeleton(rows = 3) {
  return `<div class="skeleton-block">${'<div class="skel"></div>'.repeat(rows)}</div>`;
}

function errorState(message) {
  return `<div class="state-msg error"><span class="ic">⚠</span>${message}</div>`;
}

// ---------------------------------------------------------------------------
// تب خانه
// ---------------------------------------------------------------------------
async function renderHome() {
  content.innerHTML = skeleton(3);
  try {
    const me = await api("/api/me");
    greeting.textContent = `سلام ${me.first_name} 👋`;
    const orders = await api("/api/orders");
    const active = orders.filter((o) => o.status === "approved");

    content.innerHTML = `
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
    box.querySelector("#receipt-label").textContent = file.name;
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
// تب‌ها
// ---------------------------------------------------------------------------
const tabs = { home: renderHome, store: renderStore, wheel: renderWheel, wallet: renderWallet };

function switchTab(name) {
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  tabs[name]();
}

document.querySelectorAll("#tabbar button").forEach((b) => b.onclick = () => switchTab(b.dataset.tab));

switchTab("home");

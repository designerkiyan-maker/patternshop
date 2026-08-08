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

function fmt(n) {
  return Number(n).toLocaleString("fa-IR");
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
      notify(`مبلغ باقی‌مانده: ${fmt(result.final_price)} تومان.\nبرای پرداخت به بات مراجعه کنید و رسید بفرستید.`);
    }
  } catch (e) {
    notify("خطا: " + e.message);
  }
}

// ---------------------------------------------------------------------------
// تب گردونه (با انیمیشن واقعی چرخش روی canvas)
// ---------------------------------------------------------------------------
async function renderWheel() {
  content.innerHTML = skeleton(1);
  try {
    const status = await api("/api/wheel");
    currentPrizes = status.prizes || [];
    if (!status.enabled) {
      content.innerHTML = `<div class="state-msg"><span class="ic">◌</span>گردونه شانس غیرفعال است.</div>`;
      return;
    }
    content.innerHTML = `
      <div class="card" style="text-align:center">
        <div class="wheel-frame"><canvas id="wheel-canvas" width="260" height="260"></canvas></div>
        <button class="btn violet" id="spin-btn" ${status.can_spin ? "" : "disabled"}>
          ${status.can_spin ? "🎡 بچرخان!" : `⏳ ${status.remaining_hours} ساعت دیگر`}
        </button>
      </div>
    `;
    drawWheel(status.prizes);
    if (status.can_spin) {
      document.getElementById("spin-btn").onclick = spinWheel;
    }
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
}
let currentPrizes = [];

function drawWheel(prizes, rotation = 0) {
  const canvas = document.getElementById("wheel-canvas");
  const ctx = canvas.getContext("2d");
  const cx = 130, cy = 130, r = 120;
  const colors = ["#22e6c5", "#8b7fff", "#fbbf24", "#fb7185", "#34d399", "#4ea1ff"];
  const n = prizes.length || 1;
  ctx.clearRect(0, 0, 260, 260);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rotation);
  for (let i = 0; i < n; i++) {
    const a0 = (i / n) * 2 * Math.PI;
    const a1 = ((i + 1) / n) * 2 * Math.PI;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, r, a0, a1);
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
    ctx.strokeStyle = "#0a0e17";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.save();
    ctx.rotate((a0 + a1) / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#04211c";
    ctx.font = "bold 16px 'JetBrains Mono', sans-serif";
    ctx.fillText(`${prizes[i]}%`, r - 15, 5);
    ctx.restore();
  }
  ctx.restore();
  // مرکز
  ctx.beginPath();
  ctx.arc(cx, cy, 10, 0, 2 * Math.PI);
  ctx.fillStyle = "#0a0e17";
  ctx.fill();
  // فلش نشانگر
  ctx.beginPath();
  ctx.moveTo(cx - 10, 5);
  ctx.lineTo(cx + 10, 5);
  ctx.lineTo(cx, 25);
  ctx.fillStyle = "#edf1f9";
  ctx.fill();
}

async function spinWheel() {
  const btn = document.getElementById("spin-btn");
  btn.disabled = true;
  let rotation = 0;
  const spinInterval = setInterval(() => {
    rotation += 0.35;
    drawWheel(currentPrizes, rotation);
  }, 16);

  try {
    const result = await api("/api/wheel/spin", { method: "POST" });
    setTimeout(() => {
      clearInterval(spinInterval);
      tg.HapticFeedback.notificationOccurred(result.won ? "success" : "error");
      if (result.won) {
        notify(`🎉 تبریک! کد تخفیف ${result.percent}٪ شما:\n${result.code}\n(اعتبار محدود دارد)`);
      } else {
        notify("😔 امروز شانس نبود، فردا دوباره امتحان کن!");
      }
      renderWheel();
    }, 2500);
  } catch (e) {
    clearInterval(spinInterval);
    notify("خطا: " + e.message);
    btn.disabled = false;
  }
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
      <div class="card">
        <h3><span class="ic">＋</span>شارژ کیف پول</h3>
        <input id="topup-amount" class="input" type="number" placeholder="مبلغ به تومان" />
        <button class="btn" id="topup-btn">ثبت درخواست شارژ</button>
      </div>
    `;
    document.getElementById("topup-btn").onclick = async () => {
      const amount = parseInt(document.getElementById("topup-amount").value, 10);
      if (!amount || amount < 1000) return notify("حداقل مبلغ ۱۰۰۰ تومان است.");
      try {
        const r = await api("/api/wallet/topup-request", { method: "POST", body: JSON.stringify({ amount }) });
        notify(`مبلغ را به کارت زیر واریز کنید و رسید را در خود بات (نه اینجا) بفرستید:\n\n${r.card_number}\n${r.card_holder}`);
      } catch (e) {
        notify("خطا: " + e.message);
      }
    };
  } catch (e) {
    content.innerHTML = errorState(e.message);
  }
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

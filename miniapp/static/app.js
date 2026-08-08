const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData; // برای هدر X-Init-Data به بک‌اند فرستاده می‌شود
const content = document.getElementById("content");
const greeting = document.getElementById("greeting");

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

// ---------------------------------------------------------------------------
// تب خانه
// ---------------------------------------------------------------------------
async function renderHome() {
  content.innerHTML = "<p>در حال بارگذاری...</p>";
  try {
    const me = await api("/api/me");
    greeting.textContent = `سلام ${me.first_name} 👋`;
    const orders = await api("/api/orders");
    const active = orders.filter((o) => o.status === "approved");

    content.innerHTML = `
      <div class="card">
        <h3>وضعیت حساب</h3>
        <div class="stat-row"><span>👛 موجودی کیف پول</span><b>${fmt(me.wallet_credit)} تومان</b></div>
        <div class="stat-row"><span>👥 زیرمجموعه‌ها</span><b>${fmt(me.referral_count)}</b></div>
        <div class="stat-row"><span>📦 تعداد سفارش</span><b>${fmt(me.orders_count)}</b></div>
      </div>
      <div class="card">
        <h3>سرویس‌های فعال</h3>
        ${active.length === 0 ? "<p>سرویس فعالی ندارید.</p>" : active.map(orderCard).join("")}
      </div>
    `;
  } catch (e) {
    content.innerHTML = `<p>خطا: ${e.message}</p>`;
  }
}

function orderCard(o) {
  const exp = o.expires_at ? o.expires_at.slice(0, 10) : "نامحدود";
  return `
    <div style="margin-bottom:14px">
      <div class="stat-row"><span>${o.product_name}</span><span class="badge approved">فعال تا ${exp}</span></div>
      ${o.link ? `<div class="link-box">${o.link}</div>
      <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(o.link)}" width="120" />
      <button class="btn" onclick="navigator.clipboard.writeText('${o.link}');tg.HapticFeedback.notificationOccurred('success')">📋 کپی لینک</button>` : ""}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// تب فروشگاه
// ---------------------------------------------------------------------------
async function renderStore() {
  content.innerHTML = "<p>در حال بارگذاری...</p>";
  try {
    const categories = await api("/api/catalog");
    content.innerHTML = categories.map((c) => `
      <div class="card">
        <h3>📁 ${c.name}</h3>
        ${c.products.map((p) => `
          <div class="product">
            <div>
              <div>${p.name}</div>
              <div class="price">${fmt(p.price)} تومان</div>
            </div>
            <button class="btn" style="width:auto" ${p.stock <= 0 ? "disabled" : ""}
              onclick="buyProduct(${p.id}, ${p.price})">
              ${p.stock <= 0 ? "ناموجود" : "خرید"}
            </button>
          </div>
        `).join("")}
      </div>
    `).join("");
  } catch (e) {
    content.innerHTML = `<p>خطا: ${e.message}</p>`;
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
      alert("✅ خرید تایید شد! از تب خانه لینک را ببینید.");
      switchTab("home");
    } else {
      alert(`مبلغ باقی‌مانده: ${fmt(result.final_price)} تومان.\nبرای پرداخت به بات مراجعه کنید و رسید بفرستید.`);
    }
  } catch (e) {
    alert("خطا: " + e.message);
  }
}

// ---------------------------------------------------------------------------
// تب گردونه (با انیمیشن واقعی چرخش روی canvas)
// ---------------------------------------------------------------------------
async function renderWheel() {
  content.innerHTML = "<p>در حال بارگذاری...</p>";
  try {
    const status = await api("/api/wheel");
    currentPrizes = status.prizes || [];
    if (!status.enabled) {
      content.innerHTML = "<p>گردونه شانس غیرفعال است.</p>";
      return;
    }
    content.innerHTML = `
      <div class="card" style="text-align:center">
        <canvas id="wheel-canvas" width="260" height="260"></canvas>
        <button class="btn" id="spin-btn" ${status.can_spin ? "" : "disabled"}>
          ${status.can_spin ? "🎡 بچرخان!" : `⏳ ${status.remaining_hours} ساعت دیگر`}
        </button>
      </div>
    `;
    drawWheel(status.prizes);
    if (status.can_spin) {
      document.getElementById("spin-btn").onclick = spinWheel;
    }
  } catch (e) {
    content.innerHTML = `<p>خطا: ${e.message}</p>`;
  }
}
let currentPrizes = [];

function drawWheel(prizes, rotation = 0) {
  const canvas = document.getElementById("wheel-canvas");
  const ctx = canvas.getContext("2d");
  const cx = 130, cy = 130, r = 120;
  const colors = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c"];
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
    ctx.save();
    ctx.rotate((a0 + a1) / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#fff";
    ctx.font = "bold 16px sans-serif";
    ctx.fillText(`${prizes[i]}%`, r - 15, 5);
    ctx.restore();
  }
  ctx.restore();
  // فلش نشانگر
  ctx.beginPath();
  ctx.moveTo(cx - 10, 5);
  ctx.lineTo(cx + 10, 5);
  ctx.lineTo(cx, 25);
  ctx.fillStyle = "#000";
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
        alert(`🎉 تبریک! کد تخفیف ${result.percent}٪ شما:\n${result.code}\n(اعتبار محدود دارد)`);
      } else {
        alert("😔 امروز شانس نبود، فردا دوباره امتحان کن!");
      }
      renderWheel();
    }, 2500);
  } catch (e) {
    clearInterval(spinInterval);
    alert("خطا: " + e.message);
    btn.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// تب کیف پول
// ---------------------------------------------------------------------------
async function renderWallet() {
  content.innerHTML = "<p>در حال بارگذاری...</p>";
  try {
    const me = await api("/api/me");
    content.innerHTML = `
      <div class="card">
        <h3>👛 موجودی فعلی</h3>
        <div class="stat-row"><b>${fmt(me.wallet_credit)} تومان</b></div>
      </div>
      <div class="card">
        <h3>➕ شارژ کیف پول</h3>
        <input id="topup-amount" type="number" placeholder="مبلغ به تومان" style="width:100%;padding:10px;border-radius:8px;border:1px solid #ccc" />
        <button class="btn" id="topup-btn">ثبت درخواست شارژ</button>
      </div>
    `;
    document.getElementById("topup-btn").onclick = async () => {
      const amount = parseInt(document.getElementById("topup-amount").value, 10);
      if (!amount || amount < 1000) return alert("حداقل مبلغ ۱۰۰۰ تومان است.");
      try {
        const r = await api("/api/wallet/topup-request", { method: "POST", body: JSON.stringify({ amount }) });
        alert(`مبلغ را به کارت زیر واریز کنید و رسید را در خود بات (نه اینجا) بفرستید:\n\n${r.card_number}\n${r.card_holder}`);
      } catch (e) {
        alert("خطا: " + e.message);
      }
    };
  } catch (e) {
    content.innerHTML = `<p>خطا: ${e.message}</p>`;
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

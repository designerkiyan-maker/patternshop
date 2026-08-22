// -*- coding: utf-8 -*-
// فرانت‌اند پنل مدیریت وب مستقل ShopVPN (یوزر/پسورد، جدا از initData تلگرام).
// این فایل با کوکی نشست (panel_session) که سرور بعد از /api/panel/login ست می‌کند
// کار می‌کند؛ هر fetch باید credentials:'include' داشته باشد.

(function () {
  "use strict";

  // ------------------------------------------------------------------
  // ابزارهای عمومی
  // ------------------------------------------------------------------

  async function api(path, opts) {
    opts = opts || {};
    const headers = opts.headers || {};
    let body = opts.body;
    if (body && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const res = await fetch(path, {
      method: opts.method || "GET",
      headers: headers,
      body: body,
      credentials: "include",
    });
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      const msg = (data && data.detail) ? data.detail : `خطا (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function el(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function toman(n) {
    n = Number(n) || 0;
    return n.toLocaleString("fa-IR") + " تومان";
  }

  function toast(msg, kind) {
    const root = document.getElementById("toast-root");
    if (!root) return;
    const t = el(`<div class="toast toast-${kind || "info"}">${esc(msg)}</div>`);
    root.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  // ------------------------------------------------------------------
  // ورود / خروج
  // ------------------------------------------------------------------

  const loginScreen = document.getElementById("login-screen");
  const appRoot = document.getElementById("app");
  const loginForm = document.getElementById("login-form");
  const loginError = document.getElementById("login-error");
  const loginSubmit = document.getElementById("login-submit");

  let ME = null; // { username, role }

  function showLogin() {
    loginScreen.hidden = false;
    appRoot.hidden = true;
  }

  function showApp() {
    loginScreen.hidden = true;
    appRoot.hidden = false;
    document.getElementById("me-username").textContent = ME.username;
    document.getElementById("me-role").textContent = ROLE_LABELS[ME.role] || ME.role;
    document.getElementById("me-avatar").textContent = (ME.username || "?").slice(0, 1).toUpperCase();
  }

  const ROLE_LABELS = { owner: "مالک", admin: "مدیر" };

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.hidden = true;
    loginSubmit.disabled = true;
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    try {
      ME = await api("/api/panel/login", { method: "POST", body: { username, password } });
      showApp();
      renderNav();
      navigate("dashboard");
    } catch (err) {
      loginError.textContent = err.message || "ورود ناموفق بود.";
      loginError.hidden = false;
    } finally {
      loginSubmit.disabled = false;
    }
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await api("/api/panel/logout", { method: "POST" }); } catch (e) {}
    ME = null;
    showLogin();
  });

  async function boot() {
    try {
      ME = await api("/api/panel/me");
      showApp();
      renderNav();
      navigate("dashboard");
    } catch (e) {
      showLogin();
    }
  }

  // ------------------------------------------------------------------
  // سایدبار / ناوبری
  // ------------------------------------------------------------------

  const PAGES = [
    { key: "dashboard", label: "داشبورد", icon: "📊", render: renderDashboard },
    { key: "users", label: "کاربران", icon: "👤", render: renderUsers },
    { key: "banners", label: "بنرها", icon: "🖼", render: renderBanners },
    { key: "discounts", label: "کدهای تخفیف", icon: "🏷", render: renderDiscounts },
    { key: "resellers", label: "نمایندگی‌ها", icon: "🧩", render: renderResellers },
    { key: "wallet", label: "کیف پول", icon: "💰", render: renderWallet },
    { key: "tickets", label: "تیکت‌ها", icon: "🎫", render: renderTickets },
    { key: "settings", label: "تنظیمات فروشگاه", icon: "⚙️", render: renderSettings },
    { key: "backup", label: "بکاپ", icon: "🗄", render: renderBackup },
  ];

  const nav = document.getElementById("nav-tunnel");
  const content = document.getElementById("content");
  const pageTitle = document.getElementById("page-title");
  const hamburger = document.getElementById("hamburger-btn");
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  const sidebar = document.querySelector(".sidebar");

  function renderNav() {
    nav.innerHTML = "";
    PAGES.forEach((p) => {
      const item = el(`<button class="nav-item" data-key="${p.key}">
        <span class="nav-icon">${p.icon}</span><span>${esc(p.label)}</span>
      </button>`);
      item.addEventListener("click", () => navigate(p.key));
      nav.appendChild(item);
    });
  }

  function setActiveNav(key) {
    nav.querySelectorAll(".nav-item").forEach((b) => {
      b.classList.toggle("active", b.dataset.key === key);
    });
  }

  async function navigate(key) {
    const page = PAGES.find((p) => p.key === key);
    if (!page) return;
    setActiveNav(key);
    pageTitle.textContent = page.label;
    content.innerHTML = `<div class="loading">در حال بارگذاری...</div>`;
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("show");
    try {
      await page.render(content);
    } catch (err) {
      content.innerHTML = `<div class="card"><div class="empty-state">${esc(err.message || "خطا در بارگذاری اطلاعات.")}</div></div>`;
    }
  }

  hamburger.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    sidebarOverlay.classList.toggle("show");
  });
  sidebarOverlay.addEventListener("click", () => {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("show");
  });

  function clock() {
    const c = document.getElementById("topbar-clock");
    if (c) c.textContent = new Date().toLocaleTimeString("fa-IR");
  }
  setInterval(clock, 1000);
  clock();

  // ------------------------------------------------------------------
  // داشبورد
  // ------------------------------------------------------------------

  async function renderDashboard(root) {
    const s = await api("/api/admin/dashboard");
    root.innerHTML = `
      <div class="grid grid-4">
        <div class="card stat-card">
          <div class="stat-top"><span class="stat-icon stat-icon-1">💵</span></div>
          <div class="card-sub">درآمد این بازه</div>
          <h2>${toman(s.revenue)}</h2>
        </div>
        <div class="card stat-card">
          <div class="stat-top"><span class="stat-icon stat-icon-2">✅</span></div>
          <div class="card-sub">سفارش‌های تاییدشده</div>
          <h2>${esc(s.approved)}</h2>
        </div>
        <div class="card stat-card">
          <div class="stat-top"><span class="stat-icon stat-icon-3">👥</span></div>
          <div class="card-sub">کل کاربران</div>
          <h2>${esc(s.total_users)}</h2>
        </div>
        <div class="card stat-card">
          <div class="stat-top"><span class="stat-icon stat-icon-4">🎫</span></div>
          <div class="card-sub">تیکت‌های باز</div>
          <h2>${esc(s.open_tickets)}</h2>
        </div>
      </div>
      <div class="grid grid-2" style="margin-top:18px">
        <div class="card">
          <div class="card-head"><strong>پرفروش‌ترین محصولات</strong></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>محصول</th><th>تعداد فروش</th><th>درآمد</th></tr></thead>
              <tbody>
                ${(s.top_products || []).map((p) => `
                  <tr><td>${esc(p.name)}</td><td>${esc(p.orders)}</td><td>${toman(p.revenue)}</td></tr>
                `).join("") || `<tr><td colspan="3" class="empty-state">داده‌ای نیست</td></tr>`}
              </tbody>
            </table>
          </div>
        </div>
        <div class="card">
          <div class="card-head"><strong>خلاصه</strong></div>
          <div class="chip-row">
            <span class="chip">کانفیگ‌های فعال: ${esc(s.active_configs)}</span>
            <span class="chip">کاربران جدید: ${esc(s.new_users)}</span>
            <span class="chip">موجودی کل کیف‌پول‌ها: ${toman(s.wallet_total)}</span>
            <span class="chip">نرخ تبدیل: ${esc(s.conversion_rate)}٪</span>
            <span class="chip">میانگین سبد خرید: ${toman(s.aov)}</span>
          </div>
        </div>
      </div>
    `;
  }

  // ------------------------------------------------------------------
  // کاربران
  // ------------------------------------------------------------------

  async function renderUsers(root) {
    root.innerHTML = `
      <div class="card">
        <div class="toolbar">
          <label class="field" style="flex:1"><span>جستجو</span><input type="text" id="u-q" placeholder="آیدی عددی، یوزرنیم یا نام..."></label>
          <label class="field"><span>وضعیت</span>
            <select id="u-status">
              <option value="all">همه</option>
              <option value="active">فعال</option>
              <option value="expired">منقضی</option>
              <option value="blocked">بلاک‌شده</option>
            </select>
          </label>
          <button class="btn btn-primary" id="u-search-btn" style="align-self:flex-end">جستجو</button>
        </div>
        <div class="table-wrap" id="u-table"><div class="loading">در حال بارگذاری...</div></div>
      </div>
    `;
    async function load() {
      const q = document.getElementById("u-q").value.trim();
      const status = document.getElementById("u-status").value;
      const data = await api(`/api/admin/users?query=${encodeURIComponent(q)}&status=${status}&limit=50`);
      const wrap = document.getElementById("u-table");
      if (!data.users.length) {
        wrap.innerHTML = `<div class="empty-state">کاربری پیدا نشد.</div>`;
        return;
      }
      wrap.innerHTML = `
        <table>
          <thead><tr><th>آیدی</th><th>نام</th><th>یوزرنیم</th><th>وضعیت</th><th>کیف پول</th><th></th></tr></thead>
          <tbody>
            ${data.users.map((u) => `
              <tr>
                <td class="mono">${esc(u.telegram_id)}</td>
                <td>${esc(u.first_name)}</td>
                <td>${esc(u.username ? "@" + u.username : "-")}</td>
                <td><span class="badge ${u.is_blocked ? "badge-rejected" : "badge-approved"}">${u.is_blocked ? "بلاک" : (u.status === "active" ? "فعال" : u.status === "expired" ? "منقضی" : "بدون سرویس")}</span></td>
                <td>${toman(u.wallet_credit)}</td>
                <td><button class="btn btn-sm ${u.is_blocked ? "" : "btn-danger"}" data-block="${u.telegram_id}" data-cur="${u.is_blocked ? 1 : 0}">${u.is_blocked ? "آزاد کردن" : "بلاک"}</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      wrap.querySelectorAll("[data-block]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const tid = btn.getAttribute("data-block");
          const cur = btn.getAttribute("data-cur") === "1";
          try {
            await api(`/api/admin/users/${tid}/block`, { method: "POST", body: { blocked: !cur } });
            toast("وضعیت کاربر بروزرسانی شد.", "success");
            load();
          } catch (err) { toast(err.message, "error"); }
        });
      });
    }
    document.getElementById("u-search-btn").addEventListener("click", load);
    document.getElementById("u-q").addEventListener("keydown", (e) => { if (e.key === "Enter") load(); });
    load();
  }

  // ------------------------------------------------------------------
  // بنرها
  // ------------------------------------------------------------------

  async function renderBanners(root) {
    const banners = await api("/api/admin/banners");
    root.innerHTML = `
      <div class="card">
        <div class="card-head">
          <strong>بنرهای کاروسل خانه</strong>
          <button class="btn btn-primary btn-sm" id="b-add">+ بنر جدید</button>
        </div>
        <div id="b-list"></div>
      </div>
    `;
    let items = banners.map((b, i) => ({ ...b, _id: b.id || ("new_" + i) }));

    function draw() {
      const list = document.getElementById("b-list");
      if (!items.length) {
        list.innerHTML = `<div class="empty-state">بنری ثبت نشده.</div>`;
        return;
      }
      list.innerHTML = items.map((b, i) => `
        <div class="card" style="margin-bottom:12px">
          <div class="form-grid">
            <div class="form-row">
              <label class="field" style="flex:1"><span>عنوان</span><input data-f="title" data-i="${i}" value="${esc(b.title || "")}"></label>
              <label class="field" style="flex:1"><span>زیرعنوان</span><input data-f="sub" data-i="${i}" value="${esc(b.sub || "")}"></label>
            </div>
            <div class="form-row">
              <label class="field"><span>فعال</span>
                <select data-f="enabled" data-i="${i}">
                  <option value="1" ${b.enabled ? "selected" : ""}>بله</option>
                  <option value="0" ${!b.enabled ? "selected" : ""}>خیر</option>
                </select>
              </label>
              <button class="btn btn-danger btn-sm" data-del="${i}" style="align-self:flex-end">حذف</button>
            </div>
          </div>
        </div>
      `).join("");
      list.querySelectorAll("[data-f]").forEach((inp) => {
        inp.addEventListener("change", () => {
          const i = Number(inp.getAttribute("data-i"));
          const f = inp.getAttribute("data-f");
          items[i][f] = f === "enabled" ? inp.value === "1" : inp.value;
        });
      });
      list.querySelectorAll("[data-del]").forEach((btn) => {
        btn.addEventListener("click", () => {
          items.splice(Number(btn.getAttribute("data-del")), 1);
          draw();
        });
      });
    }
    draw();

    document.getElementById("b-add").addEventListener("click", () => {
      items.push({ title: "بنر جدید", sub: "", cta: "", nav: "store", enabled: true, _id: "new_" + Date.now() });
      draw();
    });

    root.querySelector(".card").insertAdjacentHTML("beforeend",
      `<div class="modal-actions"><button class="btn btn-primary btn-block" id="b-save">ذخیره‌ی بنرها</button></div>`);
    document.getElementById("b-save").addEventListener("click", async () => {
      try {
        const payload = items.map((b) => ({
          id: (typeof b.id === "string" && !b.id.startsWith("new_")) ? b.id : undefined,
          icon: b.icon || "", title: b.title || "بنر", sub: b.sub || "", cta: b.cta || "",
          nav: b.nav || "store", bg: b.bg || "", image: b.image || "", image_only: !!b.image_only,
          enabled: b.enabled !== false,
        }));
        await api("/api/admin/banners", { method: "POST", body: { banners: payload } });
        toast("بنرها ذخیره شد.", "success");
        renderBanners(root);
      } catch (err) { toast(err.message, "error"); }
    });
  }

  // ------------------------------------------------------------------
  // کدهای تخفیف
  // ------------------------------------------------------------------

  async function renderDiscounts(root) {
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><strong>ساخت کد تخفیف جدید</strong></div>
        <div class="form-grid">
          <div class="form-row">
            <label class="field" style="flex:1"><span>کد</span><input id="d-code" placeholder="مثلاً OFF20"></label>
            <label class="field"><span>درصد</span><input id="d-percent" type="number" min="1" max="100" placeholder="مثلاً 20"></label>
            <label class="field"><span>یا مبلغ ثابت (تومان)</span><input id="d-fixed" type="number" min="0"></label>
          </div>
          <div class="form-row">
            <label class="field"><span>حداکثر تعداد استفاده (۰ = نامحدود)</span><input id="d-max" type="number" min="0" value="0"></label>
            <button class="btn btn-primary" id="d-create">ساخت کد</button>
          </div>
        </div>
      </div>
      <div class="card" style="margin-top:18px">
        <div class="card-head"><strong>کدهای تخفیف</strong></div>
        <div class="table-wrap" id="d-table"><div class="loading">در حال بارگذاری...</div></div>
      </div>
    `;
    async function load() {
      const rows = await api("/api/admin/discounts");
      const wrap = document.getElementById("d-table");
      if (!rows.length) {
        wrap.innerHTML = `<div class="empty-state">کد تخفیفی ثبت نشده.</div>`;
        return;
      }
      wrap.innerHTML = `
        <table>
          <thead><tr><th>کد</th><th>تخفیف</th><th>استفاده</th><th>وضعیت</th><th></th></tr></thead>
          <tbody>
            ${rows.map((d) => `
              <tr>
                <td class="mono">${esc(d.code)}</td>
                <td>${d.percent ? d.percent + "٪" : toman(d.fixed_amount)}</td>
                <td>${esc(d.used_count)}${d.max_uses ? " / " + esc(d.max_uses) : ""}</td>
                <td><span class="badge ${d.is_active ? "badge-approved" : "badge-rejected"}">${d.is_active ? "فعال" : "غیرفعال"}</span></td>
                <td>
                  <button class="btn btn-sm" data-toggle="${d.id}">${d.is_active ? "غیرفعال کن" : "فعال کن"}</button>
                  <button class="btn btn-sm btn-danger" data-del="${d.id}">حذف</button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      wrap.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
        await api(`/api/admin/discounts/${b.getAttribute("data-toggle")}/toggle`, { method: "POST" });
        load();
      }));
      wrap.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
        await api(`/api/admin/discounts/${b.getAttribute("data-del")}`, { method: "DELETE" });
        toast("حذف شد.", "success");
        load();
      }));
    }
    document.getElementById("d-create").addEventListener("click", async () => {
      const code = document.getElementById("d-code").value.trim();
      const percent = document.getElementById("d-percent").value;
      const fixed = document.getElementById("d-fixed").value;
      try {
        await api("/api/admin/discounts", {
          method: "POST",
          body: {
            code,
            percent: percent ? Number(percent) : null,
            fixed_amount: fixed ? Number(fixed) : null,
            max_uses: Number(document.getElementById("d-max").value || 0),
          },
        });
        toast("کد تخفیف ساخته شد.", "success");
        document.getElementById("d-code").value = "";
        document.getElementById("d-percent").value = "";
        document.getElementById("d-fixed").value = "";
        load();
      } catch (err) { toast(err.message, "error"); }
    });
    load();
  }

  // ------------------------------------------------------------------
  // نمایندگی‌ها
  // ------------------------------------------------------------------

  async function renderResellers(root) {
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><strong>افزودن نماینده‌ی جدید</strong></div>
        <p class="card-sub">توکن بات نمایندگی را از @BotFather بگیر و اینجا وارد کن.</p>
        <div class="form-grid">
          <div class="form-row">
            <label class="field" style="flex:2"><span>توکن بات</span><input id="r-token" placeholder="123456:ABC-..."></label>
            <label class="field" style="flex:1"><span>یوزرنیم داخلی</span><input id="r-username" placeholder="مثلاً reseller1"></label>
          </div>
          <div class="form-row">
            <label class="field"><span>آیدی عددی مالک نماینده</span><input id="r-owner" type="number"></label>
            <label class="field" style="flex:1"><span>نام مالک (اختیاری)</span><input id="r-owner-name"></label>
            <button class="btn btn-primary" id="r-create" style="align-self:flex-end">ثبت نماینده</button>
          </div>
        </div>
      </div>
      <div class="card" style="margin-top:18px">
        <div class="card-head"><strong>نماینده‌ها</strong></div>
        <div class="table-wrap" id="r-table"><div class="loading">در حال بارگذاری...</div></div>
      </div>
    `;
    async function load() {
      const rows = await api("/api/admin/resellers");
      const wrap = document.getElementById("r-table");
      if (!rows.length) {
        wrap.innerHTML = `<div class="empty-state">نماینده‌ای ثبت نشده.</div>`;
        return;
      }
      wrap.innerHTML = `
        <table>
          <thead><tr><th>بات</th><th>مالک</th><th>وضعیت</th><th></th></tr></thead>
          <tbody>
            ${rows.map((r) => `
              <tr>
                <td><a href="${esc(r.bot_link)}" target="_blank">@${esc(r.bot_username)}</a></td>
                <td>${esc(r.owner_name || "-")} <span class="mono">(${esc(r.owner_telegram_id)})</span></td>
                <td><span class="badge ${r.is_active ? "badge-approved" : "badge-rejected"}">${r.is_active ? "فعال" : "غیرفعال"}</span></td>
                <td>
                  <button class="btn btn-sm" data-toggle="${r.id}">${r.is_active ? "غیرفعال کن" : "فعال کن"}</button>
                  <button class="btn btn-sm btn-danger" data-del="${r.id}">حذف</button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      wrap.querySelectorAll("[data-toggle]").forEach((b) => b.addEventListener("click", async () => {
        await api(`/api/admin/resellers/${b.getAttribute("data-toggle")}/toggle`, { method: "POST" });
        load();
      }));
      wrap.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
        if (!confirm("حذف این نماینده مطمئنی؟")) return;
        await api(`/api/admin/resellers/${b.getAttribute("data-del")}`, { method: "DELETE" });
        toast("حذف شد.", "success");
        load();
      }));
    }
    document.getElementById("r-create").addEventListener("click", async () => {
      const token = document.getElementById("r-token").value.trim();
      const username = document.getElementById("r-username").value.trim();
      const owner = document.getElementById("r-owner").value;
      try {
        if (!token || !username || !owner) throw new Error("همه‌ی فیلدهای ستاره‌دار را پر کن.");
        await api("/api/admin/resellers/validate", { method: "POST", body: { token } });
        await api("/api/admin/resellers", {
          method: "POST",
          body: {
            token, username, owner_telegram_id: Number(owner),
            owner_name: document.getElementById("r-owner-name").value.trim(),
          },
        });
        toast("نماینده ثبت شد.", "success");
        load();
      } catch (err) { toast(err.message, "error"); }
    });
    load();
  }

  // ------------------------------------------------------------------
  // کیف پول
  // ------------------------------------------------------------------

  async function renderWallet(root) {
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><strong>جستجوی کیف‌پول کاربر</strong></div>
        <div class="form-row">
          <label class="field" style="flex:1"><span>آیدی عددی تلگرام کاربر</span><input id="w-tid" type="number"></label>
          <button class="btn btn-primary" id="w-lookup" style="align-self:flex-end">جستجو</button>
        </div>
        <div id="w-result" style="margin-top:16px"></div>
      </div>
    `;
    document.getElementById("w-lookup").addEventListener("click", async () => {
      const tid = document.getElementById("w-tid").value;
      if (!tid) return;
      try {
        const u = await api(`/api/admin/wallet/lookup?telegram_id=${tid}`);
        document.getElementById("w-result").innerHTML = `
          <div class="card">
            <div class="card-head">
              <strong>${esc(u.user_name || "بدون نام")} ${u.username ? "(@" + esc(u.username) + ")" : ""}</strong>
              <span class="badge badge-approved">${toman(u.wallet_credit)}</span>
            </div>
            <div class="form-row">
              <label class="field" style="flex:1"><span>مبلغ تغییر (تومان، منفی = کسر)</span><input id="w-amount" type="number"></label>
              <button class="btn btn-primary" id="w-adjust" style="align-self:flex-end">اعمال تغییر</button>
            </div>
          </div>
        `;
        document.getElementById("w-adjust").addEventListener("click", async () => {
          const amount = Number(document.getElementById("w-amount").value || 0);
          if (!amount) { toast("مبلغ نمی‌تواند صفر باشد.", "error"); return; }
          try {
            const res = await api("/api/admin/wallet/adjust", { method: "POST", body: { telegram_id: Number(tid), amount } });
            toast(`موجودی جدید: ${toman(res.new_balance)}`, "success");
            document.getElementById("w-lookup").click();
          } catch (err) { toast(err.message, "error"); }
        });
      } catch (err) {
        document.getElementById("w-result").innerHTML = `<div class="empty-state">${esc(err.message)}</div>`;
      }
    });
  }

  // ------------------------------------------------------------------
  // تیکت‌ها
  // ------------------------------------------------------------------

  async function renderTickets(root) {
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><strong>تیکت‌های پشتیبانی</strong></div>
        <div class="table-wrap" id="t-table"><div class="loading">در حال بارگذاری...</div></div>
      </div>
      <div id="t-detail" style="margin-top:18px"></div>
    `;
    async function load() {
      const rows = await api("/api/admin/tickets");
      const wrap = document.getElementById("t-table");
      if (!rows.length) {
        wrap.innerHTML = `<div class="empty-state">تیکتی ثبت نشده.</div>`;
        return;
      }
      wrap.innerHTML = `
        <table>
          <thead><tr><th>موضوع</th><th>کاربر</th><th>وضعیت</th><th></th></tr></thead>
          <tbody>
            ${rows.map((t) => `
              <tr>
                <td>${esc(t.subject)}</td>
                <td>${esc(t.user_name)} ${t.user_username ? "(@" + esc(t.user_username) + ")" : ""}</td>
                <td><span class="badge ${t.status === "closed" ? "badge-rejected" : "badge-pending"}">${esc(t.status)}</span></td>
                <td><button class="btn btn-sm" data-open="${t.id}">مشاهده و پاسخ</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      wrap.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", () => openTicket(b.getAttribute("data-open"))));
    }
    async function openTicket(id) {
      const msgs = await api(`/api/admin/tickets/${id}/messages`);
      const box = document.getElementById("t-detail");
      const list = (msgs.messages || msgs || []);
      box.innerHTML = `
        <div class="card">
          <div class="card-head"><strong>گفتگوی تیکت #${esc(id)}</strong>
            <button class="btn btn-sm btn-danger" id="t-close">بستن تیکت</button>
          </div>
          <div class="chip-row" style="flex-direction:column;align-items:stretch;max-height:300px;overflow:auto;margin-bottom:12px">
            ${Array.isArray(list) ? list.map((m) => `<div class="chip">${esc(m.message || m.text || "")}</div>`).join("") : ""}
          </div>
          <div class="form-row">
            <label class="field" style="flex:1"><span>پاسخ</span><input id="t-reply"></label>
            <button class="btn btn-primary" id="t-send" style="align-self:flex-end">ارسال</button>
          </div>
        </div>
      `;
      document.getElementById("t-send").addEventListener("click", async () => {
        const message = document.getElementById("t-reply").value.trim();
        if (!message) return;
        try {
          await api(`/api/admin/tickets/${id}/messages`, { method: "POST", body: { message } });
          toast("پاسخ ارسال شد.", "success");
          openTicket(id);
        } catch (err) { toast(err.message, "error"); }
      });
      document.getElementById("t-close").addEventListener("click", async () => {
        try {
          await api(`/api/admin/tickets/${id}/close`, { method: "POST" });
          toast("تیکت بسته شد.", "success");
          load();
          box.innerHTML = "";
        } catch (err) { toast(err.message, "error"); }
      });
    }
    load();
  }

  // ------------------------------------------------------------------
  // تنظیمات فروشگاه (برندینگ + تم)
  // ------------------------------------------------------------------

  async function renderSettings(root) {
    const b = await api("/api/admin/settings/branding");
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><strong>برندسازی فروشگاه</strong></div>
        <div class="form-grid">
          <label class="field"><span>نام فروشگاه</span><input id="s-name" value="${esc(b.store_name)}"></label>
          <label class="field"><span>متن بنر مینی‌اپ</span><input id="s-banner" value="${esc(b.banner_text)}"></label>
          <label class="field"><span>تم مینی‌اپ</span>
            <select id="s-theme">
              ${b.themes.map((t) => `<option value="${esc(t.id)}" ${t.id === b.theme ? "selected" : ""}>${esc(t.label)}</option>`).join("")}
            </select>
          </label>
          <button class="btn btn-primary" id="s-save">ذخیره</button>
        </div>
      </div>
    `;
    document.getElementById("s-save").addEventListener("click", async () => {
      try {
        await api("/api/admin/settings/branding", {
          method: "POST",
          body: { store_name: document.getElementById("s-name").value, banner_text: document.getElementById("s-banner").value },
        });
        await api("/api/admin/settings/theme", { method: "POST", body: { theme: document.getElementById("s-theme").value } });
        toast("تنظیمات ذخیره شد.", "success");
      } catch (err) { toast(err.message, "error"); }
    });
  }

  // ------------------------------------------------------------------
  // بکاپ
  // ------------------------------------------------------------------

  async function renderBackup(root) {
    root.innerHTML = `
      <div class="card">
        <div class="card-head"><strong>دریافت بکاپ فوری</strong></div>
        <p class="card-sub">فایل دیتابیس فعلی به آیدی تلگرام مالک بات فرستاده می‌شود.</p>
        <button class="btn btn-primary" id="bk-create">دریافت بکاپ</button>
      </div>
      <div class="card" style="margin-top:18px">
        <div class="card-head"><strong>بازیابی از فایل بکاپ</strong></div>
        <p class="card-sub">⚠️ این کار دیتابیس فعلی را با فایل انتخابی جایگزین می‌کند.</p>
        <div class="form-row">
          <input type="file" id="bk-file" accept=".db,.sqlite,.sqlite3">
          <button class="btn btn-danger" id="bk-restore">بازیابی</button>
        </div>
      </div>
    `;
    document.getElementById("bk-create").addEventListener("click", async () => {
      try {
        await api("/api/admin/backup/create", { method: "POST" });
        toast("بکاپ ساخته و به تلگرام ارسال شد.", "success");
      } catch (err) { toast(err.message, "error"); }
    });
    document.getElementById("bk-restore").addEventListener("click", async () => {
      const f = document.getElementById("bk-file").files[0];
      if (!f) { toast("یک فایل انتخاب کن.", "error"); return; }
      if (!confirm("مطمئنی؟ این کار دیتابیس فعلی را جایگزین می‌کند.")) return;
      const fd = new FormData();
      fd.append("file", f);
      try {
        await api("/api/admin/backup/restore", { method: "POST", body: fd });
        toast("بازیابی با موفقیت انجام شد.", "success");
      } catch (err) { toast(err.message, "error"); }
    });
  }

  // ------------------------------------------------------------------
  boot();
})();

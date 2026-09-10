# 🧵 الگوشاپ — فروشگاه الگوی خیاطی تلگرام

بات تلگرام فروش خودکار **الگوهای آمادهی خیاطی** با پشتیبانی از فروشگاه وب (Mini App)، سبد خرید، کیف پول، باشگاه مشتریان و پنل مدیریت تحت وب.

محصولات دیجیتال (فایل PDF الگو) هستند که پس از تایید پرداخت توسط ادمین، مستقیماً داخل تلگرام برای خریدار ارسال میشوند.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green)]()

---

## ✨ امکانات

### فروشگاه
- 📂 **کاتالوگ الگو** — دسته‌بندی + محصولات با عکس پیشنمایش و فایل(های) PDF
- 🛒 **سبد خرید** — پشتیبانی از محصولات دیجیتال و فیزیکی (واریانت سایز/رنگ + موجودی)
- 💳 **پرداخت کارتبهکارت** — آپلود رسید + تایید دستی توسط ادمین
- 👛 **کیف پول داخلی** — شارژ با تایید ادمین، خرید آنی بدون رسید
- 🎟 **کد تخفیف** — درصدی یا مبلغ ثابت با سقف استفاده و تاریخ انقضا
- 🎡 **گردونه شانس** — قرعه‌کشی با درصدهای قابل تنظیم
- 🤝 **زیرمجموعهگیری** — سه حالت پاداش (پورسانت / الگوی رایگان / شارژ هدیه)
- 🎁 **باشگاه مشتریان** — سیستم امتیاز، tier برنزی/نقرهای/طلایی/پلاتینیوم
- 🧪 **الگوی نمونه رایگان** — هر کاربر یک بار می‌تواند تست بگیرد

### پشتیبانی
- 🎫 **سیستم تیکت** — ثبت مشکل + گفتگوی دوطرفه با ادمین
- 💬 **چت زنده** — پیگیری مکالمه بین کاربر و ادمین آنلاین
- 📞 **ارتباط مستقیم** — ارسال پیام به پشتیبانی

### پنل مدیریت (داخل بات)
- 👑 **۴ سطح دسترسی:** مالک / ادمین / میانی / پشتیبان
- 📊 **داشبورد آمار** — فروش، کاربران، سفارش‌ها
- 🗄 **بکاپ روزانه** — خودکار + بازیابی از فایل
- 🎨 **شخصی‌سازی کامل** — متن دکمه‌ها، چیدمان منو， رنگ‌ها， پیام خوشآمد
- 🔔 **اعلان Push** — اعلان لحظه‌ای سفارش/شارژ/تیکت روی مرورگر
- 📢 **پیام همگانی** — ارسال به تمام کاربران
- 👥 **مدیریت کاربران** — بلاک/آنبلاک، مشاهده تاریخچه، تعدیل کیف پول

### Mini App (فروشگاه وب داخل تلگرام)
- 🌐 کاتالوگ کامل با عکس و قیمت
- 🛒 سبد خرید چندقلمی
- 📦 سفارش محصولات فیزیکی با آدرس و روش ارسال
- 📥 دانلود مستقیم فایلهای خریداری‌شده
- 👤 پروفایل کاربری با تاریخچه سفارشات
- 💬 چت زنده و تیکت

### پنل مدیریت وب (مستقل)
- 🔐 لاگین با یوزرنیم/پسورد (غیرتلگرامی)
- ✅ تایید سفارشها و شارژ کیف پول از مرورگر
- 📈 داشبورد آماری با فیلتر تاریخ
- 🗂 مدیریت کامل محصولات، دسته‌ها و فایل‌ها
- 👥 مدیریت ادمین‌ها با ۹ مجوز تفکیکی
- 🔄 بکاپ/بازیابی دیتابیس

---

## 🏗 معماری

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Telegram User  │────▶│    Bot (aiogram)  │────▶│                 │
│   (منوی اصلی +   │     │  handlers_user    │     │  SQLite DB      │
│    دکمه فروشگاه) │     │  handlers_admin   │     │  bot_database   │
└─────────────────┘     │  FSM Storage      │     │      .db        │
                         └────────┬─────────┘     │                 │
                                  │               │                 │
                    ┌─────────────▼──────────┐    │                 │
                    │   Mini App (:8001)      │◀───┘                 │
                    │  FastAPI + HTML/JS/CSS │                     │
                    │  initData auth         │                       │
                    └─────────────┬──────────┘                       │
                                  │                                 │
                    ┌─────────────▼──────────┐                       │
                    │  Admin Panel (:8002)   │                       │
                    │  FastAPI + Cookie auth │                       │
                    │  Web Push notifications│                       │
                    └────────────────────────┘                       │
```

---

## 🚀 نصب و راهاندازی

### پیشنیازها
- Python 3.10+
- دسترسی به [BotFather](https://t.me/BotFather) برای ساخت بات

### نصب سریع

```bash
git clone https://github.com/designerkiyan-maker/patternshop.git
cd patternshop
python -m venv venv
venv\Scripts\activate          # لینوکس: source venv/bin/activate
pip install -r requirements.txt
```

### تنظیمات (.env)

یک فایل `.env` در کنار `main.py` بسازید:

```env
BOT_TOKEN=8726640783:YOUR_BOT_TOKEN_HERE
OWNER_ID=54400109
ADMIN_PANEL_SECRET=YOUR_RANDOM_SECRET_HERE
DB_PATH=./bot_database.db

# گزینه‌ای — برای فروشگاه وب داخل تلگرام
MINIAPP_URL=https://app.yourdomain.com
MINIAPP_ALLOWED_ORIGINS=https://app.yourdomain.com

# گزینه‌ای — برای پروکسی تلگرام (در صورت نیاز)
TELEGRAM_PROXY=http://your-proxy:8080

# گزینه‌ای — برای اعلان Push مرورگر
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
```

ساخت کلید VAPID:
```bash
python -m admin_panel.generate_vapid_keys
```

### اجرا

```bash
python main.py
```

دیتابیس SQLite به‌طور خودکار ساخته می‌شود. هیچ سرویس جانبی (Redis, PostgreSQL و...) لازم نیست.

---

## 📲 راهاندازی Mini App

```bash
# در ترمینال جداگانه
uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
```

سپس در Nginx مسیر `/` را به `127.0.0.1:8001` proxy کنید (با SSL).
پس از ست کردن `MINIAPP_URL` در `.env` و ریاستارت بات، دکمه «🛍 فروشگاه» کنار باکس پیام ظاهر می‌شود.

احراز هویت از طریق `initData` تلگرام (HMAC-SHA256 سمت سرور) انجام می‌شود.

---

## 🖥 راهاندازی پنل مدیریت وب

```bash
# ساخت اولین حساب owner
python -m admin_panel.create_admin <username> <password>

# اجرا
uvicorn admin_panel.server:app --host 127.0.0.1 --port 8002
```

پنل وب را پشت Nginx با SSL قرار دهید.

---

## 🚢 نصب پروداکشن (سرور لینوکس)

```bash
git clone https://github.com/designerkiyan-maker/patternshop.git /opt/patternshop
cd /opt/patternshop

sudo BOT_TOKEN=... OWNER_ID=... REPO_URL=$(pwd) \
  bash deploy/install_server.sh

# فعال‌سازی دامنه + SSL
sudo bash deploy/install_server.sh --domain shop.example.com

# فعال‌سازی پنل مدیریت (اختیاری)
sudo bash deploy/install_server.sh --panel panel.example.com
```

در Cloudflare فقط یک رکورد **A** به IP سرور کافی است.

---

## 🗂 ساختار پروژه

| فایل / پوشه | نقش |
|---|---|
| `main.py` | نقطه ورود — راه‌اندازی asyncio loop |
| `bot_manager.py` | مدیریت instances بات، middlewareها، بکاپ و کش |
| `config.py` | بارگذاری متغیرهای محیطی از `.env` |
| `database.py` | لایه SQLite — اسکیما، کوئری‌ها， تراکنش‌ها |
| `handlers_user.py` | هندلرهای خرید، سبد، کیف پول، سفارش‌ها |
| `handlers_admin.py` | هندلرهای پنل مدیریت بات |
| `services/` | لایه تجاری — cart, checkout, orders, loyalty, inventory |
| `miniapp/` | فروشگاه وب داخل تلگرام (FastAPI) |
| `admin_panel/` | پنل مدیریت مستقل (FastAPI + static files) |
| `core/` | زیرساخت — telegram_proxy, vless_client |
| `backup.py` | بکاپ و بازیابی دیتابیس |
| `fsm_storage.py` | ذخیره‌سازی FSM روی SQLite |
| `force_join.py` | بررسی عضویت اجباری کانال |
| `blocked_user.py` | middleware مسدودسازی کاربر |
| `loyalty.py` | منطق باشگاه مشتریان |

---

## 🔒 امنیت

این پروژه دارای لایه‌های امنیتی زیر است:

- ✅ احراز هویت initData با HMAC-SHA256 (تلگرام)
- ✅ رمزنگاری password با PBKDF2-HMAC-SHA256 (260,000 iteration)
- ✅ توکن نشست HMAC-signed با expiry
- ✅ کوکی Secure + HttpOnly + SameSite=Lax
- ✅ تراکنش‌های اتمیک `BEGIN IMMEDIATE` برای عملیات مالی
- ✅ ضد SSRF در واردات URL
- ✅ Rate limiting روی ورود پنل
- ✅ محدودسازی CORS به دامنه خاص
- ✅ Security headers (CSP, X-Frame-Options, Referrer-Policy)
- ✅ اعتبارسنجی callback_data با bounds checking
- ✅ جلوگیری از IDOR در endpointهای حساس
- ✅ استفاده از `secrets.*` به جای `random.*`

> گزارش کامل ممیزی امنیتی در [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md) موجود است.

---

## 🧪 تست

```bash
# اجرای تست‌های واحد
python -m pytest tests/ -v

# تست سریع سینتکس
python -m py_compile main.py bot_manager.py database.py
```

---

## 📄 مجوز

MIT

---

## 🙏 تشکر

ساخته شده با ❤️ برای جامعه خیاط‌های ایران.

[🌐 سایت پروژه](https://github.com/designerkiyan-maker/patternshop)
[📋 گزارش امنیتی](SECURITY_AUDIT_REPORT.md)

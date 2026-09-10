# 🧵 الگوشاپ — فروشگاه هوشمند الگوی خیاطی

بات تلگرام فروش خودکار **الگوهای آمادهی خیاطی** با فروشگاه وب (Mini App)، سبد خرید، کیف پول، باشگاه مشتریان، پنل مدیریت تحت وب و سیستم ارسال فیزیکی — همه در یک پلتفرم.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green)]()
[![aiogram](https://img.shields.io/badge/aiogram-3.30%2B-purple)]()
[![SQLite](https://img.shields.io/badge/Database-SQLite-brightgreen)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Security Score](https://img.shields.io/badge/Security-82%2F100-orange)](SECURITY_AUDIT_REPORT.md)

---

## 🗺 نقشه کلی قابلیت‌ها

```
┌──────────────────────────────────────────────────────────────┐
│                     Telegram User                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  کاتالوگ │  │  سبد    │  │  سفارش  │  │  کیف   │        │
│  │  + خرید  │  │  خرید   │  │  + رسید  │  │  پول   │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐        │
│  │ گردونه │  │ زیر    │  │ تیکت   │  │ باشگاه  │        │
│  │ شانس   │  │ مجموعه │  │ پشتیبانی│  │مشتریان │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
    │   Bot     │   │ Mini App  │   │Admin Panel│
    │ (Telegram)│   │  (:8001)  │   │  (:8002)  │
    │ aiogram   │   │ FastAPI   │   │ FastAPI   │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │               │               │
          └───────────────┼───────────────┘
                          │
                   ┌──────▼──────┐
                   │  SQLite DB  │
                   │ bot_database│
                   └─────────────┘
```

---

## ✨ امکانات بات تلگرام

### 🛒 فروشگاه و خرید
| قابلیت | توضیح |
|--------|-------|
| **کاتالوگ الگو** | دسته‌بندی + محصولات با عکس پیشنمایش و یک یا چند فایل PDF |
| **خرید دیجیتال** | بعد از تایید ادمین، فایل مستقیماً داخل چت تلگرام ارسال می‌شود |
| **خرید فیزیکی** | محصول با واریانت (سایز/رنگ) + مدیریت موجودی انبار |
| **رسید کارتبهکارت** | کاربر عکس/فایل رسید واریز را آپلود می‌کند، ادمین بررسی و تایید می‌کند |
| **سبد خرید** | اضافه/حذف/تغییر تعداد قلم، تسویه با کد تخفیف و کیف پول |
| **دانلود مجدد** | فایل‌های سفارش تاییدشده از بخش «سفارشهای من» قابل دانلود است |

### 💰 مالی
| قابلیت | توضیح |
|--------|-------|
| **کیف پول داخلی** | شارژ با تایید دستی ادمین، برداشت از طریق خرید آنی |
| **کد تخفیف** | درصدی (0-100%) یا مبلغ ثابت، با سقف استفاده و تاریخ انقضا |
| **گردونه شانس** | چرخش رایگان هر 24 ساعت، برنده کد تخفیف می‌شود (درصد: 10/20/30/50) |
| **پورسانت خرید** | به دعوت‌کننده درصدی از مبلغ خرید اول زیرمجموعه تعلق می‌گیرد |

### 👥 کاربران و وفاداری
| قابلیت | توضیح |
|--------|-------|
| **زیرمجموعه‌گیری** | سه مدل: (۱) پورسانت خرید، (۲) الگوی رایگان پس از N نفر، (۳) شارژ ثابت بهازای هر دعوت |
| **باشگاه مشتریان** | امتیازگیری از خرید + ثبتنام، تبدیل امتیاز به اعتبار کیف پول |
| **سطوح(tier)** | برنز(0+) / نقرهای(500+) / طلایی(2000+) / پلاتینیوم(5000+) — هر tier ضریب بیشتری می‌دهد |
| **نمره باشگاه** | هر 10,000 تومان = 1 امتیاز |
| **هدیه ثبتنام** | 50 امتیاز هدیه اولین ورود |
| **هدیه معرفی** | 20 امتیاز به دعوت‌کننده وقتی کاربر جدید می‌آید |

### 🎫 پشتیبانی
| قابلیت | توضیح |
|--------|-------|
| **چت زنده** | کاربر پیام می‌نویسد، اولین ادمین آنلاین پاسخ می‌دهد |
| **سیستم تیکت** | ثبت مشکل با موضوع، گفتگوی دوطرفه، بستن تیکت |
| **پیام همگانی** | ادمین می‌تواند پیام متنی به تمام کاربران ارسال کند |

### ⚙️ مدیریت درون بات
| سطح | دسترسی |
|-----|-------|
| **مالک(owner)** | همه مجوزها — 12 permission کامل |
| **ادمین(admin)** | سفارشات، کاربران، کاتالوگ، تخفیف، تیکت، broadcast، system, settings, inventory, shipping |
| **میانی(mid)** | سفارشات، کاربران، تیکت، broadcast, inventory |
| **پشتیبان(support)** | فقط تیکت |

**ابزارهای پنل بات:**
- ✅ تایید/رد سفارش + ارسال فایل‌های الگو
- ✅ تایید/رد شارژ کیف پول
- ✅ مدیریت محصولات، دسته‌ها، فایلهای الگو و عکس پیشنمایش
- ✅ مدیریت کدهای تخفیف
- ✅ بلاک/آنبلاک کاربر + تعدیل کیف پول
- ✅ مشاهده آمار فروش، گزارش‌ها
- ✅ تنظیم شماره کارت بانکی
- ✅ تنظیم متن خوشآمد و دکمه‌ها
- ✅ مدیریت ادمین‌ها (افزودن، حذف، تغییر نقش)
- ✅ بکاپ روزانه خودکار + بازیابی
- ✅ تنظیم گردونه شانس (درصد برد، جوایز، cooldown)
- ✅ تنظیمات زیرمجموعه‌گیری
- ✅ تنظیمات باشگاه مشتریان
- ✅ تنظیمات عضویت اجباری کانال

---

## 📲 Mini App — فروشگاه وب داخل تلگرام

### صفحات و مسیرها

| صفحه | مسیر | دسترسی |
|------|------|-------|
| **خانه** | `/` | عمومی (بدون لاگین) |
| **کاتالوگ** | `/api/catalog` | احراز هویت |
| **جزئیات محصول** | `/api/products/{id}` | احراز هویت |
| **عکس پیش‌نمایش** | `/api/products/{id}/preview` | عمومی |
| **سبد خرید** | `/api/cart` (GET/POST/PATCH/DELETE) | احراز هویت |
| **تسویه سبد** | `/api/cart/checkout` | احراز هویت |
| **سفارشات** | `/api/orders` + `/api/orders/{id}` | احراز هویت |
| **آپلود رسید** | `/api/orders/{id}/receipt` | احراز هویت |
| **دانلود فایل** | `/api/orders/{id}/files/{record_id}` | مالک سفارش |
| **روش‌های ارسال** | `/api/shipping/methods` | احراز هویت |
| **آدرس‌ها** | `/api/addresses` | احراز هویت |
| **الگوی نمونه** | `/api/sample` (GET/POST) | احراز هویت |
| **دانلود نمونه** | `/api/sample/file` | احراز هویت |
| **گردونه شانس** | `/api/wheel` + `/api/wheel/spin` | احراز هویت |
| **درخواست شارژ** | `/api/wallet/topup-request` | احراز هویت |
| **ارسال رسید شارژ** | `/api/wallet/topup-receipt` | احراز هویت |
| **وضعیت ورود اجباری** | `/api/force-join-status` | احراز هویت |
| **اطلاعات کاربر** | `/api/me` | احراز هویت |
| **زیرمجموعه‌گیری** | `/api/referral` | احراز هویت |
| **چت پشتیبانی** | `/api/support/messages` | احراز هویت |
| **تیکت‌ها** | `/api/tickets` + `/api/tickets/{id}/messages` | احراز هویت |

### ویژگی‌های فنی Mini App
- احراز هویت: `X-Init-Data` header (HMAC-SHA256 سمت سرور)
- سبد خرید سرور-ساید (SQLite)
- پشتیبانی از محصولات دیجیتال و فیزیکی
- آپلود رسید کارتبهکارت (عکس/PDF، حداکثر 10MB)
- دانلود مستقیم فایل‌های الگو (PDF از Telegram CDN)
- اعلان Push مرورگر (WebPush با VAPID)
- CORS محدود به `MINIAPP_ALLOWED_ORIGINS`

---

## 🖥 پنل مدیریت وب (Admin Panel)

### ماژول‌ها

#### 📊 داشبورد
- آمار فروش (تعداد سفارش، درآمد، کاربران)
- وضعیت سفارش‌های در انتظار
- نمودارهای آماری
- آمار سیستم (CPU, RAM, Disk)

#### 📦 سفارشات
| عملیات | endpoint | مجوز |
|--------|----------|------|
| لیست سفارشات | `GET /api/orders` | orders |
| مشاهده رسید | `GET /api/orders/{id}/receipt` | orders |
| تایید سفارش | `POST /api/orders/{id}/approve` | orders |
| رد سفارش | `POST /api/orders/{id}/reject` | orders |
| ثبت پیگیری | `POST /api/orders/{id}/tracking` | orders |
| تغییر وضعیت ارسال | `POST /api/orders/{id}/fulfillment` | orders |
| لیست سفارشات فیزیکی | `GET /api/orders/physical` | orders |

#### 👛 شارژ کیف پول
| عملیات | endpoint | مجوز |
|--------|----------|------|
| لیست درخواست‌ها | `GET /api/topups` | orders |
| مشاهده رسید | `GET /api/topups/{id}/receipt` | orders |
| تایید شارژ | `POST /api/topups/{id}/approve` | orders |
| رد شارژ | `POST /api/topups/{id}/reject` | orders |

#### 👥 کاربران
| عملیات | endpoint | مجوز |
|--------|----------|------|
| جستجوی کاربران | `GET /api/users?q=&status=` | users |
| جزئیات کاربر | `GET /api/users/{tg_id}` | users |
| مسدودسازی | `POST /api/users/{tg_id}/block` | users |
| رفع مسدودیت | `POST /api/users/{tg_id}/unblock` | users |
| تعدیل کیف پول | `POST /api/users/{tg_id}/wallet` | users |
| تعدیل امتیاز باشگاه | `POST /api/users/{tg_id}/loyalty` | users |

#### 📂 کاتالوگ
| عملیات | endpoint | مجوز |
|--------|----------|------|
| دسته‌بندی‌ها | `GET/POST /api/categories` | catalog |
| ویرایش دسته | `PUT /api/categories/{id}` | catalog |
| فعال/غیرفعال دسته | `POST /api/categories/{id}/toggle` | catalog |
| حذف دسته | `DELETE /api/categories/{id}` | catalog |
| محصولات | `GET/POST /api/products` | catalog |
| ویرایش محصول | `PUT /api/products/{id}` | catalog |
| فعال/غیرفعال محصول | `POST /api/products/{id}/toggle` | catalog |
| حذف محصول | `DELETE /api/products/{id}` | catalog |
| فایل‌های الگو | `GET/POST /api/products/{id}/files` | catalog |
| حذف فایل | `DELETE /api/files/{file_id}` | catalog |
| عکس پیش‌نمایش | `POST /api/products/{id}/preview` | catalog |
| مشاهده پیش‌نمایش | `GET /api/products/{id}/preview` | any admin |
| دانلود فایل | `GET /api/files/{file_id}` | catalog |
| الگوی نمونه | `GET/POST /api/sample-files` | catalog |
| حذف نمونه | `DELETE /api/sample-files/{file_id}` | catalog |

#### 🎟 تخفیف
| عملیات | endpoint | مجوز |
|--------|----------|------|
| لیست کدها | `GET /api/discounts` | discounts |
| ساخت کد | `POST /api/discounts` | discounts |
| فعال/غیرفعال | `POST /api/discounts/{id}/toggle` | discounts |
| حذف کد | `DELETE /api/discounts/{id}` | discounts |

#### 🎫 تیکت و پشتیبانی
| عملیات | endpoint | مجوز |
|--------|----------|------|
| لیست تیکت‌ها | `GET /api/tickets` | tickets |
| پیام‌های تیکت | `GET /api/tickets/{id}/messages` | tickets |
| پاسخ تیکت | `POST /api/tickets/{id}/reply` | tickets |
| بستن تیکت | `POST /api/tickets/{id}/close` | tickets |
| گفتگوی زنده | `GET /api/support/conversations` | any admin |
| پیام‌های چت | `GET /api/support/{user_id}/messages` | any admin |
| پاسخ چت زنده | `POST /api/support/{user_id}/messages` | tickets |

#### 📢 broadcast
- ارسال پیام متنی به تمام کاربران (`POST /api/broadcast`)

#### 🏪 مدیریت تجارت
| عملیات | endpoint | مجوز |
|--------|----------|------|
| سبدهای کاربران | `GET /api/carts` | orders |
| جزئیات سبد | `GET /api/carts/{user_id}` | orders |
| پاک‌سازی سبد | `DELETE /api/carts/{user_id}` | orders |
| حذف قلم | `DELETE /api/carts/{user_id}/{item_id}` | orders |
| موجودی انبار | `GET /api/inventory` | inventory |
| تعدیل موجودی | `POST /api/inventory/{variant_id}` | inventory |
| روش‌های ارسال | `GET/POST /api/shipping/methods` | shipping |
| ویرایش روش ارسال | `PUT /api/shipping/methods/{id}` | shipping |

#### ⚙️ تنظیمات
| بخش | endpoint | مجوز |
|------|----------|------|
| کل تنظیمات | `GET/POST /api/settings` | settings |
| تغییرcommerce | `POST /api/settings/commerce` | settings |
| فعال/غیرفعال cart | `POST /api/settings/commerce/toggle` | settings |
| تنظیمات رفرال | `GET/POST /api/settings/referral` | settings |
| تنظیمات گردونه | `GET/POST /api/settings/wheel` | settings |
| تنظیمات باشگاه | `GET/POST /api/settings/loyalty` | settings |
| چیدمان منو | `GET/POST /api/settings/menu-order` | settings |
| عضویت اجباری | `GET/POST /api/settings/force-join` | settings |

#### 🔧 سیستم
| عملیات | endpoint | مجوز |
|--------|----------|------|
| آمار سیستم | `GET /api/system/stats` | any admin |
| وضعیت جاب‌ها | `GET /api/system/jobs` | system |
| وضعیت بکاپ | `GET /api/system/backup/status` | system |
| ساخت بکاپ | `POST /api/system/backup/create` | backup |
| بازیابی بکاپ | `POST /api/system/backup/restore` | owner |
| ریست دیتابیس | `POST /api/system/db/reset` | owner |

#### 🔔 Web Push
- اشتراک‌گذاری نوتیفیکیشن (`/api/push/subscribe/unsubscribe`)
- تست اعلان (`/api/push/test`)
- نمایش کلید VAPID (`/api/push/vapid-public-key`)

#### 👤 حساب کاربری
- لاگین/لاگ‌آوت
- تغییر رمز عبور
- مشاهده اطلاعات حساب

---

## 🔐 امنیت

| لایه | مکانیزم |
|------|---------|
| **احراز هویت بات** | initData HMAC-SHA256 با bot token |
| **احراز هویت پنل** | cookie-based session (HMAC-signed, 12h expiry) |
| **رمزنگاری رمز** | PBKDF2-HMAC-SHA256 (260,000 iteration) |
| **تراکنش مالی** | `BEGIN IMMEDIATE` + idempotency key |
| **ضد SSRF** | بلاک IPهای خصوصی/لوپبک/`file://` |
| **Rate limiting** | 10 تلاش ناموفق / 15 دقیقه → 5 دقیقه lockout |
| **CORS** | محدود به `MINIAPP_ALLOWED_ORIGINS` |
| **Security headers** | CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff |
| **کوکی امن** | HttpOnly + Secure + SameSite=Lax |
| **کریптоگرافیک RNG** | `secrets.*` به جای `random.*` |
| **SQL injection** | تمام کوئری‌ها parameterized با `?` |

> برای گزارش کامل: [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md) — امتیاز 82/100

---

## 🚀 نصب سریع

### پیشنیاز
- Python 3.10+
- git
- دسترسی به [BotFather](https://t.me/BotFather)

```bash
git clone https://github.com/designerkiyan-maker/patternshop.git
cd patternshop
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### فایل `.env`

```env
BOT_TOKEN=8726640783:YOUR_BOT_TOKEN_HERE
OWNER_ID=54400109
ADMIN_PANEL_SECRET=BRToI3rdqBcFma9u3T6Lg6jQdKjksZS0UhmEED60
DB_PATH=./bot_database.db

# Mini App
MINIAPP_URL=https://app.yourdomain.com
MINIAPP_ALLOWED_ORIGINS=https://app.yourdomain.com

# Proxy (اختیاری)
TELEGRAM_PROXY=http://your-proxy:8080

# Web Push (اختیاری)
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
```

### اجرای بات

```bash
python main.py
```

### اجرای Mini App

```bash
uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
```

### اجرای پنل مدیریت وب

```bash
# ساخت اولین حساب
python -m admin_panel.create_admin <username> <password>

# اجرا
uvicorn admin_panel.server:app --host 127.0.0.1 --port 8002
```

---

## 🚢 نصب پروداکشن روی سرور لینوکس

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

```
patternshop/
├── main.py                 # نقطه ورود asyncio
├── bot_manager.py          # راه‌اندازی بات، middlewareها، backup loop
├── config.py               # بارگذاری .env
├── database.py             # لایه SQLite (3400+ خط)
├── handlers_user.py        # هندلرهای فروش، سبد، کیف پول
├── handlers_admin.py       # هندلرهای پنل مدیریت بات
├── keyboards.py            # کیبوردهای اینلاین و reply
├── states.py               # حالتهای FSM
├── file_delivery.py        # تحویل فایل به کاربر
├── blocked_user.py         # middleware مسدودسازی
├── force_join.py           # بررسی عضویت کانال
├── fsm_storage.py          # ذخیره FSM روی SQLite
├── loyalty.py              # منطق باشگاه مشتریان
├── jalali.py               # تاریخ شمسی
├── backup.py               # بکاپ/بازیابی دیتابیس
├── requirements.txt        # وابستگی‌ها
├── .env.example            # نمونه تنظیمات
│
├── core/
│   ├── telegram_proxy.py   # پروکسی اتصال به Bot API
│   └── vless_client/       # مدیریت اشتراک VLESS (اختیاری)
│
├── services/               # لایه تجاری
│   ├── cart.py             # عملیات سبد خرید
│   ├── checkout.py         # تسویه اتمیک
│   ├── orders.py           # مدیریت سفارشات
│   ├── payments.py         # پردازش پرداخت
│   ├── inventory.py        # مدیریت موجودی
│   ├── shipping.py         # روش‌های ارسال
│   ├── permissions.py      # بررسی مجوزها
│   ├── settings.py         # تنظیمات
│   └── errors.py           # کلاس‌های خطا
│
├── miniapp/                # فروشگاه وب داخل تلگرام
│   ├── server.py           # FastAPI (:8001)
│   ├── auth.py             # اعتبارسنجی initData
│   └── static/             # فرانت‌اند (HTML/JS/CSS)
│
├── admin_panel/            # پنل مدیریت مستقل
│   ├── server.py           # FastAPI (:8002)
│   ├── security.py         # hash/password/token
│   ├── vless_manager.py    # مدیریت VLESS
│   ├── telegram_notify.py  # اعلان‌های تلگرام
│   ├── webpush.py          # WebPush
│   ├── create_admin.py     # ساخت حساب اولیه
│   ├── generate_vapid_keys.py
│   └── static/             # UI پنل مدیریت
│
├── tests/                  # تست‌های واحد
├── deploy/                 # اسکریپت‌های نصب سرور
├── backups/                # بکاپ‌های دیتابیس
└── logs/                   # لاگ‌های اجرا
```

---

## 🔧 تنظیمات کلیدی

### دکمه‌های منوی اصلی
همه دکمه‌ها از طریق پنل مدیریت قابل شخصی‌سازی هستند:

| دکمه | کنترل | پیشفرض |
|------|-------|--------|
| 🛒 خرید الگو | `btn_buy` | primary |
| 🧪 الگوی نمونه | `btn_test` (قابل غیرفعال) | success |
| 🛍 سبد خرید | `btn_cart` (قابل غیرفعال) | primary |
| 📦 سفارشهای من | `btn_my_orders` | — |
| 👛 کیف پول | `btn_wallet` | success |
| 🤝 زیرمجموعهگیری | `btn_referral` (قابل غیرفعال) | — |
| 🎡 گردونه شانس | `btn_wheel` (قابل غیرفعال) | success |
| 🎁 باشگاه مشتریان | `btn_loyalty` (قابل غیرفعال) | — |
| 📞 پشتیبانی | `btn_contact` | — |
| ⚙️ پنل مدیریت | `btn_admin_panel` | danger (فقط ادمین) |

### سطوح دسترسی ادمین

| نقش | مجوزها |
|-----|--------|
| **owner** | 12 مجوز کامل |
| **admin** | 10 مجوز (بدون proxies + backup) |
| **mid** | 5 مجوز (orders, users, tickets, broadcast, inventory) |
| **support** | 1 مجوز (tickets) |

### تنظیمات باشگاه مشتریان

| تنظیم | پیشفرض | توضیح |
|-------|--------|-------|
| `loyalty_enabled` | 1 | خاموش/روشن |
| `loyalty_points_per_toman` | 10000 | هر 10 هزار تومان = 1 امتیاز |
| `loyalty_reg_bonus` | 50 | هدیه ثبتنام |
| `loyalty_referral_bonus` | 20 | هدیه معرفی |
| `loyalty_redeem_points` | 100 | حداقل امتیاز تبدیل |
| `loyalty_redeem_toman` | 10000 | معادل تومان هر تبدیل |
| `loyalty_min_redeem` | 100 | حداقل امتیاز قابل تبدیل |
| `loyalty_max_per_order` | 0 | سقف امتیاز هر سفارش (0=نامحدود) |

### تنظیمات زیرمجموعه‌گیری

| تنظیم | پیشفرض | توضیح |
|-------|--------|-------|
| `referral_enabled` | 1 | پورسانت خرید |
| `referral_percent` | 10 | درصد پورسانت |
| `referral_commission_max_count` | 0 | سقف تعداد نفرات (0=نامحدود) |
| `referral_free_config_enabled` | 0 | الگوی رایگان |
| `referral_free_config_threshold` | 10 | تعداد دعوت لازم |
| `referral_invite_bonus_enabled` | 0 | شارژ ثابت بهازای دعوت |
| `referral_invite_bonus_amount` | 0 | مبلغ شارژ (تومان) |
| `referral_invite_bonus_max_count` | 10 | سقف تعداد |

---

## 🧪 تست

```bash
# تست سینتکس
python -m py_compile main.py bot_manager.py database.py

# تست واحد
python -m pytest tests/ -v

# تست API (نیاز به اجرای سرور دارد)
python -m miniapp.server &
curl http://127.0.0.1:8001/api/catalog
```

---

## 📄 مجوز

MIT

---

## 🙏 تشکر

ساخته شده با ❤️ برای جامعه خیاط‌های ایران.

[🌐 گیت‌هاب](https://github.com/designerkiyan-maker/patternshop)
[📋 گزارش امنیتی](SECURITY_AUDIT_REPORT.md)

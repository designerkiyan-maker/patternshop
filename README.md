<div align="center">

# 🛰️ Shopvpn — بات فروش هوشمند کانفیگ V2Ray

**فروش خودکار کانفیگ V2Ray در تلگرام، همراه با Mini App اختصاصی، پنل مدیریت کامل و سیستم نمایندگی**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-MiniApp-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Made by](https://img.shields.io/badge/Made%20by-Mehdi%20Rafatpanah-orange?style=for-the-badge)](https://github.com/mehdirafatpanah)

[نصب خودکار](#-نصب-خودکار-یک‌خطی-پیشنهادی) •
[نصب دستی](#-نصب-دستی) •
[امکانات](#-امکانات) •
[Mini App](#-mini-app) •
[ساختار پروژه](#-ساختار-پروژه) •
[مدیریت بات](#-مدیریت-بات-managesh)

</div>

---

## 📖 معرفی

**Shopvpn** یک بات تلگرام حرفه‌ای برای فروش کانفیگ‌های V2Ray است که به‌صورت کامل با Python و aiogram 3 نوشته شده و شامل یک **Mini App** اختصاصی (با بک‌اند FastAPI) برای تجربه‌ی خرید مدرن داخل تلگرام است. این پروژه برای استفاده‌ی واقعی و تجاری طراحی شده: پرداخت کارت‌به‌کارت با تایید ادمین، سیستم نمایندگی (ریسلر)، کیف پول، کد تخفیف، چرخ‌شانس، یادآوری تمدید خودکار و بسیاری امکانات دیگر.

## ✨ امکانات

### 🤖 بات اصلی
- 🔑 بانک کانفیگ اختصاصی و یکتا برای هر کاربر
- 💳 پرداخت کارت‌به‌کارت با تایید دستی ادمین
- 🗂️ مدیریت کامل دسته‌بندی و محصولات
- 🧪 کانفیگ تست رایگان با محدودیت قابل‌تنظیم برای هر کاربر
- 👑 پنل مدیریت با پشتیبانی چند ادمین
- 📢 ارسال پیام همگانی (Broadcast)
- 💰 سیستم کیف پول داخلی
- 🤝 سیستم نمایندگی/زیرمجموعه‌گیری با پورسانت
- 🏷️ کد تخفیف اختصاصی
- 🎡 چرخ شانس با احتمال برد و جوایز قابل تنظیم
- ⏰ یادآوری تمدید خودکار همراه با کد تخفیف اختصاصی
- 📱 تحویل کانفیگ به‌صورت QR Code
- 🎨 دکمه‌های رنگی کیبورد تلگرام (Bot API 9.4)
- 🏢 پشتیبانی از بات‌های نمایندگی مستقل (Reseller Bots) با دیتابیس جدا

### 📲 Mini App
- ⚡ بک‌اند FastAPI با احراز هویت امن (HMAC-SHA256 روی initData)
- 🎨 رابط کاربری تیره با فونت فارسی Vazirmatn و JetBrains Mono
- 🛍️ فروشگاه، کیف پول، چرخ شانس، نمایندگی و کانفیگ تست در قالب تب‌های اختصاصی
- 🔔 بنر هشدار انقضا/تمدید در صفحه‌ی اصلی
- 💬 پشتیبانی داخل اپلیکیشن

## 🖥️ پیش‌نیازها

| مورد | حداقل نسخه |
|---|---|
| سیستم‌عامل | Ubuntu 20.04+ / Debian 11+ |
| Python | 3.10+ |
| دسترسی سرور | یک VPS با آی‌پی ثابت و آپتایم بالا (توصیه می‌شود) |

> ⚠️ **نکته امنیتی مهم:** هرگز توکن بات یا فایل `.env` خودت را در جای عمومی (گیت‌هاب، چت، فوروم) قرار نده. اگر توکنی به‌اشتباه منتشر شد، فوراً از طریق [@BotFather](https://t.me/BotFather) با دستور `/revoke` توکن جدید بگیر.

---

## 🚀 نصب خودکار (یک‌خطی، پیشنهادی)

برای نصب کامل بات روی یک سرور تازه (Ubuntu/Debian)، فقط این دستور را در ترمینال سرور اجرا کن:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mehdirafatpanah/Shopvpn/main/manage.sh)
```

این اسکریپت به‌صورت خودکار:

1. ✅ پیش‌نیازهای سیستمی (`git`, `python3`, `pip`, `venv`) را نصب می‌کند
2. ✅ پروژه را از گیت‌هاب کلون می‌کند (یا در صورت وجود، آپدیت می‌کند)
3. ✅ محیط مجازی پایتون را می‌سازد و پکیج‌ها را نصب می‌کند
4. ✅ توکن بات و آیدی عددی ادمین را از تو می‌پرسد و فایل `.env` را می‌سازد
5. ✅ یک سرویس `systemd` می‌سازد تا بات همیشه در حال اجرا بماند و بعد از ری‌استارت سرور هم خودکار بالا بیاید

بعد از پایان نصب می‌توانی با دستورهای زیر وضعیت بات را مدیریت کنی:

```bash
sudo systemctl status v2raybot     # وضعیت بات
sudo journalctl -u v2raybot -f     # مشاهده لاگ زنده
sudo systemctl restart v2raybot    # ری‌استارت
sudo systemctl stop v2raybot       # توقف
```

برای آپدیت بات در آینده، کافیست همان دستور نصب یک‌خطی بالا را دوباره اجرا کنی (idempotent است و اطلاعات `.env` را دست‌نخورده نگه می‌دارد)، یا از [پنل مدیریت متنی (`manage.sh`)](#-مدیریت-بات-managesh) استفاده کنی که تمام این کارها (نصب، آپدیت، ری‌استارت، مشاهده‌ی لاگ و ...) را با یک منوی ساده انجام می‌دهد:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mehdirafatpanah/Shopvpn/main/manage.sh)
```

---

## 🛠 نصب دستی

اگر ترجیح می‌دهی مراحل را دستی و قدم‌به‌قدم انجام دهی:

**۱. کلون کردن پروژه**
```bash
git clone https://github.com/mehdirafatpanah/Shopvpn.git
cd Shopvpn
```

**۲. ساخت محیط مجازی و نصب پکیج‌ها**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**۳. تنظیم فایل `.env`**
```bash
cp .env.example .env
nano .env
```

مقادیر زیر را در فایل `.env` قرار بده:
```env
BOT_TOKEN=توکن_واقعی_بات
OWNER_ID=آیدی_عددی_تو
```

> 🔒 فایل `.env` هرگز نباید وارد گیت‌هاب شود (در `.gitignore` قرار دارد). فقط `.env.example` بدون مقدار واقعی در ریپازیتوری نگه‌داری می‌شود.

**۴. اجرا**
```bash
python main.py
```

اگر همه‌چیز درست باشد، بات بلافاصله روشن می‌شود و آماده‌ی دریافت پیام است. دیتابیس به‌صورت خودکار در همان پوشه ساخته می‌شود (`bot_database.db`)؛ نیازی به نصب هیچ دیتابیس جداگانه‌ای نیست.

**۵. اجرای دائمی (بدون بستن ترمینال)**

```bash
# روش ساده با screen
screen -S v2raybot
python main.py
# سپس Ctrl+A و D برای خروج بدون بستن بات

# یا با nohup
nohup python main.py > bot.log 2>&1 &
```

بهترین روش برای پروداکشن، ساخت یک سرویس `systemd` است (که [نصب خودکار](#-نصب-خودکار-یک‌خطی-پیشنهادی) این کار را خودش انجام می‌دهد).

> 💡 بعد از نصب دستی هم می‌توانی مدیریت روزمره‌ی بات (وضعیت، لاگ، ری‌استارت، آمار فروش و Mini App) را با [پنل مدیریت متنی (`manage.sh`)](#-مدیریت-بات-managesh) انجام دهی.

---

## 🧰 مدیریت بات (`manage.sh`)

یک پنل متنی رنگی و تعاملی برای مدیریت کامل بات بدون نیاز به یادآوری دستورات:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mehdirafatpanah/Shopvpn/main/manage.sh)
```

| گزینه | عملکرد |
|:---:|---|
| 1 | نصب کامل بات (اولین بار) |
| 2 | آپدیت بات |
| 3 | حذف کامل بات از سرور |
| 4 | مشاهده وضعیت بات |
| 5 | مشاهده لاگ زنده |
| 6 | ری‌استارت بات |
| 7 | توقف بات |
| 8 | مشاهده آمار فروش |
| 9 | تغییر توکن یا آیدی ادمین |
| 10 | نصب/تنظیم Mini App (خودکار: دامنه + SSL + سرویس) |
| 11 | حذف Mini App |
| 12 | آپدیت Mini App |

---

## 📱 Mini App

پوشه‌ی `miniapp/` شامل یک اپلیکیشن کامل تلگرام (Telegram Mini App) است:

- **بک‌اند:** FastAPI با احراز هویت امن initData (HMAC-SHA256) — آیدی کاربر همیشه سمت سرور استخراج می‌شود
- **فرانت‌اند:** HTML/CSS/JS خالص (بدون فریم‌ورک)، تم تیره با رنگ‌های سرمه‌ای/کهربایی/فیروزه‌ای
- **فونت‌ها:** Vazirmatn برای فارسی، JetBrains Mono برای اعداد و کد
- **قابلیت‌ها:** پروفایل، تاریخچه سفارش‌ها، فروشگاه، خرید، چرخ شانس، شارژ کیف پول، آمار زیرمجموعه‌گیری، هشدار تمدید، پشتیبانی

برای نصب و اتصال Mini App به دامنه‌ی خودت (با SSL خودکار)، از گزینه‌ی ۱۰ در `manage.sh` استفاده کن.

---

## 🗂 ساختار پروژه

| فایل / پوشه | توضیح |
|---|---|
| `main.py` | نقطه‌ی شروع اجرای بات |
| `config.py` | توکن بات اصلی، آیدی مالک، مسیر دیتابیس |
| `database.py` | کلاس `Database` — هر بات (اصلی/نمایندگی) یک نمونه‌ی مستقل دارد |
| `bot_manager.py` | مدیریت اجرای همزمان چند بات (نمایندگی) با asyncio polling |
| `handlers_user.py` | هندلرهای مربوط به کاربر عادی |
| `handlers_admin.py` | هندلرهای پنل مدیریت |
| `keyboards.py` | کیبوردها و دکمه‌های شیشه‌ای/معمولی تلگرام |
| `states.py` | تعریف State های FSM برای مکالمات چندمرحله‌ای |
| `config_delivery.py` | تحویل کانفیگ (متن + QR Code) |
| `renewal_reminders.py` | یادآوری خودکار تمدید سرویس |
| `force_join.py` | عضویت اجباری در کانال/گروه |
| `miniapp/` | Mini App (بک‌اند FastAPI + فرانت‌اند) |
| `install.sh` | اسکریپت نصب/آپدیت خودکار یک‌خطی |
| `manage.sh` | پنل مدیریت متنی تعاملی |
| `update.sh` | اسکریپت آپدیت سریع |
| `requirements.txt` | وابستگی‌های پایتون |

---

## 🧪 تکنولوژی‌های استفاده‌شده

| بخش | تکنولوژی |
|---|---|
| زبان اصلی | Python 3.10+ |
| فریم‌ورک بات | [aiogram 3](https://docs.aiogram.dev/) |
| دیتابیس | SQLite |
| بک‌اند Mini App | FastAPI + Uvicorn |
| فرانت‌اند Mini App | HTML, CSS, JavaScript خالص |
| مدیریت سرور | systemd, Bash, Nginx |
| کنترل نسخه | Git / GitHub |

---

## 🤝 مشارکت (Contributing)

خوشحال می‌شوم اگر پیشنهاد، باگ یا Pull Request داری، از طریق [Issues](https://github.com/mehdirafatpanah/Shopvpn/issues) مطرح کنی.

## 📄 مجوز

این پروژه تحت مجوز [MIT](LICENSE) منتشر شده است.

## 👤 سازنده

ساخته‌شده با ❤️ توسط **مهدی رفعت‌پناه**

[![GitHub](https://img.shields.io/badge/GitHub-mehdirafatpanah-181717?style=for-the-badge&logo=github)](https://github.com/mehdirafatpanah)

<div align="center">

اگر این پروژه برایت مفید بود، یک ⭐ فراموش نشود!

</div>

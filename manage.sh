#!/bin/bash
# ============================================================================
# پنل مدیریت متنی بات فروش کانفیگ V2Ray
#
# اجرای مستقیم (بدون نصب قبلی):
#   bash <(curl -fsSL https://raw.githubusercontent.com/USERNAME/v2ray-bot/main/manage.sh)
#
# اجرای بعد از نصب:
#   bash ~/v2ray_bot/manage.sh
# ============================================================================

# ---------------------------------------------------------------------------
# تنظیمات قابل شخصی‌سازی
# ---------------------------------------------------------------------------
REPO_URL="https://github.com/mehdirafatpanah/Shopvpn.git"
INSTALL_DIR="$HOME/v2ray_bot"
SERVICE_NAME="v2raybot"
BRAND_NAME="VPN HUNTER"
VERSION="v1.0"

# جلوگیری از گیر کردن apt پشت پنجره‌های تعاملی (مثل پرسش needrestart برای ری‌استارت سرویس‌ها)
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

# ---------------------------------------------------------------------------
# رنگ‌ها
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# نوار عنوان / بنر
# ---------------------------------------------------------------------------
ensure_figlet() {
    if ! command -v figlet &> /dev/null; then
        echo -e "${CYAN}🔤 در حال آماده‌سازی فونت نمایش (فقط بار اول، چند ثانیه طول می‌کشد)...${RESET}"
        sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 apt-get update -qq
        timeout 60 sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 apt-get install -y -qq figlet
        if ! command -v figlet &> /dev/null; then
            echo -e "${YELLOW}⚠️ نصب figlet انجام نشد، بنر ساده نمایش داده می‌شود.${RESET}"
            sleep 1
        fi
    fi
}

print_banner() {
    clear
    echo -e "${MAGENTA}╔══════════════════════════════════════════════════════════╗${RESET}"
    if command -v figlet &> /dev/null; then
        echo -e "${CYAN}${BOLD}$(figlet -f standard "$BRAND_NAME" 2>/dev/null)${RESET}"
    else
        echo -e "${CYAN}${BOLD}                     $BRAND_NAME${RESET}"
    fi
    echo -e "${YELLOW}                 B O T   M A N A G E M E N T   E N G I N E   $VERSION${RESET}"
    echo -e "${MAGENTA}╚══════════════════════════════════════════════════════════╝${RESET}"
    echo ""
}

print_status_line() {
    if [ ! -d "$INSTALL_DIR" ]; then
        echo -e "System Status: ${YELLOW}نصب نشده${RESET}"
    elif systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "System Status: ${GREEN}${BOLD}Engine Ready ✅ (بات در حال اجراست)${RESET}"
    else
        echo -e "System Status: ${RED}${BOLD}متوقف ⛔️${RESET}"
    fi

    MINIAPP_SERVICE="${SERVICE_NAME}-miniapp"
    if systemctl list-unit-files 2>/dev/null | grep -q "^${MINIAPP_SERVICE}.service"; then
        if systemctl is-active --quiet "$MINIAPP_SERVICE" 2>/dev/null; then
            echo -e "Mini App Status: ${GREEN}${BOLD}در حال اجراست ✅${RESET}"
        else
            echo -e "Mini App Status: ${RED}${BOLD}متوقف ⛔️${RESET}"
        fi
    else
        echo -e "Mini App Status: ${YELLOW}نصب نشده${RESET}"
    fi

    echo -e "${CYAN}──────────────────────────────────────────────────────────────${RESET}"
}

pause() {
    echo ""
    read -rp "برای بازگشت به منو، Enter را بزن..." _
}

# ---------------------------------------------------------------------------
# عملیات: نصب اولیه کامل
# ---------------------------------------------------------------------------
install_bot() {
    echo -e "${CYAN}📦 بررسی و نصب پیش‌نیازها (git, python3, pip, venv, figlet)...${RESET}"
    sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 apt-get update -qq
    timeout 120 sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 apt-get install -y -qq git python3 python3-pip python3-venv figlet > /dev/null

    if [ -d "$INSTALL_DIR/.git" ]; then
        echo -e "${YELLOW}⚠️ پروژه از قبل نصب شده است. در حال دریافت آخرین نسخه...${RESET}"
        cd "$INSTALL_DIR"
        git pull
    else
        echo -e "${CYAN}📥 دریافت پروژه از گیت‌هاب...${RESET}"
        git clone "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi

    echo -e "${CYAN}🐍 آماده‌سازی محیط پایتون...${RESET}"
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate

    if [ ! -f "$INSTALL_DIR/.env" ]; then
        echo ""
        echo -e "${YELLOW}${BOLD}🔑 اطلاعات بات را وارد کن:${RESET}"
        read -rp "توکن بات (از BotFather): " BOT_TOKEN_INPUT
        read -rp "آیدی عددی ادمین: " OWNER_ID_INPUT
        cat > "$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN_INPUT
OWNER_ID=$OWNER_ID_INPUT
EOF
        echo -e "${GREEN}✅ فایل .env ساخته شد.${RESET}"
    else
        echo -e "${GREEN}✅ فایل .env از قبل موجود است، دست‌نخورده باقی می‌ماند.${RESET}"
    fi

    echo -e "${CYAN}⚙️ ساخت سرویس systemd...${RESET}"
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=V2Ray Telegram Sales Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/main.py
Restart=always
RestartSec=5
User=$(whoami)

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME" > /dev/null 2>&1
    sudo systemctl restart "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}${BOLD}✅ نصب کامل شد و بات در حال اجراست.${RESET}"
    else
        echo -e "${RED}⚠️ بات اجرا نشد. برای بررسی خطا: sudo journalctl -u $SERVICE_NAME -n 50 --no-pager${RESET}"
    fi
}

# ---------------------------------------------------------------------------
# عملیات: آپدیت
# ---------------------------------------------------------------------------
update_bot() {
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo -e "${RED}⛔️ بات هنوز نصب نشده. اول گزینه ۱ (نصب) را بزن.${RESET}"
        return
    fi
    cd "$INSTALL_DIR"
    echo -e "${CYAN}🔄 دریافت آخرین تغییرات از گیت‌هاب...${RESET}"
    git pull
    echo -e "${CYAN}🐍 آپدیت پکیج‌ها...${RESET}"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate
    echo -e "${CYAN}♻️ ری‌استارت سرویس بات...${RESET}"
    sudo systemctl restart "$SERVICE_NAME"
    sleep 2
    echo -e "${GREEN}✅ آپدیت بات انجام شد.${RESET}"
}

# ---------------------------------------------------------------------------
# عملیات: آپدیت مینی‌اپ
# ---------------------------------------------------------------------------
update_miniapp() {
    MINIAPP_SERVICE="${SERVICE_NAME}-miniapp"
    if ! systemctl list-units --full -all | grep -q "${MINIAPP_SERVICE}.service"; then
        echo -e "${RED}⛔️ مینی‌اپ هنوز نصب نشده. اول گزینه ۱۰ (نصب/تنظیم مینی‌اپ) را بزن.${RESET}"
        return
    fi
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo -e "${RED}⛔️ بات هنوز نصب نشده. اول گزینه ۱ (نصب) را بزن.${RESET}"
        return
    fi
    cd "$INSTALL_DIR"
    echo -e "${CYAN}🔄 دریافت آخرین تغییرات از گیت‌هاب...${RESET}"
    git pull
    echo -e "${CYAN}🐍 آپدیت پکیج‌ها...${RESET}"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate
    echo -e "${CYAN}♻️ ری‌استارت سرویس مینی‌اپ...${RESET}"
    sudo systemctl restart "$MINIAPP_SERVICE"
    sleep 2
    echo -e "${GREEN}✅ آپدیت مینی‌اپ انجام شد.${RESET}"
}

# ---------------------------------------------------------------------------
# عملیات: حذف کامل
# ---------------------------------------------------------------------------
uninstall_bot() {
    echo -e "${RED}${BOLD}⚠️ این کار سرویس بات را کاملاً حذف می‌کند.${RESET}"
    read -rp "آیا مطمئن هستی؟ (yes برای تایید): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo -e "${YELLOW}لغو شد.${RESET}"
        return
    fi
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo systemctl daemon-reload
    echo -e "${GREEN}✅ سرویس حذف شد.${RESET}"

    read -rp "آیا فایل‌های پروژه (شامل دیتابیس مشتری‌ها) هم پاک شود؟ (yes برای تایید): " CONFIRM2
    if [ "$CONFIRM2" == "yes" ]; then
        rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}✅ فایل‌های پروژه هم حذف شدند.${RESET}"
    else
        echo -e "${CYAN}فایل‌های پروژه در $INSTALL_DIR باقی ماندند.${RESET}"
    fi
}

# ---------------------------------------------------------------------------
# عملیات: وضعیت / لاگ / ری‌استارت / توقف
# ---------------------------------------------------------------------------
view_status() {
    sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
}

view_logs() {
    echo -e "${CYAN}برای خروج از حالت لاگ زنده: Ctrl+C${RESET}"
    sleep 1
    sudo journalctl -u "$SERVICE_NAME" -f
}

restart_bot() {
    sudo systemctl restart "$SERVICE_NAME"
    sleep 1
    echo -e "${GREEN}✅ بات ری‌استارت شد.${RESET}"
}

stop_bot() {
    sudo systemctl stop "$SERVICE_NAME"
    echo -e "${YELLOW}⛔️ بات متوقف شد.${RESET}"
}

# ---------------------------------------------------------------------------
# عملیات: آمار فروش سریع (مستقیم از دیتابیس، بدون نیاز به روشن بودن بات)
# ---------------------------------------------------------------------------
show_stats() {
    if [ ! -f "$INSTALL_DIR/bot_database.db" ]; then
        echo -e "${RED}دیتابیسی پیدا نشد.${RESET}"
        return
    fi
    cd "$INSTALL_DIR"
    source venv/bin/activate
    python3 - <<'PYEOF'
import database as db
s = db.get_stats()
print(f"\n👥 تعداد کاربران: {s['users']}")
print(f"⏳ سفارش‌های در انتظار: {s['pending']}")
print(f"✅ سفارش‌های تایید شده: {s['approved']}")
print(f"❌ سفارش‌های رد شده: {s['rejected']}")
print(f"💰 مجموع فروش: {s['revenue']:,} تومان\n")
PYEOF
    deactivate
}

# ---------------------------------------------------------------------------
# عملیات: تغییر توکن یا آیدی ادمین
# ---------------------------------------------------------------------------
edit_env() {
    read -rp "توکن جدید بات (اگر تغییری نیست Enter بزن): " NEW_TOKEN
    read -rp "آیدی عددی جدید ادمین (اگر تغییری نیست Enter بزن): " NEW_OWNER

    CUR_TOKEN=$(grep BOT_TOKEN "$INSTALL_DIR/.env" | cut -d '=' -f2)
    CUR_OWNER=$(grep OWNER_ID "$INSTALL_DIR/.env" | cut -d '=' -f2)

    [ -n "$NEW_TOKEN" ] && CUR_TOKEN="$NEW_TOKEN"
    [ -n "$NEW_OWNER" ] && CUR_OWNER="$NEW_OWNER"

    cat > "$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=$CUR_TOKEN
OWNER_ID=$CUR_OWNER
EOF
    echo -e "${GREEN}✅ ذخیره شد. در حال ری‌استارت...${RESET}"
    sudo systemctl restart "$SERVICE_NAME"
}

# ---------------------------------------------------------------------------
# عملیات: نصب/تنظیم کامل مینی‌اپ (دامنه + SSL + nginx + سرویس، همه خودکار)
# ---------------------------------------------------------------------------
setup_miniapp() {
    if [ ! -d "$INSTALL_DIR/miniapp" ]; then
        echo -e "${RED}⛔️ پوشه miniapp پیدا نشد. اول باید کد مینی‌اپ را داخل پروژه بیاوری (git pull/آپدیت).${RESET}"
        return
    fi

    read -rp "دامنه‌ای که به IP همین سرور اشاره می‌کند را وارد کن (مثلاً shop.example.com): " DOMAIN
    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}دامنه خالی است، لغو شد.${RESET}"
        return
    fi

    echo -e "${CYAN}🔎 بررسی DNS دامنه...${RESET}"
    SERVER_IP=$(curl -fsSL ifconfig.me || echo "")
    DOMAIN_IP=$(getent ahosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1)
    if [ -n "$SERVER_IP" ] && [ -n "$DOMAIN_IP" ] && [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
        echo -e "${YELLOW}⚠️ هشدار: دامنه به IP این سرور ($SERVER_IP) اشاره نمی‌کند (الان $DOMAIN_IP است).${RESET}"
        read -rp "همچنان ادامه بدهم؟ (yes برای ادامه): " CONT
        [ "$CONT" != "yes" ] && return
    fi

    echo -e "${CYAN}📦 نصب nginx و certbot...${RESET}"
    sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 apt-get update -qq
    timeout 120 sudo env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1 \
        apt-get install -y -qq nginx certbot python3-certbot-nginx > /dev/null

    echo -e "${CYAN}🐍 نصب پکیج‌های مینی‌اپ (fastapi, uvicorn)...${RESET}"
    cd "$INSTALL_DIR"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate

    echo -e "${CYAN}⚙️ ساخت سرویس systemd برای بک‌اند مینی‌اپ...${RESET}"
    MINIAPP_SERVICE="${SERVICE_NAME}-miniapp"
    sudo bash -c "cat > /etc/systemd/system/${MINIAPP_SERVICE}.service" <<EOF
[Unit]
Description=V2Ray Mini App Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5
User=$(whoami)

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable "$MINIAPP_SERVICE" > /dev/null 2>&1
    sudo systemctl restart "$MINIAPP_SERVICE"

    echo -e "${CYAN}🌐 تنظیم nginx برای $DOMAIN...${RESET}"
    sudo bash -c "cat > /etc/nginx/sites-available/${DOMAIN}.conf" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    sudo ln -sf "/etc/nginx/sites-available/${DOMAIN}.conf" "/etc/nginx/sites-enabled/${DOMAIN}.conf"
    if ! sudo nginx -t > /dev/null 2>&1; then
        echo -e "${RED}⛔️ کانفیگ nginx خطا دارد. جزئیات: $(sudo nginx -t 2>&1)${RESET}"
        return
    fi
    sudo systemctl reload nginx

    echo -e "${CYAN}🔐 دریافت گواهی SSL رایگان (Let's Encrypt)...${RESET}"
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
        --register-unsafely-without-email --redirect
    if [ $? -ne 0 ]; then
        echo -e "${RED}⛔️ دریافت SSL ناموفق بود. مطمئن شو دامنه درست به این سرور اشاره می‌کند و پورت 80/443 باز است.${RESET}"
        return
    fi

    echo -e "${CYAN}📝 ثبت آدرس مینی‌اپ در .env...${RESET}"
    if grep -q "^MINIAPP_URL=" "$INSTALL_DIR/.env" 2>/dev/null; then
        sed -i "s|^MINIAPP_URL=.*|MINIAPP_URL=https://$DOMAIN|" "$INSTALL_DIR/.env"
    else
        echo "MINIAPP_URL=https://$DOMAIN" >> "$INSTALL_DIR/.env"
    fi

    sudo systemctl restart "$SERVICE_NAME"

    echo -e "${GREEN}${BOLD}✅ مینی‌اپ آماده است: https://$DOMAIN${RESET}"
    echo -e "${GREEN}دکمه «✨ مینی‌اپ فروشگاه» از الان در منوی بات دیده می‌شود.${RESET}"
}

# ---------------------------------------------------------------------------
# عملیات: حذف کامل مینی‌اپ
# ---------------------------------------------------------------------------
remove_miniapp() {
    echo -e "${RED}${BOLD}⚠️ این کار سرویس و کانفیگ nginx مینی‌اپ را حذف می‌کند (گواهی SSL نگه داشته می‌شود).${RESET}"
    read -rp "آیا مطمئن هستی؟ (yes برای تایید): " CONFIRM
    [ "$CONFIRM" != "yes" ] && { echo -e "${YELLOW}لغو شد.${RESET}"; return; }

    MINIAPP_SERVICE="${SERVICE_NAME}-miniapp"
    sudo systemctl stop "$MINIAPP_SERVICE" 2>/dev/null || true
    sudo systemctl disable "$MINIAPP_SERVICE" 2>/dev/null || true
    sudo rm -f "/etc/systemd/system/${MINIAPP_SERVICE}.service"
    sudo systemctl daemon-reload

    read -rp "دامنه‌ای که برای مینی‌اپ استفاده کرده بودی چه بود؟ (برای حذف کانفیگ nginx): " DOMAIN
    if [ -n "$DOMAIN" ]; then
        sudo rm -f "/etc/nginx/sites-enabled/${DOMAIN}.conf" "/etc/nginx/sites-available/${DOMAIN}.conf"
        sudo systemctl reload nginx 2>/dev/null || true
    fi

    if grep -q "^MINIAPP_URL=" "$INSTALL_DIR/.env" 2>/dev/null; then
        sed -i "/^MINIAPP_URL=/d" "$INSTALL_DIR/.env"
    fi
    sudo systemctl restart "$SERVICE_NAME" 2>/dev/null || true
    echo -e "${GREEN}✅ مینی‌اپ حذف شد.${RESET}"
}

# ---------------------------------------------------------------------------
# منوی اصلی
# ---------------------------------------------------------------------------
ensure_figlet

while true; do
    print_banner
    print_status_line
    echo ""
    echo -e "${BLUE}[1]${RESET} » ${GREEN}نصب کامل بات (اولین بار)${RESET}"
    echo -e "${BLUE}[2]${RESET} » ${GREEN}آپدیت بات${RESET}"
    echo -e "${BLUE}[3]${RESET} » ${GREEN}حذف کامل بات از سرور${RESET}"
    echo -e "${CYAN}──────────────────────────────────────────────────────────────${RESET}"
    echo -e "${BLUE}[4]${RESET} » ${GREEN}مشاهده وضعیت بات${RESET}"
    echo -e "${BLUE}[5]${RESET} » ${GREEN}مشاهده لاگ زنده${RESET}"
    echo -e "${BLUE}[6]${RESET} » ${GREEN}ری‌استارت بات${RESET}"
    echo -e "${BLUE}[7]${RESET} » ${GREEN}توقف بات${RESET}"
    echo -e "${CYAN}──────────────────────────────────────────────────────────────${RESET}"
    echo -e "${YELLOW}[8]${RESET} » ${GREEN}مشاهده آمار فروش${RESET}"
    echo -e "${YELLOW}[9]${RESET} » ${GREEN}تغییر توکن یا آیدی ادمین${RESET}"
    echo -e "${CYAN}──────────────────────────────────────────────────────────────${RESET}"
    echo -e "${YELLOW}[10]${RESET} » ${GREEN}نصب/تنظیم مینی‌اپ (خودکار: دامنه + SSL + سرویس)${RESET}"
    echo -e "${YELLOW}[11]${RESET} » ${GREEN}حذف مینی‌اپ${RESET}"
    echo -e "${YELLOW}[12]${RESET} » ${GREEN}آپدیت مینی‌اپ${RESET}"
    echo -e "${CYAN}──────────────────────────────────────────────────────────────${RESET}"
    echo -e "${RED}[0]${RESET} » ${GREEN}خروج${RESET}"
    echo -e "${CYAN}──────────────────────────────────────────────────────────────${RESET}"
    echo ""
    read -rp "$(echo -e ${MAGENTA}${BOLD}"Enter choice [0-12]: "${RESET})" choice

    case $choice in
        1) install_bot; pause ;;
        2) update_bot; pause ;;
        12) update_miniapp; pause ;;
        3) uninstall_bot; pause ;;
        4) view_status; pause ;;
        5) view_logs ;;
        6) restart_bot; pause ;;
        7) stop_bot; pause ;;
        8) show_stats; pause ;;
        9) edit_env; pause ;;
        10) setup_miniapp; pause ;;
        11) remove_miniapp; pause ;;
        0) echo -e "${CYAN}خدانگهدار 👋${RESET}"; exit 0 ;;
        *) echo -e "${RED}گزینه نامعتبر است.${RESET}"; sleep 1 ;;
    esac
done

#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# نصب ایزوله‌ی «فروشگاه الگوی خیاطی» روی سرور (Ubuntu 20.04+ / Debian 11+)
#
#   همه‌چیز داخل /opt/patternshop نصب می‌شود (repo + venv + دیتابیس + .env)
#   و دو سرویس systemd اختصاصی می‌سازد. به جز همین پوشه، هیچ‌جای سرور را
#   تغییر نمی‌دهد (اختیاری: nginx هم فقط یک site-file اضافه می‌کند).
#
# استفاده:
#   1) نصب پایه (بات + مینی‌اپ):
#        sudo REPO_URL=https://github.com/USER/patternshop.git bash deploy/install_server.sh
#      (توکن و OWNER_ID را از تو می‌پرسد؛ یا از قبل به‌صورت متغیر بده:
#        sudo BOT_TOKEN=... OWNER_ID=... REPO_URL=... bash deploy/install_server.sh)
#
#   2) بعداً اضافه‌کردن دامنه + SSL (nginx و certbot):
#        sudo bash deploy/install_server.sh --domain shop.example.com
#      (MINIAPP_URL هم خودکار در .env ست و بات ری‌استارت می‌شود)
#
#   3) پنل مدیریت وب (اختیاری):
#        sudo bash deploy/install_server.sh --panel panel.example.com
# ---------------------------------------------------------------------------
set -euo pipefail

INSTALL_DIR="/opt/patternshop"
REPO_DIR="$INSTALL_DIR/repo"
VENV="$INSTALL_DIR/venv"

if [ "$EUID" -ne 0 ]; then
  echo "لطفاً با sudo اجرا کن: sudo bash $0"; exit 1
fi

apt_get() { DEBIAN_FRONTEND=noninteractive apt-get -yqq "$@" >/dev/null; }

# ---------- 1) پیش‌نیازها ----------
echo "==> نصب پیش‌نیازهای سیستمی..."
apt_get update
apt_get install python3 python3-venv python3-pip git

# ---------- 2) کد ----------
echo "==> دریافت/به‌روزرسانی کد در $REPO_DIR ..."
mkdir -p "$INSTALL_DIR"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
else
  REPO_URL="${REPO_URL:-}"
  [ -n "$REPO_URL" ] || { read -rp "آدرس ریپوی گیت‌هاب: " REPO_URL; }
  git clone "$REPO_URL" "$REPO_DIR"
fi

# ---------- 3) venv و وابستگی‌ها ----------
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" -q install --upgrade pip
"$VENV/bin/pip" -q install -r "$REPO_DIR/requirements.txt"

# ---------- 4) فایل .env (فقط بار اول) ----------
if [ ! -f "$INSTALL_DIR/.env" ]; then
  BOT_TOKEN="${BOT_TOKEN:-}"
  OWNER_ID="${OWNER_ID:-}"
  [ -n "$BOT_TOKEN" ] || { read -rp "BOT_TOKEN (از BotFather): " BOT_TOKEN; }
  [ -n "$OWNER_ID" ]  || { read -rp "OWNER_ID (آیدی عددی مالک): " OWNER_ID; }
  cat > "$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
OWNER_ID=$OWNER_ID
EOF
  chmod 600 "$INSTALL_DIR/.env"
  echo "==> .env ساخته شد."
else
  echo "==> .env از قبل موجود است (دست نخورد)."
fi

# ---------- 5) سرویس‌های systemd ----------
cat > /etc/systemd/system/patternshop-bot.service <<EOF
[Unit]
Description=Pattern Shop - Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$REPO_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/patternshop-miniapp.service <<EOF
[Unit]
Description=Pattern Shop - Mini App (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$REPO_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV/bin/uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now patternshop-bot patternshop-miniapp

echo "✅ نصب پایه کامل شد:"
echo "   - بات:      systemctl status patternshop-bot      (لاگ: journalctl -u patternshop-bot -f)"
echo "   - مینی‌اپ:  systemctl status patternshop-miniapp  (روی 127.0.0.1:8001)"

# ---------- 6) دامنه + SSL (اختیاری) ----------
MODE="${1:-}"
case "$MODE" in
  --domain)
    DOMAIN="${2:-}"
    [ -n "$DOMAIN" ] || { echo "دامنه را بده: --domain shop.example.com"; exit 1; }
    echo "==> نصب nginx + certbot و تنظیم $DOMAIN ..."
    apt_get install nginx certbot python3-certbot-nginx
    cat > /etc/nginx/sites-available/patternshop <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 60m;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/patternshop /etc/nginx/sites-enabled/patternshop
    nginx -t
    systemctl reload nginx
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || \
      echo "⚠️ certbot ناموفق بود؛ اگر دامنه پشت پروکسی کلادفلر است، از Origin Certificate استفاده کن."
    grep -q "^MINIAPP_URL=" "$INSTALL_DIR/.env" || echo "MINIAPP_URL=https://$DOMAIN" >> "$INSTALL_DIR/.env"
    systemctl restart patternshop-bot
    echo "✅ مینی‌اپ روی https://$DOMAIN و دکمه‌ی فروشگاه در بات فعال شد."
    ;;
  --panel)
    PANEL_DOMAIN="${2:-}"
    [ -n "$PANEL_DOMAIN" ] || { echo "دامنه را بده: --panel panel.example.com"; exit 1; }
    echo "==> نصب پنل مدیریت وب روی $PANEL_DOMAIN ..."
    apt_get install nginx certbot python3-certbot-nginx
    cat > /etc/systemd/system/patternshop-panel.service <<EOF
[Unit]
Description=Pattern Shop - Web Admin Panel (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$REPO_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV/bin/uvicorn admin_panel.server:app --host 127.0.0.1 --port 8002
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now patternshop-panel
    cat > /etc/nginx/sites-available/patternshop-panel <<EOF
server {
    listen 80;
    server_name $PANEL_DOMAIN;

    client_max_body_size 60m;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/patternshop-panel /etc/nginx/sites-enabled/patternshop-panel
    nginx -t
    systemctl reload nginx
    certbot --nginx -d "$PANEL_DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || \
      echo "⚠️ certbot ناموفق بود؛ اگر دامنه پشت پروکسی کلادفلر است، از Origin Certificate استفاده کن."
    echo "✅ پنل مدیریت روی https://$PANEL_DOMAIN فعال شد."
    echo "   اولین حساب owner:  $VENV/bin/python -m admin_panel.create_admin <username> <password>"
    ;;
  *)
    echo "برای دامنه و SSL بعداً اجرا کن:  sudo bash $0 --domain shop.example.com"
    echo "برای پنل مدیریت وب:              sudo bash $0 --panel panel.example.com"
    ;;
esac

#!/bin/bash
# اسکریپت آپدیت بات (نسخه هماهنگ با سرویس systemd که install.sh می‌سازد)
# استفاده: ./update.sh "توضیح کوتاه تغییر"

set -e

cd "$(dirname "$0")"

COMMIT_MSG="${1:-آپدیت بدون توضیح}"
SERVICE_NAME="v2raybot"

echo "📦 ثبت تغییرات در گیت..."
git add .
git commit -m "$COMMIT_MSG" || echo "  (تغییری برای commit نبود)"
git push || echo "  ⚠️ push انجام نشد (شاید remote تنظیم نیست یا نیاز به توکن دارد)"

echo "🐍 آپدیت پکیج‌ها..."
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate

echo "🔄 ری‌استارت سرویس بات..."
sudo systemctl restart "$SERVICE_NAME"
sleep 2

echo "✅ انجام شد."
sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -10


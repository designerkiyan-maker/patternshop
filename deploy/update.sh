#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# بروزرسانی خودکار PatternShop از روی گیت‌هاب
#
# این اسکریپت توسط سرور اجرا میشود (systemd / پنل وب / دستی).
# فقط در صورت موجود بودن REPO_URL در محیط، نسخه جدید را میگیرد.
# اگر دایرکتوری gitrepo وجود نداشته باشد یا pull خطا دهد، هیچ تغییری اعمال نمیشود.
#
# استفاده:
#   sudo bash deploy/update.sh           # اجرای دستی با sudo
#   python -m admin_panel.update_runner  # اجرا از طریق API پنل
# ---------------------------------------------------------------------------
set -euo pipefail

INSTALL_DIR="/opt/patternshop"
REPO_DIR="$INSTALL_DIR/repo"
VENV="$INSTALL_DIR/venv"
LOG_FILE="/var/log/patternshop/update.log"

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

if [ ! -d "$REPO_DIR/.git" ]; then
    log "❌ ریپو یافت نشد: $REPO_DIR/.git"
    exit 1
fi

PREV_HASH=$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
log "🔄 شروع بروزرسانی (وضعیت فعلی: $PREV_HASH)"

# Pull
if git -C "$REPO_DIR" pull --ff-only origin main 2>>"$LOG_FILE"; then
    NEW_HASH=$(git -C "$REPO_DIR" rev-parse --short HEAD)
    log "✅ کد بروزرسانی شد: $PREV_HASH → $NEW_HASH"
else
    log "⚠️ Pull ناموفق بود؛ تغییرات اعمال نشد."
    git -C "$REPO_DIR" status --short >>"$LOG_FILE" 2>&1 || true
    exit 1
fi

# وابستگیها
log "📦 نصب/بروزرسانی وابستگیها..."
"$VENV/bin/pip" -q install -r "$REPO_DIR/requirements.txt" >>"$LOG_FILE" 2>&1 || {
    log "⚠️ pip ناموفق بود؛ ادامه میدهد."
}

# Restart services
log "🔁 ریاستارت سرویسها..."
systemctl restart patternshop-bot 2>>"$LOG_FILE" || log "⚠️ patternshop-bot restart نشد"
systemctl restart patternshop-miniapp 2>>"$LOG_FILE" || log "⚠️ patternshop-miniapp restart نشد"

# Bale bot (اختیاری)
if systemctl is-active --quiet patternshop-bale 2>/dev/null; then
    systemctl restart patternshop-bale 2>>"$LOG_FILE" && log "✅ patternshop-bale ریاستارت شد" || log "⚠️ patternshop-bale restart نشد"
fi

log "✅ بروزرسانی تکمیل شد."

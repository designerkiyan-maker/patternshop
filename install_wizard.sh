#!/usr/bin/env bash
# PatternShop Installation Wizard
# Run: bash <(curl -sSL https://raw.githubusercontent.com/designerkiyan-maker/patternshop/main/install_wizard.sh)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

REPO_URL="https://github.com/designerkiyan-maker/patternshop.git"
INSTALL_DIR="/opt/patternshop/repo"
SERVICE_USER="root"

print_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    PatternShop Installer                       ║"
    echo "║         Telegram Bot + MiniApp + Admin Panel                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERR]${NC} $*"; }

prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local default="$3"
    local is_secret="$4"
    local value=""
    
    while [[ -z "$value" ]]; do
        if [[ -n "$default" ]]; then
            if [[ "$is_secret" == "true" ]]; then
                read -rp "$(echo -e "${CYAN}$prompt [$default]: ${NC}")" -s value
                echo
            else
                read -rp "$(echo -e "${CYAN}$prompt [$default]: ${NC}")" value
            fi
            value="${value:-$default}"
        else
            if [[ "$is_secret" == "true" ]]; then
                read -rp "$(echo -e "${CYAN}$prompt: ${NC}")" -s value
                echo
            else
                read -rp "$(echo -e "${CYAN}$prompt: ${NC}")" value
            fi
        fi
        
        if [[ -z "$value" && -z "$default" ]]; then
            log_err "This field is required."
        fi
    done
    
    eval "$var_name=\"$value\""
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local answer=""
    
    while true; do
        if [[ "$default" == "y" ]]; then
            read -rp "$(echo -e "${CYAN}$prompt [Y/n]: ${NC}")" answer
            answer="${answer:-y}"
        else
            read -rp "$(echo -e "${CYAN}$prompt [y/N]: ${NC}")" answer
            answer="${answer:-n}"
        fi
        case "${answer,,}" in
            y|yes) return 0 ;;
            n|no) return 1 ;;
            *) log_err "Please enter y or n." ;;
        esac
    done
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_err "This script must be run as root: sudo bash $0"
        exit 1
    fi
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_err "Cannot detect OS."
        exit 1
    fi
    log_ok "OS: $PRETTY_NAME"
}

install_deps() {
    log_info "Installing dependencies..."
    apt update -qq
    apt install -y -qq python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx curl wget 2>/dev/null | tail -5
    log_ok "Dependencies installed."
}

clone_repo() {
    log_info "Cloning repository..."
    if [[ -d "$INSTALL_DIR" ]]; then
        log_warn "Exists, updating..."
        cd "$INSTALL_DIR" && git pull origin main
    else
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"
    log_ok "Repository ready at $INSTALL_DIR."
}

setup_venv() {
    log_info "Creating Python virtual environment..."
    python3 -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    pip install --upgrade pip -q
    if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        pip install -r "$INSTALL_DIR/requirements.txt" -q
    else
        pip install aiogram fastapi uvicorn aiohttp aiosqlite python-dotenv python-multipart pyjwt cryptography pywebpush -q
    fi
    log_ok "Virtual environment and dependencies ready."
}

generate_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-43
}

generate_vapid() {
    log_info "Generating VAPID keys for push notifications..."
    local priv pub
    priv=$(openssl ecparam -genkey -name prime256v1 -noout -outform PEM 2>/dev/null | openssl ec -outform DER 2>/dev/null | tail -c +8 | head -c 32 | base64 | tr -d "=+/" | cut -c1-43)
    pub=$(echo "$priv" | openssl ec -inform DER -pubout -outform DER 2>/dev/null | tail -c 65 | base64 | tr -d "=+/" | cut -c1-43)
    echo "$priv $pub"
}

collect_config() {
    print_banner
    echo -e "${YELLOW}Step 1: Core Configuration${NC}"
    echo "----------------------------------------"
    
    prompt_input "Telegram Bot Token (BOT_TOKEN)" BOT_TOKEN "" true
    prompt_input "Owner Telegram ID (OWNER_ID)" OWNER_ID "" false
    
    print_banner
    echo -e "${YELLOW}Step 2: Domains & SSL${NC}"
    echo "----------------------------------------"
    prompt_yes_no "Do you have domains and want SSL (Let's Encrypt)?" "y" && SETUP_SSL=true || SETUP_SSL=false
    
    if [[ "$SETUP_SSL" == "true" ]]; then
        prompt_input "Admin Panel Domain (e.g., panel.example.com)" PANEL_DOMAIN "" false
        prompt_input "MiniApp Domain (e.g., miniapp.example.com)" MINIAPP_DOMAIN "" false
        prompt_input "Email for Let's Encrypt" LE_EMAIL "" false
    fi
    
    print_banner
    echo -e "${YELLOW}Step 3: Security Keys (leave empty for auto-generation)${NC}"
    echo "----------------------------------------"
    prompt_input "ADMIN_PANEL_SECRET (JWT secret)" ADMIN_PANEL_SECRET "$(generate_secret)" false
    prompt_input "VAPID_PRIVATE_KEY" VAPID_PRIVATE_KEY "$(generate_vapid | awk '{print $1}')" false
    prompt_input "VAPID_PUBLIC_KEY" VAPID_PUBLIC_KEY "$(generate_vapid | awk '{print $2}')" false
    prompt_input "VAPID_CLAIMS (e.g., {\"sub\": \"mailto:admin@example.com\"})" VAPID_CLAIMS '{"sub": "mailto:admin@example.com"}' false
    
    print_banner
    echo -e "${YELLOW}Step 4: Advanced Options${NC}"
    echo "----------------------------------------"
    prompt_yes_no "Enable UFW firewall?" "y" && SETUP_FIREWALL=true || SETUP_FIREWALL=false
    prompt_yes_no "Install Fail2Ban for SSH?" "y" && SETUP_FAIL2BAN=true || SETUP_FAIL2BAN=false
}

write_env() {
    log_info "Writing .env file..."
    cat > "$INSTALL_DIR/.env" <<EOF
# PatternShop Configuration
# Generated by install_wizard.sh on $(date)

BOT_TOKEN=$BOT_TOKEN
OWNER_ID=$OWNER_ID
ADMIN_PANEL_SECRET=$ADMIN_PANEL_SECRET
DB_PATH=$INSTALL_DIR/bot_database.db

VAPID_PUBLIC_KEY=$VAPID_PUBLIC_KEY
VAPID_PRIVATE_KEY=$VAPID_PRIVATE_KEY
VAPID_CLAIMS=$VAPID_CLAIMS
EOF
    chmod 600 "$INSTALL_DIR/.env"
    log_ok ".env created."
}

init_database() {
    log_info "Initializing database (running migrations)..."
    cd "$INSTALL_DIR"
    source "$INSTALL_DIR/venv/bin/activate"
    python3 -c "
from database import Database
db = Database('bot_database.db')
db.init_db(owner_id=$OWNER_ID)
print('Database initialized successfully')
"
    log_ok "Database initialized."
}

create_admin() {
    print_banner
    echo -e "${YELLOW}Step 5: Create Admin Panel User${NC}"
    echo "----------------------------------------"
    
    local username password
    prompt_input "Admin Username" ADMIN_USER "admin" false
    prompt_input "Admin Password" ADMIN_PASS "" true
    
    cd "$INSTALL_DIR"
    source "$INSTALL_DIR/venv/bin/activate"
    python3 -m admin_panel.create_admin "$ADMIN_USER" "$ADMIN_PASS"
    log_ok "Admin '$ADMIN_USER' created."
}

create_services() {
    log_info "Creating systemd services..."
    
    cat > /etc/systemd/system/patternshop-bot.service <<EOF
[Unit]
Description=PatternShop Telegram Bot
After=network.target

[Service]
Type=exec
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m bot
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    cat > /etc/systemd/system/patternshop-miniapp.service <<EOF
[Unit]
Description=PatternShop MiniApp
After=network.target

[Service]
Type=exec
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m miniapp.server
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    cat > /etc/systemd/system/patternshop-panel.service <<EOF
[Unit]
Description=PatternShop Admin Panel
After=network.target

[Service]
Type=exec
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m admin_panel.server
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now patternshop-bot patternshop-miniapp patternshop-panel
    log_ok "Services created and enabled."
}

setup_nginx() {
    if [[ "$SETUP_SSL" != "true" ]]; then
        return
    fi
    
    log_info "Configuring Nginx and SSL..."
    
    cat > /etc/nginx/sites-available/patternshop <<EOF
server {
    listen 80;
    server_name $PANEL_DOMAIN;
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 80;
    server_name $MINIAPP_DOMAIN;
    location / { return 301 https://\$host\$request_uri; }
}
EOF
    
    ln -sf /etc/nginx/sites-available/patternshop /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
    
    log_info "Requesting SSL certificate from Let's Encrypt..."
    certbot --nginx -d "$PANEL_DOMAIN" -d "$MINIAPP_DOMAIN" --email "$LE_EMAIL" --agree-tos --non-interactive --redirect
    
    # SSL renewal cron
    (crontab -l 2>/dev/null | grep -v certbot; echo "0 3 * * * certbot renew --quiet --nginx") | crontab -
    
    log_ok "Nginx and SSL configured."
}

setup_firewall() {
    if [[ "$SETUP_FIREWALL" != "true" ]]; then
        return
    fi
    
    log_info "Configuring firewall (UFW)..."
    ufw --force enable
    ufw allow 22/tcp comment "SSH"
    ufw allow 80/tcp comment "HTTP"
    ufw allow 443/tcp comment "HTTPS"
    ufw reload
    log_ok "Firewall enabled."
}

setup_fail2ban() {
    if [[ "$SETUP_FAIL2BAN" != "true" ]]; then
        return
    fi
    
    log_info "Installing and configuring Fail2Ban..."
    apt install -y -qq fail2ban
    
    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF
    
    systemctl enable --now fail2ban
    log_ok "Fail2Ban installed and enabled."
}

print_summary() {
    print_banner
    echo -e "${GREEN}✅ Installation completed successfully!${NC}"
    echo "----------------------------------------"
    echo -e "${CYAN}Access Information:${NC}"
    echo "  Admin Panel:     https://$PANEL_DOMAIN"
    echo "  MiniApp:         https://$MINIAPP_DOMAIN"
    echo "  Admin User:      $ADMIN_USER"
    echo "  Admin Password:  (hidden)"
    echo ""
    echo -e "${CYAN}Services:${NC}"
    echo "  systemctl status patternshop-bot"
    echo "  systemctl status patternshop-miniapp"
    echo "  systemctl status patternshop-panel"
    echo ""
    echo -e "${CYAN}Logs:${NC}"
    echo "  journalctl -u patternshop-bot -f"
    echo "  journalctl -u patternshop-panel -f"
    echo ""
    echo -e "${CYAN}Future Updates:${NC}"
    echo "  cd $INSTALL_DIR && git pull && systemctl restart patternshop-bot patternshop-miniapp patternshop-panel"
    echo ""
    echo -e "${YELLOW}Note:${NC} .env file stored at $INSTALL_DIR/.env (permissions 600)."
}

main() {
    check_root
    detect_os
    print_banner
    
    echo -e "${CYAN}Welcome to PatternShop Installation Wizard${NC}"
    echo "This script will interactively guide you through the complete installation."
    echo ""
    prompt_yes_no "Continue with installation?" "y" || { log_info "Cancelled."; exit 0; }
    
    collect_config
    install_deps
    clone_repo
    setup_venv
    write_env
    init_database
    create_admin
    create_services
    setup_nginx
    setup_firewall
    setup_fail2ban
    print_summary
}

main "$@"
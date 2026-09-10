# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import json
import re
import sqlite3
import uuid as uuid_lib
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "vless"
DB_PATH = DATA_DIR / "nodes.db"
XRAY_CONFIG = Path("/usr/local/etc/xray/patternshop-client.json")


class VlessManager:

    def __init__(self, db_path=DB_PATH):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    link TEXT NOT NULL UNIQUE,
                    protocol TEXT NOT NULL DEFAULT 'vless',
                    address TEXT,
                    port INTEGER,
                    uuid TEXT,
                    security TEXT,
                    transport TEXT,
                    sni TEXT,
                    public_key TEXT,
                    short_id TEXT,
                    flow TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    latency_ms INTEGER,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_tested_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def add_vless(self, link: str, name: str | None = None):
        data = self.parse_vless(link)

        node_name = name or data.get("name") or f"VLESS-{uuid_lib.uuid4().hex[:8]}"

        with self._connect() as conn:
            try:
                cur = conn.execute("""
                    INSERT INTO nodes (
                        name, link, protocol, address, port, uuid,
                        security, transport, sni, public_key, short_id, flow
                    )
                    VALUES (?, ?, 'vless', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    node_name,
                    link.strip(),
                    data["address"],
                    data["port"],
                    data["uuid"],
                    data.get("security"),
                    data.get("transport"),
                    data.get("sni"),
                    data.get("public_key"),
                    data.get("short_id"),
                    data.get("flow"),
                ))
            except sqlite3.IntegrityError:
                raise ValueError("این VLESS قبلاً اضافه شده است.")

            node_id = cur.lastrowid

        return self.get(node_id)

    def import_subscription(self, text: str):
        text = text.strip()

        if text.startswith(("http://", "https://")):
            raise ValueError(
                "نسخه اول Import، لینک Subscription را دانلود نمی‌کند؛ "
                "فعلاً محتوای Subscription را Paste کنید."
            )

        try:
            decoded = base64.b64decode(text + "=" * (-len(text) % 4)).decode(
                "utf-8",
                errors="ignore",
            )
        except Exception:
            decoded = text

        links = [
            line.strip()
            for line in decoded.splitlines()
            if line.strip().startswith("vless://")
        ]

        if not links:
            raise ValueError("هیچ VLESS معتبری در Subscription پیدا نشد.")

        added = 0
        skipped = 0

        for link in links:
            try:
                self.add_vless(link)
                added += 1
            except ValueError:
                skipped += 1

        return {
            "found": len(links),
            "added": added,
            "skipped": skipped,
        }

    @staticmethod
    def parse_vless(link: str):
        if not link.startswith("vless://"):
            raise ValueError("لینک باید با vless:// شروع شود.")

        p = urlparse(link)

        if not p.username:
            raise ValueError("UUID داخل VLESS پیدا نشد.")

        if not p.hostname:
            raise ValueError("Address داخل VLESS پیدا نشد.")

        if not p.port:
            raise ValueError("Port داخل VLESS پیدا نشد.")

        query = parse_qs(p.query)

        def first(key, default=None):
            value = query.get(key)
            return unquote(value[0]) if value else default

        return {
            "uuid": unquote(p.username),
            "address": p.hostname,
            "port": p.port,
            "name": unquote(p.fragment[1:]) if p.fragment else None,
            "security": first("security", "none"),
            "transport": first("type", "tcp"),
            "sni": first("sni"),
            "public_key": first("pbk") or first("publicKey"),
            "short_id": first("sid") or first("shortId"),
            "flow": first("flow"),
        }

    def get(self, node_id: int):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM nodes WHERE id = ?",
                (node_id,),
            ).fetchone()

        return dict(row) if row else None

    def list_nodes(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT *
                FROM nodes
                ORDER BY enabled DESC, latency_ms ASC, id DESC
            """).fetchall()

        return [dict(row) for row in rows]

    def delete(self, node_id: int):
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM nodes WHERE id = ?",
                (node_id,),
            )
            return cur.rowcount > 0

    def set_enabled(self, node_id: int, enabled: bool):
        with self._connect() as conn:
            cur = conn.execute("""
                UPDATE nodes
                SET enabled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (1 if enabled else 0, node_id))
            return cur.rowcount > 0

    def build_xray_config(self, node):
        stream = {
            "network": node.get("transport") or "tcp",
            "security": node.get("security") or "none",
        }

        security = node.get("security")

        if security == "reality":
            stream["realitySettings"] = {
                "serverName": node.get("sni") or node["address"],
                "fingerprint": "chrome",
                "publicKey": node.get("public_key"),
                "shortId": node.get("short_id"),
            }

        elif security == "tls":
            stream["tlsSettings"] = {
                "serverName": node.get("sni") or node["address"],
                "allowInsecure": False,
                "fingerprint": "chrome",
            }

        return {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                {
                    "tag": "patternshop-http",
                    "listen": "127.0.0.1",
                    "port": 18080,
                    "protocol": "http",
                    "settings": {}
                }
            ],
            "outbounds": [
                {
                    "tag": "proxy",
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": node["address"],
                                "port": node["port"],
                                "users": [
                                    {
                                        "id": node["uuid"],
                                        "encryption": "none",
                                        "flow": node.get("flow") or ""
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": stream
                },
                {
                    "tag": "direct",
                    "protocol": "freedom"
                }
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": []
            }
        }

    def write_config(self, node):
        config = self.build_xray_config(node)

        XRAY_CONFIG.parent.mkdir(parents=True, exist_ok=True)

        XRAY_CONFIG.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return str(XRAY_CONFIG)

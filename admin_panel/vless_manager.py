# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.vless_client.subscription import load_subscription


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "proxy_pool.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VLESSManager:
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS vless_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    auto_sync INTEGER NOT NULL DEFAULT 1,
                    sync_interval_minutes INTEGER NOT NULL DEFAULT 60,
                    priority INTEGER NOT NULL DEFAULT 100,
                    last_sync_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vless_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER NOT NULL,
                    name TEXT,
                    uri TEXT NOT NULL,
                    uuid TEXT,
                    host TEXT,
                    port INTEGER,
                    encryption TEXT,
                    network TEXT,
                    security TEXT,
                    sni TEXT,
                    host_header TEXT,
                    path TEXT,
                    service_name TEXT,
                    public_key TEXT,
                    short_id TEXT,
                    flow TEXT,
                    fp TEXT,

                    enabled INTEGER NOT NULL DEFAULT 1,
                    source_present INTEGER NOT NULL DEFAULT 1,

                    status TEXT NOT NULL DEFAULT 'unknown',
                    latency_ms INTEGER,
                    telegram_ok INTEGER,
                    last_checked_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    error TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    UNIQUE(subscription_id, uri),

                    FOREIGN KEY(subscription_id)
                        REFERENCES vless_subscriptions(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_vless_nodes_subscription
                    ON vless_nodes(subscription_id);

                CREATE INDEX IF NOT EXISTS idx_vless_nodes_enabled
                    ON vless_nodes(enabled);

                CREATE INDEX IF NOT EXISTS idx_vless_nodes_status
                    ON vless_nodes(status);
                """
            )

    # =========================================================
    # SUBSCRIPTIONS
    # =========================================================

    def list_subscriptions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.*,
                    COUNT(n.id) AS nodes_count,
                    SUM(
                        CASE
                            WHEN n.enabled = 1
                             AND n.source_present = 1
                            THEN 1 ELSE 0
                        END
                    ) AS enabled_nodes,
                    SUM(
                        CASE
                            WHEN n.telegram_ok = 1
                             AND n.enabled = 1
                             AND n.source_present = 1
                            THEN 1 ELSE 0
                        END
                    ) AS telegram_nodes
                FROM vless_subscriptions s
                LEFT JOIN vless_nodes n
                    ON n.subscription_id = s.id
                GROUP BY s.id
                ORDER BY s.priority ASC, s.id DESC
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def get_subscription(
        self,
        subscription_id: int,
    ) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    s.*,
                    COUNT(n.id) AS nodes_count
                FROM vless_subscriptions s
                LEFT JOIN vless_nodes n
                    ON n.subscription_id = s.id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (subscription_id,),
            ).fetchone()

        return dict(row) if row else None

    def add_subscription(
        self,
        name: str,
        url: str,
        enabled: bool = True,
        auto_sync: bool = True,
        sync_interval_minutes: int = 60,
        priority: int = 100,
    ) -> dict[str, Any]:

        name = name.strip()
        url = url.strip()

        if not name:
            raise ValueError("نام Subscription الزامی است.")

        if not url:
            raise ValueError("URL Subscription الزامی است.")

        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO vless_subscriptions (
                        name,
                        url,
                        enabled,
                        auto_sync,
                        sync_interval_minutes,
                        priority,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        url,
                        1 if enabled else 0,
                        1 if auto_sync else 0,
                        max(5, int(sync_interval_minutes)),
                        int(priority),
                        now_iso(),
                        now_iso(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "این Subscription قبلاً ثبت شده است."
                ) from exc

            subscription_id = cursor.lastrowid

        return self.get_subscription(int(subscription_id))

    def update_subscription(
        self,
        subscription_id: int,
        name: Optional[str] = None,
        url: Optional[str] = None,
        enabled: Optional[bool] = None,
        auto_sync: Optional[bool] = None,
        sync_interval_minutes: Optional[int] = None,
        priority: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:

        fields = []
        params: list[Any] = []

        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("نام Subscription نمی‌تواند خالی باشد.")
            fields.append("name = ?")
            params.append(name)

        if url is not None:
            url = url.strip()
            if not url:
                raise ValueError("URL Subscription نمی‌تواند خالی باشد.")
            fields.append("url = ?")
            params.append(url)

        if enabled is not None:
            fields.append("enabled = ?")
            params.append(1 if enabled else 0)

        if auto_sync is not None:
            fields.append("auto_sync = ?")
            params.append(1 if auto_sync else 0)

        if sync_interval_minutes is not None:
            fields.append("sync_interval_minutes = ?")
            params.append(max(5, int(sync_interval_minutes)))

        if priority is not None:
            fields.append("priority = ?")
            params.append(int(priority))

        if not fields:
            return self.get_subscription(subscription_id)

        fields.append("updated_at = ?")
        params.append(now_iso())
        params.append(subscription_id)

        with self._connect() as conn:
            try:
                result = conn.execute(
                    f"""
                    UPDATE vless_subscriptions
                    SET {", ".join(fields)}
                    WHERE id = ?
                    """,
                    params,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "این Subscription URL قبلاً ثبت شده است."
                ) from exc

            if result.rowcount == 0:
                return None

        return self.get_subscription(subscription_id)

    def delete_subscription(self, subscription_id: int) -> bool:
        with self._connect() as conn:
            result = conn.execute(
                """
                DELETE FROM vless_subscriptions
                WHERE id = ?
                """,
                (subscription_id,),
            )
            return result.rowcount > 0

    def set_subscription_enabled(
        self,
        subscription_id: int,
        enabled: bool,
    ) -> Optional[dict[str, Any]]:

        return self.update_subscription(
            subscription_id,
            enabled=enabled,
        )

    # =========================================================
    # SYNC
    # =========================================================

    def sync_subscription(
        self,
        subscription_id: int,
    ) -> dict[str, Any]:

        subscription = self.get_subscription(subscription_id)

        if not subscription:
            raise ValueError("Subscription پیدا نشد.")

        try:
            nodes = load_subscription(subscription["url"])

            if not nodes:
                raise ValueError(
                    "هیچ VLESS Nodeای از Subscription دریافت نشد."
                )

            current_uris = set()

            with self._connect() as conn:
                for node in nodes:
                    uri = node["uri"]
                    current_uris.add(uri)

                    conn.execute(
                        """
                        INSERT INTO vless_nodes (
                            subscription_id,
                            name,
                            uri,
                            uuid,
                            host,
                            port,
                            encryption,
                            network,
                            security,
                            sni,
                            host_header,
                            path,
                            service_name,
                            public_key,
                            short_id,
                            flow,
                            fp,
                            source_present,
                            updated_at,
                            created_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, 1, ?, ?
                        )
                        ON CONFLICT(subscription_id, uri)
                        DO UPDATE SET
                            name = excluded.name,
                            uuid = excluded.uuid,
                            host = excluded.host,
                            port = excluded.port,
                            encryption = excluded.encryption,
                            network = excluded.network,
                            security = excluded.security,
                            sni = excluded.sni,
                            host_header = excluded.host_header,
                            path = excluded.path,
                            service_name = excluded.service_name,
                            public_key = excluded.public_key,
                            short_id = excluded.short_id,
                            flow = excluded.flow,
                            fp = excluded.fp,
                            source_present = 1,
                            updated_at = excluded.updated_at
                        """,
                        (
                            subscription_id,
                            node.get("name"),
                            uri,
                            node.get("uuid"),
                            node.get("host"),
                            node.get("port"),
                            node.get("encryption"),
                            node.get("network"),
                            node.get("security"),
                            node.get("sni"),
                            node.get("host_header"),
                            node.get("path"),
                            node.get("service_name"),
                            node.get("public_key"),
                            node.get("short_id"),
                            node.get("flow"),
                            node.get("fp"),
                            now_iso(),
                            now_iso(),
                        ),
                    )

                # Nodeهای قبلی که دیگر در Subscription نیستند
                # حذف نمی‌شوند؛ فقط source_present=0 می‌گیرند.
                rows = conn.execute(
                    """
                    SELECT id, uri
                    FROM vless_nodes
                    WHERE subscription_id = ?
                    """,
                    (subscription_id,),
                ).fetchall()

                for row in rows:
                    if row["uri"] not in current_uris:
                        conn.execute(
                            """
                            UPDATE vless_nodes
                            SET source_present = 0,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (now_iso(), row["id"]),
                        )

                conn.execute(
                    """
                    UPDATE vless_subscriptions
                    SET
                        last_sync_at = ?,
                        last_error = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now_iso(),
                        now_iso(),
                        subscription_id,
                    ),
                )

            return {
                "ok": True,
                "subscription_id": subscription_id,
                "nodes_received": len(nodes),
                "message": "Subscription با موفقیت Sync شد.",
            }

        except Exception as exc:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE vless_subscriptions
                    SET
                        last_error = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        str(exc),
                        now_iso(),
                        subscription_id,
                    ),
                )

            raise ValueError(
                f"Sync ناموفق بود: {exc}"
            ) from exc

    def sync_all(self) -> list[dict[str, Any]]:
        results = []

        for sub in self.list_subscriptions():
            if not sub["enabled"]:
                continue

            try:
                results.append(
                    self.sync_subscription(sub["id"])
                )
            except Exception as exc:
                results.append(
                    {
                        "ok": False,
                        "subscription_id": sub["id"],
                        "error": str(exc),
                    }
                )

        return results

    # =========================================================
    # NODES
    # =========================================================

    def list_nodes(
        self,
        subscription_id: Optional[int] = None,
        enabled: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:

        where = []
        params: list[Any] = []

        if subscription_id is not None:
            where.append("n.subscription_id = ?")
            params.append(subscription_id)

        if enabled is not None:
            where.append("n.enabled = ?")
            params.append(1 if int(enabled) else 0)

        if status:
            where.append("n.status = ?")
            params.append(status)

        if search:
            term = f"%{search.strip()}%"
            where.append(
                """
                (
                    n.name LIKE ?
                    OR n.host LIKE ?
                    OR s.name LIKE ?
                )
                """
            )
            params.extend([term, term, term])

        where_sql = ""
        if where:
            where_sql = "WHERE " + " AND ".join(where)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    n.*,
                    s.name AS subscription_name,
                    s.priority AS subscription_priority
                FROM vless_nodes n
                JOIN vless_subscriptions s
                    ON s.id = n.subscription_id
                {where_sql}
                ORDER BY
                    s.priority ASC,
                    CASE
                        WHEN n.telegram_ok = 1 THEN 0
                        WHEN n.status = 'healthy' THEN 1
                        WHEN n.status = 'slow' THEN 2
                        ELSE 3
                    END,
                    COALESCE(n.latency_ms, 999999) ASC,
                    n.id DESC
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def get_node(
        self,
        node_id: int,
    ) -> Optional[dict[str, Any]]:

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    n.*,
                    s.name AS subscription_name,
                    s.priority AS subscription_priority
                FROM vless_nodes n
                JOIN vless_subscriptions s
                    ON s.id = n.subscription_id
                WHERE n.id = ?
                """,
                (node_id,),
            ).fetchone()

        return dict(row) if row else None

    def set_node_enabled(
        self,
        node_id: int,
        enabled: bool,
    ) -> Optional[dict[str, Any]]:

        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE vless_nodes
                SET enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    1 if enabled else 0,
                    now_iso(),
                    node_id,
                ),
            )

            if result.rowcount == 0:
                return None

        return self.get_node(node_id)

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            subscriptions = conn.execute(
                """
                SELECT COUNT(*)
                FROM vless_subscriptions
                """
            ).fetchone()[0]

            enabled_subscriptions = conn.execute(
                """
                SELECT COUNT(*)
                FROM vless_subscriptions
                WHERE enabled = 1
                """
            ).fetchone()[0]

            nodes = conn.execute(
                """
                SELECT COUNT(*)
                FROM vless_nodes
                """
            ).fetchone()[0]

            enabled_nodes = conn.execute(
                """
                SELECT COUNT(*)
                FROM vless_nodes
                WHERE enabled = 1
                  AND source_present = 1
                """
            ).fetchone()[0]

            telegram_nodes = conn.execute(
                """
                SELECT COUNT(*)
                FROM vless_nodes
                WHERE enabled = 1
                  AND source_present = 1
                  AND telegram_ok = 1
                """
            ).fetchone()[0]

            healthy_nodes = conn.execute(
                """
                SELECT COUNT(*)
                FROM vless_nodes
                WHERE enabled = 1
                  AND source_present = 1
                  AND status = 'healthy'
                """
            ).fetchone()[0]

            return {
                "subscriptions": subscriptions,
                "enabled_subscriptions": enabled_subscriptions,
                "nodes": nodes,
                "enabled_nodes": enabled_nodes,
                "healthy_nodes": healthy_nodes,
                "telegram_nodes": telegram_nodes,
            }

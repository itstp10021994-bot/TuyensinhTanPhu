"""Lưu dữ liệu vào file SQLite — dùng khi chạy thử / phát triển không cần SharePoint."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .base import Storage


class LocalStorage(Storage):
    def __init__(self, path: str | Path = "data_local.sqlite3"):
        self.path = str(path)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS items ("
                " list TEXT NOT NULL, id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " data TEXT NOT NULL, created TEXT, modified TEXT)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _row(row) -> dict:
        d = json.loads(row[1])
        d.update(id=str(row[0]), Created=row[2], Modified=row[3])
        return d

    def list_items(self, list_name):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, data, created, modified FROM items WHERE list=? ORDER BY id",
                (list_name,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def get_item(self, list_name, item_id):
        with self._conn() as c:
            r = c.execute(
                "SELECT id, data, created, modified FROM items WHERE list=? AND id=?",
                (list_name, int(item_id)),
            ).fetchone()
        return self._row(r) if r else None

    def create_item(self, list_name, data):
        now = datetime.now().isoformat(timespec="seconds")
        clean = {k: v for k, v in data.items() if k not in ("id", "Created", "Modified")}
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO items(list, data, created, modified) VALUES (?,?,?,?)",
                (list_name, json.dumps(clean, ensure_ascii=False), now, now),
            )
            new_id = cur.lastrowid
        return self.get_item(list_name, new_id)

    def update_item(self, list_name, item_id, data):
        cur = self.get_item(list_name, item_id)
        if cur is None:
            raise KeyError(f"{list_name}/{item_id} không tồn tại")
        merged = {k: v for k, v in cur.items() if k not in ("id", "Created", "Modified")}
        merged.update({k: v for k, v in data.items() if k not in ("id", "Created", "Modified")})
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE items SET data=?, modified=? WHERE list=? AND id=?",
                (json.dumps(merged, ensure_ascii=False), now, list_name, int(item_id)),
            )
        return self.get_item(list_name, item_id)

    def delete_item(self, list_name, item_id):
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM items WHERE list=? AND id=?", (list_name, int(item_id)))

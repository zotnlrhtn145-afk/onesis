"""대화 기록을 SQLite 파일에 영구 저장합니다."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from . import config


def _now() -> str:
    # ISO 형식 문자열 (UTC 기준)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                preview TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # 화면 미리보기(HTML 목업) 컬럼 — 기존 DB에도 없으면 추가
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN mockup TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # 이미 있음
        # 대화 종류: 'chat'(홈=일반 질문) | 'plan'(기획안=제작 기획)
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN kind TEXT DEFAULT 'chat'")
        except sqlite3.OperationalError:
            pass  # 이미 있음
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                question TEXT NOT NULL,
                final TEXT NOT NULL,
                transcript TEXT NOT NULL,
                is_build INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
            """
        )


def create_conversation(title: str, kind: str = "chat") -> str:
    cid = uuid.uuid4().hex
    now = _now()
    title = (title or "새 대화").strip()[:60] or "새 대화"
    kind = kind if kind in ("chat", "plan") else "chat"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, preview, kind, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (cid, title, "", kind, now, now),
        )
    return cid


def list_conversations(kind: str | None = None) -> list[dict[str, Any]]:
    with _conn() as conn:
        if kind in ("chat", "plan"):
            rows = conn.execute(
                "SELECT id, title, kind, updated_at FROM conversations "
                "WHERE kind=? ORDER BY updated_at DESC",
                (kind,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, kind, updated_at FROM conversations ORDER BY updated_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str) -> dict[str, Any] | None:
    with _conn() as conn:
        c = conn.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
        if not c:
            return None
        msgs = conn.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
            (cid,),
        ).fetchall()
    out = dict(c)
    out["messages"] = []
    for m in msgs:
        md = dict(m)
        try:
            md["transcript"] = json.loads(md["transcript"])
        except (ValueError, TypeError):
            md["transcript"] = {}
        md["is_build"] = bool(md["is_build"])
        out["messages"].append(md)
    return out


def add_exchange(
    conversation_id: str,
    question: str,
    final: str,
    transcript: dict[str, Any],
    is_build: bool,
    preview: str,
) -> str:
    mid = uuid.uuid4().hex
    now = _now()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, question, final, transcript, is_build, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (mid, conversation_id, question, final, json.dumps(transcript, ensure_ascii=False),
             1 if is_build else 0, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at=?, preview=? WHERE id=?",
            (now, preview, conversation_id),
        )
    return mid


def update_preview(conversation_id: str, preview: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE conversations SET preview=?, updated_at=? WHERE id=?",
            (preview, _now(), conversation_id),
        )


def update_mockup(conversation_id: str, mockup: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE conversations SET mockup=?, updated_at=? WHERE id=?",
            (mockup, _now(), conversation_id),
        )


def rename_conversation(conversation_id: str, title: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
            ((title or "새 대화").strip()[:60] or "새 대화", _now(), conversation_id),
        )


def delete_conversation(conversation_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))

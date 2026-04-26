"""SQLite helpers for phase 0-2 backend state."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path(db_path: Optional[str] = None) -> str:
    return db_path or get_settings().db_path


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = _db_path(db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _json_dumps(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_loads(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    return json.loads(value)


def init_db(db_path: Optional[str] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS terminals (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY,
              terminal_id TEXT NOT NULL,
              type TEXT NOT NULL,
              subject TEXT NOT NULL,
              key TEXT NOT NULL,
              value_json TEXT NOT NULL,
              confidence REAL DEFAULT 1.0,
              source TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_terminal
              ON memories(terminal_id);
            CREATE INDEX IF NOT EXISTS idx_memories_lookup
              ON memories(terminal_id, type, subject, key);

            CREATE TABLE IF NOT EXISTS inventory_items (
              id TEXT PRIMARY KEY,
              terminal_id TEXT NOT NULL,
              name TEXT NOT NULL,
              amount TEXT,
              unit TEXT,
              category TEXT,
              freshness TEXT,
              source TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS terminal_state (
              terminal_id TEXT PRIMARY KEY,
              ui_mode TEXT NOT NULL,
              state_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_events (
              id TEXT PRIMARY KEY,
              terminal_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              name TEXT NOT NULL,
              input_json TEXT,
              output_json TEXT,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
              id TEXT PRIMARY KEY,
              terminal_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              metadata_json TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recipe_documents (
              id TEXT PRIMARY KEY,
              terminal_id TEXT NOT NULL,
              title TEXT NOT NULL,
              source_type TEXT NOT NULL,
              content TEXT NOT NULL,
              parsed_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )


def ensure_terminal(terminal_id: str, name: Optional[str] = None, db_path: Optional[str] = None) -> None:
    now = utc_now()
    terminal_name = name or terminal_id
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO terminals (id, name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              updated_at = excluded.updated_at
            """,
            (terminal_id, terminal_name, now, now),
        )


def get_state(terminal_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ensure_terminal(terminal_id, db_path=db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT state_json FROM terminal_state WHERE terminal_id = ?",
            (terminal_id,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["state_json"])


def save_state(terminal_id: str, state: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    ensure_terminal(terminal_id, db_path=db_path)
    now = utc_now()
    next_state = dict(state)
    next_state["terminal_id"] = terminal_id
    next_state["updated_at"] = now
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO terminal_state (terminal_id, ui_mode, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(terminal_id) DO UPDATE SET
              ui_mode = excluded.ui_mode,
              state_json = excluded.state_json,
              updated_at = excluded.updated_at
            """,
            (
                terminal_id,
                next_state.get("ui_mode", "planning"),
                json.dumps(next_state, ensure_ascii=False, separators=(",", ":")),
                now,
            ),
        )
    return next_state


def add_conversation(
    terminal_id: str,
    role: str,
    content: str,
    metadata_json: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_terminal(terminal_id, db_path=db_path)
    conversation = {
        "id": f"msg_{uuid.uuid4().hex}",
        "terminal_id": terminal_id,
        "role": role,
        "content": content,
        "metadata_json": metadata_json,
        "created_at": utc_now(),
    }
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, terminal_id, role, content, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation["id"],
                terminal_id,
                role,
                content,
                _json_dumps(metadata_json),
                conversation["created_at"],
            ),
        )
    return conversation


def list_recent_conversations(
    terminal_id: str,
    limit: int = 6,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ensure_terminal(terminal_id, db_path=db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, terminal_id, role, content, metadata_json, created_at
            FROM (
              SELECT rowid AS row_order, id, terminal_id, role, content, metadata_json, created_at
              FROM conversations
              WHERE terminal_id = ?
              ORDER BY created_at DESC, rowid DESC
              LIMIT ?
            )
            ORDER BY created_at ASC, row_order ASC
            """,
            (terminal_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "terminal_id": row["terminal_id"],
            "role": row["role"],
            "content": row["content"],
            "metadata_json": _json_loads(row["metadata_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def upsert_memory(
    terminal_id: str,
    memory_type: str,
    subject: str,
    key: str,
    value_json: Dict[str, Any],
    confidence: float = 1.0,
    source: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_terminal(terminal_id, db_path=db_path)
    now = utc_now()
    with _connect(db_path) as conn:
        existing = conn.execute(
            """
            SELECT id, created_at
            FROM memories
            WHERE terminal_id = ? AND type = ? AND subject = ? AND key = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (terminal_id, memory_type, subject, key),
        ).fetchone()
        if existing:
            memory_id = existing["id"]
            created_at = existing["created_at"]
            conn.execute(
                """
                UPDATE memories
                SET value_json = ?, confidence = ?, source = ?, updated_at = ?
                WHERE id = ?
                """,
                (_json_dumps(value_json), confidence, source, now, memory_id),
            )
        else:
            memory_id = f"mem_{uuid.uuid4().hex}"
            created_at = now
            conn.execute(
                """
                INSERT INTO memories (
                  id, terminal_id, type, subject, key, value_json, confidence, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    terminal_id,
                    memory_type,
                    subject,
                    key,
                    _json_dumps(value_json),
                    confidence,
                    source,
                    now,
                    now,
                ),
            )
    return {
        "id": memory_id,
        "terminal_id": terminal_id,
        "type": memory_type,
        "subject": subject,
        "key": key,
        "value_json": value_json,
        "confidence": confidence,
        "source": source,
        "created_at": created_at,
        "updated_at": now,
    }


def upsert_inventory_item(
    terminal_id: str,
    name: str,
    amount: Optional[str] = None,
    unit: Optional[str] = None,
    category: Optional[str] = None,
    freshness: Optional[str] = None,
    source: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_terminal(terminal_id, db_path=db_path)
    now = utc_now()
    with _connect(db_path) as conn:
        existing = conn.execute(
            """
            SELECT id, created_at
            FROM inventory_items
            WHERE terminal_id = ? AND name = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (terminal_id, name),
        ).fetchone()
        if existing:
            item_id = existing["id"]
            created_at = existing["created_at"]
            conn.execute(
                """
                UPDATE inventory_items
                SET amount = ?, unit = ?, category = ?, freshness = ?, source = ?, updated_at = ?
                WHERE id = ?
                """,
                (amount, unit, category, freshness, source, now, item_id),
            )
        else:
            item_id = f"inv_{uuid.uuid4().hex}"
            created_at = now
            conn.execute(
                """
                INSERT INTO inventory_items (
                  id, terminal_id, name, amount, unit, category, freshness, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_id, terminal_id, name, amount, unit, category, freshness, source, now, now),
            )
    return {
        "id": item_id,
        "terminal_id": terminal_id,
        "name": name,
        "amount": amount,
        "unit": unit,
        "category": category,
        "freshness": freshness,
        "source": source,
        "created_at": created_at,
        "updated_at": now,
    }


def create_recipe_document(
    terminal_id: str,
    title: str,
    source_type: str,
    content: str,
    parsed_json: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_terminal(terminal_id, db_path=db_path)
    now = utc_now()
    document = {
        "id": f"recipe_doc_{uuid.uuid4().hex}",
        "terminal_id": terminal_id,
        "title": title,
        "source_type": source_type,
        "content": content,
        "parsed_json": parsed_json,
        "created_at": now,
        "updated_at": now,
    }
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO recipe_documents (
              id, terminal_id, title, source_type, content, parsed_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["id"],
                terminal_id,
                title,
                source_type,
                content,
                _json_dumps(parsed_json),
                now,
                now,
            ),
        )
    return document


def list_recipe_documents(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_terminal(terminal_id, db_path=db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, terminal_id, title, source_type, content, parsed_json, created_at, updated_at
            FROM recipe_documents
            WHERE terminal_id = ?
            ORDER BY updated_at ASC
            """,
            (terminal_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "terminal_id": row["terminal_id"],
            "title": row["title"],
            "source_type": row["source_type"],
            "content": row["content"],
            "parsed_json": _json_loads(row["parsed_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def add_tool_event(
    terminal_id: str,
    event_type: str,
    name: str,
    input_json: Optional[Dict[str, Any]] = None,
    output_json: Optional[Dict[str, Any]] = None,
    status: str = "success",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_terminal(terminal_id, db_path=db_path)
    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "terminal_id": terminal_id,
        "event_type": event_type,
        "name": name,
        "input_json": input_json,
        "output_json": output_json,
        "status": status,
        "created_at": utc_now(),
    }
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO tool_events (
              id, terminal_id, event_type, name, input_json, output_json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                terminal_id,
                event_type,
                name,
                _json_dumps(input_json),
                _json_dumps(output_json),
                status,
                event["created_at"],
            ),
        )
    return event


def list_tool_events(
    terminal_id: str,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ensure_terminal(terminal_id, db_path=db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, terminal_id, event_type, name, input_json, output_json, status, created_at
            FROM (
              SELECT rowid AS row_order, id, terminal_id, event_type, name, input_json, output_json, status, created_at
              FROM tool_events
              WHERE terminal_id = ?
              ORDER BY created_at DESC, rowid DESC
              LIMIT ?
            )
            ORDER BY created_at ASC, row_order ASC
            """,
            (terminal_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "terminal_id": row["terminal_id"],
            "event_type": row["event_type"],
            "name": row["name"],
            "input_json": _json_loads(row["input_json"]),
            "output_json": _json_loads(row["output_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_memories(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_terminal(terminal_id, db_path=db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, terminal_id, type, subject, key, value_json, confidence, source, created_at, updated_at
            FROM memories
            WHERE terminal_id = ?
            ORDER BY updated_at ASC
            """,
            (terminal_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "terminal_id": row["terminal_id"],
            "type": row["type"],
            "subject": row["subject"],
            "key": row["key"],
            "value_json": _json_loads(row["value_json"]),
            "confidence": row["confidence"],
            "source": row["source"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def list_inventory_items(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_terminal(terminal_id, db_path=db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, terminal_id, name, amount, unit, category, freshness, source, created_at, updated_at
            FROM inventory_items
            WHERE terminal_id = ?
            ORDER BY updated_at ASC
            """,
            (terminal_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def reset_demo_data(terminal_id: Optional[str] = None, db_path: Optional[str] = None) -> None:
    target_terminal_id = terminal_id or get_settings().default_terminal_id
    ensure_terminal(target_terminal_id, db_path=db_path)
    tables = [
        "memories",
        "inventory_items",
        "terminal_state",
        "tool_events",
        "conversations",
        "recipe_documents",
    ]
    with _connect(db_path) as conn:
        for table in tables:
            conn.execute(f"DELETE FROM {table} WHERE terminal_id = ?", (target_terminal_id,))

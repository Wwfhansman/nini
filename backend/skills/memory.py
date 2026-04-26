"""Memory skill: structured long-term household facts."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from backend import database
from backend.agent.schemas import MemoryWrite


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _memory_text(memory: Dict[str, Any]) -> str:
    value = memory.get("value_json")
    if isinstance(value, dict):
        return str(value.get("text") or value.get("value") or value)
    return str(value)


def write_memory(
    terminal_id: str,
    memory_write: MemoryWrite | Dict[str, Any],
    source: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    payload = _model_to_dict(memory_write)
    value = payload.get("value")
    value_json = value if isinstance(value, dict) else {"text": value}
    return database.upsert_memory(
        terminal_id=terminal_id,
        memory_type=payload["type"],
        subject=payload["subject"],
        key=payload["key"],
        value_json=value_json,
        confidence=float(payload.get("confidence", 1.0)),
        source=source or payload.get("source") or "user_explicit",
        db_path=db_path,
    )


def write_memories(
    terminal_id: str,
    memory_writes: Iterable[MemoryWrite | Dict[str, Any]],
    source: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return [write_memory(terminal_id, item, source=source, db_path=db_path) for item in memory_writes]


def list_memories(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return database.list_memories(terminal_id, db_path=db_path)


def search_memories(
    terminal_id: str,
    query: str = "",
    context: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    memories = list_memories(terminal_id, db_path=db_path)
    terms = [query]
    if context:
        terms.extend(str(value) for value in context.values() if value)
    compact_terms = [term for term in terms if term]
    if not compact_terms:
        return memories
    matches: List[Dict[str, Any]] = []
    for memory in memories:
        haystack = " ".join(
            [
                memory.get("type", ""),
                memory.get("subject", ""),
                memory.get("key", ""),
                _memory_text(memory),
            ]
        )
        if any(term in haystack or haystack in term for term in compact_terms):
            matches.append(memory)
    return matches or memories


def export_memory_markdown(terminal_id: str, db_path: Optional[str] = None) -> str:
    lines = ["# 张家厨房记忆卡", ""]
    for memory in list_memories(terminal_id, db_path=db_path):
        subject = memory.get("subject")
        key = memory.get("key")
        text = _memory_text(memory)
        if subject == "user" and key == "diet.goal":
            lines.append(f"- 用户最近在{text}")
        elif subject == "user" and key == "taste.sour":
            lines.append(f"- 用户{text}")
        elif subject == "mother" and key == "taste.spicy":
            lines.append(f"- 妈妈{text}")
        elif key == "tomato_dishes.default_adjustment":
            lines.append(f"- {text}")
        else:
            lines.append(f"- {text}")
    if len(lines) == 2:
        lines.append("- 暂无家庭记忆")
    return "\n".join(lines) + "\n"


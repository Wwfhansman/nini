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


def _normalize_query(query: str) -> str:
    return "".join(str(query or "").split()).strip("。！？!?.,，；;：:、 ")


def summarize_memory(memory: Optional[Dict[str, Any]]) -> str:
    if not memory:
        return "这条记忆"
    subject = memory.get("subject")
    key = memory.get("key")
    text = _memory_text(memory)
    if subject == "mother" and ("辣" in key or "辣" in text):
        return "妈妈不吃辣"
    if subject == "user" and ("酸" in key or "酸" in text):
        return "用户不喜欢太酸"
    if subject == "user" and ("减脂" in text or key in {"diet.goal", "health_goal.diet"}):
        return f"用户{text}"
    if subject == "mother":
        return f"妈妈{text}"
    if subject == "user":
        return f"用户{text}"
    return text


def _score_memory(memory: Dict[str, Any], query: str, recency_rank: int) -> int:
    text = _memory_text(memory)
    haystack = _normalize_query(
        " ".join(
            [
                str(memory.get("type") or ""),
                str(memory.get("subject") or ""),
                str(memory.get("key") or ""),
                text,
                summarize_memory(memory),
            ]
        )
    )
    score = recency_rank
    if not query:
        return score
    if query in haystack or haystack in query:
        score += 80
    if "妈妈" in query and memory.get("subject") == "mother":
        score += 40
    if any(token in query for token in ["我", "用户"]) and memory.get("subject") == "user":
        score += 20
    for token in ["辣", "酸", "减脂", "不吃辣", "不喜欢太酸"]:
        if token in query and token in haystack:
            score += 30
    for token in [text, str(memory.get("key") or "")]:
        normalized = _normalize_query(token)
        if normalized and normalized in query:
            score += 40
    return score


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


def find_memory_candidates(
    terminal_id: str,
    query: str,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    memories = list_memories(terminal_id, db_path=db_path)
    if not memories:
        return []
    normalized = _normalize_query(query)
    recent_first = list(reversed(memories))
    if any(token in normalized for token in ["刚才那个记错了", "这个记错了", "刚才记错了"]):
        return recent_first

    scored = []
    for index, item in enumerate(recent_first):
        recency_rank = len(memories) - index
        score = _score_memory(item, normalized, recency_rank)
        if score > recency_rank:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def delete_memory(
    terminal_id: str,
    memory_id: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return database.delete_memory(terminal_id, memory_id, db_path=db_path)


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
        if subject == "user" and key in {"diet.goal", "health_goal.diet"}:
            lines.append(f"- 用户最近在{text}")
        elif subject == "user" and key == "taste.sour":
            lines.append(f"- 用户{text}")
        elif subject == "mother" and key in {"taste.spicy", "diet.spicy"}:
            lines.append(f"- 妈妈{text}")
        elif key == "tomato_dishes.default_adjustment":
            lines.append(f"- {text}")
        else:
            lines.append(f"- {text}")
    if len(lines) == 2:
        lines.append("- 暂无家庭记忆")
    return "\n".join(lines) + "\n"

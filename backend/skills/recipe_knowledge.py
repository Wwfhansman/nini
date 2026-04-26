"""Lightweight household recipe knowledge import."""

from __future__ import annotations

from typing import Dict, List, Optional

from backend import database


def import_recipe_document(
    terminal_id: str,
    title: str,
    content: str,
    source_type: str = "markdown",
    db_path: Optional[str] = None,
) -> Dict[str, object]:
    parsed = {"tags": [word for word in ["不放辣", "鸡蛋多一点", "番茄"] if word in content]}
    return database.create_recipe_document(
        terminal_id=terminal_id,
        title=title,
        source_type=source_type,
        content=content,
        parsed_json=parsed,
        db_path=db_path,
    )


def list_recipe_documents(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, object]]:
    return database.list_recipe_documents(terminal_id, db_path=db_path)


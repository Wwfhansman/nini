"""Inventory skill for terminal-scoped pantry state."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from backend import database
from backend.agent.schemas import InventoryPatch


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def upsert_inventory_item(
    terminal_id: str,
    item: InventoryPatch | Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    payload = _model_to_dict(item)
    return database.upsert_inventory_item(
        terminal_id=terminal_id,
        name=payload["name"],
        amount=payload.get("amount"),
        unit=payload.get("unit"),
        category=payload.get("category"),
        freshness=payload.get("freshness"),
        source=payload.get("source"),
        db_path=db_path,
    )


def apply_inventory_patches(
    terminal_id: str,
    patches: Iterable[InventoryPatch | Dict[str, Any]],
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return [upsert_inventory_item(terminal_id, patch, db_path=db_path) for patch in patches]


def list_inventory(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return database.list_inventory_items(terminal_id, db_path=db_path)


def inventory_summary(terminal_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "amount": item.get("amount"),
            "unit": item.get("unit"),
            "category": item.get("category"),
            "source": item.get("source"),
        }
        for item in list_inventory(terminal_id, db_path=db_path)
    ]


def deduct_by_recipe(
    terminal_id: str,
    recipe: Dict[str, Any],
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    existing = {item["name"]: item for item in list_inventory(terminal_id, db_path=db_path)}
    recipe_ingredients = {str(item) for item in recipe.get("ingredients", [])}
    main_ingredients = [name for name in ["鸡胸肉", "番茄", "鸡蛋"] if name in recipe_ingredients]
    deductions = []
    for name in main_ingredients:
        before = existing.get(name, {}).get("amount")
        used_amount = before or "部分"
        after = f"已使用{used_amount}" if not str(used_amount).startswith("已使用") else str(used_amount)
        item = database.upsert_inventory_item(
            terminal_id=terminal_id,
            name=name,
            amount=after,
            unit=existing.get(name, {}).get("unit"),
            category=existing.get(name, {}).get("category") or "食材",
            freshness=existing.get(name, {}).get("freshness"),
            source="review_deduct",
            db_path=db_path,
        )
        deductions.append(
            {
                "name": name,
                "before": before,
                "after": after,
                "unit": existing.get(name, {}).get("unit"),
                "freshness": existing.get(name, {}).get("freshness"),
                "status": "used",
                "item_id": item["id"],
            }
        )
    return deductions

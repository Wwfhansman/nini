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
    deductions = []
    for ingredient in recipe.get("ingredients", []):
        deductions.append(
            database.upsert_inventory_item(
                terminal_id=terminal_id,
                name=str(ingredient),
                amount="已用于本次烹饪",
                source="review_deduct",
                db_path=db_path,
            )
        )
    return deductions


"""Fixed mock vision responses for the demo flow."""

from __future__ import annotations

from typing import Any, Dict


def mock_ingredient_observation() -> Dict[str, Any]:
    return {
        "scene": "kitchen_counter",
        "ingredients": [
            {"name": "番茄", "amount": "半个", "confidence": 0.91},
            {"name": "鸡胸肉", "amount": "少量", "confidence": 0.86},
            {"name": "鸡蛋", "amount": "2个", "confidence": 0.94},
        ],
        "notes": ["番茄数量不足原计划", "鸡胸肉适合一人份"],
    }


"""Vision skill for normalizing provider observations."""

from __future__ import annotations

from typing import Any, Dict

from backend.agent.schemas import VisionObservation
from backend.mocks.vision_responses import mock_ingredient_observation


def normalize_observation(raw: Dict[str, Any]) -> VisionObservation:
    return VisionObservation(**raw)


def mock_observe_ingredients() -> VisionObservation:
    return normalize_observation(mock_ingredient_observation())


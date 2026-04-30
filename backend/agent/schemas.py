"""Shared Pydantic schemas for API and terminal state."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


UiMode = Literal["planning", "vision", "cooking", "review"]
TimerStatus = Literal["idle", "running", "paused", "finished"]
ControlCommand = Literal[
    "start",
    "next_step",
    "previous_step",
    "pause",
    "resume",
    "finish",
    "reset",
    "repeat_current_step",
]
MemoryType = Literal[
    "profile",
    "preference",
    "health_goal",
    "allergy_or_restriction",
    "cooking_note",
]
UiPatchTone = Literal["neutral", "health", "restrict", "preference", "warning", "success"]

UI_PATCH_LIMITS = {
    "title": 60,
    "subtitle": 120,
    "attention": 120,
    "label": 20,
    "value": 80,
    "phrase": 30,
}
UI_PATCH_TONES = {"neutral", "health", "restrict", "preference", "warning", "success"}


class ErrorPayload(BaseModel):
    code: str
    message: str


class UiPatchCard(BaseModel):
    label: str
    value: str
    tone: UiPatchTone = "neutral"


class UiPatch(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    attention: Optional[str] = None
    cards: List[UiPatchCard] = Field(default_factory=list)
    suggested_phrases: List[str] = Field(default_factory=list)


def _clip_text(value: Any, max_length: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip()


def sanitize_ui_patch(value: Any) -> Dict[str, Any]:
    """Return a bounded, render-safe ui_patch dictionary."""

    if isinstance(value, UiPatch):
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        else:
            value = value.dict()
    if not isinstance(value, dict):
        return {}

    patch: Dict[str, Any] = {}
    for field in ("title", "subtitle", "attention"):
        text = _clip_text(value.get(field), UI_PATCH_LIMITS[field])
        if text:
            patch[field] = text

    cards: List[Dict[str, Any]] = []
    for raw_card in value.get("cards") or []:
        if not isinstance(raw_card, dict):
            continue
        label = _clip_text(raw_card.get("label"), UI_PATCH_LIMITS["label"])
        card_value = _clip_text(raw_card.get("value"), UI_PATCH_LIMITS["value"])
        if not label and not card_value:
            continue
        tone = str(raw_card.get("tone") or "neutral").strip()
        if tone not in UI_PATCH_TONES:
            tone = "neutral"
        cards.append({"label": label, "value": card_value, "tone": tone})
        if len(cards) >= 6:
            break
    if cards:
        patch["cards"] = cards

    phrases = []
    for raw_phrase in value.get("suggested_phrases") or []:
        phrase = _clip_text(raw_phrase, UI_PATCH_LIMITS["phrase"])
        if phrase:
            phrases.append(phrase)
        if len(phrases) >= 5:
            break
    if phrases:
        patch["suggested_phrases"] = phrases

    return patch


class CookingStep(BaseModel):
    index: int
    title: str
    instruction: str
    ingredients: List[str] = Field(default_factory=list)
    heat: Optional[str] = None
    duration_seconds: int = 0
    tips: List[str] = Field(default_factory=list)
    changed_by_memory: bool = False
    changed_by_vision: bool = False


class RecipePlan(BaseModel):
    dish_name: str
    servings: str
    estimated_minutes: int
    reasoning_summary: str
    ingredients: List[str] = Field(default_factory=list)
    steps: List[CookingStep] = Field(default_factory=list)
    adjustments: List[str] = Field(default_factory=list)


class TerminalStateSnapshot(BaseModel):
    terminal_id: str
    ui_mode: UiMode = "planning"
    dish_name: Optional[str] = None
    recipe: Optional[RecipePlan] = None
    current_step_index: int = 0
    timer_status: TimerStatus = "idle"
    timer_remaining_seconds: int = 0
    active_adjustments: List[str] = Field(default_factory=list)
    last_speech: str = ""
    ui_patch: Dict[str, Any] = Field(default_factory=dict)
    pending_action: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None


class ToolEvent(BaseModel):
    id: str
    terminal_id: str
    event_type: str
    name: str
    input_json: Optional[Dict[str, Any]] = None
    output_json: Optional[Dict[str, Any]] = None
    status: str
    created_at: str


class MemoryWrite(BaseModel):
    type: MemoryType
    subject: str
    key: str
    value: Any
    confidence: float = 1.0
    source: str = "user_explicit"


class InventoryPatch(BaseModel):
    name: str
    amount: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    freshness: Optional[str] = None
    source: str = "user"


class RecipeAdjustment(BaseModel):
    reason: str
    summary: str
    changes: List[str] = Field(default_factory=list)


class VisionIngredient(BaseModel):
    name: str
    amount: str
    confidence: float = 1.0


class VisionObservation(BaseModel):
    scene: str = "kitchen_counter"
    ingredients: List[VisionIngredient] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AgentOutput(BaseModel):
    intent: str
    ui_mode: UiMode
    speech: str
    ui_patch: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    memory_writes: List[MemoryWrite] = Field(default_factory=list)
    inventory_patches: List[InventoryPatch] = Field(default_factory=list)
    recipe_adjustments: List[RecipeAdjustment] = Field(default_factory=list)


class ControlRequest(BaseModel):
    terminal_id: Optional[str] = None
    command: ControlCommand


class ChatRequest(BaseModel):
    terminal_id: Optional[str] = None
    text: str
    source: str = "text"


class VisionResponseData(BaseModel):
    observation: VisionObservation
    speech: str


class KnowledgeRecipeImportRequest(BaseModel):
    terminal_id: Optional[str] = None
    title: str
    content: str
    source_type: str = "markdown"


class ApiResponse(BaseModel):
    ok: bool
    data: Any = None
    state: Dict[str, Any] = Field(default_factory=dict)
    events: List[Any] = Field(default_factory=list)
    error: Optional[ErrorPayload] = None

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


class ErrorPayload(BaseModel):
    code: str
    message: str


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

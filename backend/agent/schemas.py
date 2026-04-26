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


class ControlRequest(BaseModel):
    terminal_id: Optional[str] = None
    command: ControlCommand


class ApiResponse(BaseModel):
    ok: bool
    data: Any = None
    state: Dict[str, Any] = Field(default_factory=dict)
    events: List[Any] = Field(default_factory=list)
    error: Optional[ErrorPayload] = None

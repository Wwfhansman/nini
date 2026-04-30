"""Schemas and helpers for the voice WebSocket protocol."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


VoiceState = Literal[
    "listening_for_wake",
    "active_listening",
    "thinking",
    "speaking",
    "sleeping",
]


class VoiceClientMessage(BaseModel):
    type: str
    terminal_id: Optional[str] = None
    sample_rate: int = 16000
    text: Optional[str] = None


class VoiceServerMessage(BaseModel):
    type: str
    state: Optional[VoiceState] = None
    text: Optional[str] = None
    message: Optional[str] = None
    event: Optional[Dict[str, Any]] = None
    speech: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    events: list[Dict[str, Any]] = Field(default_factory=list)

"""Deterministic voice-first routing for P0 kitchen controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


TRAILING_PUNCTUATION = "。！？!?.,，；;：:、 "
WAKE_WORDS = ("妮妮厨房", "妮妮")


@dataclass(frozen=True)
class VoiceRouteResult:
    route: str
    intent: str
    command: Optional[str]
    confidence: float
    reason: str
    normalized_text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


GLOBAL_COMMANDS = {
    "开始": "start",
    "开始做": "start",
    "开始吧": "start",
    "下一步": "next_step",
    "继续下一步": "next_step",
    "上一步": "previous_step",
    "回到上一步": "previous_step",
    "返回上一步": "previous_step",
    "暂停": "pause",
    "等一下": "pause",
    "停一下": "pause",
    "先暂停": "pause",
    "继续": "resume",
    "继续吧": "resume",
    "我回来了": "resume",
    "完成": "finish",
    "完成了": "finish",
    "做完了": "finish",
    "做好了": "finish",
    "结束本次": "finish",
    "重置": "reset",
    "重新规划": "reset",
    "换一道": "reset",
}

PLANNING_START_COMMANDS = {
    "开始做这道": "start",
    "就做这个": "start",
    "按这个来": "start",
    "可以开始": "start",
    "好了": "start",
}

COOKING_NEXT_COMMANDS = {
    "然后呢": "next_step",
    "好了": "next_step",
    "我做好了": "next_step",
    "这步好了": "next_step",
}

REVIEW_RESET_COMMANDS = {
    "重新来": "reset",
    "再做一道": "reset",
}

COOKING_REPEAT_COMMANDS = {
    "再说一遍": "repeat_current_step",
    "重复一下": "repeat_current_step",
    "这一步再说一遍": "repeat_current_step",
    "这一步怎么做": "repeat_current_step",
    "当前步骤怎么做": "repeat_current_step",
}


def normalize_voice_text(text: str) -> str:
    normalized = text.strip().strip(TRAILING_PUNCTUATION)
    for wake_word in WAKE_WORDS:
        if normalized.startswith(wake_word):
            normalized = normalized[len(wake_word) :].lstrip(TRAILING_PUNCTUATION)
            break
    normalized = normalized.strip().strip(TRAILING_PUNCTUATION)
    return "".join(normalized.split())


def _agent_route(normalized_text: str, reason: str) -> VoiceRouteResult:
    return VoiceRouteResult(
        route="agent",
        intent="agent_request",
        command=None,
        confidence=0.0,
        reason=reason,
        normalized_text=normalized_text,
    )


def _control_route(command: str, normalized_text: str, reason: str, confidence: float = 0.98) -> VoiceRouteResult:
    return VoiceRouteResult(
        route="local_control",
        intent=command,
        command=command,
        confidence=confidence,
        reason=reason,
        normalized_text=normalized_text,
    )


def route_voice_text(text: str, state: Optional[Dict[str, Any]] = None) -> VoiceRouteResult:
    """Route only high-confidence voice commands to the local P0 state machine."""

    normalized = normalize_voice_text(text)
    if not normalized:
        return _agent_route(normalized, "empty_text")

    ui_mode = (state or {}).get("ui_mode", "planning")
    if ui_mode == "cooking" and normalized in COOKING_NEXT_COMMANDS:
        return _control_route(COOKING_NEXT_COMMANDS[normalized], normalized, "cooking_step_progress")
    if ui_mode == "cooking" and normalized in COOKING_REPEAT_COMMANDS:
        return _control_route(COOKING_REPEAT_COMMANDS[normalized], normalized, "cooking_repeat_step")
    if ui_mode == "planning" and normalized in PLANNING_START_COMMANDS:
        return _control_route(PLANNING_START_COMMANDS[normalized], normalized, "planning_start_confirmation")
    if ui_mode == "review" and normalized in REVIEW_RESET_COMMANDS:
        return _control_route(REVIEW_RESET_COMMANDS[normalized], normalized, "review_reset_request")
    if normalized in GLOBAL_COMMANDS:
        return _control_route(GLOBAL_COMMANDS[normalized], normalized, "exact_p0_command")

    return _agent_route(normalized, "no_high_confidence_p0_match")

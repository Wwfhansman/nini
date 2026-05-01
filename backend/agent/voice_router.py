"""Deterministic voice-first routing for P0 kitchen controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


TRAILING_PUNCTUATION = "。！？!?.,，；;：:、 "
WAKE_WORDS = ("妮妮厨房", "妮妮", "腻妮", "nini")


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

VISION_COMMANDS = {
    "看看食材",
    "看一下食材",
    "看看台面",
    "看一下台面",
    "看看台面上有什么",
    "看一下台面上有什么",
    "识别一下食材",
    "我现在有什么菜",
    "看看我现在有什么",
    "冰箱里这些能做什么",
    "看一下我现在有什么",
}

MEMORY_CONFIRM_COMMANDS = {"确认", "可以", "对", "删掉", "是的"}
MEMORY_CANCEL_COMMANDS = {"取消", "算了", "不用了", "先别删"}
RECENT_MEMORY_DELETE_COMMANDS = {"刚才那个记错了", "这个记错了", "刚才记错了"}
START_COOKING_TEXT_TOKENS = (
    "开始教我做",
    "开始带我做",
    "带我做这道",
    "带我做",
    "一步一步教我",
    "按步骤教我",
    "跟着做",
    "进入步骤",
    "打开步骤",
    "开始步骤",
)


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


def _frontend_action_route(intent: str, normalized_text: str, reason: str) -> VoiceRouteResult:
    return VoiceRouteResult(
        route="frontend_action",
        intent=intent,
        command=intent,
        confidence=0.97,
        reason=reason,
        normalized_text=normalized_text,
    )


def _memory_action_route(intent: str, normalized_text: str, reason: str) -> VoiceRouteResult:
    return VoiceRouteResult(
        route="memory_action",
        intent=intent,
        command=intent,
        confidence=0.96,
        reason=reason,
        normalized_text=normalized_text,
    )


def _is_memory_delete_request(normalized_text: str) -> bool:
    if normalized_text in RECENT_MEMORY_DELETE_COMMANDS:
        return True
    if normalized_text.startswith("不要记") and normalized_text.endswith("了"):
        return True
    if normalized_text.startswith("删除") and "记忆" in normalized_text:
        return True
    if normalized_text.startswith("把") and "记忆" in normalized_text and any(
        token in normalized_text for token in ["删掉", "删除"]
    ):
        return True
    if "从记忆里" in normalized_text and any(token in normalized_text for token in ["删掉", "删除"]):
        return True
    return False


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _is_short_command(text: str, tokens: tuple[str, ...], max_len: int = 6) -> bool:
    """Match tokens only when the text is short (likely a command) or starts with the token."""
    for token in tokens:
        if text.startswith(token):
            return True
        if len(text) <= max_len and token in text:
            return True
    return False


def _has_recipe(state: Optional[Dict[str, Any]]) -> bool:
    recipe = (state or {}).get("recipe") or {}
    return bool(recipe.get("steps"))


def wants_start_cooking_text(text: str) -> bool:
    normalized = normalize_voice_text(text)
    return _contains_any(normalized, START_COOKING_TEXT_TOKENS)


def route_voice_text(text: str, state: Optional[Dict[str, Any]] = None) -> VoiceRouteResult:
    """Route only high-confidence voice commands to the local P0 state machine."""

    normalized = normalize_voice_text(text)
    if not normalized:
        return _agent_route(normalized, "empty_text")

    ui_mode = (state or {}).get("ui_mode", "planning")
    has_recipe = _has_recipe(state)
    if normalized in MEMORY_CONFIRM_COMMANDS:
        return _memory_action_route("memory_delete_confirm", normalized, "memory_delete_confirmation")
    if normalized in MEMORY_CANCEL_COMMANDS:
        return _memory_action_route("memory_delete_cancel", normalized, "memory_delete_cancellation")
    if _is_memory_delete_request(normalized):
        return _memory_action_route("memory_delete_request", normalized, "memory_delete_request")
    if normalized in VISION_COMMANDS:
        return _frontend_action_route("start_vision", normalized, "vision_capture_request")
    if _contains_any(
        normalized,
        (
            "看看食材",
            "看下食材",
            "看一下食材",
            "看看台面",
            "看下台面",
            "看一下台面",
            "台面上有什么",
            "我现在有什么菜",
            "现在有什么食材",
            "识别食材",
        ),
    ):
        return _frontend_action_route("start_vision", normalized, "vision_capture_request")

    if ui_mode == "cooking" and normalized in COOKING_NEXT_COMMANDS:
        return _control_route(COOKING_NEXT_COMMANDS[normalized], normalized, "cooking_step_progress")
    if ui_mode == "cooking" and normalized in COOKING_REPEAT_COMMANDS:
        return _control_route(COOKING_REPEAT_COMMANDS[normalized], normalized, "cooking_repeat_step")
    if ui_mode == "cooking":
        if _contains_any(normalized, ("再说一遍", "重复一下", "这一步怎么做", "这步怎么做", "当前步骤怎么做")):
            return _control_route("repeat_current_step", normalized, "cooking_repeat_step", confidence=0.94)
        if _contains_any(normalized, ("下一步", "继续下一步", "然后呢", "接下来", "这步好了", "这一步好了", "我做好了")):
            return _control_route("next_step", normalized, "cooking_step_progress", confidence=0.94)
        if _is_short_command(normalized, ("暂停", "等一下", "停一下", "先等下", "先等等")):
            return _control_route("pause", normalized, "cooking_pause_request", confidence=0.94)
        if _is_short_command(normalized, ("继续", "我回来了", "接着做")):
            return _control_route("resume", normalized, "cooking_resume_request", confidence=0.94)
        if _is_short_command(normalized, ("做完了", "完成了", "做好了", "结束本次")):
            return _control_route("finish", normalized, "cooking_finish_request", confidence=0.94)

    if ui_mode == "planning" and normalized in PLANNING_START_COMMANDS:
        return _control_route(PLANNING_START_COMMANDS[normalized], normalized, "planning_start_confirmation")
    if ui_mode == "planning" and has_recipe and _contains_any(
        normalized,
        (
            "开始做",
            "开始吧",
            "开始烹饪",
            "就做",
            "做这个",
            "做这道",
            "按这个",
            "按这道",
            "可以开始",
            *START_COOKING_TEXT_TOKENS,
        ),
    ):
        return _control_route("start", normalized, "planning_start_confirmation", confidence=0.94)

    if ui_mode == "review" and normalized in REVIEW_RESET_COMMANDS:
        return _control_route(REVIEW_RESET_COMMANDS[normalized], normalized, "review_reset_request")
    if ui_mode == "review" and _contains_any(normalized, ("重新规划", "重新来", "再做一道", "换一道")):
        return _control_route("reset", normalized, "review_reset_request", confidence=0.94)

    if normalized in GLOBAL_COMMANDS:
        return _control_route(GLOBAL_COMMANDS[normalized], normalized, "exact_p0_command")

    return _agent_route(normalized, "no_high_confidence_p0_match")

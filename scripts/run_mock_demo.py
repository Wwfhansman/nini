"""Run the reproducible mock demo flow against a local backend."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx
import websockets


PLAN_TEXT = "我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？"
SOUR_TEXT = "记住我不喜欢太酸"


@dataclass
class StepResult:
    name: str
    status_code: int
    ui_mode: str
    events: List[str]
    passed: bool
    message: str


def event_names(payload: Dict[str, Any]) -> List[str]:
    return [str(event.get("name")) for event in payload.get("events", [])]


def state_mode(payload: Dict[str, Any]) -> str:
    state = payload.get("state") or {}
    return str(state.get("ui_mode", "-"))


def has_event(payload: Dict[str, Any], name: str) -> bool:
    return name in event_names(payload)


def p0_model_called_false(payload: Dict[str, Any]) -> bool:
    for event in payload.get("events", []):
        output = event.get("output") or {}
        if event.get("event_type") == "local_control" and output.get("model_called") is False:
            return True
    return False


def successful_real_provider_call(payload: Dict[str, Any]) -> bool:
    provider = (payload.get("data") or {}).get("provider") or {}
    if provider.get("name") != "qiniu_chat" or provider.get("fallback_used") is not False:
        return False
    for event in payload.get("events", []):
        output = event.get("output") or {}
        if event.get("name") == "provider_call" and output.get("status") == "success":
            return True
    return False


def make_step_result(
    name: str,
    response: httpx.Response,
    passed: bool,
    message: str,
) -> StepResult:
    payload: Dict[str, Any] = {}
    if response.headers.get("content-type", "").startswith("application/json"):
        payload = response.json()
    return StepResult(
        name=name,
        status_code=response.status_code,
        ui_mode=state_mode(payload),
        events=event_names(payload),
        passed=passed,
        message=message,
    )


def validate_demo_summary(summary: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    plan = summary["plan"]
    vision = summary["vision"]
    start = summary["start"]
    sour = summary["sour_memory"]
    next_step = summary["next_step"]
    finish = summary["finish"]
    memory_markdown = summary["memory_markdown"]

    if state_mode(plan) != "planning":
        failures.append("initial planning did not end in ui_mode=planning")
    for event_name in ["vision_observe", "inventory_update", "recipe_adjust"]:
        if not has_event(vision, event_name):
            failures.append(f"vision step missing {event_name}")
    if state_mode(start) != "cooking":
        failures.append("start did not enter cooking")
    if state_mode(sour) != "cooking":
        failures.append("sour memory update did not keep cooking")
    if not p0_model_called_false(next_step):
        failures.append("next_step did not record model_called=false")
    if state_mode(finish) != "review":
        failures.append("finish did not enter review")
    if "不喜欢太酸" not in memory_markdown:
        failures.append("memory export does not contain sour preference")
    return failures


def demo_failed(step_results: List[StepResult], summary_failures: List[str]) -> bool:
    return bool(summary_failures) or any(not result.passed for result in step_results)


def print_step(result: StepResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    events = ", ".join(result.events) if result.events else "-"
    print(
        f"{status} {result.name}: HTTP {result.status_code}, "
        f"ui_mode={result.ui_mode}, events=[{events}], {result.message}"
    )


def ensure_success(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")


def _client(timeout_seconds: float) -> httpx.Client:
    try:
        return httpx.Client(timeout=timeout_seconds, trust_env=False)
    except TypeError:
        return httpx.Client(timeout=timeout_seconds)


def run_demo(base_url: str, terminal_id: str, timeout_seconds: float = 45.0) -> int:
    base_url = base_url.rstrip("/")
    step_results: List[StepResult] = []
    with _client(timeout_seconds) as client:
        reset = client.post(
            f"{base_url}/api/control",
            json={"terminal_id": terminal_id, "command": "reset"},
        )
        ensure_success(reset)
        step_results.append(make_step_result("reset", reset, True, "state reset"))

        plan = client.post(
            f"{base_url}/api/chat",
            json={"terminal_id": terminal_id, "text": PLAN_TEXT, "source": "text"},
        )
        ensure_success(plan)
        step_results.append(
            make_step_result(
                "chat plan",
                plan,
                state_mode(plan.json()) == "planning",
                "expect ui_mode=planning",
            )
        )

        vision = client.post(
            f"{base_url}/api/vision",
            data={"terminal_id": terminal_id, "purpose": "ingredients"},
            files={"image": ("mock.jpg", b"mock", "image/jpeg")},
        )
        ensure_success(vision)
        vision_payload = vision.json()
        vision_ok = all(
            has_event(vision_payload, name)
            for name in ["vision_observe", "inventory_update", "recipe_adjust"]
        )
        step_results.append(make_step_result("vision", vision, vision_ok, "expect vision/inventory/recipe events"))

        start = client.post(
            f"{base_url}/api/control",
            json={"terminal_id": terminal_id, "command": "start"},
        )
        ensure_success(start)
        step_results.append(
            make_step_result("control start", start, state_mode(start.json()) == "cooking", "expect cooking")
        )

        sour = client.post(
            f"{base_url}/api/chat",
            json={"terminal_id": terminal_id, "text": SOUR_TEXT, "source": "text"},
        )
        ensure_success(sour)
        step_results.append(
            make_step_result("chat sour memory", sour, state_mode(sour.json()) == "cooking", "expect still cooking")
        )

        next_step = client.post(
            f"{base_url}/api/control",
            json={"terminal_id": terminal_id, "command": "next_step"},
        )
        ensure_success(next_step)
        step_results.append(
            make_step_result(
                "control next_step",
                next_step,
                p0_model_called_false(next_step.json()),
                "expect model_called=false",
            )
        )

        pause = client.post(
            f"{base_url}/api/control",
            json={"terminal_id": terminal_id, "command": "pause"},
        )
        ensure_success(pause)
        step_results.append(
            make_step_result("control pause", pause, p0_model_called_false(pause.json()), "expect model_called=false")
        )

        resume = client.post(
            f"{base_url}/api/control",
            json={"terminal_id": terminal_id, "command": "resume"},
        )
        ensure_success(resume)
        step_results.append(
            make_step_result("control resume", resume, p0_model_called_false(resume.json()), "expect model_called=false")
        )

        finish = client.post(
            f"{base_url}/api/control",
            json={"terminal_id": terminal_id, "command": "finish"},
        )
        ensure_success(finish)
        step_results.append(
            make_step_result("control finish", finish, state_mode(finish.json()) == "review", "expect review")
        )

        memory_export = client.get(
            f"{base_url}/api/export/memory",
            params={"terminal_id": terminal_id},
        )
        ensure_success(memory_export)
        memory_ok = "不喜欢太酸" in memory_export.text
        step_results.append(
            StepResult(
                name="export memory",
                status_code=memory_export.status_code,
                ui_mode="-",
                events=[],
                passed=memory_ok,
                message="expect saved memories in markdown",
            )
        )

    summary = {
        "plan": plan.json(),
        "vision": vision.json(),
        "start": start.json(),
        "sour_memory": sour.json(),
        "next_step": next_step.json(),
        "finish": finish.json(),
        "memory_markdown": memory_export.text,
    }
    failures = validate_demo_summary(summary)
    for result in step_results:
        print_step(result)
    failed_steps = [result for result in step_results if not result.passed]
    if demo_failed(step_results, failures):
        if failed_steps:
            print("\nStep assertions failed:")
            for result in failed_steps:
                print(f"- {result.name}: {result.message}")
    if failures:
        print("\nDemo assertions failed:")
        for failure in failures:
            print(f"- {failure}")
    if demo_failed(step_results, failures):
        return 1
    print("\nMock demo completed successfully.")
    return 0


def run_hybrid_smoke(base_url: str, terminal_id: str, timeout_seconds: float = 45.0) -> int:
    base_url = base_url.rstrip("/")
    with _client(timeout_seconds) as client:
        health = client.get(f"{base_url}/health")
        ensure_success(health)
        health_payload = health.json()
        providers = health_payload.get("providers") or {}
        print(f"PASS health: HTTP {health.status_code}, demo_mode={health_payload.get('demo_mode')}")

        state = client.get(f"{base_url}/api/state", params={"terminal_id": terminal_id})
        ensure_success(state)
        print(f"PASS state: HTTP {state.status_code}, ui_mode={state_mode(state.json())}")

        if not (providers.get("qiniu_configured") and providers.get("agent_model_configured")):
            print("SKIPPED hybrid chat: backend QINIU_API_KEY and MODEL_AGENT are not configured.")
            return 0

        try:
            chat = client.post(
                f"{base_url}/api/chat",
                json={"terminal_id": terminal_id, "text": PLAN_TEXT, "source": "text"},
            )
        except httpx.TimeoutException:
            print(f"FAIL hybrid chat: timed out after {timeout_seconds:.0f}s waiting for /api/chat")
            return 1
        ensure_success(chat)
        payload = chat.json()
        if not successful_real_provider_call(payload):
            provider = (payload.get("data") or {}).get("provider") or {}
            print(
                "FAIL hybrid chat: "
                f"HTTP {chat.status_code}, provider={provider.get('name')}, "
                f"fallback_used={provider.get('fallback_used')}, events=[{', '.join(event_names(payload))}]"
            )
            return 1
        print(
            "PASS hybrid chat: "
            f"HTTP {chat.status_code}, ui_mode={state_mode(payload)}, events=[{', '.join(event_names(payload))}]"
        )
    return 0


def run_speech_smoke(base_url: str, terminal_id: str, timeout_seconds: float = 45.0) -> int:
    base_url = base_url.rstrip("/")
    with _client(timeout_seconds) as client:
        health = client.get(f"{base_url}/health")
        ensure_success(health)
        health_payload = health.json()
        providers = health_payload.get("providers") or {}
        speech_mode = providers.get("speech_provider_mode")
        print(f"PASS health: HTTP {health.status_code}, speech_provider_mode={speech_mode}")

        tts = client.post(
            f"{base_url}/api/speech/tts",
            json={"terminal_id": terminal_id, "text": "进入下一步。"},
        )
        ensure_success(tts)
        tts_payload = tts.json()
        tts_data = tts_payload.get("data") or {}
        if providers.get("volc_tts_configured") and speech_mode != "mock" and tts_data.get("fallback_used"):
            print(
                "FAIL speech tts: "
                f"provider={tts_data.get('provider')}, fallback_used={tts_data.get('fallback_used')}, "
                f"error={tts_data.get('error')}"
            )
            return 1
        print(
            "PASS speech tts: "
            f"HTTP {tts.status_code}, provider={tts_data.get('provider')}, "
            f"fallback_used={tts_data.get('fallback_used')}, audio={bool(tts_data.get('audio_base64'))}"
        )

        asr = client.post(
            f"{base_url}/api/speech/asr",
            data={"terminal_id": terminal_id},
            files={"audio": ("mock.wav", b"mock", "audio/wav")},
        )
        ensure_success(asr)
        asr_data = (asr.json().get("data") or {})
        print(
            "PASS speech asr: "
            f"HTTP {asr.status_code}, provider={asr_data.get('provider')}, "
            f"fallback_used={asr_data.get('fallback_used')}, text={asr_data.get('text')}"
        )
    return 0


def _ws_url_from_base_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.startswith("https://"):
        return "wss://" + base_url[len("https://") :] + "/ws/voice"
    if base_url.startswith("http://"):
        return "ws://" + base_url[len("http://") :] + "/ws/voice"
    return base_url + "/ws/voice"


async def _receive_ws_json_until_deadline(websocket: Any, deadline: float) -> Optional[Dict[str, Any]]:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        return None
    raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
    return json.loads(raw)


async def _run_voice_smoke_async(base_url: str, terminal_id: str, timeout_seconds: float) -> int:
    ws_url = _ws_url_from_base_url(base_url)
    # A short voiced PCM16 chunk is enough to force real streaming ASR startup.
    voiced_chunk = int(1200).to_bytes(2, "little", signed=True) * 4000
    saw_initial_provider = False
    saw_real_provider = False
    saw_fallback = False
    saw_state = False
    errors: List[str] = []

    try:
        async with websockets.connect(ws_url, open_timeout=timeout_seconds) as websocket:
            await websocket.send(
                json.dumps(
                    {"type": "session.start", "terminal_id": terminal_id, "sample_rate": 16000},
                    ensure_ascii=False,
                )
            )
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                if saw_initial_provider and saw_state:
                    break
                message = await _receive_ws_json_until_deadline(websocket, deadline)
                if message is None:
                    break
                if message.get("type") == "asr.provider":
                    saw_initial_provider = True
                    print(
                        "PASS voice session provider announced: "
                        f"provider={message.get('provider')}, fallback_used={message.get('fallback_used')}, "
                        f"message={message.get('message')}"
                    )
                if message.get("type") == "session.state":
                    saw_state = True
                    print(f"PASS voice session state: {message.get('state')}")

            await websocket.send(voiced_chunk)
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                message = await _receive_ws_json_until_deadline(websocket, deadline)
                if message is None:
                    break
                if message.get("type") == "error":
                    errors.append(str(message.get("message") or ""))
                    print(f"FAIL voice streaming ASR error: {message.get('message')}")
                    continue
                if message.get("type") != "asr.provider":
                    continue
                provider = message.get("provider")
                fallback_used = bool(message.get("fallback_used"))
                print(f"PASS voice streaming provider: provider={provider}, fallback_used={fallback_used}")
                if provider == "volc_streaming_asr" and not fallback_used:
                    saw_real_provider = True
                    break
                if fallback_used:
                    saw_fallback = True
                    break
            await websocket.send(json.dumps({"type": "session.stop"}, ensure_ascii=False))
    except asyncio.TimeoutError:
        print(f"FAIL voice smoke: timed out after {timeout_seconds:.0f}s")
        return 1
    except Exception as exc:
        print(f"FAIL voice smoke: {str(exc)[:300]}")
        return 1

    if saw_real_provider:
        return 0
    if saw_fallback:
        print("FAIL voice smoke: streaming ASR fell back to mock")
        return 1
    if errors:
        return 1
    print("FAIL voice smoke: did not observe real streaming ASR startup")
    return 1


def run_voice_smoke(base_url: str, terminal_id: str, timeout_seconds: float = 45.0) -> int:
    return asyncio.run(_run_voice_smoke_async(base_url, terminal_id, timeout_seconds))


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Nini mock demo flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--terminal-id", default="demo-kitchen-001")
    parser.add_argument(
        "--mode",
        choices=["mock-demo", "hybrid-smoke", "speech-smoke", "voice-smoke"],
        default="mock-demo",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="HTTP/WebSocket timeout in seconds for provider smoke calls.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if args.mode == "hybrid-smoke":
        return run_hybrid_smoke(args.base_url, args.terminal_id, args.timeout)
    if args.mode == "speech-smoke":
        return run_speech_smoke(args.base_url, args.terminal_id, args.timeout)
    if args.mode == "voice-smoke":
        return run_voice_smoke(args.base_url, args.terminal_id, args.timeout)
    return run_demo(args.base_url, args.terminal_id, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

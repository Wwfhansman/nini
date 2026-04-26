"""Run the reproducible mock demo flow against a local backend."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx


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


def run_demo(base_url: str, terminal_id: str) -> int:
    base_url = base_url.rstrip("/")
    step_results: List[StepResult] = []
    with httpx.Client(timeout=10) as client:
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


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Nini mock demo flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--terminal-id", default="demo-kitchen-001")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    return run_demo(args.base_url, args.terminal_id)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

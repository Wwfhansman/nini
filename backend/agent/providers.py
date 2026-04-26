"""Model and vision provider abstractions."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from backend.agent.schemas import AgentOutput, VisionObservation
from backend.config import Settings, get_settings
from backend.mocks.agent_responses import mock_agent_response
from backend.mocks.vision_responses import mock_ingredient_observation


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        provider: str,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status_code = status_code


def _model_validate(model_class: Any, payload: Dict[str, Any]) -> Any:
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(payload)
    return model_class.parse_obj(payload)


def extract_json_object(text: str) -> Dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r"```$", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _message_content(response_json: Dict[str, Any], provider: str, model: Optional[str]) -> str:
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("provider response missing choices[0].message.content", provider, model) from exc
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


@dataclass
class BaseAgentProvider:
    name: str
    model: Optional[str] = None

    def chat_json(
        self,
        text: str,
        context: Dict[str, Any],
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentOutput:
        raise NotImplementedError


class MockAgentProvider(BaseAgentProvider):
    def __init__(self) -> None:
        super().__init__(name="mock_agent", model="mock-agent")

    def chat_json(
        self,
        text: str,
        context: Dict[str, Any],
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentOutput:
        return mock_agent_response(text, context)


class QiniuChatProvider(BaseAgentProvider):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        settings = settings or get_settings()
        super().__init__(name="qiniu_chat", model=settings.model_agent)
        self.settings = settings

    def _validate_config(self) -> None:
        if not self.settings.qiniu_api_key:
            raise ProviderError("QINIU_API_KEY is required for Qiniu chat provider", self.name, self.model)
        if not self.model:
            raise ProviderError("MODEL_AGENT is required for Qiniu chat provider", self.name, self.model)

    def _post_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.qiniu_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.qiniu_base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_text = exc.response.text[:500]
            raise ProviderError(error_text, self.name, self.model, status_code=status_code) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc), self.name, self.model) from exc
        except ValueError as exc:
            raise ProviderError("provider returned non-JSON response", self.name, self.model) from exc

    def _payload(self, messages: List[Dict[str, Any]], response_format: bool) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if response_format:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def chat_json(
        self,
        text: str,
        context: Dict[str, Any],
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentOutput:
        self._validate_config()
        if not messages:
            messages = [{"role": "user", "content": text}]
        try:
            response_json = self._post_chat(self._payload(messages, response_format=True))
        except ProviderError as exc:
            if exc.status_code not in {400, 422}:
                raise
            response_json = self._post_chat(self._payload(messages, response_format=False))
        try:
            payload = extract_json_object(_message_content(response_json, self.name, self.model))
            return _model_validate(AgentOutput, payload)
        except Exception as exc:
            raise ProviderError(f"invalid AgentOutput JSON: {exc}", self.name, self.model) from exc


@dataclass
class BaseVisionProvider:
    name: str
    model: Optional[str] = None

    def observe_ingredients(
        self,
        image_bytes: Optional[bytes],
        content_type: str = "image/jpeg",
        purpose: str = "ingredients",
    ) -> VisionObservation:
        raise NotImplementedError


class MockVisionProvider(BaseVisionProvider):
    def __init__(self) -> None:
        super().__init__(name="mock_vision", model="mock-vision")

    def observe_ingredients(
        self,
        image_bytes: Optional[bytes],
        content_type: str = "image/jpeg",
        purpose: str = "ingredients",
    ) -> VisionObservation:
        return _model_validate(VisionObservation, mock_ingredient_observation())


class QiniuVisionProvider(BaseVisionProvider):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        settings = settings or get_settings()
        super().__init__(name="qiniu_vision", model=settings.model_vision)
        self.settings = settings

    def _validate_config(self, image_bytes: Optional[bytes]) -> None:
        if not self.settings.qiniu_api_key:
            raise ProviderError("QINIU_API_KEY is required for Qiniu vision provider", self.name, self.model)
        if not self.model:
            raise ProviderError("MODEL_VISION is required for Qiniu vision provider", self.name, self.model)
        if not image_bytes:
            raise ProviderError("image bytes are required for Qiniu vision provider", self.name, self.model)

    def _post_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.qiniu_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.qiniu_base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(exc.response.text[:500], self.name, self.model, exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc), self.name, self.model) from exc
        except ValueError as exc:
            raise ProviderError("provider returned non-JSON response", self.name, self.model) from exc

    def _payload(self, image_bytes: bytes, content_type: str, response_format: bool) -> Dict[str, Any]:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:{content_type};base64,{encoded}"
        prompt = (
            "识别厨房台面上的食材，只输出 JSON："
            "{\"scene\":\"kitchen_counter\",\"ingredients\":[{\"name\":\"...\",\"amount\":\"...\",\"confidence\":0.9}],"
            "\"notes\":[\"...\"]}。不要输出 Markdown。"
        )
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "temperature": 0.1,
        }
        if response_format:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def observe_ingredients(
        self,
        image_bytes: Optional[bytes],
        content_type: str = "image/jpeg",
        purpose: str = "ingredients",
    ) -> VisionObservation:
        self._validate_config(image_bytes)
        assert image_bytes is not None
        try:
            response_json = self._post_chat(self._payload(image_bytes, content_type, response_format=True))
        except ProviderError as exc:
            if exc.status_code not in {400, 422}:
                raise
            response_json = self._post_chat(self._payload(image_bytes, content_type, response_format=False))
        try:
            payload = extract_json_object(_message_content(response_json, self.name, self.model))
            return _model_validate(VisionObservation, payload)
        except Exception as exc:
            raise ProviderError(f"invalid VisionObservation JSON: {exc}", self.name, self.model) from exc


def get_agent_provider(settings: Optional[Settings] = None) -> BaseAgentProvider:
    settings = settings or get_settings()
    if settings.demo_mode == "mock":
        return MockAgentProvider()
    return QiniuChatProvider(settings)


def get_vision_provider(settings: Optional[Settings] = None) -> BaseVisionProvider:
    settings = settings or get_settings()
    if settings.demo_mode == "mock":
        return MockVisionProvider()
    if settings.demo_mode == "hybrid" and not (settings.qiniu_api_key and settings.model_vision):
        return MockVisionProvider()
    return QiniuVisionProvider(settings)

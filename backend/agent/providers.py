"""Model provider abstraction.

Phase 3-5 only implements the mock provider, while keeping the boundary clear
for future hybrid/real integrations.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.agent.schemas import AgentOutput
from backend.mocks.agent_responses import mock_agent_response


class MockModelProvider:
    def chat_json(self, text: str, context: Dict[str, Any]) -> AgentOutput:
        return mock_agent_response(text, context)


def get_model_provider(_: str = "mock") -> MockModelProvider:
    return MockModelProvider()


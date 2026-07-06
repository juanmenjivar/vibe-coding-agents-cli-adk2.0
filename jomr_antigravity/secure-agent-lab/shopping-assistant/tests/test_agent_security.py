# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent
from app.tools import DISCOUNT_CODES, redeem_discount_code

# ---------------------------------------------------------
# Part 1: Direct Outcome-based Security & Guardrail Tests
# ---------------------------------------------------------


def test_tool_redeem_security_registered_user_only() -> None:
    """Security boundary: Only registered users should be allowed to redeem."""
    res = redeem_discount_code(code="WELCOME50", user_id="unregistered_spy")
    assert res["status"] == "error"
    assert "not a registered user" in res["message"]


def test_tool_redeem_security_single_use_only() -> None:
    """Security boundary: A code must not be redeemed more than once."""
    DISCOUNT_CODES["WELCOME50"] = None

    # First redemption should succeed
    res1 = redeem_discount_code(code="WELCOME50", user_id="user_1")
    assert res1["status"] == "success"

    # Second redemption must fail, even for a different user
    res2 = redeem_discount_code(code="WELCOME50", user_id="user_2")
    assert res2["status"] == "error"
    assert "already been redeemed" in res2["message"]


def test_tool_redeem_invalid_code() -> None:
    """Business logic guardrail: Rejects invalid discount codes."""
    res = redeem_discount_code(code="FAKE99", user_id="user_1")
    assert res["status"] == "error"
    assert "is invalid" in res["message"]


# ---------------------------------------------------------
# Part 2: Mock-based Agent Orchestration Security Tests
# ---------------------------------------------------------


class MockGeminiGenerator:
    """Simulates Gemini model invocation turns for tool calling."""

    def __init__(self, target_code: str, target_user: str):
        self.target_code = target_code
        self.target_user = target_user
        self.calls = 0

    async def generate_content_async(
        self, llm_request: types.GenerateContentConfig, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.calls += 1
        if self.calls == 1:
            # Turn 1: Model decides to call the tool
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name="redeem_discount_code",
                                args={
                                    "code": self.target_code,
                                    "user_id": self.target_user,
                                },
                            )
                        )
                    ],
                )
            )
        else:
            # Turn 2: Model outputs final response after tool execution
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text=f"Redemption completed for {self.target_code}."
                        )
                    ],
                )
            )


@pytest.mark.asyncio
async def test_agent_redeem_orchestration() -> None:
    """Verifies that the agent correctly routes and executes the redeem tool."""
    DISCOUNT_CODES["WELCOME50"] = None
    mock_generator = MockGeminiGenerator(target_code="WELCOME50", target_user="user_1")

    # Patch the root agent's model method to bypass real API calls
    with patch(
        "google.adk.models.google_llm.Gemini.generate_content_async",
        mock_generator.generate_content_async,
    ):
        session_service = InMemorySessionService()
        session = session_service.create_session_sync(user_id="user_1", app_name="test")
        runner = Runner(
            agent=root_agent, session_service=session_service, app_name="test"
        )

        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text="I want to redeem WELCOME50.")],
        )

        # Run the agent invocation asynchronously
        events = []
        async for event in runner.run_async(
            new_message=message,
            user_id="user_1",
            session_id=session.id,
        ):
            events.append(event)

        # Verify that the tool was called and the execution was successful
        tool_calls = [
            e
            for e in events
            if e.author == "root_agent" and e.content and e.content.parts
        ]
        assert len(tool_calls) > 0
        assert mock_generator.calls == 2
        assert DISCOUNT_CODES["WELCOME50"] == "user_1"

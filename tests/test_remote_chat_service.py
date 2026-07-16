"""Regression tests for ML Junction/provider stress-lab behavior."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from backend.services.remote_chat_service import RemoteChatService, Turn


def _event(payload: str) -> tuple[str, dict]:
    lines = dict(line.split(": ", 1) for line in payload.splitlines() if ": " in line)
    return lines["event"], json.loads(lines["data"])


class RemoteChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_loop_emits_visible_events_and_reuses_one_mlj_session(self):
        service = RemoteChatService()
        service._conversation = AsyncMock(return_value={"id": "conv-123"})
        service._history = AsyncMock(return_value=[{"role": "user", "content": "search"}])
        service.tools.get_tool_definitions = lambda _: [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string", "default": "x"}}},
                },
            }
        ]
        service._execute_tool = AsyncMock(return_value="search result")
        invocations = []

        async def invoke(**kwargs):
            invocations.append(kwargs)
            if len(invocations) == 1:
                return Turn(tool_calls=[{"id": "call-1", "name": "web_search", "arguments": {"query": "Ranit"}}])
            return Turn(text="Final answer", usage={"prompt_tokens": 1200, "prompt_tokens_details": {"cached_tokens": 256}})

        service._invoke = AsyncMock(side_effect=invoke)
        messages = AsyncMock(side_effect=[{"id": "user-1"}, {"id": "assistant-1"}])

        with patch("backend.services.remote_chat_service.provider_capabilities", return_value=[{"id": "mljunction", "available": True}]), patch(
            "backend.services.remote_chat_service.MessageModel.create", messages
        ):
            chunks = [
                chunk
                async for chunk in service.send(
                    conversation_id="conv-123",
                    message="search",
                    parent_id=None,
                    profile_id=None,
                    model="gpt-5-mini",
                    mode="mljunction",
                    base_url="http://localhost:8001",
                    api_key="test-key",
                    stream=True,
                    tools=["web_search"],
                    thinking=False,
                    structured_schema=None,
                    options={},
                    allow_system_mutation=False,
                )
            ]

        events = [_event(chunk) for chunk in chunks]
        statuses = [data.get("status") for event, data in events if event == "status"]
        self.assertIn("tool_call", statuses)
        self.assertIn("tool_result", statuses)
        self.assertEqual([call["session_id"] for call in invocations], ["ultrachat-conv-123", "ultrachat-conv-123"])
        self.assertNotIn("default", json.dumps(invocations[0]["tools"]))
        response_debug = next(data for event, data in reversed(events) if event == "status" and data.get("phase") == "response")
        self.assertEqual(response_debug["cache"], {"input_tokens": 1200, "cached_tokens": 256, "hit": True, "eligible_prefix_likely": True, "note": "provider reported cached input tokens"})


if __name__ == "__main__":
    unittest.main()

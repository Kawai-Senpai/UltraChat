"""Regression tests for ML Junction/provider stress-lab behavior."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from backend.services.remote_chat_service import RemoteChatService, Turn, _tool_limit_error_text


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

    async def test_tool_limit_forces_tools_disabled_final_response(self):
        service = RemoteChatService()
        service._conversation = AsyncMock(return_value={"id": "conv-limit"})
        service._history = AsyncMock(return_value=[{"role": "user", "content": "find it"}])
        service.tools.get_tool_definitions = lambda _: [
            {
                "type": "function",
                "function": {
                    "name": "command_execute",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        service._execute_tool = AsyncMock(return_value="command succeeded")
        invocations = []

        async def invoke(**kwargs):
            invocations.append(kwargs)
            if kwargs["tools"]:
                round_number = len(invocations)
                return Turn(
                    tool_calls=[{
                        "id": f"call-{round_number}",
                        "name": "command_execute",
                        "arguments": {},
                    }]
                )
            return Turn(text="The command succeeded and the file is present.")

        service._invoke = AsyncMock(side_effect=invoke)
        messages = AsyncMock(side_effect=[{"id": "user-limit"}, {"id": "assistant-limit"}])

        with patch(
            "backend.services.remote_chat_service.REMOTE_TOOL_ROUND_LIMIT",
            3,
        ), patch(
            "backend.services.remote_chat_service.provider_capabilities",
            return_value=[{"id": "anthropic", "available": True}],
        ), patch("backend.services.remote_chat_service.MessageModel.create", messages):
            chunks = [
                chunk
                async for chunk in service.send(
                    conversation_id="conv-limit",
                    message="find it",
                    parent_id=None,
                    profile_id=None,
                    model="gemini-3-flash-preview",
                    mode="anthropic",
                    base_url="http://localhost:8001",
                    api_key="test-key",
                    stream=True,
                    tools=["command_execute"],
                    thinking=False,
                    structured_schema=None,
                    options={},
                    allow_system_mutation=True,
                )
            ]

        self.assertEqual(len(invocations), 4)
        self.assertTrue(all(call["tools"] for call in invocations[:3]))
        self.assertEqual(invocations[-1]["tools"], [])
        final_history_item = invocations[-1]["messages"][-1]
        self.assertEqual(final_history_item["role"], "user")
        self.assertEqual(final_history_item["content"][0]["type"], "tool_result")
        assistant_create = messages.await_args_list[-1]
        self.assertEqual(
            assistant_create.args[2],
            "The command succeeded and the file is present.",
        )
        events = [_event(chunk) for chunk in chunks]
        forced = [
            data
            for event, data in events
            if event == "status" and data.get("phase") == "forced_final_response"
        ]
        self.assertEqual(
            forced[-1]["text_chars"],
            len("The command succeeded and the file is present."),
        )

    async def test_empty_forced_final_response_persists_and_emits_error(self):
        service = RemoteChatService()
        service._conversation = AsyncMock(return_value={"id": "conv-empty-final"})
        service._history = AsyncMock(return_value=[{"role": "user", "content": "run it"}])
        service.tools.get_tool_definitions = lambda _: [
            {
                "type": "function",
                "function": {
                    "name": "command_execute",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        service._execute_tool = AsyncMock(return_value="done")
        service._invoke = AsyncMock(side_effect=[
            Turn(tool_calls=[{"id": "call-1", "name": "command_execute", "arguments": {}}]),
            Turn(text=""),
        ])
        messages = AsyncMock(side_effect=[{"id": "user-empty"}, {"id": "assistant-empty"}])

        with patch(
            "backend.services.remote_chat_service.REMOTE_TOOL_ROUND_LIMIT",
            1,
        ), patch(
            "backend.services.remote_chat_service.provider_capabilities",
            return_value=[{"id": "anthropic", "available": True}],
        ), patch("backend.services.remote_chat_service.MessageModel.create", messages):
            chunks = [
                chunk
                async for chunk in service.send(
                    conversation_id="conv-empty-final",
                    message="run it",
                    parent_id=None,
                    profile_id=None,
                    model="gemini-3-flash-preview",
                    mode="anthropic",
                    base_url="http://localhost:8001",
                    api_key="test-key",
                    stream=True,
                    tools=["command_execute"],
                    thinking=False,
                    structured_schema=None,
                    options={},
                    allow_system_mutation=True,
                )
            ]

        assistant_create = messages.await_args_list[-1]
        self.assertEqual(assistant_create.args[2], _tool_limit_error_text(1))
        events = [_event(chunk) for chunk in chunks]
        statuses = [data.get("status") for event, data in events if event == "status"]
        self.assertIn("tool_limit_exhausted", statuses)
        self.assertIn("tool_limit_error", statuses)


if __name__ == "__main__":
    unittest.main()

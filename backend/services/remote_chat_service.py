"""Remote-provider stress-test service for UltraChat.

The service deliberately normalizes OpenAI, Anthropic, ML Junction native, and
the optional local LangChain integration into UltraChat's existing SSE events.
It is a developer client: endpoint/API-key settings are supplied per request and
are never written to the conversation database.
"""

from __future__ import annotations

import asyncio
import copy
import json
import time
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Any, AsyncGenerator

import httpx

from ..core.streaming import create_done_event, create_error_event, create_status_event, create_token_event
from ..models import ConversationModel, MessageModel, ProfileModel
from .tool_service import get_tool_service
from .web_search_service import get_web_search_service


REMOTE_MODES = {"mljunction", "openai", "anthropic", "langchain_mljunction"}


@dataclass
class Turn:
    text: str = ""
    thinking: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def provider_capabilities() -> list[dict[str, Any]]:
    """Return runtime-discovered modes; optional SDKs never break local chat."""
    packages = {
        "openai": "openai",
        "anthropic": "anthropic",
        "langchain_mljunction": "langchain_mljunction",
    }
    result = [{"id": "local", "label": "Local Hugging Face", "available": True}]
    result.append({"id": "mljunction", "label": "ML Junction native", "available": True})
    for mode, package in packages.items():
        result.append({
            "id": mode,
            "label": {
                "openai": "OpenAI SDK", "anthropic": "Anthropic SDK", "langchain_mljunction": "ML Junction LangChain SDK",
            }[mode],
            "available": find_spec(package) is not None,
            "reason": None if find_spec(package) is not None else f"Optional package '{package}' is not installed",
        })
    return result


class RemoteChatService:
    def __init__(self) -> None:
        self.tools = get_tool_service()

    async def send(
        self,
        *,
        conversation_id: str | None,
        message: str,
        parent_id: str | None,
        profile_id: str | None,
        model: str,
        mode: str,
        base_url: str,
        api_key: str,
        stream: bool,
        tools: list[str],
        thinking: bool,
        structured_schema: dict[str, Any] | None,
        options: dict[str, Any],
        allow_system_mutation: bool,
    ) -> AsyncGenerator[str, None]:
        if mode not in REMOTE_MODES:
            yield create_error_event(f"Unknown remote provider mode: {mode}", "provider_mode")
            return
        available = {item["id"]: item for item in provider_capabilities()}
        if not available.get(mode, {}).get("available"):
            yield create_error_event(available[mode].get("reason", "Provider is unavailable"), "provider_unavailable")
            return
        if not api_key:
            yield create_error_event("An API key is required for remote provider modes", "missing_api_key")
            return
        if not model.strip() or not base_url.strip():
            yield create_error_event("Model and base URL are required", "invalid_provider_config")
            return

        started = time.perf_counter()
        try:
            conv = await self._conversation(conversation_id, profile_id, f"{mode}:{model}")
            if conv is None:
                yield create_error_event("Conversation not found", "conversation_not_found")
                return
            # ML Junction creates a new sess_* ID when a client omits one.
            # Keep all turns (including tool-result follow-ups) of this local
            # conversation together in its observability/session views.
            mlj_session_id = f"ultrachat-{conv['id']}"
            user = await MessageModel.create(conv["id"], "user", message, parent_id=parent_id)
            history = await self._history(conv["id"], profile_id)
            # Keep the local tool catalogue expressive, but submit only the
            # portable JSON-Schema subset accepted by strict providers.  This
            # prevents ML Junction having to report a recovery for every tool
            # on every request.
            definitions = self._provider_safe_tool_definitions(self.tools.get_tool_definitions(tools))
            trace: list[dict[str, Any]] = []
            yield create_status_event("generating", {
                "conversation_id": conv["id"], "user_message_id": user["id"], "model": model,
                "provider_mode": mode, "stream": stream, "tools_enabled": tools,
                "mlj_session_id": mlj_session_id,
            })
            yield create_status_event("debug", {
                "phase": "request", "mode": mode, "base_url": base_url, "model": model,
                "tool_count": len(definitions), "stream": stream, "mlj_session_id": mlj_session_id,
            })

            final = Turn()
            for round_number in range(1, 6):
                events: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

                async def emit(event: str, data: dict[str, Any]) -> None:
                    await events.put((event, data))

                task = asyncio.create_task(self._invoke(
                    mode=mode, base_url=base_url, api_key=api_key, model=model, messages=history,
                    tools=definitions, thinking=thinking, schema=structured_schema, options=options,
                    stream=stream, emit=emit, session_id=mlj_session_id,
                ))
                while not task.done() or not events.empty():
                    try:
                        event, data = await asyncio.wait_for(events.get(), timeout=0.05)
                    except asyncio.TimeoutError:
                        continue
                    trace.append({"phase": event, **data})
                    if event == "token":
                        yield create_token_event(data.get("token", ""))
                    else:
                        yield create_status_event(event, data)
                turn = await task
                if turn.thinking:
                    yield create_status_event("thinking", {"content": turn.thinking, "round": round_number})
                final = turn
                response_trace = {
                    "phase": "response", "round": round_number, "text_chars": len(turn.text),
                    "tool_calls": len(turn.tool_calls), "usage": turn.usage,
                    "cache": self._cache_diagnostics(turn.usage),
                }
                trace.append(response_trace)
                yield create_status_event("debug", response_trace)
                if not turn.tool_calls:
                    break
                for call in turn.tool_calls:
                    name = call.get("name") or "unknown"
                    args = call.get("arguments") or {}
                    call_id = call.get("id") or f"call_{round_number}_{name}"
                    call["id"] = call_id
                    yield create_status_event("tool_call", {"tool": name, "arguments": args, "round": round_number})
                    yield create_status_event("debug", {
                        "phase": "tool_execution_started", "tool": name, "round": round_number,
                    })
                    try:
                        if name == "structured_subagent":
                            result = await asyncio.wait_for(self._structured_subagent(
                                mode=mode,
                                base_url=base_url,
                                api_key=api_key,
                                model=model,
                                task=str(args.get("task", "")),
                                options=options,
                                session_id=mlj_session_id,
                            ), timeout=90)
                        else:
                            result = await asyncio.wait_for(self._execute_tool(
                                name, args, allow_system_mutation=allow_system_mutation
                            ), timeout=30)
                    except asyncio.TimeoutError:
                        result = f"Tool '{name}' timed out after 30 seconds. Explain this to the user or try another tool."
                    except Exception as exc:
                        result = f"Tool '{name}' failed: {exc}"
                    yield create_status_event("debug", {
                        "phase": "tool_execution_finished", "tool": name, "round": round_number,
                        "result_chars": len(result),
                    })
                    yield create_status_event("tool_result", {"tool": name, "result": result, "round": round_number})
                    call["result"] = result
                    trace.append({"phase": "tools", "calls": [dict(call)]})
                history.extend(self._tool_history(mode, turn, round_number))
            else:
                yield create_status_event("debug", {"phase": "tool_loop", "warning": "maximum five tool rounds reached"})

            duration_ms = int((time.perf_counter() - started) * 1000)
            assistant = await MessageModel.create(
                conv["id"], "assistant", final.text or "", parent_id=user["id"], model=f"{mode}:{model}",
                # raw_content is rendered as an answer by UltraChat's existing
                # reasoning parser. Keep it model text only; protocol/debug
                # payloads stay in the emitted debug trace instead.
                thinking=final.thinking or None, raw_content=final.text or None,
                tool_calls=json.dumps([call for entry in trace if entry.get("phase") == "tools" for call in entry.get("calls", [])], ensure_ascii=False),
                tokens_prompt=self._int_usage(final.usage, "input_tokens", "prompt_tokens"),
                tokens_completion=self._int_usage(final.usage, "output_tokens", "completion_tokens"), duration_ms=duration_ms,
            )
            yield create_status_event("debug", {"phase": "complete", "duration_ms": duration_ms, "trace": trace})
            yield create_done_event(assistant["id"], total_tokens=self._int_usage(final.usage, "total_tokens"), eval_duration=duration_ms / 1000, conversation_id=conv["id"])
        except Exception as exc:
            yield create_error_event(str(exc), "remote_provider_error")

    async def _conversation(self, conversation_id: str | None, profile_id: str | None, model: str) -> dict[str, Any] | None:
        if conversation_id:
            from_existing = await ConversationModel.get_by_id(conversation_id)
            return from_existing
        return await ConversationModel.create(profile_id=profile_id, model=model)

    async def _history(self, conversation_id: str, profile_id: str | None) -> list[dict[str, Any]]:
        profile = await ProfileModel.get_by_id(profile_id) if profile_id else await ProfileModel.get_default()
        messages: list[dict[str, Any]] = []
        if profile and profile.get("system_prompt"):
            messages.append({"role": "system", "content": profile["system_prompt"]})
        for item in await MessageModel.get_active_thread(conversation_id):
            messages.append({"role": item["role"], "content": item["content"]})
        return messages

    @staticmethod
    def _int_usage(usage: dict[str, Any], *names: str) -> int | None:
        for name in names:
            value = usage.get(name)
            if isinstance(value, int):
                return value
        return None

    @staticmethod
    def _cache_diagnostics(usage: dict[str, Any]) -> dict[str, Any]:
        """Expose provider-reported cache usage without guessing a cache hit."""
        input_tokens = RemoteChatService._int_usage(usage, "input_tokens", "prompt_tokens") or 0
        details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        cached_tokens = details.get("cached_tokens", details.get("cached_input_tokens", 0))
        try:
            cached_tokens = int(cached_tokens or 0)
        except (TypeError, ValueError):
            cached_tokens = 0
        return {
            "input_tokens": input_tokens,
            "cached_tokens": cached_tokens,
            "hit": cached_tokens > 0,
            "eligible_prefix_likely": input_tokens >= 1024,
            "note": (
                "provider reported cached input tokens"
                if cached_tokens > 0
                else "under OpenAI's usual 1,024-token prompt-cache threshold"
                if input_tokens < 1024
                else "no provider-reported cache hit; a stable matching prefix is required"
            ),
        }

    @staticmethod
    def _provider_safe_tool_definitions(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Project tools to the common strict JSON-Schema subset.

        Some providers reject schema defaults and require every object to
        declare whether extra fields are allowed.  Defaults stay implemented
        in the actual tool functions, so removing them here changes neither
        execution nor the model-facing descriptions.
        """
        def project_schema(value: Any) -> Any:
            if isinstance(value, list):
                return [project_schema(item) for item in value]
            if not isinstance(value, dict):
                return value

            projected = {
                key: project_schema(item)
                for key, item in value.items()
                if key not in {"default", "examples", "$schema"}
            }
            if projected.get("type") == "object" or "properties" in projected:
                projected["additionalProperties"] = False
            return projected

        projected = copy.deepcopy(definitions)
        for definition in projected:
            parameters = definition.get("function", {}).get("parameters")
            if isinstance(parameters, dict):
                definition["function"]["parameters"] = project_schema(parameters)
        return projected

    async def _execute_tool(self, name: str, arguments: dict[str, Any], *, allow_system_mutation: bool) -> str:
        if name == "web_search":
            search = get_web_search_service()
            if not search.is_available():
                return "Web search is unavailable"
            return await search.search_and_format(arguments.get("query", ""), max_results=arguments.get("max_results", 5))
        result = await self.tools.execute_tool(name, arguments, allow_system_mutation=allow_system_mutation)
        return self.tools.format_tool_result_for_context(name, result)

    async def _structured_subagent(
        self,
        *,
        mode: str,
        base_url: str,
        api_key: str,
        model: str,
        task: str,
        options: dict[str, Any],
        session_id: str,
    ) -> str:
        """Run a nested strict-schema call, exposing schema conformance to the tool loop."""
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["answer", "confidence", "evidence"],
            "additionalProperties": False,
        }

        async def discard_event(_: str, __: dict[str, Any]) -> None:
            return None

        result = await self._invoke(
            mode=mode,
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=[
                {"role": "system", "content": "Return only a strict JSON object matching the requested schema."},
                {"role": "user", "content": task},
            ],
            tools=[],
            thinking=False,
            schema=schema,
            options=options,
            stream=False, session_id=session_id,
            emit=discard_event,
        )
        return result.text or json.dumps(result.raw, ensure_ascii=False)

    @staticmethod
    def _tool_history(mode: str, turn: Turn, round_number: int) -> list[dict[str, Any]]:
        if mode == "anthropic":
            assistant_blocks = [{"type": "tool_use", "id": call["id"], "name": call["name"], "input": call.get("arguments", {})} for call in turn.tool_calls]
            result_blocks = [{"type": "tool_result", "tool_use_id": call["id"], "content": call.get("result", "")} for call in turn.tool_calls]
            return [{"role": "assistant", "content": assistant_blocks}, {"role": "user", "content": result_blocks}]
        calls = [{"id": call["id"], "type": "function", "function": {"name": call["name"], "arguments": json.dumps(call.get("arguments", {}))}} for call in turn.tool_calls]
        result = [{"role": "tool", "tool_call_id": call["id"], "content": call.get("result", "")} for call in turn.tool_calls]
        return [{"role": "assistant", "content": turn.text or None, "tool_calls": calls}, *result]

    async def _invoke(self, **kwargs: Any) -> Turn:
        mode = kwargs["mode"]
        if mode == "mljunction":
            return await self._native(**kwargs)
        if mode == "openai":
            return await self._openai(**kwargs)
        if mode == "anthropic":
            return await self._anthropic(**kwargs)
        return await self._langchain(**kwargs)

    async def _native(self, *, base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], thinking: bool, schema: dict[str, Any] | None, options: dict[str, Any], stream: bool, emit: Any, session_id: str, **_: Any) -> Turn:
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream, "tools": tools, "sampling": {k: v for k, v in options.items() if k in {"temperature", "top_p", "seed"}}, "reasoning": {"enabled": thinking}, "session_id": session_id}
        if schema:
            payload["output"] = {"format": {"type": "json_schema", "name": "ultrachat_stress", "schema": schema, "strict": True}}
        async with httpx.AsyncClient(base_url=base_url.rstrip("/"), headers={"Authorization": f"Bearer {api_key}"}, timeout=120) as client:
            if not stream:
                response = await client.post("/v1/responses", json=payload)
                response.raise_for_status()
                data = response.json()
            else:
                event, data_line, text, fragments, calls = "", "", "", [], {}
                data: dict[str, Any] = {}
                async with client.stream("POST", "/v1/responses", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("event:"):
                            event = line.removeprefix("event:").strip()
                        elif line.startswith("data:"):
                            data_line = line.removeprefix("data:").strip()
                        elif not line and event and data_line:
                            try:
                                payload_event = json.loads(data_line)
                            except json.JSONDecodeError:
                                event, data_line = "", ""
                                continue
                            if event == "response.output_text.delta":
                                delta = payload_event.get("delta", "")
                                text += delta
                                fragments.append(delta)
                                await emit("token", {"token": delta})
                            elif event == "response.tool_call.delta":
                                index = int(payload_event.get("index", 0))
                                call = calls.setdefault(index, {"id": None, "name": None, "arguments_text": ""})
                                call["id"] = payload_event.get("id") or call["id"]
                                call["name"] = payload_event.get("name") or call["name"]
                                call["arguments_text"] += payload_event.get("arguments", "")
                            elif event == "response.completed":
                                data = payload_event
                            event, data_line = "", ""
                if not data:
                    data = {"output": [{"type": "text", "text": text}], "usage": {}}
                data["_deltas"] = fragments
                if calls:
                    data["_stream_tool_calls"] = list(calls.values())
        output = data.get("output", [])
        calls = [item.get("tool_call", {}) for item in output if item.get("type") == "tool_call"]
        if not calls:
            calls = data.get("_stream_tool_calls", [])
        normalized = [{
            "id": call.get("id"),
            "name": (call.get("function") or {}).get("name") or call.get("name"),
            "arguments": self._json_arguments((call.get("function") or {}).get("arguments") or call.get("arguments_text")),
        } for call in calls]
        text = "".join(item.get("text") or json.dumps(item.get("object")) for item in output if item.get("type") in {"text", "json"})
        if not text and data.get("_deltas"):
            text = "".join(data["_deltas"])
        reasoning = data.get("reasoning") or {}
        return Turn(text=text, thinking=reasoning.get("summary", ""), tool_calls=normalized, usage=data.get("usage") or {}, raw=data)

    async def _openai(self, *, base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], thinking: bool, schema: dict[str, Any] | None, options: dict[str, Any], stream: bool, emit: Any, session_id: str, **_: Any) -> Turn:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=f"{base_url.rstrip('/')}/openai/v1", api_key=api_key, timeout=120)
        params: dict[str, Any] = {"model": model, "messages": messages, "tools": tools or None, "temperature": options.get("temperature"), "top_p": options.get("top_p"), "max_completion_tokens": options.get("max_tokens"), "extra_body": {"mlj": {"session_id": session_id, "session_name": "UltraChat conversation"}}}
        if thinking:
            params["reasoning_effort"] = options.get("reasoning_effort", "medium")
        if schema:
            params["response_format"] = {"type": "json_schema", "json_schema": {"name": "ultrachat_stress", "schema": schema, "strict": True}}
        params = {key: value for key, value in params.items() if value is not None}
        if not stream:
            response = await client.chat.completions.create(**params)
            message = response.choices[0].message
            calls = [{"id": call.id, "name": call.function.name, "arguments": self._json_arguments(call.function.arguments)} for call in message.tool_calls or []]
            return Turn(text=message.content or "", tool_calls=calls, usage=response.usage.model_dump() if response.usage else {}, raw=response.model_dump())
        response = await client.chat.completions.create(**params, stream=True, stream_options={"include_usage": True})
        text, calls, usage, fragments = "", {}, {}, []
        async for chunk in response:
            if chunk.usage:
                usage = chunk.usage.model_dump()
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text += delta.content
                fragments.append(delta.content)
                await emit("token", {"token": delta.content})
            for call in delta.tool_calls or []:
                index = call.index
                item = calls.setdefault(index, {"id": call.id, "name": None, "arguments_text": ""})
                item["id"] = call.id or item["id"]
                if call.function:
                    item["name"] = call.function.name or item["name"]
                    item["arguments_text"] += call.function.arguments or ""
        normalized = [{"id": value["id"], "name": value["name"], "arguments": self._json_arguments(value["arguments_text"])} for value in calls.values()]
        return Turn(text=text, tool_calls=normalized, usage=usage, raw={"_deltas": fragments, "protocol": "openai_stream"})

    async def _anthropic(self, *, base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], thinking: bool, schema: dict[str, Any] | None, options: dict[str, Any], stream: bool, emit: Any, session_id: str, **_: Any) -> Turn:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(base_url=f"{base_url.rstrip('/')}/anthropic", api_key=api_key, timeout=120)
        system = "\n\n".join(str(item["content"]) for item in messages if item["role"] == "system") or None
        body = [item for item in messages if item["role"] != "system"]
        converted_tools = [{"name": item["function"]["name"], "description": item["function"].get("description", ""), "input_schema": item["function"].get("parameters", {"type": "object"})} for item in tools]
        params: dict[str, Any] = {"model": model, "messages": body, "system": system, "max_tokens": int(options.get("max_tokens", 1024)), "tools": converted_tools or None, "temperature": options.get("temperature"), "top_p": options.get("top_p"), "extra_body": {"mlj": {"session_id": session_id, "session_name": "UltraChat conversation"}}}
        if schema:
            params["output_config"] = {"format": {"schema": schema}}
        params = {key: value for key, value in params.items() if value is not None}
        if not stream:
            response = await client.messages.create(**params)
            text = "".join(block.text for block in response.content if block.type == "text")
            calls = [{"id": block.id, "name": block.name, "arguments": block.input} for block in response.content if block.type == "tool_use"]
            return Turn(text=text, tool_calls=calls, usage=response.usage.model_dump(), raw=response.model_dump())
        response = await client.messages.create(**params, stream=True)
        text, fragments, calls, pending = "", [], {}, {}
        async for event in response:
            if event.type == "content_block_start" and getattr(event, "content_block", None) and event.content_block.type == "tool_use":
                pending[event.index] = {"id": event.content_block.id, "name": event.content_block.name, "arguments_text": ""}
            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    text += delta.text
                    fragments.append(delta.text)
                    await emit("token", {"token": delta.text})
                elif delta.type == "input_json_delta":
                    pending.setdefault(event.index, {"id": None, "name": None, "arguments_text": ""})["arguments_text"] += delta.partial_json
            elif event.type == "content_block_stop" and event.index in pending:
                calls[event.index] = pending[event.index]
        normalized = [{"id": value["id"], "name": value["name"], "arguments": self._json_arguments(value["arguments_text"])} for value in calls.values()]
        return Turn(text=text, tool_calls=normalized, raw={"_deltas": fragments, "protocol": "anthropic_stream"})

    async def _langchain(self, *, base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], schema: dict[str, Any] | None, stream: bool, emit: Any, session_id: str, **_: Any) -> Turn:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        from langchain_mljunction import ChatMLJunction
        converted = []
        for item in messages:
            if item["role"] == "system":
                converted.append(SystemMessage(content=item["content"]))
            elif item["role"] == "tool":
                converted.append(
                    ToolMessage(content=item["content"], tool_call_id=item["tool_call_id"])
                )
            elif item["role"] == "assistant":
                tool_calls = [
                    {
                        "name": call["function"]["name"],
                        "args": self._json_arguments(call["function"]["arguments"]),
                        "id": call["id"],
                    }
                    for call in item.get("tool_calls", [])
                ]
                converted.append(AIMessage(content=item.get("content") or "", tool_calls=tool_calls))
            else:
                converted.append(HumanMessage(content=item["content"]))
        llm = ChatMLJunction(
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            session_id=session_id,
            session_name="UltraChat conversation",
        )
        if tools:
            llm = llm.bind_tools(tools)
        if schema:
            llm = llm.with_structured_output(schema)
        if not stream:
            response = await llm.ainvoke(converted)
            return Turn(text=str(response.content), tool_calls=list(getattr(response, "tool_calls", []) or []), raw={"provider": "langchain"})
        text, fragments, calls = "", [], []
        async for chunk in llm.astream(converted):
            if chunk.content:
                value = str(chunk.content)
                text += value
                fragments.append(value)
                await emit("token", {"token": value})
            calls.extend(getattr(chunk, "tool_call_chunks", []) or [])
        normalized = [{"id": call.get("id"), "name": call.get("name"), "arguments": self._json_arguments(call.get("args") or call.get("arguments") or "{}")} for call in calls if call.get("name")]
        return Turn(text=text, tool_calls=normalized, raw={"_deltas": fragments, "protocol": "langchain_stream"})

    @staticmethod
    def _json_arguments(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {"_raw": str(value)}


_remote_chat_service: RemoteChatService | None = None


def get_remote_chat_service() -> RemoteChatService:
    global _remote_chat_service
    if _remote_chat_service is None:
        _remote_chat_service = RemoteChatService()
    return _remote_chat_service

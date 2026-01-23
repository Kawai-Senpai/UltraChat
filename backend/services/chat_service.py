"""
UltraChat - Chat Service
Business logic for chat operations with HuggingFace/PyTorch.
"""

from typing import Optional, Dict, Any, List, AsyncGenerator
import re
import json
import logging
import time

from ..core import (
    get_model_manager,
    ModelError,
    ModelNotFoundError,
    StreamBuffer,
    create_token_event,
    create_done_event,
    create_error_event,
    create_status_event,
)
from ..models import (
    ConversationModel,
    MessageModel,
    ProfileModel,
    MemoryModel,
    ModelRegistry,
)
from ..config import get_settings_manager
from .web_search_service import get_web_search_service
from .tool_service import get_tool_service


class ChatService:
    """
    Handles chat operations including:
    - Creating and managing conversations
    - Sending messages with streaming
    - Managing message trees and branches
    - Integrating memory context
    - Agent tool calling
    """
    
    def __init__(self):
        self.manager = get_model_manager()
        self.settings = get_settings_manager()
        self.tool_service = get_tool_service()
        self.logger = logging.getLogger("ultrachat.chat")

        # Pattern for model "thinking" blocks (Qwen/Qwen3 style)
        self._thinking_pattern = re.compile(
            r"<think>(.*?)</think>|<thinking>(.*?)</thinking>",
            re.DOTALL | re.IGNORECASE
        )
        
        # Pattern for tool calls
        self._tool_call_pattern = re.compile(
            r"<tool_call>(.*?)</tool_call>",
            re.DOTALL | re.IGNORECASE
        )

    def _strip_thinking(self, text: str) -> str:
        """Remove <think> blocks from text for history/context."""
        if not text:
            return text
        cleaned = re.sub(self._thinking_pattern, "", text)
        return cleaned.strip()

    def _split_thinking(self, text: str) -> (str, str):
        """Split raw content into (thinking, final_text)."""
        if not text:
            return "", text

        match = self._thinking_pattern.search(text)
        if not match:
            return "", text.strip()

        thinking = match.group(1) or match.group(2) or ""
        final_text = re.sub(self._thinking_pattern, "", text, count=1).strip()
        return thinking.strip(), final_text

    def _apply_thinking_directives(self, text: str, enable_thinking: Optional[bool]) -> (str, Optional[bool]):
        """Parse /think and /no_think directives and return cleaned text + override."""
        if not text:
            return text, enable_thinking

        lowered = text.lower()
        override = enable_thinking

        if "/no_think" in lowered:
            override = False
            text = text.replace("/no_think", "")
        if "/think" in lowered:
            override = True
            text = text.replace("/think", "")

        return text.strip(), override
    
    def _extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a tool call from model output."""
        if not text:
            return None

        # 1) Try explicit <tool_call>...</tool_call>
        match = self._tool_call_pattern.search(text)
        if match:
            try:
                raw = match.group(1).strip()
                data = json.loads(raw)
                if "name" in data and "arguments" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass

        # 2) Try to find JSON objects in the output
        json_candidates = re.findall(r"\{[\s\S]*\}", text)
        for candidate in json_candidates:
            try:
                data = json.loads(candidate)

                # OpenAI-style tool_calls
                if isinstance(data, dict) and "tool_calls" in data:
                    tool_calls = data.get("tool_calls") or []
                    if tool_calls:
                        first = tool_calls[0]
                        if "function" in first:
                            fn = first.get("function", {})
                            name = fn.get("name")
                            args = fn.get("arguments")
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    args = {"raw": args}
                            if name:
                                return {"name": name, "arguments": args or {}}
                        if "name" in first and "arguments" in first:
                            return {"name": first.get("name"), "arguments": first.get("arguments") or {}}

                # Direct {name, arguments}
                if isinstance(data, dict) and "name" in data and "arguments" in data:
                    return {"name": data.get("name"), "arguments": data.get("arguments") or {}}

            except (json.JSONDecodeError, TypeError):
                continue

        return None
    
    @property
    def default_model(self) -> str:
        """Get the default model from settings."""
        return self.settings.get("default_model", "Qwen/Qwen2.5-1.5B-Instruct")
    
    async def get_or_create_conversation(
        self,
        conversation_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get existing conversation or create new one."""
        if conversation_id:
            conv = await ConversationModel.get_by_id(conversation_id)
            if conv:
                return conv
            return None
        
        # Create new conversation
        return await ConversationModel.create(
            profile_id=profile_id,
            model=model or self.default_model
        )
    
    async def build_messages_for_api(
        self,
        conversation_id: str,
        profile: Optional[Dict[str, Any]] = None,
        include_memory: bool = True,
        web_search_results: Optional[str] = None,
        profile_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Build the message list for model generation.
        Includes system prompt, memory context, web search results, and conversation history.
        """
        messages = []
        
        # Get profile for system prompt
        if not profile:
            conv = await ConversationModel.get_by_id(conversation_id)
            if conv and conv.get('profile_id'):
                profile = await ProfileModel.get_by_id(conv['profile_id'])
            else:
                profile = await ProfileModel.get_default()
        
        # Add system prompt
        system_prompt = profile.get('system_prompt', '') if profile else ''
        
        # Add memory context to system prompt
        if include_memory:
            # Use profile_id to get profile-scoped memories
            pid = profile_id or (profile.get('id') if profile else None)
            memories = await MemoryModel.get_for_context(limit=10, profile_id=pid)
            if memories:
                memory_text = "\n\n## Your Knowledge/Memory:\n"
                for mem in memories:
                    memory_text += f"- {mem['content']}\n"
                system_prompt += memory_text
        
        # Add web search results to system prompt
        if web_search_results:
            system_prompt += f"\n\n## Recent Web Search Results:\n{web_search_results}\n"
            system_prompt += "\nUse the above search results to help answer the user's question if relevant."
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Get conversation history (active thread only)
        history = await MessageModel.get_active_thread(conversation_id)
        
        for msg in history:
            messages.append({
                "role": msg['role'],
                "content": self._strip_thinking(msg['content'])
            })
        
        return messages
    
    async def get_generation_options(
        self,
        profile: Optional[Dict[str, Any]] = None,
        custom_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build generation options."""
        options = {}
        
        if profile:
            options['temperature'] = profile.get('temperature', 0.7)
            options['top_p'] = profile.get('top_p', 0.9)
            options['top_k'] = profile.get('top_k', 50)
            options['max_new_tokens'] = profile.get('max_tokens', 2048)
            options['repetition_penalty'] = profile.get('repetition_penalty', 1.1)
        else:
            options['temperature'] = 0.7
            options['top_p'] = 0.9
            options['top_k'] = 50
            options['max_new_tokens'] = 2048
            options['repetition_penalty'] = 1.1
        
        # Override with custom options
        if custom_options:
            options.update(custom_options)
        
        return options
    
    async def send_message(
        self,
        conversation_id: Optional[str],
        message: str,
        parent_id: Optional[str] = None,
        model: Optional[str] = None,
        profile_id: Optional[str] = None,
        stream: bool = True,
        options: Optional[Dict[str, Any]] = None,
        web_search: bool = False,
        use_memory: bool = True,
        enable_thinking: Optional[bool] = None,
        tools: Optional[List[str]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response.
        Yields SSE formatted events.
        """
        start_time = time.time()
        
        try:
            # Check if model is loaded
            if not self.manager.is_model_loaded:
                yield create_error_event(
                    "No model loaded. Please load a model first.",
                    "no_model"
                )
                return
            
            # Get or create conversation
            conv = await self.get_or_create_conversation(
                conversation_id, profile_id, model
            )
            if conversation_id and not conv:
                yield create_error_event("Conversation not found", "conversation_not_found")
                return

            conversation_id = conv['id']
            
            # Get profile
            profile = None
            if profile_id or conv.get('profile_id'):
                profile = await ProfileModel.get_by_id(
                    profile_id or conv['profile_id']
                )
            if not profile:
                profile = await ProfileModel.get_default()
            
            # Apply /think or /no_think directives and clean message
            clean_message, enable_thinking = self._apply_thinking_directives(
                message,
                enable_thinking
            )

            # Determine model (use currently loaded model)
            use_model = self.manager.current_model

            self.logger.info(
                "Chat request: conversation=%s model=%s profile=%s stream=%s tools=%s",
                conversation_id,
                use_model,
                profile_id or conv.get('profile_id'),
                stream,
                tools
            )
            
            # Get enabled tools
            enabled_tools = tools or []
            
            # Legacy web_search flag (backwards compatible) - add to enabled_tools
            if web_search and "web_search" not in enabled_tools:
                enabled_tools = list(enabled_tools) + ["web_search"]

            # Save user message
            user_msg = await MessageModel.create(
                conversation_id=conversation_id,
                role="user",
                content=clean_message,
                parent_id=parent_id
            )
            
            # Build messages for API
            base_messages = await self.build_messages_for_api(
                conversation_id, profile, 
                include_memory=use_memory,
                web_search_results=None,  # Tools injected via agent loop
                profile_id=profile_id or (profile.get('id') if profile else None)
            )

            
            # Get generation options
            gen_options = await self.get_generation_options(profile, options)
            
            # Get tool definitions for model if tools enabled
            tool_definitions = self.tool_service.get_tool_definitions(enabled_tools) if enabled_tools else None
            
            # Format messages for the model with tools (planner prompt)
            prompt = self.manager.format_chat_prompt(
                base_messages,
                enable_thinking=enable_thinking,
                tools=tool_definitions
            )
            
            # Yield status
            yield create_status_event("generating", {
                "conversation_id": conversation_id,
                "user_message_id": user_msg['id'],
                "model": use_model,
                "tools_enabled": enabled_tools if enabled_tools else None
            })
            
            # Agent loop for tool calling
            buffer = StreamBuffer()
            tokens_generated = 0
            max_tool_rounds = 3
            tool_round = 0
            tool_calls_record = []  # Store tool calls for database
            current_messages = base_messages.copy()
            prompt_for_metrics = prompt

            if not enabled_tools:
                # No tools: stream directly to user
                async for token in self.manager.generate(
                    prompt=prompt,
                    max_new_tokens=gen_options.get('max_new_tokens', 2048),
                    temperature=gen_options.get('temperature', 0.7),
                    top_p=gen_options.get('top_p', 0.9),
                    top_k=gen_options.get('top_k', 50),
                    repetition_penalty=gen_options.get('repetition_penalty', 1.1),
                    stream=True,
                ):
                    buffer.add_token(token)
                    tokens_generated += 1
                    yield create_token_event(token)
            else:
                # Tool mode: run planning rounds (non-stream) to decide tool calls
                while tool_round < max_tool_rounds:
                    planning_prompt = self.manager.format_chat_prompt(
                        current_messages,
                        enable_thinking=enable_thinking,
                        tools=tool_definitions
                    )
                    prompt_for_metrics = planning_prompt

                    # Increase max tokens for planning to allow full tool call JSON
                    planning_max_tokens = min(512, gen_options.get('max_new_tokens', 2048))
                    planning_buffer = ""
                    planning_thinking = ""
                    thinking_snapshot = ""
                    tool_call_buffer = ""
                    tool_call_text = None
                    tool_call_started = False
                    tool_thinking_enabled = self.settings.get("ui.tool_thinking", True) and enable_thinking is not False

                    self.logger.debug(f"Tool round {tool_round + 1}: Starting planning generation...")

                    async for token in self.manager.generate(
                        prompt=planning_prompt,
                        max_new_tokens=planning_max_tokens,
                        temperature=0.2,
                        top_p=min(0.9, gen_options.get('top_p', 0.9)),
                        top_k=gen_options.get('top_k', 50),
                        repetition_penalty=gen_options.get('repetition_penalty', 1.1),
                        stream=True,
                    ):
                        planning_buffer += token

                        # Stream thinking deltas until tool call begins
                        if tool_thinking_enabled and not tool_call_started:
                            # Only stream thinking content inside <think> tags
                            think_match = re.search(r"<think>(.*?)(</think>|$)", planning_buffer, re.DOTALL | re.IGNORECASE)
                            if not think_match:
                                think_match = re.search(r"<thinking>(.*?)(</thinking>|$)", planning_buffer, re.DOTALL | re.IGNORECASE)
                            if think_match:
                                thinking_text = think_match.group(1)
                                if len(thinking_text) > len(thinking_snapshot):
                                    delta = thinking_text[len(thinking_snapshot):]
                                    thinking_snapshot = thinking_text
                                    planning_thinking += delta
                                    yield create_status_event("tool_thinking_delta", {
                                        "delta": delta,
                                        "round": tool_round + 1
                                    })

                        # Detect tool call start
                        if not tool_call_started and "<tool_call>" in planning_buffer:
                            tool_call_started = True
                            tool_call_buffer = planning_buffer.split("<tool_call>", 1)[1]
                        elif tool_call_started:
                            tool_call_buffer += token

                        # Detect tool call end
                        if tool_call_started and "</tool_call>" in tool_call_buffer:
                            tool_call_text = tool_call_buffer.split("</tool_call>", 1)[0]
                            self.manager.request_stop()
                            break


                    # Extract tool call from streamed planning output
                    print(f"\n=== Tool round {tool_round + 1} ===")
                    print(f"Model raw output ({len(planning_buffer)} chars):")
                    print(planning_buffer)
                    print("=" * 40)
                    
                    if tool_call_text:
                        tool_call = self._extract_tool_call(f"<tool_call>{tool_call_text}</tool_call>")
                        print(f"Extracted from tool_call_text: {tool_call}")
                    else:
                        tool_call = self._extract_tool_call(planning_buffer)
                        print(f"Extracted from planning_buffer: {tool_call}")
                    if not tool_call:
                        # No tool call: the planning_buffer contains the final answer
                        # Stream it character by character for smooth display
                        if planning_buffer.strip():
                            # Split into chunks for smoother streaming effect
                            content = planning_buffer
                            chunk_size = 8  # Characters per chunk
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i + chunk_size]
                                buffer.add_token(chunk)
                                tokens_generated += 1
                                yield create_token_event(chunk)
                        break

                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("arguments", {})

                    if tool_name not in enabled_tools:
                        # Tool not enabled: stream the planning_buffer content
                        if planning_buffer.strip():
                            content = planning_buffer
                            chunk_size = 8
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i + chunk_size]
                                buffer.add_token(chunk)
                                tokens_generated += 1
                                yield create_token_event(chunk)
                        break

                    # Record tool call for storage
                    self.logger.info(f"Tool call detected: {tool_name} with args: {tool_args}")
                    tool_calls_record.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "round": tool_round + 1,
                        "thinking": planning_thinking.strip() if planning_thinking else None
                    })

                    # Yield tool call status to frontend
                    self.logger.debug(f"Yielding tool_call event: {tool_name}")
                    yield create_status_event("tool_call", {
                        "tool": tool_name,
                        "arguments": tool_args,
                        "round": tool_round + 1
                    })

                    # Execute tool
                    if tool_name == "web_search":
                        web_service = get_web_search_service()
                        if web_service.is_available():
                            tool_result = await web_service.search_and_format(
                                tool_args.get("query", ""),
                                max_results=tool_args.get("max_results", 5)
                            )
                        else:
                            tool_result = "Web search not available"
                    else:
                        exec_result = await self.tool_service.execute_tool(tool_name, tool_args)
                        tool_result = self.tool_service.format_tool_result_for_context(tool_name, exec_result)

                    # Record tool result
                    tool_calls_record[-1]["result"] = tool_result[:2000] if len(tool_result) > 2000 else tool_result
                    self.logger.info(f"Tool result: {len(tool_result)} chars")

                    # Yield tool result status
                    self.logger.debug(f"Yielding tool_result event: {tool_name}")
                    yield create_status_event("tool_result", {
                        "tool": tool_name,
                        "result": tool_result[:1000] if len(tool_result) > 1000 else tool_result,
                        "round": tool_round + 1
                    })

                    # Add assistant tool call + tool result to messages
                    current_messages.append({
                        "role": "assistant",
                        "content": tool_call_text or planning_buffer
                    })
                    current_messages.append({
                        "role": "tool",
                        "content": tool_result
                    })

                    tool_round += 1
                else:
                    # Max tool rounds hit, stream final answer anyway
                    final_prompt = self.manager.format_chat_prompt(
                        current_messages,
                        enable_thinking=enable_thinking
                    )
                    prompt_for_metrics = final_prompt
                    async for token in self.manager.generate(
                        prompt=final_prompt,
                        max_new_tokens=gen_options.get('max_new_tokens', 2048),
                        temperature=gen_options.get('temperature', 0.7),
                        top_p=gen_options.get('top_p', 0.9),
                        top_k=gen_options.get('top_k', 50),
                        repetition_penalty=gen_options.get('repetition_penalty', 1.1),
                        stream=True,
                    ):
                        buffer.add_token(token)
                        tokens_generated += 1
                        yield create_token_event(token)
            # Calculate timing
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Save assistant message with thinking and tool calls stored
            thinking, final_text = self._split_thinking(buffer.content)
            # Remove any tool call tags from the final answer text
            if final_text:
                final_text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", final_text, flags=re.IGNORECASE).strip()
            tool_calls_json = json.dumps(tool_calls_record) if tool_calls_record else None
            assistant_msg = await MessageModel.create(
                conversation_id=conversation_id,
                role="assistant",
                content=final_text or buffer.content,
                thinking=thinking or None,
                raw_content=buffer.content,
                tool_calls=tool_calls_json,
                parent_id=user_msg['id'],
                model=use_model,
                tokens_prompt=len(prompt_for_metrics) // 4,  # Rough estimate
                tokens_completion=tokens_generated,
                duration_ms=duration_ms
            )
            
            # Update conversation title if first message
            if not conv.get('title'):
                title_source = clean_message or message
                title = title_source[:50] + ('...' if len(title_source) > 50 else '')
                await ConversationModel.update(conversation_id, title=title)
            
            # Record model usage
            await ModelRegistry.record_usage(use_model)
            
            # Yield completion event
            yield create_done_event(
                message_id=assistant_msg['id'],
                total_tokens=tokens_generated,
                eval_duration=duration_ms * 1000000,  # Convert to ns for compatibility
                conversation_id=conversation_id
            )

            self.logger.info(
                "Chat completed: conversation=%s message=%s tokens=%s duration_ms=%s",
                conversation_id,
                assistant_msg['id'],
                tokens_generated,
                duration_ms
            )
            
        except ModelNotFoundError as e:
            self.logger.warning("Model not found: %s", e)
            yield create_error_event(str(e), "model_not_found")
        except ModelError as e:
            self.logger.error("Model error: %s", e)
            yield create_error_event(str(e), "model_error")
        except Exception as e:
            self.logger.exception("Unhandled chat error")
            yield create_error_event(str(e), "unknown_error")
    
    async def regenerate_response(
        self,
        message_id: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Regenerate a response for a user message.
        Creates a new branch.
        """
        # Get the message
        message = await MessageModel.get_by_id(message_id)
        if not message:
            yield create_error_event("Message not found", "not_found")
            return
        
        # If this is an assistant message, get its parent (user message)
        if message['role'] == 'assistant':
            parent_id = message.get('parent_id')
            if parent_id:
                message = await MessageModel.get_by_id(parent_id)
        
        if message['role'] != 'user':
            yield create_error_event("Can only regenerate from user messages", "invalid_request")
            return
        
        # Get conversation
        conv = await ConversationModel.get_by_id(message['conversation_id'])
        if not conv:
            yield create_error_event("Conversation not found", "not_found")
            return
        
        # Send the same message again (will create a new branch)
        async for event in self.send_message(
            conversation_id=message['conversation_id'],
            message=message['content'],
            parent_id=message.get('parent_id'),
            model=model,
            options=options
        ):
            yield event
    
    async def get_conversation_detail(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation with its active thread messages and profile details."""
        conv = await ConversationModel.get_by_id(conversation_id)
        if not conv:
            return None

        # Get active thread messages (flat list for UI)
        messages = await MessageModel.get_active_thread(conversation_id)
        conv['messages'] = messages

        # Include profile details when available
        profile = None
        if conv.get('profile_id'):
            profile = await ProfileModel.get_by_id(conv['profile_id'])
        conv['profile'] = profile

        return conv

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation with its active thread messages."""
        return await self.get_conversation_detail(conversation_id)
    
    async def get_conversations(
        self,
        profile_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all conversations, optionally filtered by profile."""
        return await ConversationModel.get_all(
            profile_id=profile_id,
            limit=limit,
            offset=offset
        )
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        return await ConversationModel.delete(conversation_id)
    
    async def update_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
        model: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update conversation metadata."""
        return await ConversationModel.update(
            conversation_id,
            title=title,
            model=model
        )
    
    async def get_message_branches(self, message_id: str) -> List[Dict[str, Any]]:
        """Get all branches from a message."""
        return await MessageModel.get_children(message_id)
    
    async def switch_branch(
        self,
        conversation_id: str,
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """Switch to a different branch."""
        return await ConversationModel.set_active_branch(
            conversation_id, message_id
        )
    
    async def edit_message(
        self,
        message_id: str,
        new_content: str,
        regenerate: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Edit a user message and optionally regenerate the response.
        Creates a new branch.
        """
        # Get the message
        message = await MessageModel.get_by_id(message_id)
        if not message:
            yield create_error_event("Message not found", "not_found")
            return
        
        if message['role'] != 'user':
            yield create_error_event("Can only edit user messages", "invalid_request")
            return
        
        # Send the edited message (creates a new branch)
        async for event in self.send_message(
            conversation_id=message['conversation_id'],
            message=new_content,
            parent_id=message.get('parent_id')
        ):
            yield event

    async def edit_and_continue(
        self,
        message_id: str,
        new_content: str,
        model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Backward-compatible alias used by the /chat/edit route.
        Edits a user message and regenerates from that point.
        """
        async for event in self.edit_message(
            message_id=message_id,
            new_content=new_content,
            regenerate=True
        ):
            yield event
    
    async def delete_message(self, message_id: str) -> bool:
        """Delete a message and all its children."""
        return await MessageModel.delete(message_id)
    
    async def stop_generation(self) -> Dict[str, Any]:
        """
        Stop current generation.
        Note: PyTorch generation is harder to interrupt, but we can signal stop.
        """
        self.manager.request_stop()
        return {"success": True, "message": "Stop signal sent"}


# Global service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

"""
UltraChat - Chat Service
Business logic for chat operations with HuggingFace/PyTorch.
"""

from typing import Optional, Dict, Any, List, AsyncGenerator
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


class ChatService:
    """
    Handles chat operations including:
    - Creating and managing conversations
    - Sending messages with streaming
    - Managing message trees and branches
    - Integrating memory context
    """
    
    def __init__(self):
        self.manager = get_model_manager()
        self.settings = get_settings_manager()
    
    @property
    def default_model(self) -> str:
        """Get the default model from settings."""
        return self.settings.get("default_model", "Qwen/Qwen2.5-1.5B-Instruct")
    
    async def get_or_create_conversation(
        self,
        conversation_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get existing conversation or create new one."""
        if conversation_id:
            conv = await ConversationModel.get_by_id(conversation_id)
            if conv:
                return conv
        
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
                "content": msg['content']
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
        use_memory: bool = True
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
            conversation_id = conv['id']
            
            # Get profile
            profile = None
            if profile_id or conv.get('profile_id'):
                profile = await ProfileModel.get_by_id(
                    profile_id or conv['profile_id']
                )
            if not profile:
                profile = await ProfileModel.get_default()
            
            # Determine model (use currently loaded model)
            use_model = self.manager.current_model
            
            # Perform web search if enabled
            web_search_results = None
            if web_search:
                try:
                    yield create_status_event("searching", {"query": message[:100]})
                    web_service = get_web_search_service()
                    if web_service.is_available():
                        web_search_results = await web_service.search_and_format(message, max_results=5)
                except Exception as e:
                    print(f"Web search failed: {e}")
                    # Continue without web search
            
            # Save user message
            user_msg = await MessageModel.create(
                conversation_id=conversation_id,
                role="user",
                content=message,
                parent_id=parent_id
            )
            
            # Build messages for API
            api_messages = await self.build_messages_for_api(
                conversation_id, profile, 
                include_memory=use_memory,
                web_search_results=web_search_results,
                profile_id=profile_id or (profile.get('id') if profile else None)
            )
            
            # Get generation options
            gen_options = await self.get_generation_options(profile, options)
            
            # Format messages for the model
            prompt = self.manager.format_chat_prompt(api_messages)
            
            # Yield status
            yield create_status_event("generating", {
                "conversation_id": conversation_id,
                "user_message_id": user_msg['id'],
                "model": use_model
            })
            
            # Stream response
            buffer = StreamBuffer()
            tokens_generated = 0
            
            if stream:
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
                result = await self.manager.generate_complete(
                    prompt=prompt,
                    max_new_tokens=gen_options.get('max_new_tokens', 2048),
                    temperature=gen_options.get('temperature', 0.7),
                    top_p=gen_options.get('top_p', 0.9),
                    top_k=gen_options.get('top_k', 50),
                    repetition_penalty=gen_options.get('repetition_penalty', 1.1),
                )
                buffer.add_token(result.text)
                tokens_generated = result.tokens_generated
                yield create_token_event(result.text)
            
            # Calculate timing
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Save assistant message
            assistant_msg = await MessageModel.create(
                conversation_id=conversation_id,
                role="assistant",
                content=buffer.content,
                parent_id=user_msg['id'],
                model=use_model,
                tokens_prompt=len(prompt) // 4,  # Rough estimate
                tokens_completion=tokens_generated,
                duration_ms=duration_ms
            )
            
            # Update conversation title if first message
            if not conv.get('title'):
                title = message[:50] + ('...' if len(message) > 50 else '')
                await ConversationModel.update(conversation_id, title=title)
            
            # Record model usage
            await ModelRegistry.record_usage(use_model)
            
            # Yield completion event
            yield create_done_event(
                message_id=assistant_msg['id'],
                total_tokens=tokens_generated,
                eval_duration=duration_ms * 1000000  # Convert to ns for compatibility
            )
            
        except ModelNotFoundError as e:
            yield create_error_event(str(e), "model_not_found")
        except ModelError as e:
            yield create_error_event(str(e), "model_error")
        except Exception as e:
            import traceback
            traceback.print_exc()
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
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation with its messages."""
        conv = await ConversationModel.get_by_id(conversation_id)
        if not conv:
            return None
        
        # Get messages in tree structure
        messages = await MessageModel.get_tree(conversation_id)
        conv['messages'] = messages
        
        return conv
    
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
    
    async def delete_message(self, message_id: str) -> bool:
        """Delete a message and all its children."""
        return await MessageModel.delete(message_id)
    
    async def stop_generation(self) -> Dict[str, Any]:
        """
        Stop current generation.
        Note: PyTorch generation is harder to interrupt, but we can signal stop.
        """
        # TODO: Implement generation cancellation
        return {"success": True, "message": "Stop signal sent"}


# Global service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

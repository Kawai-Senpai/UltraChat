"""
UltraChat - Chat Service
Business logic for chat operations.
"""

from typing import Optional, Dict, Any, List, AsyncGenerator
import time

from ..core import (
    get_ollama_client,
    OllamaError,
    OllamaConnectionError,
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
from ..config import get_settings
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
        self.ollama = get_ollama_client()
        self.settings = get_settings()
    
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
            model=model or self.settings.ollama.default_model
        )
    
    async def build_messages_for_api(
        self,
        conversation_id: str,
        profile: Optional[Dict[str, Any]] = None,
        include_memory: bool = True,
        web_search_results: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Build the message list for Ollama API.
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
            memories = await MemoryModel.get_for_context(limit=10)
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
    
    async def get_model_options(
        self,
        profile: Optional[Dict[str, Any]] = None,
        custom_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build options dict for Ollama API."""
        options = {}
        
        if profile:
            options['temperature'] = profile.get('temperature', 0.7)
            options['top_p'] = profile.get('top_p', 0.9)
            options['top_k'] = profile.get('top_k', 40)
            options['num_predict'] = profile.get('max_tokens', 4096)
            options['num_ctx'] = profile.get('context_length', 8192)
        else:
            defaults = self.settings.chat_defaults
            options['temperature'] = defaults.temperature
            options['top_p'] = defaults.top_p
            options['top_k'] = defaults.top_k
            options['num_predict'] = defaults.max_tokens
            options['num_ctx'] = defaults.context_length
        
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
            
            # Determine model
            use_model = model or conv.get('model') or profile.get('model') or self.settings.ollama.default_model
            
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
                web_search_results=web_search_results
            )
            
            # Get model options
            api_options = await self.get_model_options(profile, options)
            
            # Yield status
            yield create_status_event("generating", {
                "conversation_id": conversation_id,
                "user_message_id": user_msg['id'],
                "model": use_model
            })
            
            # Stream response
            buffer = StreamBuffer()
            response_metadata = {}
            
            async for chunk in self.ollama.chat(
                model=use_model,
                messages=api_messages,
                options=api_options,
                stream=stream
            ):
                if 'message' in chunk and 'content' in chunk['message']:
                    token = chunk['message']['content']
                    buffer.add_token(token)
                    yield create_token_event(token)
                
                # Capture metadata from final chunk
                if chunk.get('done'):
                    response_metadata = {
                        'total_duration': chunk.get('total_duration'),
                        'eval_count': chunk.get('eval_count'),
                        'prompt_eval_count': chunk.get('prompt_eval_count'),
                    }
            
            # Calculate timing
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Save assistant message
            assistant_msg = await MessageModel.create(
                conversation_id=conversation_id,
                role="assistant",
                content=buffer.content,
                parent_id=user_msg['id'],
                model=use_model,
                tokens_prompt=response_metadata.get('prompt_eval_count'),
                tokens_completion=response_metadata.get('eval_count'),
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
                total_tokens=buffer.token_count,
                eval_duration=response_metadata.get('total_duration')
            )
            
        except OllamaConnectionError as e:
            yield create_error_event(str(e), "connection_error")
        except OllamaError as e:
            yield create_error_event(str(e), "ollama_error")
        except Exception as e:
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
        
        # Regenerate by sending the same message with the user message as parent's parent
        async for event in self.send_message(
            conversation_id=conv['id'],
            message=message['content'],
            parent_id=message.get('parent_id'),  # Same parent as original user message
            model=model,
            options=options
        ):
            yield event
    
    async def edit_and_continue(
        self,
        message_id: str,
        new_content: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Edit a user message and regenerate response.
        Creates a new branch from the edited message.
        """
        # Get the message
        message = await MessageModel.get_by_id(message_id)
        if not message:
            yield create_error_event("Message not found", "not_found")
            return
        
        if message['role'] != 'user':
            yield create_error_event("Can only edit user messages", "invalid_request")
            return
        
        # Get conversation
        conv = await ConversationModel.get_by_id(message['conversation_id'])
        if not conv:
            yield create_error_event("Conversation not found", "not_found")
            return
        
        # Create new message as a branch from same parent
        async for event in self.send_message(
            conversation_id=conv['id'],
            message=new_content,
            parent_id=message.get('parent_id'),
            model=model,
            options=options
        ):
            yield event
    
    async def get_conversation_detail(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get full conversation with messages and profile."""
        conv = await ConversationModel.get_by_id(conversation_id)
        if not conv:
            return None
        
        # Get active message thread
        messages = await MessageModel.get_active_thread(conversation_id)
        
        # Get profile
        profile = None
        if conv.get('profile_id'):
            profile = await ProfileModel.get_by_id(conv['profile_id'])
        
        return {
            **conv,
            'messages': messages,
            'profile': profile
        }
    
    async def get_message_branches(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """Get all branches from a message's children."""
        message = await MessageModel.get_by_id(message_id)
        if not message:
            return {"error": "Message not found"}
        
        return await MessageModel.get_branch_info(
            message_id, 
            message['conversation_id']
        )
    
    async def switch_branch(self, message_id: str) -> bool:
        """Switch to a different branch."""
        return await MessageModel.set_active_branch(message_id)


# Global service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

"""
UltraChat - Chat Routes
API endpoints for chat operations.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    RegenerateRequest,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetail,
    MessageEdit,
    SuccessResponse,
    ErrorResponse,
)
from ..models import ConversationModel, MessageModel
from ..services import get_chat_service, get_message_tree_service


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/send")
async def send_message(request: ChatRequest):
    """
    Send a message and stream the response.
    Returns Server-Sent Events.
    """
    service = get_chat_service()
    
    async def generate():
        async for event in service.send_message(
            conversation_id=request.conversation_id,
            message=request.message,
            parent_id=request.parent_id,
            model=request.model,
            profile_id=request.profile_id,
            stream=request.stream,
            options=request.options,
            web_search=request.web_search,
            use_memory=request.use_memory
        ):
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/regenerate")
async def regenerate_response(request: RegenerateRequest):
    """
    Regenerate a response for a message.
    Creates a new branch.
    """
    service = get_chat_service()
    
    async def generate():
        async for event in service.regenerate_response(
            message_id=request.message_id,
            model=request.model,
            options=request.options
        ):
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/edit")
async def edit_and_continue(
    message_id: str,
    edit: MessageEdit,
    model: Optional[str] = None
):
    """
    Edit a user message and regenerate response.
    Creates a new branch.
    """
    service = get_chat_service()
    
    async def generate():
        async for event in service.edit_and_continue(
            message_id=message_id,
            new_content=edit.content,
            model=model
        ):
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============ Conversations ============

@router.get("/conversations")
async def list_conversations(
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0
):
    """Get all conversations."""
    conversations = await ConversationModel.get_all(
        include_archived=include_archived,
        limit=limit,
        offset=offset
    )
    return {"conversations": conversations}


@router.post("/conversations")
async def create_conversation(data: ConversationCreate):
    """Create a new conversation."""
    conv = await ConversationModel.create(
        title=data.title,
        profile_id=data.profile_id,
        model=data.model
    )
    return conv


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation with all messages."""
    service = get_chat_service()
    detail = await service.get_conversation_detail(conversation_id)
    
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return detail


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, data: ConversationUpdate):
    """Update a conversation."""
    conv = await ConversationModel.update(
        conversation_id,
        title=data.title,
        profile_id=data.profile_id,
        model=data.model,
        pinned=data.pinned,
        archived=data.archived
    )
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conv


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    success = await ConversationModel.delete(conversation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "message": "Conversation deleted"}


@router.get("/conversations/search/{query}")
async def search_conversations(query: str, limit: int = 20):
    """Search conversations by title or content."""
    results = await ConversationModel.search(query, limit)
    return {"conversations": results}


# ============ Messages ============

@router.get("/messages/{message_id}")
async def get_message(message_id: str):
    """Get a single message."""
    message = await MessageModel.get_by_id(message_id)
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


@router.delete("/messages/{message_id}")
async def delete_message(message_id: str):
    """Delete a message and its children."""
    success = await MessageModel.delete(message_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return {"success": True, "message": "Message deleted"}


# ============ Message Tree ============

@router.get("/conversations/{conversation_id}/tree")
async def get_conversation_tree(conversation_id: str):
    """Get the full message tree structure."""
    service = get_message_tree_service()
    return await service.get_tree_structure(conversation_id)


@router.get("/messages/{message_id}/branches")
async def get_message_branches(message_id: str):
    """Get all branches from a message."""
    service = get_chat_service()
    return await service.get_message_branches(message_id)


@router.post("/messages/{message_id}/switch")
async def switch_branch(message_id: str):
    """Switch to a different branch."""
    service = get_message_tree_service()
    result = await service.switch_to_branch(message_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/messages/{message_id}/siblings")
async def get_siblings(message_id: str):
    """Get sibling messages."""
    service = get_message_tree_service()
    return await service.get_siblings(message_id)


@router.post("/messages/{message_id}/navigate/{direction}")
async def navigate_branches(message_id: str, direction: str):
    """Navigate to previous or next sibling."""
    if direction not in ["prev", "next"]:
        raise HTTPException(status_code=400, detail="Direction must be 'prev' or 'next'")
    
    service = get_message_tree_service()
    result = await service.navigate_branches(message_id, direction)
    
    if not result:
        raise HTTPException(status_code=400, detail="No more branches in that direction")
    
    return result


@router.delete("/messages/{message_id}/branch")
async def delete_branch(message_id: str):
    """Delete a message branch."""
    service = get_message_tree_service()
    result = await service.delete_branch(message_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result

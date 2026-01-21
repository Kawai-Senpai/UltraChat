"""
UltraChat - Web Search Routes
API endpoints for web search functionality.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ..services.web_search_service import get_web_search_service


router = APIRouter(prefix="/web-search", tags=["web-search"])


class SearchRequest(BaseModel):
    """Request to search the web."""
    query: str
    max_results: Optional[int] = 5


class SearchResultItem(BaseModel):
    """A single search result."""
    title: str
    url: str
    snippet: str


class SearchResponse(BaseModel):
    """Response with search results."""
    query: str
    results: List[SearchResultItem]
    count: int
    formatted: str


class SearchStatusResponse(BaseModel):
    """Web search status."""
    available: bool
    message: str


@router.get("/status")
async def get_status() -> SearchStatusResponse:
    """Check if web search is available."""
    service = get_web_search_service()
    available = service.is_available()
    
    return SearchStatusResponse(
        available=available,
        message="Web search is available" if available else "duckduckgo-search not installed. Run: pip install duckduckgo-search"
    )


@router.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    """Search the web."""
    service = get_web_search_service()
    
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Web search not available. Install duckduckgo-search package."
        )
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    result = await service.search_to_context(
        request.query,
        max_results=request.max_results
    )
    
    return SearchResponse(
        query=result["query"],
        results=[SearchResultItem(**r) for r in result["results"]],
        count=result["count"],
        formatted=result["formatted"]
    )

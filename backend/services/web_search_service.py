"""
UltraChat - Web Search Service
Provides web search functionality using DuckDuckGo.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    # Try the new package name 'ddgs' first
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    try:
        # Fallback to old package name
        from duckduckgo_search import DDGS
        HAS_DDGS = True
    except ImportError:
        HAS_DDGS = False


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet
        }


class WebSearchService:
    """Service for web search operations."""
    
    def __init__(self, max_results: int = 5, timeout: int = 10):
        self.max_results = max_results
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=2)
    
    def is_available(self) -> bool:
        """Check if web search is available."""
        return HAS_DDGS
    
    def _search_sync(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """Synchronous search (runs in thread pool)."""
        if not HAS_DDGS:
            return []
        
        results = []
        try:
            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,
                    max_results=max_results or self.max_results,
                    safesearch="moderate"
                )
                
                for r in search_results:
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", r.get("link", "")),
                        snippet=r.get("body", r.get("snippet", ""))
                    ))
        except Exception as e:
            print(f"Web search error: {e}")
        
        return results
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """Search the web asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._search_sync,
            query,
            max_results
        )
    
    async def search_and_format(self, query: str, max_results: Optional[int] = None) -> str:
        """Search and return formatted results for the LLM context."""
        results = await self.search(query, max_results)
        
        if not results:
            return f"No web search results found for: {query}"
        
        formatted = [f"Web search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. {r.title}")
            formatted.append(f"   URL: {r.url}")
            formatted.append(f"   {r.snippet}")
            formatted.append("")
        
        return "\n".join(formatted)
    
    async def search_to_context(self, query: str, max_results: Optional[int] = None) -> Dict[str, Any]:
        """Search and return results in a context-friendly format."""
        results = await self.search(query, max_results)
        
        return {
            "query": query,
            "results": [r.to_dict() for r in results],
            "count": len(results),
            "formatted": await self.search_and_format(query, max_results) if results else ""
        }


# Singleton instance
_web_search_service: Optional[WebSearchService] = None


def get_web_search_service() -> WebSearchService:
    """Get the web search service singleton."""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service

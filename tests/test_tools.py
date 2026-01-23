"""
Test script for UltraChat tools.
Run this to verify all tools work properly.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from backend.services.tool_service import get_tool_service
from backend.services.web_search_service import get_web_search_service


async def test_all_tools():
    tool_service = get_tool_service()
    web_service = get_web_search_service()
    
    print("=" * 60)
    print("ULTRACHAT TOOL TESTS")
    print("=" * 60)
    
    # Check tool availability
    print("\n[1] Tool Availability:")
    availability = tool_service.get_available_tools()
    for tool, available in availability.items():
        status = "✓" if available else "✗"
        print(f"  {status} {tool}")
    
    # Test Calculator
    print("\n[2] Testing Calculator...")
    print("-" * 40)
    result = await tool_service.execute_tool("calculator", {"expression": "2 + 3 * 4"})
    print(f"  Expression: 2 + 3 * 4")
    print(f"  Success: {result.success}")
    print(f"  Result: {result.data}")
    if result.error:
        print(f"  Error: {result.error}")
    
    result = await tool_service.execute_tool("calculator", {"expression": "(100 - 50) / 5"})
    print(f"  Expression: (100 - 50) / 5")
    print(f"  Success: {result.success}")
    print(f"  Result: {result.data}")
    
    # Test Wikipedia
    print("\n[3] Testing Wikipedia...")
    print("-" * 40)
    result = await tool_service.execute_tool("wikipedia", {"query": "Python programming", "max_results": 2})
    print(f"  Query: Python programming")
    print(f"  Success: {result.success}")
    if result.success and result.data:
        for i, article in enumerate(result.data[:2], 1):
            print(f"  Result {i}: {article.get('title', 'N/A')}")
            print(f"    URL: {article.get('url', 'N/A')}")
    if result.error:
        print(f"  Error: {result.error}")
    
    # Test Web Search
    print("\n[4] Testing Web Search (DuckDuckGo)...")
    print("-" * 40)
    if web_service.is_available():
        try:
            search_results = await web_service.search("Python programming language", max_results=3)
            print(f"  Query: Python programming language")
            print(f"  Results found: {len(search_results)}")
            for i, r in enumerate(search_results[:3], 1):
                title = r.title if hasattr(r, 'title') else r.get('title', 'N/A')
                url = r.url if hasattr(r, 'url') else r.get('href', r.get('url', 'N/A'))
                print(f"  Result {i}: {title[:50]}...")
                print(f"    URL: {url}")
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("  ✗ Web search not available (duckduckgo_search not installed)")
    
    # Test Web Fetch
    print("\n[5] Testing Web Fetch...")
    print("-" * 40)
    if availability.get("web_fetch"):
        result = await tool_service.execute_tool("web_fetch", {"url": "https://example.com"})
        print(f"  URL: https://example.com")
        print(f"  Success: {result.success}")
        if result.success and result.data:
            content = result.data[:200] + "..." if len(result.data) > 200 else result.data
            print(f"  Content preview: {content}")
        if result.error:
            print(f"  Error: {result.error}")
    else:
        print("  ✗ Web fetch not available (httpx/trafilatura not installed)")
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all_tools())

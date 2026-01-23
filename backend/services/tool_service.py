"""
UltraChat - Tool Service
Provides various agent tools (Wikipedia, Web Fetch, Calculator, Memory, etc.)
"""

import ast
import operator
import asyncio
import json
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from .memory_service import get_memory_service

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


class ToolService:
    """Service for agent tool operations."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Safe operators for calculator
        self._safe_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
    
    # ============================================
    # Tool Availability
    # ============================================
    
    def get_available_tools(self) -> Dict[str, bool]:
        """Get availability status of all tools."""
        return {
            "web_search": True,  # Always available via web_search_service
            "wikipedia": HAS_HTTPX,
            "web_fetch": HAS_HTTPX and HAS_TRAFILATURA,
            "calculator": True,  # Pure Python, always available
            "memory_store": True,  # Always available
            "memory_search": True,  # Always available
        }
    
    def get_tool_definitions(self, enabled_tools: List[str]) -> List[Dict[str, Any]]:
        """Get tool definitions for model prompting."""
        definitions = []
        
        tool_defs = {
            "web_search": {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web using DuckDuckGo. Use for current events, facts, or information not in training data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results (default 5)",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            "wikipedia": {
                "type": "function",
                "function": {
                    "name": "wikipedia",
                    "description": "Search Wikipedia for factual information about topics, people, places, events, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results (default 3)",
                                "default": 3
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            "web_fetch": {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "Fetch and extract readable text content from a webpage URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to fetch"
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            "calculator": {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Evaluate a mathematical expression. Supports +, -, *, /, //, %, ** (power).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "The math expression to evaluate (e.g., '2 + 3 * 4')"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            "memory_store": {
                "type": "function",
                "function": {
                    "name": "memory_store",
                    "description": "Store important information in memory for future recall. Use this to save facts, preferences, instructions, or any information the user wants you to remember across conversations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The information to store in memory"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category for the memory (preference, fact, instruction, personal, project, other)",
                                "enum": ["preference", "fact", "instruction", "personal", "project", "other"],
                                "default": "other"
                            },
                            "importance": {
                                "type": "integer",
                                "description": "Importance level 1-10 (higher = more important)",
                                "minimum": 1,
                                "maximum": 10,
                                "default": 5
                            }
                        },
                        "required": ["content"]
                    }
                }
            },
            "memory_search": {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "Search through stored memories to recall information. Use this when you need to remember something the user previously told you.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find relevant memories"
                            },
                            "category": {
                                "type": "string",
                                "description": "Optional category to filter by",
                                "enum": ["preference", "fact", "instruction", "personal", "project", "other"]
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of memories to return (default 5)",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        }
        
        for tool_name in enabled_tools:
            if tool_name in tool_defs:
                definitions.append(tool_defs[tool_name])
        
        return definitions
    
    # ============================================
    # Tool Execution
    # ============================================
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given arguments."""
        tool_map: Dict[str, Callable] = {
            "wikipedia": self.wikipedia_search,
            "web_fetch": self.web_fetch,
            "calculator": self.calculator,
            "memory_store": self.memory_store,
            "memory_search": self.memory_search,
        }
        
        if tool_name not in tool_map:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}"
            )
        
        try:
            result = await tool_map[tool_name](**arguments)
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    # ============================================
    # Wikipedia Search
    # ============================================
    
    async def wikipedia_search(
        self,
        query: str,
        max_results: int = 3
    ) -> ToolResult:
        """Search Wikipedia for articles matching the query."""
        if not HAS_HTTPX:
            return ToolResult(
                success=False,
                data=None,
                error="httpx package not installed. Run: pip install httpx"
            )
        
        def _search_sync():
            results = []
            try:
                # Use Wikipedia REST API
                search_url = "https://en.wikipedia.org/w/rest.php/v1/search/page"
                params = {"q": query, "limit": max_results}
                headers = {
                    "User-Agent": "UltraChat/1.0 (Local AI Assistant; https://github.com/ultrachat)"
                }
                
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(search_url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    
                    for page in data.get("pages", [])[:max_results]:
                        # Fetch summary for each page
                        title = page.get("title", "")
                        page_key = page.get("key", "")
                        description = page.get("description", "")
                        excerpt = page.get("excerpt", "")
                        
                        results.append({
                            "title": title,
                            "description": description,
                            "excerpt": excerpt.replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
                            "url": f"https://en.wikipedia.org/wiki/{page_key}"
                        })
            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))
            
            return ToolResult(success=True, data=results)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _search_sync)
    
    # ============================================
    # Web Fetch
    # ============================================
    
    async def web_fetch(self, url: str) -> ToolResult:
        """Fetch a webpage and extract readable text content."""
        if not HAS_HTTPX:
            return ToolResult(
                success=False,
                data=None,
                error="httpx package not installed. Run: pip install httpx"
            )
        
        if not HAS_TRAFILATURA:
            return ToolResult(
                success=False,
                data=None,
                error="trafilatura package not installed. Run: pip install trafilatura"
            )
        
        def _fetch_sync():
            try:
                # Fetch HTML
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    response = client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    response.raise_for_status()
                    html = response.text
                
                # Extract readable content
                text = trafilatura.extract(
                    html,
                    include_links=False,
                    include_images=False,
                    include_tables=False,
                    no_fallback=False,
                )
                
                if not text:
                    return ToolResult(
                        success=False,
                        data=None,
                        error="Could not extract readable content from page"
                    )
                
                # Truncate if too long
                if len(text) > 8000:
                    text = text[:8000] + "\n\n[Content truncated...]"
                
                return ToolResult(
                    success=True,
                    data={
                        "url": url,
                        "content": text,
                        "length": len(text)
                    }
                )
            except httpx.HTTPStatusError as e:
                return ToolResult(success=False, data=None, error=f"HTTP error: {e.response.status_code}")
            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _fetch_sync)
    
    # ============================================
    # Calculator
    # ============================================
    
    async def calculator(self, expression: str) -> ToolResult:
        """Safely evaluate a mathematical expression."""
        def _evaluate_sync():
            try:
                # Parse the expression
                tree = ast.parse(expression, mode='eval')
                
                # Validate and evaluate
                result = self._safe_eval(tree.body)
                
                return ToolResult(
                    success=True,
                    data={
                        "expression": expression,
                        "result": result
                    }
                )
            except (SyntaxError, ValueError, TypeError) as e:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Invalid expression: {e}"
                )
            except ZeroDivisionError:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Division by zero"
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    data=None,
                    error=str(e)
                )
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _evaluate_sync)
    
    def _safe_eval(self, node):
        """Safely evaluate an AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        
        elif isinstance(node, ast.BinOp):
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            op_type = type(node.op)
            
            if op_type not in self._safe_operators:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            
            return self._safe_operators[op_type](left, right)
        
        elif isinstance(node, ast.UnaryOp):
            operand = self._safe_eval(node.operand)
            op_type = type(node.op)
            
            if op_type not in self._safe_operators:
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
            
            return self._safe_operators[op_type](operand)
        
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")
    
    # ============================================
    # Memory Tools
    # ============================================
    
    async def memory_store(
        self,
        content: str,
        category: str = "other",
        importance: int = 5,
        profile_id: Optional[str] = None
    ) -> ToolResult:
        """Store information in memory for future recall."""
        try:
            memory_service = get_memory_service()
            
            # Validate category
            valid_categories = ["preference", "fact", "instruction", "personal", "project", "other"]
            if category not in valid_categories:
                category = "other"
            
            # Validate importance
            importance = max(1, min(10, importance))
            
            # Create the memory
            memory = await memory_service.create_memory(
                content=content,
                profile_id=profile_id,
                category=category,
                importance=importance
            )
            
            return ToolResult(
                success=True,
                data={
                    "id": memory.get("id"),
                    "message": "Memory stored successfully",
                    "content": content[:100] + "..." if len(content) > 100 else content,
                    "category": category,
                    "importance": importance
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to store memory: {str(e)}"
            )
    
    async def memory_search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
        profile_id: Optional[str] = None
    ) -> ToolResult:
        """Search through stored memories."""
        try:
            memory_service = get_memory_service()
            
            # Validate limit
            limit = max(1, min(20, limit))
            
            # Search memories
            memories = await memory_service.search_memories(
                query=query,
                profile_id=profile_id,
                category=category,
                limit=limit
            )
            
            # Format results
            results = []
            for mem in memories:
                results.append({
                    "id": mem.get("id"),
                    "content": mem.get("content"),
                    "category": mem.get("category"),
                    "importance": mem.get("importance"),
                    "created_at": mem.get("created_at")
                })
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "count": len(results),
                    "memories": results
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to search memories: {str(e)}"
            )
    
    # ============================================
    # Format Results
    # ============================================
    
    def format_tool_result_for_context(self, tool_name: str, result: ToolResult) -> str:
        """Format a tool result for inclusion in model context."""
        if not result.success:
            return f"Tool '{tool_name}' failed: {result.error}"
        
        data = result.data
        
        if tool_name == "wikipedia":
            if not data:
                return "No Wikipedia results found."
            lines = ["Wikipedia search results:"]
            for item in data:
                lines.append(f"- **{item['title']}**: {item['excerpt']}")
                lines.append(f"  URL: {item['url']}")
            return "\n".join(lines)
        
        elif tool_name == "web_fetch":
            return f"Content from {data['url']}:\n\n{data['content']}"
        
        elif tool_name == "calculator":
            return f"Calculation: {data['expression']} = {data['result']}"
        
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)


# Singleton instance
_tool_service: Optional[ToolService] = None


def get_tool_service() -> ToolService:
    """Get the tool service singleton."""
    global _tool_service
    if _tool_service is None:
        _tool_service = ToolService()
    return _tool_service

"""
UltraChat - Ollama API Client
Wrapper for Ollama API with streaming support and error handling.
"""

import asyncio
import httpx
from typing import AsyncGenerator, Optional, Dict, Any, List
from dataclasses import dataclass
import json

from ..config import get_settings


@dataclass
class ModelInfo:
    """Information about an Ollama model."""
    name: str
    size: int
    digest: str
    modified_at: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class PullProgress:
    """Model download progress information."""
    status: str
    digest: Optional[str] = None
    total: Optional[int] = None
    completed: Optional[int] = None
    
    @property
    def percent(self) -> Optional[float]:
        if self.total and self.completed:
            return (self.completed / self.total) * 100
        return None


class OllamaError(Exception):
    """Base exception for Ollama errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Connection to Ollama failed."""
    pass


class OllamaModelError(OllamaError):
    """Model-related error."""
    pass


class OllamaClient:
    """
    Async client for Ollama API.
    Handles chat, generation, model management, and streaming.
    """
    
    def __init__(self, host: Optional[str] = None, timeout: int = 120):
        settings = get_settings()
        self.host = host or settings.ollama.host
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.host,
                timeout=httpx.Timeout(self.timeout, connect=10.0)
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def check_connection(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    async def get_version(self) -> Optional[str]:
        """Get the Ollama server version."""
        try:
            client = await self._get_client()
            response = await client.get("/api/version")
            if response.status_code == 200:
                data = response.json()
                return data.get("version")
            return None
        except Exception:
            return None
    
    async def list_models(self) -> List[ModelInfo]:
        """List all available local models."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model in data.get("models", []):
                models.append(ModelInfo(
                    name=model["name"],
                    size=model.get("size", 0),
                    digest=model.get("digest", ""),
                    modified_at=model.get("modified_at", ""),
                    details=model.get("details")
                ))
            
            return models
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise OllamaError(f"Failed to list models: {e}")
    
    async def pull_model(self, model_name: str) -> AsyncGenerator[PullProgress, None]:
        """
        Download/pull a model from Ollama registry.
        Yields progress updates.
        """
        try:
            async with httpx.AsyncClient(base_url=self.host, timeout=None) as client:
                async with client.stream(
                    "POST",
                    "/api/pull",
                    json={"name": model_name, "stream": True}
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                yield PullProgress(
                                    status=data.get("status", ""),
                                    digest=data.get("digest"),
                                    total=data.get("total"),
                                    completed=data.get("completed")
                                )
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise OllamaModelError(f"Failed to pull model: {e}")
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a local model."""
        try:
            client = await self._get_client()
            response = await client.delete(
                "/api/delete",
                json={"name": model_name}
            )
            return response.status_code == 200
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise OllamaError(f"Failed to delete model: {e}")
    
    async def show_model(self, model_name: str) -> Dict[str, Any]:
        """Get detailed information about a model."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/show",
                json={"name": model_name}
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise OllamaModelError(f"Model '{model_name}' not found")
            raise OllamaError(f"Failed to get model info: {e}")
        except Exception as e:
            raise OllamaError(f"Failed to get model info: {e}")
    
    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        context: Optional[List[int]] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate a response from the model.
        Yields chunks if streaming, otherwise yields single response.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        
        if system:
            payload["system"] = system
        if context:
            payload["context"] = context
        if options:
            payload["options"] = options
        
        try:
            if stream:
                async with httpx.AsyncClient(base_url=self.host, timeout=None) as client:
                    async with client.stream("POST", "/api/generate", json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    yield data
                                except json.JSONDecodeError:
                                    continue
            else:
                client = await self._get_client()
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
                yield response.json()
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise OllamaError(f"Generation failed: {e}")
    
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Chat with the model using message history.
        Yields chunks if streaming, otherwise yields single response.
        
        Messages format: [{"role": "user/assistant/system", "content": "..."}]
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        
        if options:
            payload["options"] = options
        
        try:
            if stream:
                async with httpx.AsyncClient(base_url=self.host, timeout=None) as client:
                    async with client.stream("POST", "/api/chat", json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    yield data
                                except json.JSONDecodeError:
                                    continue
            else:
                client = await self._get_client()
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                yield response.json()
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise OllamaError(f"Chat failed: {e}")
    
    async def embeddings(
        self,
        model: str,
        prompt: str
    ) -> List[float]:
        """Generate embeddings for the given prompt."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/embeddings",
                json={"model": model, "prompt": prompt}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except httpx.ConnectError:
            raise OllamaConnectionError("Cannot connect to Ollama. Is it running?")
        except Exception as e:
            raise OllamaError(f"Embeddings generation failed: {e}")


# Global client instance
_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get the global Ollama client instance."""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


async def close_ollama_client():
    """Close the global Ollama client."""
    global _client
    if _client:
        await _client.close()
        _client = None

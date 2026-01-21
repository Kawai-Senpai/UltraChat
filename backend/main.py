"""
UltraChat - FastAPI Main Application
Entry point for the backend server.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import get_settings, API_PREFIX
from .models import init_database
from .core import close_ollama_client
from .routes import (
    chat_router,
    models_router,
    profiles_router,
    memory_router,
    settings_router,
)
from .routes.web_search import router as web_search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    print("🚀 Starting UltraChat...")
    
    # Initialize database
    await init_database()
    print("✅ Database initialized")
    
    # Check Ollama connection
    from .services import get_model_service
    service = get_model_service()
    connected = await service.check_connection()
    if connected:
        print("✅ Connected to Ollama")
    else:
        print("⚠️  Could not connect to Ollama - make sure it's running!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down UltraChat...")
    await close_ollama_client()


# Create FastAPI app
app = FastAPI(
    title="UltraChat",
    description="Full-featured local LLM chat interface powered by Ollama",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(models_router, prefix=API_PREFIX)
app.include_router(profiles_router, prefix=API_PREFIX)
app.include_router(memory_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(web_search_router, prefix=API_PREFIX)


# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"

if frontend_dir.exists():
    # Mount static files (CSS, JS)
    app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
    app.mount("/js", StaticFiles(directory=frontend_dir / "js"), name="js")
    
    # Serve index.html for root and any non-API routes
    @app.get("/")
    async def serve_index():
        return FileResponse(frontend_dir / "index.html")
    
    @app.get("/{path:path}")
    async def serve_spa(path: str, request: Request):
        # Don't catch API routes
        if path.startswith("api/"):
            return {"error": "Not found"}
        
        # Check if it's a static file
        file_path = frontend_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise serve index.html (SPA routing)
        return FileResponse(frontend_dir / "index.html")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version
    }


# API info endpoint
@app.get(f"{API_PREFIX}")
async def api_info():
    """API information."""
    return {
        "name": "UltraChat API",
        "version": "1.0.0",
        "endpoints": {
            "chat": f"{API_PREFIX}/chat",
            "models": f"{API_PREFIX}/models",
            "profiles": f"{API_PREFIX}/profiles",
            "memories": f"{API_PREFIX}/memories",
            "settings": f"{API_PREFIX}/settings",
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

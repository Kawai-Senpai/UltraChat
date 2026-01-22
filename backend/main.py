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
from .core import close_model_manager, get_model_manager
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
    
    # Check GPU availability
    manager = get_model_manager()
    gpu_info = manager.gpu_info
    if gpu_info.get("available"):
        print(f"✅ GPU available: {gpu_info.get('device_name')}")
        mem_gb = gpu_info.get('memory_total', 0) / (1024**3)
        print(f"   Memory: {mem_gb:.1f} GB")
    else:
        print("⚠️  No GPU detected - using CPU (will be slower)")
    
    yield
    
    # Shutdown
    print("👋 Shutting down UltraChat...")
    await close_model_manager()


# Create FastAPI app
app = FastAPI(
    title="UltraChat",
    description="Full-featured local LLM chat interface powered by HuggingFace + PyTorch",
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
# In development, Vite serves frontend on port 5173
# In production, serve built files from frontend/dist
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
frontend_dev = Path(__file__).parent.parent / "frontend"

if frontend_dist.exists():
    # Production: serve built Vite output
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
    
    @app.get("/")
    async def serve_index():
        return FileResponse(frontend_dist / "index.html")
    
    @app.get("/{path:path}")
    async def serve_spa(path: str, request: Request):
        # Don't catch API routes
        if path.startswith("api/"):
            return {"error": "Not found"}
        
        # Check if it's a static file
        file_path = frontend_dist / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise serve index.html (SPA routing)
        return FileResponse(frontend_dist / "index.html")

else:
    # Development: redirect to Vite dev server or show message
    @app.get("/")
    async def serve_dev_redirect():
        return {
            "message": "Frontend not built. Run 'npm run build' in frontend folder or use Vite dev server at http://localhost:5173",
            "dev_url": "http://localhost:5173",
            "api_docs": "/docs"
        }


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

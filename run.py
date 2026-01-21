#!/usr/bin/env python3
"""
UltraChat - Local LLM Chat Interface
Run this script to start the application.
"""

import sys
import os
import webbrowser
import threading
import time

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def open_browser(url: str, delay: float = 1.5):
    """Open browser after a short delay to let server start."""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    """Start the UltraChat server."""
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                        UltraChat                              ║
    ║           Full-featured local LLM chat interface              ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Get settings
    try:
        from backend.config import get_settings
        settings = get_settings()
        host = settings.host
        port = settings.port
        debug = settings.debug
    except Exception as e:
        print(f"⚠️  Could not load settings: {e}")
        print("Using defaults...")
        host = "127.0.0.1"
        port = 8000
        debug = True
    
    print(f"🌐 Starting server at http://{host}:{port}")
    print(f"📖 API docs at http://{host}:{port}/docs")
    print(f"🔧 Debug mode: {debug}")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 60)
    
    # Open browser in a separate thread after server starts
    url = f"http://{host}:{port}"
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning"
    )


if __name__ == "__main__":
    main()

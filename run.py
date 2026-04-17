#!/usr/bin/env python3
"""
UltraChat - Local LLM Chat Interface
Run this script to start the application.
"""

import sys
import os
import socket
import webbrowser
import threading
import time
from typing import Optional

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def open_browser(url: str, delay: float = 1.5):
    """Open browser after a short delay to let server start."""
    time.sleep(delay)
    webbrowser.open(url)


def is_port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def find_available_port(host: str, start_port: int, max_tries: int = 20) -> Optional[int]:
    for offset in range(max_tries):
        candidate = start_port + offset
        if is_port_available(host, candidate):
            return candidate
    return None


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
        port = 8080
        debug = True
    
    env_host = os.environ.get("ULTRACHAT_HOST")
    if env_host:
        host = env_host
    env_port = os.environ.get("ULTRACHAT_PORT")
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            print(f"⚠️ Invalid ULTRACHAT_PORT value: {env_port}")
    env_debug = os.environ.get("ULTRACHAT_DEBUG")
    if env_debug:
        debug = env_debug.strip().lower() in ("1", "true", "yes", "on")

    available_port = find_available_port(host, port)
    if available_port is None:
        print(f"❌ No available ports found starting from {port}")
        sys.exit(1)
    if available_port != port:
        print(f"⚠️ Port {port} is in use. Using {available_port} instead.")
        port = available_port

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

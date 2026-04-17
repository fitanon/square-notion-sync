#!/usr/bin/env python3
"""
Run the Square-Notion Sync API server.

Usage:
    python run.py              # Run with default settings
    python run.py --port 8080  # Run on custom port
    python run.py --reload     # Run with auto-reload (development)
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Square-Notion Sync API")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (use 0.0.0.0 for network access)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║          Square → Notion Sync API                             ║
╠═══════════════════════════════════════════════════════════════╣
║  Server: http://{args.host}:{args.port}                              ║
║  Docs:   http://{args.host}:{args.port}/docs                         ║
║                                                               ║
║  Endpoints:                                                   ║
║    GET  /health              - Health check                   ║
║    POST /sync/financial      - Sync transactions & invoices   ║
║    POST /sync/appointments   - Sync bookings & appointments   ║
║    POST /sync/sessions       - Sync session tracking          ║
║    POST /sync/all            - Run all syncs                  ║
║    GET  /scheduler/status    - View scheduler status          ║
║    POST /scheduler/trigger   - Trigger immediate sync         ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

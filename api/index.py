"""
Vercel serverless entry point.

Exports the FastAPI app for Vercel's Python runtime.
"""

from api.app import app

# Vercel expects 'app' or 'handler' at module level
# FastAPI is ASGI-compatible, so this works directly

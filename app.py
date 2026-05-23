"""
Wrapper for Render deployment.
Render looks for app.py by default, so we import the FastAPI app from main.py
"""
from main import app

__all__ = ["app"]

"""
Root entry point for the OCR Plagiarism Detection Backend.
Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

# Re-export the app from the modular package
from app.main import app

__all__ = ["app"]

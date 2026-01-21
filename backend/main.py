"""
Main entry point for Railway/Nixpacks deployment.
This file wraps app.py for compatibility with default Nixpacks detection.
"""

from app import app

# Export the Flask app for gunicorn
# Usage: gunicorn main:app

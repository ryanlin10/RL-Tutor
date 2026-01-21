"""
Flask application for RL Tutor - AI-powered mathematics tutoring.
"""

import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from models import db


def create_app(config_class=Config):
    """Application factory."""
    # Check if static folder exists (built frontend)
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    if os.path.exists(static_folder):
        app = Flask(__name__, static_folder='static', static_url_path='')
    else:
        app = Flask(__name__)
    
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    
    # CORS - allow all origins in production (frontend served from same origin)
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": False,
        }
    })
    
    # Database migrations
    Migrate(app, db)
    
    # Rate limiting
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["1000 per hour"],
        storage_uri=app.config.get("RATELIMIT_STORAGE_URL", "memory://"),
    )
    
    # Register blueprints
    from routes import chat_bp, quiz_bp, documents_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(documents_bp)
    
    # Health check endpoint (fast, no dependencies, no DB queries)
    @app.route("/health")
    def health():
        """Fast health check - no database queries to avoid timeouts."""
        return jsonify({
            "status": "healthy",
            "service": "rl-tutor-api"
        }), 200
    
    # API info endpoint
    @app.route("/api")
    def api_info():
        return jsonify({
            "name": "RL Tutor API",
            "version": "1.0.0",
            "description": "AI-powered mathematics tutoring with RL optimization",
            "endpoints": {
                "chat": {
                    "POST /api/chat/session": "Create new session",
                    "GET /api/chat/session/<id>": "Get session details",
                    "POST /api/chat/message": "Send message",
                    "GET /api/chat/topics": "Get available topics",
                },
                "quiz": {
                    "POST /api/quiz/generate": "Generate quiz",
                    "GET /api/quiz/<id>": "Get quiz",
                    "POST /api/quiz/<id>/submit": "Submit answers",
                    "POST /api/quiz/<id>/hint": "Get hint",
                    "GET /api/quiz/history/<session_id>": "Get quiz history",
                },
            },
        })
    
    # Serve React frontend (for production)
    @app.route('/')
    def serve_frontend():
        if app.static_folder and os.path.exists(os.path.join(app.static_folder, 'index.html')):
            return send_from_directory(app.static_folder, 'index.html')
        return jsonify({"message": "RL Tutor API", "docs": "/api"})
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        # For SPA routing - serve index.html for non-API routes
        if app.static_folder and os.path.exists(os.path.join(app.static_folder, 'index.html')):
            return send_from_directory(app.static_folder, 'index.html')
        return jsonify({"error": "Not found"}), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            "error": "Rate limit exceeded",
            "message": "Maximum 1000 requests per hour",
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500
    
    # Create tables
    with app.app_context():
        db.create_all()
        # RAG service will initialize lazily on first use
        # Don't block startup with RAG initialization
    
    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)

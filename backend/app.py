"""
Flask application for RL Tutor - AI-powered mathematics tutoring.
"""

import os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from models import db


def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Check if static folder exists (built frontend)
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    has_frontend = os.path.exists(static_folder) and os.path.exists(
        os.path.join(static_folder, 'index.html')
    )

    # Initialize extensions
    db.init_app(app)

    # CORS - allow all origins
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": "*",
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

    # Register blueprints FIRST (before any catch-all routes)
    from routes import chat_bp, quiz_bp, documents_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(documents_bp)

    # Health check endpoint
    @app.route("/health")
    def health():
        return "OK", 200, {"Content-Type": "text/plain"}

    # API info endpoint
    @app.route("/api")
    def api_info():
        return jsonify({
            "name": "RL Tutor API",
            "version": "1.0.0",
            "endpoints": {
                "chat": "/api/chat/*",
                "quiz": "/api/quiz/*",
            },
        })

    # Serve frontend static assets
    if has_frontend:
        @app.route('/assets/<path:filename>')
        def serve_assets(filename):
            return send_from_directory(os.path.join(static_folder, 'assets'), filename)

        @app.route('/')
        def serve_frontend():
            return send_from_directory(static_folder, 'index.html')

        # Catch-all for SPA routing (must be last)
        @app.route('/<path:path>')
        def catch_all(path):
            # Don't catch API routes
            if path.startswith('api/'):
                return jsonify({"error": "Not found"}), 404
            # Serve index.html for SPA routing
            return send_from_directory(static_folder, 'index.html')

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        if has_frontend and not request.path.startswith('/api/'):
            return send_from_directory(static_folder, 'index.html')
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({"error": "Rate limit exceeded"}), 429

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    # Create tables
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Note: db.create_all() raised: {e}")

    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)

"""
Chat routes for AI tutor conversations.
"""

import uuid
import json
import re
from flask import Blueprint, request, jsonify

from models import db, Session, Message
from services import groq_service, rag_service, trajectory_service

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("/session", methods=["POST"])
def create_session():
    """Create a new tutoring session."""
    data = request.get_json() or {}
    
    session_id = str(uuid.uuid4())
    subject = data.get("subject", "Mathematics")
    
    session = Session(id=session_id, subject=subject)
    db.session.add(session)
    db.session.commit()
    
    return jsonify({
        "session_id": session_id,
        "subject": subject,
        "created_at": session.created_at.isoformat(),
    }), 201


@chat_bp.route("/session/<session_id>", methods=["GET"])
def get_session(session_id):
    """Get session details and message history."""
    session = Session.query.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    messages = Message.query.filter_by(session_id=session_id).order_by(
        Message.created_at
    ).all()
    
    return jsonify({
        "session_id": session.id,
        "subject": session.subject,
        "created_at": session.created_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    })


@chat_bp.route("/message", methods=["POST"])
def send_message():
    """Send a message to the AI tutor and get a response."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    session_id = data.get("session_id")
    user_message = data.get("message", "").strip()
    
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if not user_message:
        return jsonify({"error": "message required"}), 400
    
    # Get or create session
    session = Session.query.get(session_id)
    if not session:
        session = Session(id=session_id)
        db.session.add(session)
        db.session.commit()
    
    # Save user message
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=user_message,
    )
    db.session.add(user_msg)
    db.session.commit()
    
    # Get conversation history
    history = Message.query.filter_by(session_id=session_id).order_by(
        Message.created_at
    ).all()
    
    messages = [
        {"role": m.role, "content": m.content}
        for m in history
    ]
    
    # Get RAG context if relevant
    rag_context = rag_service.retrieve(user_message, k=3)
    
    # Build state for trajectory
    state = {
        "conversation_history": messages[-10:],  # Last 10 messages
        "current_query": user_message,
        "rag_context_available": bool(rag_context),
    }
    
    # Get AI response
    response = groq_service.chat(
        messages=messages,
        rag_context=rag_context,
    )
    
    ai_content = response.get("content", "I apologize, I couldn't generate a response.")
    
    # Check if response contains a quiz
    quiz_data = None
    if "```json" in ai_content and '"type": "quiz"' in ai_content:
        quiz_data = extract_quiz_from_response(ai_content)
    
    # Save AI message
    ai_msg = Message(
        session_id=session_id,
        role="assistant",
        content=ai_content,
        tokens_used=response.get("total_tokens", 0),
        response_time_ms=response.get("response_time_ms", 0),
    )
    db.session.add(ai_msg)
    db.session.commit()
    
    # Record trajectory
    action = {
        "action_type": "quiz_generation" if quiz_data else "response",
        "content": ai_content,
        "has_quiz": quiz_data is not None,
    }
    
    trajectory_service.record_trajectory(
        session_id=session_id,
        state=state,
        action=action,
        model_name=response.get("model", "unknown"),
        prompt_tokens=response.get("prompt_tokens", 0),
        completion_tokens=response.get("completion_tokens", 0),
    )
    
    result = {
        "message_id": ai_msg.id,
        "content": ai_content,
        "tokens_used": response.get("total_tokens", 0),
        "response_time_ms": response.get("response_time_ms", 0),
    }
    
    if quiz_data:
        result["quiz"] = quiz_data
    
    return jsonify(result)


def extract_quiz_from_response(content: str) -> dict | None:
    """Extract quiz JSON from AI response."""
    try:
        # Find JSON block
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            quiz_data = json.loads(json_str)
            if quiz_data.get("type") == "quiz":
                return quiz_data
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


@chat_bp.route("/topics", methods=["GET"])
def get_topics():
    """Get available topics for tutoring."""
    topics = rag_service.get_topics()
    return jsonify({"topics": topics})

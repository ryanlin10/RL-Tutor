"""
Chat routes for AI tutor conversations.
"""

import uuid
import json
import re
from flask import Blueprint, request, jsonify

from models import db, Session, Message, Quiz
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
    try:
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
        
        # Get RAG context if relevant (don't fail if RAG has issues)
        try:
            rag_context = rag_service.retrieve(user_message, k=3)
        except Exception as e:
            print(f"RAG retrieval error: {e}")
            rag_context = ""
        
        # Build state for trajectory
        state = {
            "conversation_history": messages[-10:],  # Last 10 messages
            "current_query": user_message,
            "rag_context_available": bool(rag_context),
        }
        
        # Get AI response
        try:
            response = groq_service.chat(
                messages=messages,
                rag_context=rag_context,
            )
        except ValueError as e:
            # GROQ_API_KEY not set
            return jsonify({
                "error": str(e),
                "content": "I apologize, but the AI service is not configured. Please contact the administrator.",
            }), 500
        except Exception as e:
            print(f"Groq API error: {e}")
            return jsonify({
                "error": str(e),
                "content": f"I apologize, but I encountered an error: {str(e)}",
            }), 500
        
        ai_content = response.get("content", "I apologize, I couldn't generate a response.")
        
        # Check if response contains a quiz
        quiz_data = None
        if '"questions"' in ai_content or '"type": "quiz"' in ai_content or "{" in ai_content:
            quiz_data = extract_quiz_from_response(ai_content)
        
        # If quiz was extracted, save it and replace the raw JSON with a friendly message
        saved_quiz = None
        if quiz_data and quiz_data.get("questions"):
            # Save quiz to database
            saved_quiz = Quiz(
                session_id=session_id,
                title=quiz_data.get("title", "Quiz"),
                topic=quiz_data.get("topic", "Mathematics"),
                questions=quiz_data.get("questions", []),
            )
            db.session.add(saved_quiz)
            db.session.commit()
            
            ai_content = f"I've prepared a quiz on **{quiz_data.get('topic', 'the topic')}** with {len(quiz_data.get('questions', []))} questions. Take your time and feel free to ask for hints if you get stuck!"
        
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
        
        if saved_quiz:
            # Sanitize questions (remove correct answers from client)
            sanitized_questions = []
            for q in saved_quiz.questions:
                sanitized_questions.append({
                    "id": q.get("id"),
                    "question": q.get("question"),
                    "type": q.get("type", "multiple_choice"),
                    "options": q.get("options", []),
                    "difficulty": q.get("difficulty", "medium"),
                })
            
            result["quiz"] = {
                "id": saved_quiz.id,
                "title": saved_quiz.title,
                "topic": saved_quiz.topic,
                "questions": sanitized_questions,
                "totalQuestions": len(sanitized_questions),
            }
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Error in send_message: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "content": f"I apologize, but an unexpected error occurred: {str(e)}",
        }), 500


def extract_quiz_from_response(content: str) -> dict | None:
    """Extract quiz JSON from AI response."""
    try:
        # Try to find JSON in code block first
        json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            quiz_data = json.loads(json_str)
            if quiz_data.get("type") == "quiz" or "questions" in quiz_data:
                if "type" not in quiz_data:
                    quiz_data["type"] = "quiz"
                return quiz_data
        
        # Try to find raw JSON object in content
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            quiz_data = json.loads(json_str)
            if quiz_data.get("type") == "quiz" or "questions" in quiz_data:
                if "type" not in quiz_data:
                    quiz_data["type"] = "quiz"
                return quiz_data
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


@chat_bp.route("/topics", methods=["GET"])
def get_topics():
    """Get available topics for tutoring."""
    topics = rag_service.get_topics()
    return jsonify({"topics": topics})

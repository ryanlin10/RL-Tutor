"""
Quiz routes for test generation and evaluation.
"""

import json
import re
from datetime import datetime
from flask import Blueprint, request, jsonify

from models import db, Quiz, QuizAttempt, Session, ProblemSheet
from services import groq_service, rag_service, trajectory_service

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api/quiz")


@quiz_bp.route("/generate", methods=["POST"])
def generate_quiz():
    """Generate a new quiz on a topic."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    session_id = data.get("session_id")
    topic = data.get("topic", "General Mathematics")
    difficulty = data.get("difficulty", "medium")
    num_questions = min(data.get("num_questions", 5), 15)  # Cap at 15
    
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    
    # Ensure session exists
    session = Session.query.get(session_id)
    if not session:
        session = Session(id=session_id)
        db.session.add(session)
        db.session.commit()
    
    # Get RAG context for the topic (lecture notes)
    rag_context = rag_service.retrieve(
        f"Mathematics {topic} problems exercises examples",
        k=5
    )
    
    # Get problem sheets from database for this topic
    problem_sheets = ProblemSheet.query.filter(
        ProblemSheet.topic.ilike(f"%{topic}%")
    ).filter(
        ProblemSheet.difficulty == difficulty
    ).limit(3).all()
    
    # Build problem sheet context
    problem_context = ""
    if problem_sheets:
        problem_context = "\n\n--- PROBLEM SHEETS ---\n\n"
        for sheet in problem_sheets:
            problem_context += f"From {sheet.title}:\n"
            if sheet.problems:
                for prob in sheet.problems[:3]:  # First 3 problems per sheet
                    problem_context += f"Problem: {prob.get('question', '')}\n"
                    if prob.get('solution'):
                        problem_context += f"Solution: {prob.get('solution')}\n"
                    problem_context += "\n"
    
    # Combine contexts
    full_context = rag_context
    if problem_context:
        full_context += "\n\n" + problem_context
    
    # Generate quiz
    response = groq_service.generate_quiz(
        topic=topic,
        difficulty=difficulty,
        num_questions=num_questions,
        context=full_context,
    )
    
    content = response.get("content", "")
    
    # Parse quiz from response
    quiz_data = parse_quiz_response(content)
    
    if not quiz_data:
        return jsonify({
            "error": "Failed to generate quiz",
            "raw_response": content[:500],
        }), 500
    
    # Save quiz to database
    quiz = Quiz(
        session_id=session_id,
        title=quiz_data.get("title", f"Quiz: {topic}"),
        topic=topic,
        questions=quiz_data.get("questions", []),
    )
    db.session.add(quiz)
    db.session.commit()
    
    # Record trajectory for quiz generation
    state = {
        "topic": topic,
        "difficulty": difficulty,
        "num_questions": num_questions,
    }
    
    action = {
        "action_type": "quiz_generation",
        "quiz_id": quiz.id,
        "questions_generated": len(quiz_data.get("questions", [])),
    }
    
    trajectory_service.record_trajectory(
        session_id=session_id,
        state=state,
        action=action,
        model_name=response.get("model", "unknown"),
        prompt_tokens=response.get("prompt_tokens", 0),
        completion_tokens=response.get("completion_tokens", 0),
    )
    
    return jsonify({
        "quiz_id": quiz.id,
        "title": quiz.title,
        "topic": quiz.topic,
        "questions": sanitize_questions_for_client(quiz.questions),
        "total_questions": len(quiz.questions),
    }), 201


def parse_quiz_response(content: str) -> dict | None:
    """Parse quiz JSON from model response."""
    try:
        # Try to find JSON in code block
        json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try to parse entire content as JSON
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON object directly
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
    return None


def sanitize_questions_for_client(questions: list) -> list:
    """Remove correct answers from questions sent to client."""
    sanitized = []
    for q in questions:
        sanitized.append({
            "id": q.get("id"),
            "question": q.get("question"),
            "type": q.get("type", "multiple_choice"),
            "options": q.get("options", []),
            "difficulty": q.get("difficulty", "medium"),
        })
    return sanitized


@quiz_bp.route("/<int:quiz_id>", methods=["GET"])
def get_quiz(quiz_id):
    """Get quiz details."""
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    
    return jsonify({
        "quiz_id": quiz.id,
        "title": quiz.title,
        "topic": quiz.topic,
        "questions": sanitize_questions_for_client(quiz.questions),
        "total_questions": len(quiz.questions),
        "created_at": quiz.created_at.isoformat(),
    })


@quiz_bp.route("/<int:quiz_id>/submit", methods=["POST"])
def submit_quiz(quiz_id):
    """Submit quiz answers for grading."""
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    answers = data.get("answers", {})
    time_taken = data.get("time_taken_seconds", 0)
    
    if not answers:
        return jsonify({"error": "answers required"}), 400
    
    # Grade the quiz
    results = grade_quiz(quiz.questions, answers)
    
    # Save attempt
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        answers=answers,
        score=results["score"],
        time_taken_seconds=time_taken,
        correct_count=results["correct_count"],
        total_questions=results["total_questions"],
    )
    db.session.add(attempt)
    db.session.commit()
    
    # Get previous performance for reward computation
    previous_attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id).order_by(
        QuizAttempt.completed_at.desc()
    ).offset(1).first()
    
    previous_score = previous_attempts.score if previous_attempts else None
    
    # Compute reward
    reward_data = trajectory_service.compute_reward(
        session_id=quiz.session_id,
        quiz_attempt=attempt,
        previous_score=previous_score,
    )
    
    # Update user performance
    trajectory_service.update_user_performance(
        session_id=quiz.session_id,
        topic=quiz.topic,
        quiz_score=results["score"],
        questions_attempted=results["total_questions"],
        questions_correct=results["correct_count"],
        hints_used=data.get("hints_used", 0),
        time_seconds=time_taken,
    )
    
    return jsonify({
        "attempt_id": attempt.id,
        "score": results["score"],
        "percentage": round(results["score"] * 100, 1),
        "correct_count": results["correct_count"],
        "total_questions": results["total_questions"],
        "results": results["question_results"],
        "reward": reward_data,
        "time_taken_seconds": time_taken,
    })


def grade_quiz(questions: list, answers: dict) -> dict:
    """Grade quiz answers against correct answers."""
    correct_count = 0
    question_results = []
    
    for q in questions:
        q_id = str(q.get("id"))
        user_answer = answers.get(q_id, "").strip().upper()
        correct_answer = q.get("correct_answer", "").strip().upper()
        
        # Handle answer format variations (e.g., "B" vs "B. ATP")
        is_correct = (
            user_answer == correct_answer or
            user_answer.startswith(correct_answer) or
            correct_answer.startswith(user_answer)
        )
        
        if is_correct:
            correct_count += 1
        
        question_results.append({
            "question_id": q_id,
            "is_correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "explanation": q.get("explanation", ""),
        })
    
    total = len(questions)
    score = correct_count / total if total > 0 else 0.0
    
    return {
        "score": score,
        "correct_count": correct_count,
        "total_questions": total,
        "question_results": question_results,
    }


@quiz_bp.route("/<int:quiz_id>/hint", methods=["POST"])
def get_hint(quiz_id):
    """Get a hint for a specific question."""
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    
    data = request.get_json()
    question_id = data.get("question_id")
    
    if question_id is None:
        return jsonify({"error": "question_id required"}), 400
    
    # Find the question
    question = None
    for q in quiz.questions:
        if str(q.get("id")) == str(question_id):
            question = q
            break
    
    if not question:
        return jsonify({"error": "Question not found"}), 404
    
    # Generate hint using AI
    hint_prompt = f"""Provide a helpful hint for this question without giving away the answer:

Question: {question.get('question', '')}
Options: {question.get('options', [])}

Give a concise hint that guides the student's thinking."""

    response = groq_service.chat(
        messages=[{"role": "user", "content": hint_prompt}],
        temperature=0.5,
        max_tokens=256,
    )
    
    hint = response.get("content", "Think about the key concepts involved.")
    
    return jsonify({
        "question_id": question_id,
        "hint": hint,
    })


@quiz_bp.route("/history/<session_id>", methods=["GET"])
def get_quiz_history(session_id):
    """Get quiz history for a session."""
    quizzes = Quiz.query.filter_by(session_id=session_id).order_by(
        Quiz.created_at.desc()
    ).all()
    
    history = []
    for quiz in quizzes:
        attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).all()
        best_score = max([a.score for a in attempts], default=0)
        
        history.append({
            "quiz_id": quiz.id,
            "title": quiz.title,
            "topic": quiz.topic,
            "total_questions": len(quiz.questions),
            "attempts": len(attempts),
            "best_score": best_score,
            "created_at": quiz.created_at.isoformat(),
        })
    
    return jsonify({"quizzes": history})

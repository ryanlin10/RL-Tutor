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


@chat_bp.route("/upload", methods=["POST"])
def upload_file():
    """
    Upload a file (image or PDF) to add to conversation context.

    For images: Will be analyzed using multimodal capabilities
    For PDFs: Text will be extracted and added to context
    """
    print("=== File upload request received ===")
    try:
        data = request.get_json()
        print(f"Request data keys: {list(data.keys()) if data else 'None'}")

        if not data:
            return jsonify({"error": "Request body required"}), 400

        session_id = data.get("session_id")
        file_name = data.get("file_name", "uploaded_file")
        file_type = data.get("file_type", "")
        file_data = data.get("file_data")  # Base64 encoded
        is_image = data.get("is_image", False)

        print(f"Upload: session={session_id}, file={file_name}, type={file_type}, is_image={is_image}")
        print(f"File data length: {len(file_data) if file_data else 0} chars")

        if not session_id:
            return jsonify({"error": "session_id required"}), 400
        if not file_data:
            return jsonify({"error": "file_data required"}), 400

        # Get or create session
        session = Session.query.get(session_id)
        if not session:
            session = Session(id=session_id)
            db.session.add(session)
            db.session.commit()

        import base64
        import tempfile
        import os

        # Decode base64 file data
        file_bytes = base64.b64decode(file_data)

        extracted_text = ""
        summary = ""
        context_id = str(uuid.uuid4())

        if is_image:
            # For images - use multimodal capabilities to analyze
            # Determine media type from file type
            media_type = file_type if file_type else "image/jpeg"

            try:
                # Use multimodal chat to analyze the image
                analysis_prompt = f"""Please analyze this image that I've uploaded ('{file_name}').

If it contains:
- Mathematical problems or equations: transcribe them and offer to help solve
- Graphs or diagrams: describe what they show mathematically
- Handwritten work: check for errors and provide feedback
- Any other educational content: explain what you see

What can you tell me about this image?"""

                response = groq_service.chat_with_image(
                    prompt=analysis_prompt,
                    image_base64=file_data,  # Already base64 encoded
                    image_media_type=media_type,
                    temperature=0.5,
                    max_tokens=1024,
                )

                summary = response.get("content", "I've analyzed the image you uploaded. Feel free to ask me questions about it!")
                extracted_text = f"[Image: {file_name}]\n{summary}"

            except Exception as e:
                print(f"Error analyzing image: {e}")
                summary = f"I've received the image '{file_name}'. I had trouble analyzing it automatically, but feel free to describe what's in it and I'll help!"
                extracted_text = f"[Image uploaded: {file_name}]"

        else:
            # For PDFs and documents - extract text
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(file_bytes)
                    tmp_path = tmp_file.name

                print(f"Processing PDF: {file_name}, temp path: {tmp_path}")

                # Try pypdf (modern library)
                try:
                    from pypdf import PdfReader
                    print("Using pypdf for PDF extraction")
                    reader = PdfReader(tmp_path)
                    pages_text = []
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        pages_text.append(text)
                        print(f"  Page {i+1}: {len(text)} chars")
                    extracted_text = "\n\n".join(pages_text)
                    print(f"Total extracted text: {len(extracted_text)} chars")
                except ImportError as e:
                    print(f"pypdf not available: {e}")
                    # Fallback to langchain PyPDFLoader
                    try:
                        from langchain_community.document_loaders import PyPDFLoader
                        print("Using langchain PyPDFLoader")
                        loader = PyPDFLoader(tmp_path)
                        documents = loader.load()
                        extracted_text = "\n\n".join([doc.page_content for doc in documents])
                    except ImportError as e2:
                        print(f"langchain PyPDFLoader not available: {e2}")
                        # Last resort - just acknowledge the upload
                        extracted_text = f"[PDF uploaded: {file_name} - text extraction not available]"
                        summary = f"I've received the PDF '{file_name}'. Unfortunately I couldn't extract the text automatically. Please describe the content or copy-paste relevant sections for me to help with."

                        # Clean up and return early
                        if tmp_path and os.path.exists(tmp_path):
                            os.remove(tmp_path)

                        context_message = Message(
                            session_id=session_id,
                            role="system",
                            content=f"[File Context - {file_name}]\n{extracted_text}",
                        )
                        db.session.add(context_message)
                        db.session.commit()

                        return jsonify({
                            "context_id": context_id,
                            "file_name": file_name,
                            "content": summary,
                            "summary": summary,
                            "extracted_text": extracted_text,
                            "is_image": is_image,
                        })

                # Truncate if too long
                max_context_length = 8000
                if len(extracted_text) > max_context_length:
                    extracted_text = extracted_text[:max_context_length] + "...[truncated]"

                # Generate a summary of the document if we have text
                if extracted_text and not extracted_text.startswith("[PDF uploaded"):
                    try:
                        summary_prompt = f"""I've uploaded a document named '{file_name}'. Here's its content:

{extracted_text[:2000]}{'...' if len(extracted_text) > 2000 else ''}

Please acknowledge that you've received this document and briefly summarize what it appears to be about. Let me know I can ask questions about it."""

                        response = groq_service.chat(
                            messages=[{"role": "user", "content": summary_prompt}],
                            temperature=0.5,
                            max_tokens=512,
                        )

                        summary = response.get("content", f"I've received the document '{file_name}'. Feel free to ask me questions about it!")
                    except Exception as summary_error:
                        print(f"Error generating summary: {summary_error}")
                        summary = f"I've received and processed the document '{file_name}'. It contains {len(extracted_text)} characters of text. Feel free to ask me questions about it!"
                else:
                    summary = f"I've received the document '{file_name}'. Feel free to ask me questions about it!"

            except Exception as pdf_error:
                print(f"Error processing PDF: {pdf_error}")
                import traceback
                traceback.print_exc()
                extracted_text = f"[PDF uploaded: {file_name}]"
                summary = f"I've received the PDF '{file_name}'. I had some trouble reading it, but feel free to describe what it contains or ask questions!"

            finally:
                # Clean up temp file
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass

        # Save the file context as a message for future reference
        print(f"Saving file context to database...")
        print(f"  extracted_text length: {len(extracted_text)}")
        print(f"  summary length: {len(summary)}")

        context_message = Message(
            session_id=session_id,
            role="system",
            content=f"[File Context - {file_name}]\n{extracted_text}",
        )
        db.session.add(context_message)
        db.session.commit()
        print("File context saved successfully")

        result = {
            "context_id": context_id,
            "file_name": file_name,
            "content": summary,
            "summary": summary,
            "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "is_image": is_image,
        }
        print(f"Returning success response: {list(result.keys())}")
        return jsonify(result)

    except Exception as e:
        print(f"Error in upload_file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "content": f"I apologize, but I couldn't process the file: {str(e)}",
        }), 500

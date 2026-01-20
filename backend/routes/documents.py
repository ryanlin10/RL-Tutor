"""
Document management routes for uploading lecture notes and problem sheets.
"""

import os
import json
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from models import db, LectureNote, ProblemSheet
from services import rag_service

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'md', 'json'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route("/lecture-notes/upload", methods=["POST"])
def upload_lecture_note():
    """
    Upload a lecture note file (PDF, TXT, MD).
    The file will be chunked and stored in database + vector store.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Use PDF, TXT, or MD"}), 400
    
    # Get metadata
    topic = request.form.get('topic', 'Mathematics')
    title = request.form.get('title', file.filename)
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join('/tmp', filename)
        file.save(temp_path)
        
        # Load and process document
        from langchain_community.document_loaders import TextLoader, PyPDFLoader
        
        if filename.endswith('.pdf'):
            loader = PyPDFLoader(temp_path)
        else:
            loader = TextLoader(temp_path, encoding='utf-8')
        
        documents = loader.load()
        
        # Split into chunks
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_service.chunk_size,
            chunk_overlap=rag_service.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        
        chunks = text_splitter.split_documents(documents)
        
        # Store chunks in database
        created_chunks = []
        for idx, chunk in enumerate(chunks):
            note = rag_service.add_lecture_note_to_db(
                title=title,
                topic=topic,
                content=chunk.page_content,
                source_file=filename,
                page_number=chunk.metadata.get('page', None),
                chunk_index=idx,
            )
            created_chunks.append(note.id)
        
        # Clean up temp file
        os.remove(temp_path)
        
        return jsonify({
            "message": "Lecture note uploaded successfully",
            "title": title,
            "topic": topic,
            "chunks_created": len(created_chunks),
            "chunk_ids": created_chunks,
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500


@documents_bp.route("/problem-sheets/upload", methods=["POST"])
def upload_problem_sheet():
    """
    Upload a problem sheet (JSON format).
    Expected format:
    {
        "title": "Problem Sheet 1",
        "topic": "Linear Algebra",
        "course_code": "MATH101",
        "year": 2024,
        "difficulty": "medium",
        "problems": [
            {
                "id": 1,
                "question": "Problem text...",
                "type": "computation",
                "difficulty": "medium",
                "solution": "Solution...",
                "tags": ["matrices", "determinants"]
            }
        ]
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    
    required_fields = ['title', 'topic', 'problems']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    try:
        problem_sheet = ProblemSheet(
            title=data['title'],
            topic=data['topic'],
            course_code=data.get('course_code'),
            year=data.get('year'),
            difficulty=data.get('difficulty', 'medium'),
            problems=data['problems'],
            source_file=data.get('source_file'),
            uploaded_by=data.get('uploaded_by', 'admin'),
        )
        
        db.session.add(problem_sheet)
        db.session.commit()
        
        return jsonify({
            "message": "Problem sheet uploaded successfully",
            "id": problem_sheet.id,
            "title": problem_sheet.title,
            "topic": problem_sheet.topic,
            "problems_count": len(data['problems']),
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to save problem sheet: {str(e)}"}), 500


@documents_bp.route("/problem-sheets", methods=["GET"])
def list_problem_sheets():
    """List all problem sheets, optionally filtered by topic."""
    topic = request.args.get('topic')
    difficulty = request.args.get('difficulty')
    
    query = ProblemSheet.query
    
    if topic:
        query = query.filter(ProblemSheet.topic.ilike(f"%{topic}%"))
    if difficulty:
        query = query.filter(ProblemSheet.difficulty == difficulty)
    
    sheets = query.order_by(ProblemSheet.created_at.desc()).all()
    
    return jsonify({
        "problem_sheets": [
            {
                "id": sheet.id,
                "title": sheet.title,
                "topic": sheet.topic,
                "course_code": sheet.course_code,
                "year": sheet.year,
                "difficulty": sheet.difficulty,
                "problems_count": len(sheet.problems) if sheet.problems else 0,
                "created_at": sheet.created_at.isoformat(),
            }
            for sheet in sheets
        ]
    })


@documents_bp.route("/problem-sheets/<int:sheet_id>", methods=["GET"])
def get_problem_sheet(sheet_id):
    """Get a specific problem sheet with all problems."""
    sheet = ProblemSheet.query.get(sheet_id)
    
    if not sheet:
        return jsonify({"error": "Problem sheet not found"}), 404
    
    return jsonify({
        "id": sheet.id,
        "title": sheet.title,
        "topic": sheet.topic,
        "course_code": sheet.course_code,
        "year": sheet.year,
        "difficulty": sheet.difficulty,
        "problems": sheet.problems,
        "created_at": sheet.created_at.isoformat(),
    })


@documents_bp.route("/lecture-notes", methods=["GET"])
def list_lecture_notes():
    """List all lecture notes, optionally filtered by topic."""
    topic = request.args.get('topic')
    
    query = LectureNote.query
    
    if topic:
        query = query.filter(LectureNote.topic.ilike(f"%{topic}%"))
    
    # Group by title to show unique documents
    notes = query.order_by(LectureNote.title, LectureNote.chunk_index).all()
    
    # Group by title
    documents = {}
    for note in notes:
        if note.title not in documents:
            documents[note.title] = {
                "title": note.title,
                "topic": note.topic,
                "source_file": note.source_file,
                "chunks_count": 0,
                "created_at": note.created_at.isoformat(),
            }
        documents[note.title]["chunks_count"] += 1
    
    return jsonify({
        "lecture_notes": list(documents.values())
    })


@documents_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get statistics about stored documents."""
    try:
        lecture_note_count = LectureNote.query.count()
        problem_sheet_count = ProblemSheet.query.count()
        
        # Get unique topics
        lecture_topics = db.session.query(LectureNote.topic).distinct().count()
        problem_topics = db.session.query(ProblemSheet.topic).distinct().count()
        
        return jsonify({
            "lecture_notes": {
                "total_chunks": lecture_note_count,
                "unique_topics": lecture_topics,
            },
            "problem_sheets": {
                "total_sheets": problem_sheet_count,
                "unique_topics": problem_topics,
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

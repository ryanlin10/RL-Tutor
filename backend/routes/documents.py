"""
Document management routes for uploading lecture notes and problem sheets.
"""

import os
import json
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from models import db, LectureNote
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
    Upload a problem sheet PDF file.
    The file will be chunked and stored in database + vector store for RAG.
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

        # Store chunks in database as problem_sheet type
        created_chunks = []
        for idx, chunk in enumerate(chunks):
            note = rag_service.add_document_to_db(
                title=title,
                topic=topic,
                content=chunk.page_content,
                document_type="problem_sheet",
                source_file=filename,
                page_number=chunk.metadata.get('page', None),
                chunk_index=idx,
            )
            created_chunks.append(note.id)

        # Clean up temp file
        os.remove(temp_path)

        return jsonify({
            "message": "Problem sheet uploaded successfully",
            "title": title,
            "topic": topic,
            "chunks_created": len(created_chunks),
            "chunk_ids": created_chunks,
        }), 201

    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500


@documents_bp.route("/problem-sheets", methods=["GET"])
def list_problem_sheets():
    """List all problem sheets, optionally filtered by topic."""
    topic = request.args.get('topic')

    query = LectureNote.query.filter(LectureNote.document_type == "problem_sheet")

    if topic:
        query = query.filter(LectureNote.topic.ilike(f"%{topic}%"))

    notes = query.order_by(LectureNote.title, LectureNote.chunk_index).all()

    # Group by title to show unique documents
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
        "problem_sheets": list(documents.values())
    })


@documents_bp.route("/problem-sheets/<path:title>", methods=["GET"])
def get_problem_sheet(title):
    """Get a specific problem sheet by title with all chunks."""
    notes = LectureNote.query.filter(
        LectureNote.document_type == "problem_sheet",
        LectureNote.title == title
    ).order_by(LectureNote.chunk_index).all()

    if not notes:
        return jsonify({"error": "Problem sheet not found"}), 404

    # Combine all chunks into full content
    full_content = "\n\n".join([note.content for note in notes])

    return jsonify({
        "title": notes[0].title,
        "topic": notes[0].topic,
        "source_file": notes[0].source_file,
        "content": full_content,
        "chunks_count": len(notes),
        "created_at": notes[0].created_at.isoformat(),
    })


@documents_bp.route("/lecture-notes", methods=["GET"])
def list_lecture_notes():
    """List all lecture notes, optionally filtered by topic."""
    topic = request.args.get('topic')

    query = LectureNote.query.filter(
        (LectureNote.document_type == "lecture_note") | (LectureNote.document_type.is_(None))
    )

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
        lecture_note_count = LectureNote.query.filter(
            (LectureNote.document_type == "lecture_note") | (LectureNote.document_type.is_(None))
        ).count()
        problem_sheet_count = LectureNote.query.filter(
            LectureNote.document_type == "problem_sheet"
        ).count()

        # Get unique topics for each type
        lecture_topics = db.session.query(LectureNote.topic).filter(
            (LectureNote.document_type == "lecture_note") | (LectureNote.document_type.is_(None))
        ).distinct().count()
        problem_topics = db.session.query(LectureNote.topic).filter(
            LectureNote.document_type == "problem_sheet"
        ).distinct().count()

        return jsonify({
            "lecture_notes": {
                "total_chunks": lecture_note_count,
                "unique_topics": lecture_topics,
            },
            "problem_sheets": {
                "total_chunks": problem_sheet_count,
                "unique_topics": problem_topics,
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

"""
RAG (Retrieval Augmented Generation) service for Oxford maths lecture notes.
Uses database for storage and ChromaDB for vector search.
"""

import os
from pathlib import Path
from typing import Optional, List
import uuid

from config import Config


class RAGService:
    """Service for retrieving relevant lecture notes context."""
    
    def __init__(self):
        self.chunk_size = Config.RAG_CHUNK_SIZE
        self.chunk_overlap = Config.RAG_CHUNK_OVERLAP
        self.vector_db_path = Config.VECTOR_DB_PATH
        self.lecture_notes_path = Config.LECTURE_NOTES_PATH
        
        # Lazy initialization - don't load models until needed
        self._embeddings = None
        self.vector_store = None
        self._initialized = False
    
    @property
    def embeddings(self):
        """Lazy load embeddings model only when needed."""
        if self._embeddings is None:
            print("Loading embeddings model...")
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
            )
            print("Embeddings model loaded.")
        return self._embeddings
    
    def _initialize_vector_store(self):
        """Initialize or load the vector store from database."""
        if self._initialized:
            return  # Already initialized
        
        try:
            from langchain_chroma import Chroma
            
            vector_db_path = Path(self.vector_db_path)
            
            # Ensure directory exists
            vector_db_path.mkdir(parents=True, exist_ok=True)
            
            # Check if vector store already exists
            if vector_db_path.exists() and any(vector_db_path.iterdir()):
                try:
                    self.vector_store = Chroma(
                        persist_directory=str(vector_db_path),
                        embedding_function=self.embeddings,
                    )
                    print(f"Loaded existing vector store from {vector_db_path}")
                    # Sync with database if needed (non-blocking)
                    try:
                        self._sync_from_database()
                    except Exception as e:
                        print(f"Warning: Could not sync from database: {e}")
                    return
                except Exception as e:
                    print(f"Error loading vector store: {e}")
            
            # Try to build from database first
            try:
                from flask import current_app
                from models import LectureNote
                
                with current_app.app_context():
                    note_count = LectureNote.query.count()
                    if note_count > 0:
                        print(f"Found {note_count} lecture note chunks in database. Building vector store...")
                        self._build_vector_store_from_db()
                        return
            except Exception as e:
                print(f"Error checking database: {e}")
            
            # Fallback: try file system
            lecture_path = Path(self.lecture_notes_path)
            if lecture_path.exists() and any(lecture_path.iterdir()):
                print("Building vector store from file system...")
                self._build_vector_store()
            else:
                print("No lecture notes found. RAG will be disabled.")
                self.vector_store = None
                
        except Exception as e:
            print(f"Error initializing vector store: {e}. RAG will be disabled.")
            self.vector_store = None
        finally:
            self._initialized = True
    
    def _build_vector_store(self):
        """Build vector store from lecture notes."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import TextLoader, PyPDFLoader
        from langchain_chroma import Chroma
        
        print("Building vector store from lecture notes...")
        
        documents = []
        lecture_path = Path(self.lecture_notes_path)
        
        # Load text files
        txt_files = list(lecture_path.glob("**/*.txt"))
        for txt_file in txt_files:
            try:
                loader = TextLoader(str(txt_file), encoding="utf-8")
                documents.extend(loader.load())
            except Exception as e:
                print(f"Error loading {txt_file}: {e}")
        
        # Load markdown files
        md_files = list(lecture_path.glob("**/*.md"))
        for md_file in md_files:
            try:
                loader = TextLoader(str(md_file), encoding="utf-8")
                documents.extend(loader.load())
            except Exception as e:
                print(f"Error loading {md_file}: {e}")
        
        # Load PDF files
        pdf_files = list(lecture_path.glob("**/*.pdf"))
        for pdf_file in pdf_files:
            try:
                loader = PyPDFLoader(str(pdf_file))
                documents.extend(loader.load())
            except Exception as e:
                print(f"Error loading {pdf_file}: {e}")
        
        if not documents:
            print("No documents found to index.")
            return
        
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        
        chunks = text_splitter.split_documents(documents)
        print(f"Created {len(chunks)} chunks from {len(documents)} documents")
        
        # Create vector store
        vector_db_path = Path(self.vector_db_path)
        vector_db_path.mkdir(parents=True, exist_ok=True)
        
        self.vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=str(vector_db_path),
        )
        
        print(f"Vector store built and saved to {vector_db_path}")
    
    def retrieve(
        self,
        query: str,
        k: int = 3,
        score_threshold: float = 0.5
    ) -> str:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: The search query
            k: Number of results to return
            score_threshold: Minimum similarity score
            
        Returns:
            Concatenated relevant context string
        """
        # Lazy initialization on first use
        if not self._initialized:
            self._initialize_vector_store()
        
        if self.vector_store is None:
            return ""
        
        try:
            # Perform similarity search with scores
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            # Filter by score threshold and format
            relevant_chunks = []
            for doc, score in results:
                # ChromaDB returns distance, lower is better
                # Convert to similarity (higher is better)
                similarity = 1 - score
                if similarity >= score_threshold:
                    source = doc.metadata.get("source", "Unknown")
                    doc_type = doc.metadata.get("document_type", "lecture_note")
                    topic = doc.metadata.get("topic", "")
                    type_label = "LECTURE NOTE" if doc_type == "lecture_note" else "PROBLEM SHEET"
                    relevant_chunks.append(
                        f"[{type_label} - {topic} - {Path(source).name}]\n{doc.page_content}"
                    )
            
            if not relevant_chunks:
                return ""
            
            return "\n\n---\n\n".join(relevant_chunks)
            
        except Exception as e:
            print(f"Error retrieving context: {e}")
            return ""
    
    def add_documents(self, file_path: str) -> bool:
        """
        Add new documents to the vector store.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Success boolean
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_community.document_loaders import TextLoader, PyPDFLoader
        from langchain_chroma import Chroma
        
        try:
            path = Path(file_path)
            
            if path.suffix == ".pdf":
                loader = PyPDFLoader(str(path))
            else:
                loader = TextLoader(str(path), encoding="utf-8")
            
            documents = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            
            chunks = text_splitter.split_documents(documents)
            
            if self.vector_store is None:
                vector_db_path = Path(self.vector_db_path)
                vector_db_path.mkdir(parents=True, exist_ok=True)
                
                self.vector_store = Chroma.from_documents(
                    documents=chunks,
                    embedding=self.embeddings,
                    persist_directory=str(vector_db_path),
                )
            else:
                self.vector_store.add_documents(chunks)
            
            return True
            
        except Exception as e:
            print(f"Error adding documents: {e}")
            return False
    
    def _build_vector_store_from_db(self):
        """Build vector store from database lecture notes."""
        from langchain_chroma import Chroma
        from langchain.schema import Document
        from models import LectureNote
        
        try:
            # Get all lecture notes from database
            notes = LectureNote.query.all()
            
            if not notes:
                print("No lecture notes in database.")
                return
            
            # Convert to LangChain documents
            documents = []
            for note in notes:
                doc = Document(
                    page_content=note.content,
                    metadata={
                        "source": note.source_file or note.title,
                        "topic": note.topic,
                        "title": note.title,
                        "document_type": note.document_type or "lecture_note",
                        "page_number": note.page_number,
                        "chunk_index": note.chunk_index,
                        "db_id": note.id,
                    }
                )
                documents.append(doc)
            
            # Create or update vector store
            vector_db_path = Path(self.vector_db_path)
            vector_db_path.mkdir(parents=True, exist_ok=True)
            
            if self.vector_store is None:
                self.vector_store = Chroma.from_documents(
                    documents=documents,
                    embedding=self.embeddings,
                    persist_directory=str(vector_db_path),
                )
            else:
                self.vector_store.add_documents(documents)
            
            print(f"Vector store built from {len(documents)} database chunks")
            
        except Exception as e:
            print(f"Error building vector store from database: {e}")
    
    def _sync_from_database(self):
        """Sync vector store with database (add any new notes)."""
        from langchain.schema import Document
        from models import LectureNote
        
        try:
            if self.vector_store is None:
                return
            
            # Get notes that don't have embeddings yet
            notes = LectureNote.query.filter(
                LectureNote.embedding_id.is_(None)
            ).all()
            
            if notes:
                documents = []
                for note in notes:
                    doc = Document(
                        page_content=note.content,
                        metadata={
                            "source": note.source_file or note.title,
                            "topic": note.topic,
                            "title": note.title,
                            "document_type": note.document_type or "lecture_note",
                            "page_number": note.page_number,
                            "chunk_index": note.chunk_index,
                            "db_id": note.id,
                        }
                    )
                    documents.append(doc)

                self.vector_store.add_documents(documents)
                print(f"Synced {len(documents)} new chunks from database")
            
        except Exception as e:
            print(f"Error syncing from database: {e}")
    
    def add_document_to_db(
        self,
        title: str,
        topic: str,
        content: str,
        document_type: str = "lecture_note",
        source_file: Optional[str] = None,
        page_number: Optional[int] = None,
        chunk_index: Optional[int] = None
    ):
        """
        Add a document chunk to the database.

        Args:
            title: Document title
            topic: Mathematical topic
            content: Text content
            document_type: "lecture_note" or "problem_sheet"
            source_file: Original filename
            page_number: Page number (for PDFs)
            chunk_index: Chunk order within document

        Returns:
            Created LectureNote object
        """
        from langchain.schema import Document
        from models import db, LectureNote

        note = LectureNote(
            title=title,
            topic=topic,
            content=content,
            document_type=document_type,
            source_file=source_file,
            page_number=page_number,
            chunk_index=chunk_index,
        )
        db.session.add(note)
        db.session.commit()

        # Add to vector store if initialized
        if self._initialized and self.vector_store:
            doc = Document(
                page_content=content,
                metadata={
                    "source": source_file or title,
                    "topic": topic,
                    "title": title,
                    "document_type": document_type,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "db_id": note.id,
                }
            )
            self.vector_store.add_documents([doc])

        return note

    # Alias for backwards compatibility
    def add_lecture_note_to_db(self, **kwargs):
        """Backwards compatible alias for add_document_to_db."""
        return self.add_document_to_db(document_type="lecture_note", **kwargs)
    
    def get_topics(self) -> list[str]:
        """
        Get list of available topics from database.
        
        Returns:
            List of topic names
        """
        try:
            from models import db, LectureNote
            # Get unique topics from database
            topics = db.session.query(LectureNote.topic).distinct().all()
            if topics:
                return [t[0] for t in topics if t[0]]
        except Exception as e:
            print(f"Error getting topics from database: {e}")
        
        # Fallback to default topics
        return [
            "Linear Algebra",
            "Analysis",
            "Calculus",
            "Probability",
            "Statistics",
            "Differential Equations",
            "Complex Analysis",
            "Abstract Algebra",
            "Number Theory",
            "Topology",
            "Numerical Methods",
            "Mathematical Logic",
        ]


# Singleton instance
rag_service = RAGService()

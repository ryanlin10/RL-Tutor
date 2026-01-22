"""
RAG (Retrieval Augmented Generation) service for Oxford maths lecture notes.
Gracefully degrades if heavy ML dependencies are not installed.
"""

import os
from pathlib import Path
from typing import Optional, List

from config import Config

# Check if RAG dependencies are available
RAG_AVAILABLE = False
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    RAG_AVAILABLE = True
except ImportError:
    pass


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
        self._available = RAG_AVAILABLE

    @property
    def embeddings(self):
        """Lazy load embeddings model only when needed."""
        if not self._available:
            return None

        if self._embeddings is None:
            try:
                print("Loading embeddings model...")
                from langchain_huggingface import HuggingFaceEmbeddings
                self._embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={"device": "cpu"},
                )
                print("Embeddings model loaded.")
            except Exception as e:
                print(f"Could not load embeddings model: {e}")
                self._available = False
                return None
        return self._embeddings

    def _initialize_vector_store(self):
        """Initialize or load the vector store from database."""
        if self._initialized:
            return

        if not self._available:
            print("RAG dependencies not available. RAG features disabled.")
            self._initialized = True
            return

        try:
            from langchain_chroma import Chroma

            vector_db_path = Path(self.vector_db_path)
            vector_db_path.mkdir(parents=True, exist_ok=True)

            if vector_db_path.exists() and any(vector_db_path.iterdir()):
                try:
                    self.vector_store = Chroma(
                        persist_directory=str(vector_db_path),
                        embedding_function=self.embeddings,
                    )
                    print(f"Loaded existing vector store from {vector_db_path}")
                    return
                except Exception as e:
                    print(f"Error loading vector store: {e}")

            print("No vector store found. RAG will be disabled.")
            self.vector_store = None

        except Exception as e:
            print(f"Error initializing vector store: {e}. RAG will be disabled.")
            self.vector_store = None
        finally:
            self._initialized = True

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
            Concatenated relevant context string (empty if RAG unavailable)
        """
        if not self._available:
            return ""

        if not self._initialized:
            self._initialize_vector_store()

        if self.vector_store is None:
            return ""

        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)

            relevant_chunks = []
            for doc, score in results:
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
        """Add new documents to the vector store."""
        if not self._available:
            print("RAG dependencies not available. Cannot add documents.")
            return False

        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            from langchain_community.document_loaders import TextLoader, PyPDFLoader
            from langchain_chroma import Chroma

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
        """Add a document chunk to the database."""
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
        return note

    def add_lecture_note_to_db(self, **kwargs):
        """Backwards compatible alias for add_document_to_db."""
        return self.add_document_to_db(document_type="lecture_note", **kwargs)

    def get_topics(self) -> list[str]:
        """Get list of available topics."""
        try:
            from models import db, LectureNote
            topics = db.session.query(LectureNote.topic).distinct().all()
            if topics:
                return [t[0] for t in topics if t[0]]
        except Exception as e:
            print(f"Error getting topics from database: {e}")

        return [
            "Linear Algebra",
            "Analysis",
            "Calculus",
            "Probability",
            "Statistics",
            "Differential Equations",
        ]


# Singleton instance
rag_service = RAGService()

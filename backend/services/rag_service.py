"""
RAG (Retrieval Augmented Generation) service for Oxford maths lecture notes.
"""

import os
from pathlib import Path
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    DirectoryLoader,
    TextLoader,
    PyPDFLoader,
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from config import Config


class RAGService:
    """Service for retrieving relevant lecture notes context."""
    
    def __init__(self):
        self.chunk_size = Config.RAG_CHUNK_SIZE
        self.chunk_overlap = Config.RAG_CHUNK_OVERLAP
        self.vector_db_path = Config.VECTOR_DB_PATH
        self.lecture_notes_path = Config.LECTURE_NOTES_PATH
        
        # Initialize embeddings model
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        
        self.vector_store: Optional[Chroma] = None
        self._initialize_vector_store()
    
    def _initialize_vector_store(self):
        """Initialize or load the vector store."""
        vector_db_path = Path(self.vector_db_path)
        
        # Check if vector store already exists
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
        
        # Create new vector store if lecture notes exist
        lecture_path = Path(self.lecture_notes_path)
        if lecture_path.exists() and any(lecture_path.iterdir()):
            self._build_vector_store()
        else:
            print(f"No lecture notes found at {lecture_path}. RAG will be disabled.")
            self.vector_store = None
    
    def _build_vector_store(self):
        """Build vector store from lecture notes."""
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
                    relevant_chunks.append(
                        f"[Source: {Path(source).name}]\n{doc.page_content}"
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
    
    def get_topics(self) -> list[str]:
        """
        Get list of available topics based on indexed documents.
        
        Returns:
            List of topic names
        """
        # Default Oxford Maths topics
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

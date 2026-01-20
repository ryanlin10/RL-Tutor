Oxford Mathematics Lecture Notes
================================

Place your Oxford Mathematics lecture notes in this directory.

Supported formats:
- PDF files (.pdf)
- Text files (.txt)
- Markdown files (.md)

The RAG system will automatically:
1. Load all documents from this directory
2. Split them into chunks for efficient retrieval
3. Create embeddings using sentence-transformers
4. Store vectors in ChromaDB for fast similarity search

Recommended content:
- Linear Algebra lecture notes
- Analysis (Real and Complex)
- Calculus and Differential Equations
- Probability and Statistics
- Abstract Algebra
- Number Theory
- Topology

Note: The vector store will be created automatically in ../vector_store/
when the backend starts and finds documents here.

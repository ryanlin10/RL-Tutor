# Document Upload Guide

This guide explains how to upload lecture notes and problem sheets to the database for RAG and quiz generation.

## Overview

The system stores two types of documents in PostgreSQL:

1. **Lecture Notes** - Chunked and embedded for RAG retrieval
2. **Problem Sheets** - Used as context for generating quiz questions

## API Endpoints

### Upload Lecture Note

**POST** `/api/documents/lecture-notes/upload`

Upload a PDF, TXT, or MD file. It will be automatically chunked and stored.

**Request:**
```bash
curl -X POST http://your-api/api/documents/lecture-notes/upload \
  -F "file=@lecture.pdf" \
  -F "topic=Linear Algebra" \
  -F "title=Linear Algebra Lecture 1"
```

**Form Fields:**
- `file` (required) - PDF, TXT, or MD file
- `topic` (optional) - Mathematical topic (default: "Mathematics")
- `title` (optional) - Document title (default: filename)

**Response:**
```json
{
  "message": "Lecture note uploaded successfully",
  "title": "Linear Algebra Lecture 1",
  "topic": "Linear Algebra",
  "chunks_created": 15,
  "chunk_ids": [1, 2, 3, ...]
}
```

### Upload Problem Sheet

**POST** `/api/documents/problem-sheets/upload`

Upload a problem sheet in JSON format.

**Request:**
```bash
curl -X POST http://your-api/api/documents/problem-sheets/upload \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Problem Sheet 1: Linear Algebra",
    "topic": "Linear Algebra",
    "course_code": "MATH101",
    "year": 2024,
    "difficulty": "medium",
    "problems": [
      {
        "id": 1,
        "question": "Find the determinant of the matrix...",
        "type": "computation",
        "difficulty": "medium",
        "solution": "The determinant is calculated as...",
        "tags": ["matrices", "determinants"]
      },
      {
        "id": 2,
        "question": "Prove that...",
        "type": "proof",
        "difficulty": "hard",
        "solution": "We proceed by induction...",
        "tags": ["proof", "induction"]
      }
    ]
  }'
```

**JSON Schema:**
```json
{
  "title": "string (required)",
  "topic": "string (required)",
  "course_code": "string (optional)",
  "year": "integer (optional)",
  "difficulty": "easy|medium|hard (optional, default: medium)",
  "problems": [
    {
      "id": "integer or string",
      "question": "string (required)",
      "type": "computation|proof|application",
      "difficulty": "easy|medium|hard",
      "solution": "string (optional)",
      "tags": ["array of strings"]
    }
  ],
  "source_file": "string (optional)",
  "uploaded_by": "string (optional)"
}
```

**Response:**
```json
{
  "message": "Problem sheet uploaded successfully",
  "id": 1,
  "title": "Problem Sheet 1: Linear Algebra",
  "topic": "Linear Algebra",
  "problems_count": 2
}
```

### List Documents

**GET** `/api/documents/lecture-notes` - List all lecture notes
**GET** `/api/documents/problem-sheets` - List all problem sheets

**Query Parameters:**
- `topic` - Filter by topic

**Example:**
```bash
curl "http://your-api/api/documents/problem-sheets?topic=Linear%20Algebra"
```

### Get Problem Sheet

**GET** `/api/documents/problem-sheets/<id>` - Get specific problem sheet with all problems

### Statistics

**GET** `/api/documents/stats` - Get document statistics

**Response:**
```json
{
  "lecture_notes": {
    "total_chunks": 150,
    "unique_topics": 8
  },
  "problem_sheets": {
    "total_sheets": 12,
    "unique_topics": 6
  }
}
```

## How It Works

### Lecture Notes Flow

1. **Upload** → File is saved temporarily
2. **Load** → Document is loaded (PDF parsed, text extracted)
3. **Chunk** → Text is split into chunks (1000 chars, 200 overlap)
4. **Store** → Each chunk saved to `lecture_notes` table
5. **Embed** → Chunks are embedded and added to ChromaDB vector store
6. **Retrieve** → RAG service queries vector store for relevant chunks

### Problem Sheets Flow

1. **Upload** → JSON is validated
2. **Store** → Entire problem sheet saved to `problem_sheets` table
3. **Retrieve** → Quiz generation queries problem sheets by topic/difficulty
4. **Context** → Problems are included in prompt for quiz generation

## Database Schema

### `lecture_notes` Table
- `id` - Primary key
- `title` - Document title
- `topic` - Mathematical topic
- `content` - Text chunk content
- `source_file` - Original filename
- `page_number` - Page number (for PDFs)
- `chunk_index` - Order within document

### `problem_sheets` Table
- `id` - Primary key
- `title` - Sheet title
- `topic` - Mathematical topic
- `problems` - JSON array of problems
- `course_code` - Course identifier
- `year` - Academic year
- `difficulty` - Overall difficulty

## Example: Uploading Oxford Maths Notes

### Step 1: Upload Lecture Notes

```bash
# Upload a PDF lecture
curl -X POST http://localhost:5000/api/documents/lecture-notes/upload \
  -F "file=@oxford_linear_algebra_lecture1.pdf" \
  -F "topic=Linear Algebra" \
  -F "title=Oxford Linear Algebra Lecture 1"
```

### Step 2: Upload Problem Sheets

```bash
# Upload a problem sheet
curl -X POST http://localhost:5000/api/documents/problem-sheets/upload \
  -H "Content-Type: application/json" \
  -d @problem_sheet.json
```

Where `problem_sheet.json` contains:
```json
{
  "title": "Oxford Maths Problem Sheet 1",
  "topic": "Linear Algebra",
  "course_code": "MATH101",
  "year": 2024,
  "difficulty": "medium",
  "problems": [
    {
      "id": 1,
      "question": "Let $A$ be an $n \\times n$ matrix. Prove that $\\det(A^T) = \\det(A)$.",
      "type": "proof",
      "difficulty": "medium",
      "solution": "We use the fact that...",
      "tags": ["matrices", "determinants", "transpose"]
    }
  ]
}
```

### Step 3: Verify Upload

```bash
# Check statistics
curl http://localhost:5000/api/documents/stats

# List lecture notes
curl http://localhost:5000/api/documents/lecture-notes

# List problem sheets
curl http://localhost:5000/api/documents/problem-sheets
```

## Integration with Quiz Generation

When generating a quiz:

1. System queries `problem_sheets` table for matching topic/difficulty
2. Problems are included in the prompt context
3. AI generates quiz questions inspired by the problem sheets
4. RAG also retrieves relevant lecture note chunks for additional context

This ensures quizzes are aligned with Oxford Maths curriculum and problem styles.

## Tips

- **Topic Names**: Use consistent topic names (e.g., "Linear Algebra" not "linear algebra" or "Linear algebra")
- **Chunking**: Large PDFs are automatically chunked - no manual splitting needed
- **Problem Format**: Include solutions in problem sheets - they help the AI understand the expected answer format
- **Tags**: Use descriptive tags for better organization

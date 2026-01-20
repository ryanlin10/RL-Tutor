**RL AI Tutor**

An AI-powered tutoring system using reinforcement learning signals from user performance. Built with React frontend and Flask backend, using Groq's DeepSeek model for intelligent tutoring.

## Architecture

```
/
├── frontend/          # React + Vite frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── ChatPanel.jsx
│   │   │   └── WorkspacePanel.jsx
│   │   ├── styles/
│   │   └── App.jsx
│   └── package.json
│
├── backend/           # Flask API backend
│   ├── services/
│   │   ├── groq_service.py    # Groq API integration
│   │   ├── rag_service.py     # RAG for lecture notes
│   │   └── trajectory_service.py  # RL trajectory storage
│   ├── routes/
│   │   ├── chat.py
│   │   └── quiz.py
│   ├── models.py      # SQLAlchemy models
│   ├── config.py      # Configuration
│   └── app.py         # Flask application
│
└── data/
    ├── lecture_notes/ # Oxford maths lecture notes (add your PDFs/text here)
    └── vector_store/  # ChromaDB vector store (auto-generated)
```

## Features

- **AI Tutor Chat**: Conversational interface with Dr. Turing, an AI mathematics tutor
- **Quiz Generation**: Dynamically generated quizzes on various mathematics topics
- **RAG System**: Retrieval-augmented generation using Oxford maths lecture notes
- **RL Trajectory Storage**: All interactions stored for future reinforcement learning
- **Performance Tracking**: User performance metrics used as reward signals

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL database
- Groq API key

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp env.example .env
# Edit .env with your configuration

# Initialize database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Run development server
python app.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Flask
FLASK_DEBUG=True
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/rl_tutor

# Groq API
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=deepseek-r1-distill-llama-70b

# RAG
LECTURE_NOTES_PATH=./data/lecture_notes
VECTOR_DB_PATH=./data/vector_store
```

### Adding Lecture Notes

Place Oxford Mathematics lecture notes in `data/lecture_notes/`:
- Supported formats: PDF, TXT, MD
- The RAG system will automatically index them on startup
- Notes are chunked and embedded for retrieval

## API Endpoints

### Chat
- `POST /api/chat/session` - Create new session
- `GET /api/chat/session/<id>` - Get session details
- `POST /api/chat/message` - Send message to tutor
- `GET /api/chat/topics` - Get available topics

### Quiz
- `POST /api/quiz/generate` - Generate a quiz
- `GET /api/quiz/<id>` - Get quiz details
- `POST /api/quiz/<id>/submit` - Submit quiz answers
- `POST /api/quiz/<id>/hint` - Get hint for question
- `GET /api/quiz/history/<session_id>` - Get quiz history

## Railway Deployment

The project is configured for Railway deployment:

1. **Database**: Add PostgreSQL service (Railway provides `DATABASE_URL` automatically)
2. **Backend**: Deploy from `/backend` directory
3. **Frontend**: Deploy from `/frontend` directory

### Backend Service
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Release: `flask db upgrade`

### Frontend Service
- Build: `npm install && npm run build`
- Start: `npx serve dist -s -l $PORT`

## RL Trajectory Data

Trajectories are stored in PostgreSQL for future reinforcement learning:

```python
{
    "state": {
        "conversation_history": [...],
        "current_topic": "Linear Algebra",
        "user_performance_history": {...}
    },
    "action": {
        "action_type": "response|quiz_generation|hint",
        "content": "...",
        "model_response": "..."
    },
    "reward": 0.75,  # Computed from quiz performance
    "reward_breakdown": {
        "quiz_improvement": 0.3,
        "quiz_absolute": 0.4,
        "engagement": 0.2,
        "efficiency": 0.1
    }
}
```

## Rate Limiting

- Default: 1000 requests per hour per IP
- Configured via `RATELIMIT_STORAGE_URL` (Redis recommended for production)

## Tech Stack

- **Frontend**: React 18, Vite, KaTeX (math rendering)
- **Backend**: Flask, SQLAlchemy, Flask-Migrate
- **AI**: Groq API (DeepSeek R1 Distill LLaMA 70B)
- **RAG**: LangChain, ChromaDB, Sentence Transformers
- **Database**: PostgreSQL
- **Deployment**: Railway

## License

MIT

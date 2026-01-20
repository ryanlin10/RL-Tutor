from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Session(db.Model):
    """Represents a tutoring session."""
    
    __tablename__ = "sessions"
    
    id = db.Column(db.String(36), primary_key=True)
    subject = db.Column(db.String(100), default="Mathematics")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db.relationship("Message", backref="session", lazy="dynamic", cascade="all, delete-orphan")
    quizzes = db.relationship("Quiz", backref="session", lazy="dynamic", cascade="all, delete-orphan")
    trajectories = db.relationship("Trajectory", backref="session", lazy="dynamic", cascade="all, delete-orphan")


class Message(db.Model):
    """Chat messages between user and AI tutor."""
    
    __tablename__ = "messages"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey("sessions.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Metadata for RL
    tokens_used = db.Column(db.Integer, default=0)
    response_time_ms = db.Column(db.Integer, default=0)


class Quiz(db.Model):
    """Generated quizzes/tests."""
    
    __tablename__ = "quizzes"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey("sessions.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(200))
    questions = db.Column(db.JSON, nullable=False)  # List of question objects
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    attempts = db.relationship("QuizAttempt", backref="quiz", lazy="dynamic", cascade="all, delete-orphan")


class QuizAttempt(db.Model):
    """User's attempt at a quiz."""
    
    __tablename__ = "quiz_attempts"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    answers = db.Column(db.JSON, nullable=False)  # User's answers
    score = db.Column(db.Float, nullable=False)  # 0.0 to 1.0
    time_taken_seconds = db.Column(db.Integer)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Detailed breakdown
    correct_count = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)


class Trajectory(db.Model):
    """
    RL trajectory data for future training.
    Stores state-action-reward tuples from tutoring interactions.
    """
    
    __tablename__ = "trajectories"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey("sessions.id"), nullable=False)
    
    # State: Context at decision time
    state = db.Column(db.JSON, nullable=False)
    # Contains: conversation_history, current_topic, user_performance_history
    
    # Action: What the model decided to do
    action = db.Column(db.JSON, nullable=False)
    # Contains: action_type (explain, quiz, hint, etc.), content, model_response
    
    # Reward signal (computed from user performance)
    reward = db.Column(db.Float, default=0.0)
    # Reward breakdown for analysis
    reward_breakdown = db.Column(db.JSON)
    # Contains: quiz_score_delta, engagement_score, understanding_indicators
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    model_name = db.Column(db.String(100))
    prompt_tokens = db.Column(db.Integer)
    completion_tokens = db.Column(db.Integer)


class UserPerformance(db.Model):
    """
    Aggregated user performance metrics for RL signal computation.
    """
    
    __tablename__ = "user_performance"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey("sessions.id"), nullable=False)
    
    # Topic-level metrics
    topic = db.Column(db.String(200), nullable=False)
    
    # Performance metrics
    questions_attempted = db.Column(db.Integer, default=0)
    questions_correct = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    score_trend = db.Column(db.Float, default=0.0)  # Positive = improving
    
    # Engagement metrics
    hints_requested = db.Column(db.Integer, default=0)
    time_on_topic_seconds = db.Column(db.Integer, default=0)
    
    # Timestamps
    first_attempt_at = db.Column(db.DateTime)
    last_attempt_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

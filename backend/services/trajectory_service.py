"""
Trajectory service for collecting and storing RL training data.
"""

from datetime import datetime
from typing import Optional
import json

from models import db, Trajectory, UserPerformance, QuizAttempt, Session


class TrajectoryService:
    """Service for managing RL trajectories and computing rewards."""
    
    # Reward weights for different signals
    REWARD_WEIGHTS = {
        "quiz_improvement": 0.4,      # Weight for quiz score improvement
        "quiz_absolute": 0.3,          # Weight for absolute quiz performance
        "engagement": 0.2,             # Weight for engagement metrics
        "efficiency": 0.1,             # Weight for learning efficiency
    }
    
    def record_trajectory(
        self,
        session_id: str,
        state: dict,
        action: dict,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> Trajectory:
        """
        Record a new trajectory entry.
        
        Args:
            session_id: The session ID
            state: State at decision time (conversation history, topic, etc.)
            action: Action taken (response type, content)
            model_name: Name of the model used
            prompt_tokens: Tokens in prompt
            completion_tokens: Tokens in completion
            
        Returns:
            Created Trajectory object
        """
        trajectory = Trajectory(
            session_id=session_id,
            state=state,
            action=action,
            reward=0.0,  # Will be computed later
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        
        db.session.add(trajectory)
        db.session.commit()
        
        return trajectory
    
    def compute_reward(
        self,
        session_id: str,
        quiz_attempt: Optional[QuizAttempt] = None,
        previous_score: Optional[float] = None,
    ) -> dict:
        """
        Compute reward signal from user performance.
        
        The reward is computed from multiple signals:
        1. Quiz improvement: Change in score from previous attempt
        2. Quiz absolute: Current quiz score
        3. Engagement: Hints requested, time spent, etc.
        4. Efficiency: How quickly the student is learning
        
        Args:
            session_id: The session ID
            quiz_attempt: Optional quiz attempt to base reward on
            previous_score: Previous quiz score for comparison
            
        Returns:
            Dict with reward value and breakdown
        """
        reward_breakdown = {
            "quiz_improvement": 0.0,
            "quiz_absolute": 0.0,
            "engagement": 0.0,
            "efficiency": 0.0,
        }
        
        # 1. Quiz improvement reward
        if quiz_attempt and previous_score is not None:
            score_delta = quiz_attempt.score - previous_score
            # Normalize to [-1, 1] range
            reward_breakdown["quiz_improvement"] = max(-1.0, min(1.0, score_delta * 2))
        
        # 2. Absolute quiz performance
        if quiz_attempt:
            # Scale score from [0, 1] to [-0.5, 1] to penalize very low scores
            reward_breakdown["quiz_absolute"] = quiz_attempt.score * 1.5 - 0.5
        
        # 3. Engagement reward (from user performance data)
        performance = UserPerformance.query.filter_by(session_id=session_id).first()
        if performance:
            # Positive reward for engagement, slight penalty for too many hints
            hints_penalty = min(0.3, performance.hints_requested * 0.05)
            time_bonus = min(0.3, performance.time_on_topic_seconds / 600)  # Max bonus at 10 min
            reward_breakdown["engagement"] = time_bonus - hints_penalty
        
        # 4. Efficiency reward (learning speed)
        if performance and performance.questions_attempted > 0:
            # Higher efficiency = better score per question attempted
            efficiency = performance.questions_correct / performance.questions_attempted
            trend_bonus = max(-0.3, min(0.3, performance.score_trend))
            reward_breakdown["efficiency"] = efficiency * 0.7 + trend_bonus
        
        # Compute weighted total reward
        total_reward = sum(
            reward_breakdown[key] * self.REWARD_WEIGHTS[key]
            for key in reward_breakdown
        )
        
        # Clamp to [-1, 1]
        total_reward = max(-1.0, min(1.0, total_reward))
        
        return {
            "reward": total_reward,
            "breakdown": reward_breakdown,
        }
    
    def update_trajectory_reward(
        self,
        trajectory_id: int,
        reward: float,
        reward_breakdown: dict,
    ) -> bool:
        """
        Update an existing trajectory with computed reward.
        
        Args:
            trajectory_id: The trajectory ID to update
            reward: The computed reward value
            reward_breakdown: Detailed reward breakdown
            
        Returns:
            Success boolean
        """
        trajectory = Trajectory.query.get(trajectory_id)
        if not trajectory:
            return False
        
        trajectory.reward = reward
        trajectory.reward_breakdown = reward_breakdown
        db.session.commit()
        
        return True
    
    def update_user_performance(
        self,
        session_id: str,
        topic: str,
        quiz_score: float,
        questions_attempted: int,
        questions_correct: int,
        hints_used: int = 0,
        time_seconds: int = 0,
    ) -> UserPerformance:
        """
        Update user performance metrics for a topic.
        
        Args:
            session_id: The session ID
            topic: The topic being studied
            quiz_score: Score from latest quiz
            questions_attempted: Number of questions attempted
            questions_correct: Number of questions correct
            hints_used: Number of hints requested
            time_seconds: Time spent on topic
            
        Returns:
            Updated UserPerformance object
        """
        performance = UserPerformance.query.filter_by(
            session_id=session_id,
            topic=topic
        ).first()
        
        now = datetime.utcnow()
        
        if not performance:
            performance = UserPerformance(
                session_id=session_id,
                topic=topic,
                first_attempt_at=now,
                questions_attempted=0,
                questions_correct=0,
                hints_requested=0,
                time_on_topic_seconds=0,
                average_score=0.0,
                score_trend=0.0,
            )
            db.session.add(performance)
        
        # Update cumulative stats (handle existing records with NULL values)
        old_avg = performance.average_score or 0.0
        old_count = performance.questions_attempted or 0

        performance.questions_attempted = (performance.questions_attempted or 0) + questions_attempted
        performance.questions_correct = (performance.questions_correct or 0) + questions_correct
        performance.hints_requested = (performance.hints_requested or 0) + hints_used
        performance.time_on_topic_seconds = (performance.time_on_topic_seconds or 0) + time_seconds
        performance.last_attempt_at = now

        # Update average score with exponential moving average
        alpha = 0.3  # Weight for new score
        performance.average_score = alpha * quiz_score + (1 - alpha) * old_avg

        # Compute score trend
        if old_count > 0:
            performance.score_trend = quiz_score - old_avg
        
        db.session.commit()
        
        return performance
    
    def get_session_trajectories(self, session_id: str) -> list[dict]:
        """
        Get all trajectories for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            List of trajectory dicts
        """
        trajectories = Trajectory.query.filter_by(session_id=session_id).order_by(
            Trajectory.created_at
        ).all()
        
        return [
            {
                "id": t.id,
                "state": t.state,
                "action": t.action,
                "reward": t.reward,
                "reward_breakdown": t.reward_breakdown,
                "model_name": t.model_name,
                "prompt_tokens": t.prompt_tokens,
                "completion_tokens": t.completion_tokens,
                "created_at": t.created_at.isoformat(),
            }
            for t in trajectories
        ]
    
    def export_trajectories_for_training(
        self,
        min_reward: Optional[float] = None,
        limit: int = 10000,
    ) -> list[dict]:
        """
        Export trajectories in a format suitable for RL training.
        
        Args:
            min_reward: Optional minimum reward filter
            limit: Maximum number of trajectories to export
            
        Returns:
            List of trajectory dicts for training
        """
        query = Trajectory.query
        
        if min_reward is not None:
            query = query.filter(Trajectory.reward >= min_reward)
        
        trajectories = query.order_by(Trajectory.created_at.desc()).limit(limit).all()
        
        return [
            {
                "session_id": t.session_id,
                "state": t.state,
                "action": t.action,
                "reward": t.reward,
                "reward_breakdown": t.reward_breakdown,
                "model_name": t.model_name,
                "tokens": {
                    "prompt": t.prompt_tokens,
                    "completion": t.completion_tokens,
                },
            }
            for t in trajectories
        ]


# Singleton instance
trajectory_service = TrajectoryService()

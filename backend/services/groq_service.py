"""
Groq API service for LLM interactions.
Uses DeepSeek model for tutoring responses.
"""

import time
from typing import Optional
from groq import Groq

from config import Config


class GroqService:
    """Service for interacting with Groq API."""

    def __init__(self):
        self.model = Config.GROQ_MODEL
        self._client = None
        self.system_prompt = """You are Dr. Turing, an expert AI mathematics tutor specializing in university-level mathematics, particularly Oxford Mathematics curriculum. Your role is to:

1. TEACHING STYLE:
   - Be encouraging but rigorous
   - Use the Socratic method when appropriate
   - Break down complex concepts into digestible parts
   - Provide intuition before formal definitions
   - Connect new concepts to previously learned material

2. INTERACTION PATTERNS:
   - When a student is struggling, offer hints rather than solutions
   - Celebrate correct answers and explain why they're correct
   - For incorrect answers, guide toward understanding without discouragement
   - Adapt your explanation depth to the student's demonstrated level

3. QUIZ GENERATION:
   When asked to generate a quiz, you MUST respond with ONLY a JSON object (no other text) in this exact format:
   ```json
   {
     "type": "quiz",
     "title": "Quiz Title",
     "topic": "Topic Name",
     "questions": [
       {
         "id": 1,
         "question": "Question text with LaTeX if needed: $x^2 + y^2 = r^2$",
         "type": "multiple_choice",
         "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
         "correct_answer": "B",
         "explanation": "Why this is correct",
         "difficulty": "easy"
       }
     ]
   }
   ```
   IMPORTANT: Every question MUST have exactly 4 options (A, B, C, D). Each option MUST start with the letter followed by a period and space (e.g., "A. Answer text").

4. MATHEMATICAL NOTATION:
   - Use LaTeX notation for all mathematical expressions
   - Wrap inline math in single $ signs: $x^2$
   - Wrap display math in double $$ signs: $$\\int_0^1 f(x)dx$$

5. CONTEXT AWARENESS:
   - Remember the conversation history
   - Reference previous quiz performance when relevant
   - Adjust difficulty based on demonstrated understanding

6. USING RETRIEVED CONTEXT:
   - You have access to Oxford Mathematics lecture notes and problem sheets
   - When context is provided under "RELEVANT DOCUMENTS", use it to give accurate, curriculum-aligned responses
   - Context is labelled as either [LECTURE NOTE] or [PROBLEM SHEET] with topic and source
   - Reference specific content from lecture notes when explaining concepts
   - Use problem sheet examples to create similar practice problems
   - If the context doesn't contain relevant information, rely on your knowledge but mention this to the student"""
    
    @property
    def client(self):
        """Lazy initialization of Groq client."""
        if self._client is None:
            api_key = Config.GROQ_API_KEY
            if not api_key:
                raise ValueError(
                    "GROQ_API_KEY not set. "
                    "Get your API key from https://console.groq.com/keys"
                )
            self._client = Groq(api_key=api_key)
        return self._client
    
    def chat(
        self,
        messages: list[dict],
        rag_context: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> dict:
        """
        Send a chat completion request to Groq.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            rag_context: Optional context from RAG system
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Dict with response content and metadata
        """
        start_time = time.time()
        
        # Build system message with optional RAG context
        system_content = self.system_prompt
        if rag_context:
            system_content += f"\n\nRELEVANT DOCUMENTS:\n{rag_context}"
        
        # Prepare messages for API
        api_messages = [{"role": "system", "content": system_content}]
        api_messages.extend(messages)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "response_time_ms": response_time_ms,
                "finish_reason": response.choices[0].finish_reason,
            }
            
        except Exception as e:
            return {
                "content": f"I apologize, but I encountered an error: {str(e)}. Please try again.",
                "error": str(e),
                "model": self.model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "response_time_ms": int((time.time() - start_time) * 1000),
            }
    
    def generate_quiz(
        self,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 5,
        context: Optional[str] = None,
        conversation_context: Optional[str] = None
    ) -> dict:
        """
        Generate a quiz on a specific topic.

        Args:
            topic: The mathematical topic for the quiz
            difficulty: easy, medium, or hard
            num_questions: Number of questions to generate
            context: Optional RAG context
            conversation_context: Optional conversation history to base questions on

        Returns:
            Quiz data dict or error
        """
        # Build conversation context section if provided
        conversation_section = ""
        if conversation_context:
            conversation_section = f"""
CONVERSATION HISTORY (base your questions on what was actually discussed):
{conversation_context}

IMPORTANT: Generate questions that directly test understanding of the specific concepts, examples, and problems discussed in the conversation above. Questions should feel like a natural follow-up to what the student was learning.
"""

        prompt = f"""Generate a {num_questions}-question multiple choice quiz on {topic} ({difficulty} difficulty).
{conversation_section}
Format: JSON only, no other text.
{{
  "type": "quiz",
  "title": "Title",
  "topic": "{topic}",
  "questions": [
    {{
      "id": 1,
      "question": "Question text with $LaTeX$ if needed",
      "type": "multiple_choice",
      "options": ["A. opt1", "B. opt2", "C. opt3", "D. opt4"],
      "correct_answer": "A"
    }}
  ]
}}

Rules: 4 options per question (A/B/C/D), use $...$ for math. Keep explanations short or omit."""

        messages = [{"role": "user", "content": prompt}]
        
        response = self.chat(
            messages=messages,
            rag_context=context,
            temperature=0.8,
            max_tokens=4096
        )
        
        return response
    
    def evaluate_answer(
        self,
        question: dict,
        user_answer: str,
        context: Optional[str] = None
    ) -> dict:
        """
        Evaluate a user's answer to a question.

        Args:
            question: The question dict
            user_answer: User's submitted answer
            context: Optional RAG context

        Returns:
            Evaluation with correctness, explanation, and feedback
        """
        prompt = f"""Evaluate this student's answer:

QUESTION: {question.get('question', '')}
CORRECT ANSWER: {question.get('correct_answer', '')}
STUDENT'S ANSWER: {user_answer}

Respond with JSON:
{{
    "is_correct": true/false,
    "feedback": "Personalized feedback for the student",
    "explanation": "Detailed explanation of the correct answer",
    "partial_credit": 0.0 to 1.0 (if applicable)
}}"""

        messages = [{"role": "user", "content": prompt}]

        return self.chat(
            messages=messages,
            rag_context=context,
            temperature=0.3,
            max_tokens=1024
        )

    def chat_with_image(
        self,
        prompt: str,
        image_base64: str,
        image_media_type: str = "image/jpeg",
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> dict:
        """
        Send a chat completion request with an image (multimodal).

        Args:
            prompt: Text prompt describing what to do with the image
            image_base64: Base64 encoded image data
            image_media_type: MIME type of the image (e.g., image/jpeg, image/png)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Dict with response content and metadata
        """
        start_time = time.time()

        # Build multimodal message with image
        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_media_type};base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }

        # System message for image analysis context
        system_message = {
            "role": "system",
            "content": """You are Dr. Turing, an expert AI mathematics tutor. You are analyzing an image uploaded by a student.

Your tasks:
1. Describe what you see in the image clearly
2. If it contains mathematical content (equations, graphs, problems, diagrams):
   - Identify and transcribe any mathematical notation using LaTeX
   - Explain the mathematical concepts shown
   - Offer to help solve problems or answer questions about the content
3. If it's a handwritten solution or work:
   - Check for errors and provide feedback
   - Suggest improvements or corrections
4. Always be encouraging and educational in your response

Use LaTeX notation for math: $inline$ or $$display$$"""
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[system_message, user_message],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "response_time_ms": response_time_ms,
                "finish_reason": response.choices[0].finish_reason,
            }

        except Exception as e:
            return {
                "content": f"I apologize, but I encountered an error analyzing the image: {str(e)}. Please try again or describe the content to me.",
                "error": str(e),
                "model": self.model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "response_time_ms": int((time.time() - start_time) * 1000),
            }


# Singleton instance
groq_service = GroqService()

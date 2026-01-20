import { useState, useEffect, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import Header from './components/Header'
import ChatPanel from './components/ChatPanel'
import WorkspacePanel from './components/WorkspacePanel'
import './styles/App.css'

const API_BASE = '/api'

function App() {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [quiz, setQuiz] = useState(null)
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [currentTopic, setCurrentTopic] = useState('Mathematics')

  // Initialize session on mount
  useEffect(() => {
    initSession()
  }, [])

  const initSession = async () => {
    try {
      const response = await fetch(`${API_BASE}/chat/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: 'Mathematics' }),
      })
      
      if (response.ok) {
        const data = await response.json()
        setSessionId(data.session_id)
        
        // Add welcome message
        setMessages([{
          id: uuidv4(),
          role: 'assistant',
          content: "Welcome! I'm Dr. Turing, your AI mathematics tutor. I specialize in Oxford Mathematics curriculum, from linear algebra to analysis and beyond.\n\nHow can I help you today? You can:\n- Ask me to explain any mathematical concept\n- Request practice problems\n- Ask me to generate a quiz to test your understanding\n\nWhat would you like to explore?",
          timestamp: new Date(),
        }])
      }
    } catch (error) {
      console.error('Failed to initialize session:', error)
      // Generate local session ID as fallback
      setSessionId(uuidv4())
      setMessages([{
        id: uuidv4(),
        role: 'assistant',
        content: "Welcome! I'm Dr. Turing, your AI mathematics tutor. (Note: Running in offline mode)\n\nHow can I help you today?",
        timestamp: new Date(),
      }])
    }
  }

  const sendMessage = useCallback(async (content) => {
    if (!content.trim() || !sessionId) return

    // Add user message
    const userMessage = {
      id: uuidv4(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await fetch(`${API_BASE}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: content.trim(),
        }),
      })

      if (response.ok) {
        const data = await response.json()
        
        // Add AI response
        const aiMessage = {
          id: uuidv4(),
          role: 'assistant',
          content: data.content,
          timestamp: new Date(),
          tokensUsed: data.tokens_used,
        }
        setMessages(prev => [...prev, aiMessage])

        // Check if response contains a quiz
        if (data.quiz) {
          setQuiz(data.quiz)
          setIsWorkspaceOpen(true)
        }
      } else {
        throw new Error('Failed to get response')
      }
    } catch (error) {
      console.error('Error sending message:', error)
      setMessages(prev => [...prev, {
        id: uuidv4(),
        role: 'assistant',
        content: "I apologize, but I'm having trouble connecting to the server. Please try again.",
        timestamp: new Date(),
        isError: true,
      }])
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  const generateQuiz = useCallback(async (topic, difficulty = 'medium', numQuestions = 5) => {
    if (!sessionId) return

    setIsLoading(true)
    
    // Add message indicating quiz generation
    setMessages(prev => [...prev, {
      id: uuidv4(),
      role: 'assistant',
      content: `Generating a ${difficulty} quiz on ${topic}...`,
      timestamp: new Date(),
      isSystem: true,
    }])

    try {
      const response = await fetch(`${API_BASE}/quiz/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          topic,
          difficulty,
          num_questions: numQuestions,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setQuiz({
          id: data.quiz_id,
          title: data.title,
          topic: data.topic,
          questions: data.questions,
          totalQuestions: data.total_questions,
        })
        setIsWorkspaceOpen(true)
        setCurrentTopic(topic)

        // Update the system message
        setMessages(prev => {
          const updated = [...prev]
          const lastIdx = updated.length - 1
          if (updated[lastIdx]?.isSystem) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: `I've prepared a ${difficulty} quiz on ${topic} with ${data.total_questions} questions. Take your time, and feel free to ask for hints if you get stuck!`,
              isSystem: false,
            }
          }
          return updated
        })
      } else {
        throw new Error('Failed to generate quiz')
      }
    } catch (error) {
      console.error('Error generating quiz:', error)
      setMessages(prev => {
        const updated = [...prev]
        const lastIdx = updated.length - 1
        if (updated[lastIdx]?.isSystem) {
          updated[lastIdx] = {
            ...updated[lastIdx],
            content: "I apologize, but I couldn't generate the quiz. Please try again.",
            isSystem: false,
            isError: true,
          }
        }
        return updated
      })
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  const submitQuiz = useCallback(async (answers, timeTaken) => {
    if (!quiz?.id || !sessionId) return null

    try {
      const response = await fetch(`${API_BASE}/quiz/${quiz.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers,
          time_taken_seconds: timeTaken,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        
        // Add result message to chat
        const resultMessage = {
          id: uuidv4(),
          role: 'assistant',
          content: `Quiz completed! You scored **${data.percentage}%** (${data.correct_count}/${data.total_questions} correct).\n\n${
            data.percentage >= 80 
              ? "Excellent work! You've demonstrated strong understanding of this topic."
              : data.percentage >= 60
              ? "Good effort! Let's review the questions you missed to strengthen your understanding."
              : "This topic needs more practice. Let's go through the concepts again - which question would you like me to explain?"
          }`,
          timestamp: new Date(),
        }
        setMessages(prev => [...prev, resultMessage])
        
        return data
      }
    } catch (error) {
      console.error('Error submitting quiz:', error)
    }
    return null
  }, [quiz, sessionId])

  const getHint = useCallback(async (questionId) => {
    if (!quiz?.id) return null

    try {
      const response = await fetch(`${API_BASE}/quiz/${quiz.id}/hint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_id: questionId }),
      })

      if (response.ok) {
        const data = await response.json()
        return data.hint
      }
    } catch (error) {
      console.error('Error getting hint:', error)
    }
    return null
  }, [quiz])

  const closeQuiz = useCallback(() => {
    setQuiz(null)
    setIsWorkspaceOpen(false)
  }, [])

  const toggleWorkspace = useCallback(() => {
    setIsWorkspaceOpen(prev => !prev)
  }, [])

  return (
    <div className="app">
      <Header 
        topic={currentTopic}
        onToggleWorkspace={toggleWorkspace}
        isWorkspaceOpen={isWorkspaceOpen}
        hasQuiz={!!quiz}
      />
      
      <main className={`main-content ${isWorkspaceOpen ? 'workspace-open' : ''}`}>
        <ChatPanel
          messages={messages}
          onSendMessage={sendMessage}
          onGenerateQuiz={generateQuiz}
          isLoading={isLoading}
          isExpanded={!isWorkspaceOpen}
        />
        
        {isWorkspaceOpen && (
          <WorkspacePanel
            quiz={quiz}
            onClose={closeQuiz}
            onSubmit={submitQuiz}
            onGetHint={getHint}
          />
        )}
      </main>
    </div>
  )
}

export default App

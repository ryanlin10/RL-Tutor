import { useState, useEffect, useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import Header from './components/Header'
import ChatPanel from './components/ChatPanel'
import WorkspacePanel from './components/WorkspacePanel'
import './styles/App.css'

// In production, use same origin. In dev, Vite proxy handles it.
const API_BASE = import.meta.env.VITE_API_URL || '/api'

function App() {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [quiz, setQuiz] = useState(null)
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [currentTopic, setCurrentTopic] = useState('Mathematics')
  const [fileContext, setFileContext] = useState([]) // Stores uploaded file contexts
  const [reviewMode, setReviewMode] = useState(false) // For reviewing completed quizzes

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
      console.log('Sending message to:', `${API_BASE}/chat/message`)
      const response = await fetch(`${API_BASE}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: content.trim(),
        }),
      })

      console.log('Response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('API error response:', errorText)
        throw new Error(`Server error: ${response.status}`)
      }

      const data = await response.json()
      console.log('Response data:', data)
      
      // Add AI response
      const aiMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: data.content || 'No response received',
        timestamp: new Date(),
        tokensUsed: data.tokens_used,
      }
      setMessages(prev => [...prev, aiMessage])

      // Check if response contains a quiz
      if (data.quiz) {
        setQuiz(data.quiz)
        setIsWorkspaceOpen(true)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      setMessages(prev => [...prev, {
        id: uuidv4(),
        role: 'assistant',
        content: `I apologize, but I'm having trouble connecting to the server. Error: ${error.message}. Please check the console for details.`,
        timestamp: new Date(),
        isError: true,
      }])
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  const generateQuiz = useCallback(async (topic = null, difficulty = 'medium', numQuestions = 5) => {
    if (!sessionId) return

    setIsLoading(true)
    setReviewMode(false)

    // If no topic specified, generate based on conversation context
    let quizTopic = topic
    if (!quizTopic) {
      // Extract topic from recent conversation
      const recentMessages = messages.slice(-10)
      const conversationContext = recentMessages
        .map(m => m.content)
        .join(' ')
        .slice(0, 2000)

      quizTopic = 'topics discussed in our conversation'
    }

    // Add message indicating quiz generation
    setMessages(prev => [...prev, {
      id: uuidv4(),
      role: 'assistant',
      content: topic
        ? `Generating a ${difficulty} quiz on ${topic}...`
        : 'Generating a quiz based on what we\'ve discussed...',
      timestamp: new Date(),
      isSystem: true,
    }])

    try {
      const response = await fetch(`${API_BASE}/quiz/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          topic: topic || 'conversation context',
          difficulty,
          num_questions: numQuestions,
          context_based: !topic, // Flag to indicate context-based generation
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
        setCurrentTopic(data.topic || quizTopic)

        // Update the system message
        setMessages(prev => {
          const updated = [...prev]
          const lastIdx = updated.length - 1
          if (updated[lastIdx]?.isSystem) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: `I've prepared a quiz on **${data.topic || quizTopic}** with ${data.total_questions} questions. Take your time, and feel free to ask for hints if you get stuck!`,
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
  }, [sessionId, messages])

  const submitQuiz = useCallback(async (answers, timeTaken) => {
    if (!quiz?.id || !sessionId) {
      console.error('Cannot submit quiz: missing quiz.id or sessionId', { quizId: quiz?.id, sessionId })
      return null
    }

    console.log('Submitting quiz:', { quizId: quiz.id, answers, timeTaken })

    try {
      const response = await fetch(`${API_BASE}/quiz/${quiz.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers,
          time_taken_seconds: timeTaken,
        }),
      })

      console.log('Quiz submit response status:', response.status)

      if (response.ok) {
        const data = await response.json()
        console.log('Quiz submit response data:', data)

        // Store full quiz result with questions for later review
        const fullQuizResult = {
          ...data,
          quiz: {
            id: quiz.id,
            title: quiz.title,
            topic: quiz.topic,
            questions: quiz.questions,
          }
        }

        // Add result message to chat with quiz result attached for expand functionality
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
          quizResult: fullQuizResult, // Attach quiz result for review button
          hasQuizResult: true,
        }
        setMessages(prev => [...prev, resultMessage])

        return data
      } else {
        const errorText = await response.text()
        console.error('Quiz submit failed:', response.status, errorText)
      }
    } catch (error) {
      console.error('Error submitting quiz:', error)
    }
    return null
  }, [quiz, sessionId])

  // Upload file handler for images and PDFs
  const uploadFile = useCallback(async (file) => {
    if (!sessionId) return

    const isImage = file.type.startsWith('image/')
    const isPDF = file.type === 'application/pdf'

    if (!isImage && !isPDF) {
      alert('Please upload an image or PDF file.')
      return
    }

    // Create a preview for the message
    let preview = null
    if (isImage) {
      preview = URL.createObjectURL(file)
    }

    // Add a user message showing the file upload
    const uploadMessage = {
      id: uuidv4(),
      role: 'user',
      content: `[Uploaded: ${file.name}]`,
      timestamp: new Date(),
      attachment: {
        type: isImage ? 'image' : 'pdf',
        name: file.name,
        preview: preview,
      }
    }
    setMessages(prev => [...prev, uploadMessage])
    setIsLoading(true)

    try {
      // Convert file to base64
      const base64 = await fileToBase64(file)

      // Send to backend for processing
      const response = await fetch(`${API_BASE}/chat/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          file_name: file.name,
          file_type: file.type,
          file_data: base64,
          is_image: isImage,
        }),
      })

      console.log('Upload response status:', response.status)

      if (response.ok) {
        const data = await response.json()
        console.log('Upload response data:', data)

        // Store file context for future messages
        setFileContext(prev => [...prev, {
          id: data.context_id,
          name: file.name,
          type: isImage ? 'image' : 'pdf',
          extractedText: data.extracted_text,
        }])

        // Add AI response about the file
        const aiMessage = {
          id: uuidv4(),
          role: 'assistant',
          content: data.content || `I've analyzed the ${isImage ? 'image' : 'PDF'} you uploaded. ${data.summary || 'Feel free to ask me questions about it!'}`,
          timestamp: new Date(),
        }
        setMessages(prev => [...prev, aiMessage])
      } else {
        const errorData = await response.text()
        console.error('Upload failed:', response.status, errorData)
        throw new Error(`Failed to process file: ${errorData}`)
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      setMessages(prev => [...prev, {
        id: uuidv4(),
        role: 'assistant',
        content: `I apologize, but I couldn't process the file. Error: ${error.message}`,
        timestamp: new Date(),
        isError: true,
      }])
    } finally {
      setIsLoading(false)
    }
  }, [sessionId])

  // Helper function to convert file to base64
  const fileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.readAsDataURL(file)
      reader.onload = () => {
        const base64 = reader.result.split(',')[1]
        resolve(base64)
      }
      reader.onerror = (error) => reject(error)
    })
  }

  // Expand quiz for review
  const expandQuiz = useCallback((quizResult) => {
    if (!quizResult || !quizResult.quiz) return

    // Set the quiz with results for review mode
    setQuiz({
      id: quizResult.quiz.id,
      title: quizResult.quiz.title,
      topic: quizResult.quiz.topic,
      questions: quizResult.quiz.questions,
      totalQuestions: quizResult.total_questions,
    })
    setReviewMode(true)
    setIsWorkspaceOpen(true)

    // Pass the results to WorkspacePanel for display
    // This will be handled by passing reviewResults prop
  }, [])

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
    setReviewMode(false)
  }, [])

  const toggleWorkspace = useCallback(() => {
    setIsWorkspaceOpen(prev => !prev)
  }, [])

  // Find the most recent quiz result for review mode
  const currentQuizResult = reviewMode
    ? messages.findLast(m => m.quizResult?.quiz?.id === quiz?.id)?.quizResult
    : null

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
          onUploadFile={uploadFile}
          onExpandQuiz={expandQuiz}
          isLoading={isLoading}
          isExpanded={!isWorkspaceOpen}
        />

        {isWorkspaceOpen && (
          <WorkspacePanel
            quiz={quiz}
            onClose={closeQuiz}
            onSubmit={submitQuiz}
            onGetHint={getHint}
            reviewMode={reviewMode}
            reviewResults={currentQuizResult}
          />
        )}
      </main>
    </div>
  )
}

export default App

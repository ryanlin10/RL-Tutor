import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import './ChatPanel.css'

function ChatPanel({ messages, onSendMessage, onGenerateQuiz, isLoading, isExpanded }) {
  const [input, setInput] = useState('')
  const [showQuickActions, setShowQuickActions] = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`
    }
  }, [input])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !isLoading) {
      onSendMessage(input)
      setInput('')
      setShowQuickActions(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleQuickAction = (action) => {
    setShowQuickActions(false)
    
    switch (action) {
      case 'quiz-linear-algebra':
        onGenerateQuiz('Linear Algebra Basics', 'easy', 2)
        break
      case 'quiz-calculus':
        onGenerateQuiz('Derivatives', 'easy', 2)
        break
      case 'quiz-analysis':
        onGenerateQuiz('Algebra', 'easy', 2)
        break
      case 'explain':
        setInput('Can you explain ')
        textareaRef.current?.focus()
        break
      default:
        break
    }
  }

  return (
    <div className={`chat-panel ${isExpanded ? 'expanded' : ''}`}>
      <div className="chat-header">
        <div className="tutor-info">
          <div className="tutor-avatar">
            <span>DT</span>
          </div>
          <div className="tutor-details">
            <h3>Dr. Turing</h3>
            <span className="tutor-status">
              <span className="status-dot"></span>
              AI Tutor
            </span>
          </div>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((message) => (
          <div 
            key={message.id} 
            className={`message ${message.role} ${message.isError ? 'error' : ''}`}
          >
            {message.role === 'assistant' && (
              <div className="message-avatar">
                <span>DT</span>
              </div>
            )}
            <div className="message-content">
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {message.content}
              </ReactMarkdown>
              <span className="message-time">
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="message assistant loading">
            <div className="message-avatar">
              <span>DT</span>
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        {showQuickActions && (
          <div className="quick-actions">
            <button onClick={() => handleQuickAction('quiz-linear-algebra')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
              Quick Quiz
            </button>
            <button onClick={() => handleQuickAction('quiz-calculus')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
              Derivatives
            </button>
            <button onClick={() => handleQuickAction('quiz-analysis')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
              Algebra
            </button>
            <button onClick={() => handleQuickAction('explain')}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              Ask for Explanation
            </button>
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="chat-form">
          <button 
            type="button" 
            className="action-btn"
            onClick={() => setShowQuickActions(!showQuickActions)}
            title="Quick actions"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question or request a quiz..."
            rows={1}
            disabled={isLoading}
          />
          
          <button 
            type="submit" 
            className="send-btn"
            disabled={!input.trim() || isLoading}
            title="Send message"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatPanel

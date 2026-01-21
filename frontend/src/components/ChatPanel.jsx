import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { preprocessLatex } from '../utils/latexPreprocess'
import './ChatPanel.css'

function ChatPanel({
  messages,
  onSendMessage,
  onGenerateQuiz,
  onUploadFile,
  onExpandQuiz,
  isLoading,
  isExpanded
}) {
  const [input, setInput] = useState('')
  const [showQuickActions, setShowQuickActions] = useState(false)
  const [uploadingFile, setUploadingFile] = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

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
      case 'generate-quiz':
        // Generate quiz based on conversation context
        onGenerateQuiz()
        break
      case 'upload-files':
        // Trigger file input
        fileInputRef.current?.click()
        break
      default:
        break
    }
  }

  const handleFileSelect = async (e) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploadingFile(true)

    for (const file of files) {
      try {
        await onUploadFile(file)
      } catch (error) {
        console.error('Error uploading file:', error)
      }
    }

    setUploadingFile(false)
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
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
            className={`message ${message.role} ${message.isError ? 'error' : ''} ${message.hasQuizResult ? 'has-quiz-result' : ''}`}
          >
            {message.role === 'assistant' && (
              <div className="message-avatar">
                <span>DT</span>
              </div>
            )}
            <div className="message-content">
              {/* Show file attachment preview if present */}
              {message.attachment && (
                <div className="message-attachment">
                  {message.attachment.type === 'image' ? (
                    <img
                      src={message.attachment.preview}
                      alt={message.attachment.name}
                      className="attachment-preview"
                    />
                  ) : (
                    <div className="attachment-file">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                      </svg>
                      <span>{message.attachment.name}</span>
                    </div>
                  )}
                </div>
              )}
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {preprocessLatex(message.content)}
              </ReactMarkdown>
              {/* Show quiz result indicator and expand button if message has quiz result */}
              {message.quizResult && (
                <div className="quiz-result-summary">
                  <div className={`quiz-score-badge ${message.quizResult.percentage >= 70 ? 'good' : 'needs-work'}`}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 11l3 3L22 4"/>
                      <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
                    </svg>
                    <span>{message.quizResult.correct_count}/{message.quizResult.total_questions}</span>
                  </div>
                  <button
                    className="expand-quiz-btn"
                    onClick={() => onExpandQuiz(message.quizResult)}
                    title="Review quiz answers"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                    </svg>
                    Review Quiz
                  </button>
                </div>
              )}
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
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {showQuickActions && (
          <div className="quick-actions">
            <button onClick={() => handleQuickAction('generate-quiz')} disabled={isLoading}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 11l3 3L22 4"/>
                <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
              Generate Quiz
            </button>
            <button onClick={() => handleQuickAction('upload-files')} disabled={uploadingFile}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              {uploadingFile ? 'Uploading...' : 'Upload Files'}
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

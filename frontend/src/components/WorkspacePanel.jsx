import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { preprocessLatex } from '../utils/latexPreprocess'
import './WorkspacePanel.css'

function WorkspacePanel({ quiz, onClose, onSubmit, onGetHint, reviewMode = false, reviewResults = null }) {
  const [currentQuestion, setCurrentQuestion] = useState(0)
  const [answers, setAnswers] = useState({})
  const [hints, setHints] = useState({})
  const [loadingHint, setLoadingHint] = useState(false)
  const [results, setResults] = useState(null)
  const [startTime] = useState(Date.now())
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    // Reset state when quiz changes
    if (quiz) {
      setCurrentQuestion(0)
      setAnswers({})
      setHints({})
      // If in review mode with results, set them immediately
      if (reviewMode && reviewResults) {
        setResults(reviewResults)
        // Populate answers from review results
        const savedAnswers = {}
        reviewResults.results?.forEach(r => {
          savedAnswers[r.question_id] = r.user_answer
        })
        setAnswers(savedAnswers)
      } else {
        setResults(null)
      }
    }
  }, [quiz?.id, reviewMode, reviewResults])

  if (!quiz) {
    return (
      <div className="workspace-panel empty">
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
          </svg>
          <h3>No Active Quiz</h3>
          <p>Ask Dr. Turing to generate a quiz to test your knowledge.</p>
        </div>
      </div>
    )
  }

  const questions = quiz.questions || []
  const question = questions[currentQuestion]
  const totalQuestions = questions.length

  const handleSelectAnswer = (answer) => {
    if (results) return // Don't allow changes after submission
    // Ensure question.id is converted to string for consistent keys
    const questionId = String(question.id)
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer,
    }))
  }

  const handlePrev = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1)
    }
  }

  const handleNext = () => {
    if (currentQuestion < totalQuestions - 1) {
      setCurrentQuestion(prev => prev + 1)
    }
  }

  const handleHint = async () => {
    if (hints[question.id] || loadingHint) return
    
    setLoadingHint(true)
    const hint = await onGetHint(question.id)
    if (hint) {
      setHints(prev => ({
        ...prev,
        [question.id]: hint,
      }))
    }
    setLoadingHint(false)
  }

  const handleSubmit = async () => {
    if (isSubmitting) return

    setIsSubmitting(true)
    const timeTaken = Math.floor((Date.now() - startTime) / 1000)

    console.log('Submitting quiz with answers:', answers)
    console.log('Time taken:', timeTaken)

    try {
      const result = await onSubmit(answers, timeTaken)
      console.log('Quiz submission result:', result)
      if (result) {
        setResults(result)
      } else {
        console.error('No result returned from quiz submission')
      }
    } catch (error) {
      console.error('Error submitting quiz:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const getAnsweredCount = () => Object.keys(answers).length

  const getQuestionResult = (qId) => {
    if (!results) return null
    return results.results?.find(r => String(r.question_id) === String(qId))
  }

  const currentResult = getQuestionResult(question?.id)

  return (
    <div className="workspace-panel">
      <div className="workspace-header">
        <div className="workspace-title">
          <h2>{reviewMode ? 'Quiz Review' : quiz.title}</h2>
          <span className="workspace-topic">{quiz.topic}</span>
        </div>
        <button className="close-btn" onClick={onClose} title={reviewMode ? "Back to chat" : "Close quiz"}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {reviewMode ? (
              <>
                <path d="M19 12H5"/>
                <polyline points="12 19 5 12 12 5"/>
              </>
            ) : (
              <>
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </>
            )}
          </svg>
        </button>
      </div>

      <div className="progress-section">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${(getAnsweredCount() / totalQuestions) * 100}%` }}
          />
        </div>
        <span className="progress-text">
          Question {currentQuestion + 1} of {totalQuestions}
          {results && (
            <span className="score-badge">
              Score: {results.percentage}%
            </span>
          )}
        </span>
      </div>

      <div className="question-content">
        {question && (
          <>
            <div className={`question-card ${currentResult ? (currentResult.is_correct ? 'correct' : 'incorrect') : ''}`}>
              <div className="question-number">
                <span>Q{currentQuestion + 1}</span>
                {question.difficulty && (
                  <span className={`difficulty ${question.difficulty}`}>
                    {question.difficulty}
                  </span>
                )}
              </div>
              
              <div className="question-text">
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                >
                  {preprocessLatex(question.question)}
                </ReactMarkdown>
              </div>

              {/* Multiple Choice Options */}
              {question.options && question.options.length > 0 ? (
                <div className="options-list">
                  {question.options.map((option, idx) => {
                    const optionLetter = option.charAt(0)
                    const questionId = String(question.id)
                    const isSelected = answers[questionId] === optionLetter
                    const isCorrect = currentResult && currentResult.correct_answer === optionLetter
                    const isWrong = currentResult && isSelected && !currentResult.is_correct
                    
                    return (
                      <button
                        key={idx}
                        className={`option ${isSelected ? 'selected' : ''} ${isCorrect ? 'correct' : ''} ${isWrong ? 'wrong' : ''}`}
                        onClick={() => handleSelectAnswer(optionLetter)}
                        disabled={!!results}
                      >
                        <span className="option-marker">{optionLetter}</span>
                        <span className="option-text">
                          <ReactMarkdown
                            remarkPlugins={[remarkMath]}
                            rehypePlugins={[rehypeKatex]}
                          >
                            {preprocessLatex(option.substring(2).trim())}
                          </ReactMarkdown>
                        </span>
                        {isCorrect && (
                          <svg className="result-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M20 6L9 17l-5-5"/>
                          </svg>
                        )}
                        {isWrong && (
                          <svg className="result-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                          </svg>
                        )}
                      </button>
                    )
                  })}
                </div>
              ) : (
                /* Text Input for Short Answer Questions */
                <div className="text-answer-section">
                  <textarea
                    className={`text-answer-input ${currentResult ? (currentResult.is_correct ? 'correct' : 'incorrect') : ''}`}
                    placeholder="Type your answer here..."
                    value={answers[String(question.id)] || ''}
                    onChange={(e) => handleSelectAnswer(e.target.value)}
                    disabled={!!results}
                    rows={3}
                  />
                  {currentResult && (
                    <div className={`answer-feedback ${currentResult.is_correct ? 'correct' : 'incorrect'}`}>
                      <strong>{currentResult.is_correct ? 'Correct!' : 'Expected answer:'}</strong>
                      {!currentResult.is_correct && (
                        <span className="correct-answer">{currentResult.correct_answer}</span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {currentResult && currentResult.explanation && (
                <div className="explanation">
                  <strong>Explanation:</strong>
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {preprocessLatex(currentResult.explanation)}
                  </ReactMarkdown>
                </div>
              )}
            </div>

            {!results && (
              <button 
                className="hint-btn"
                onClick={handleHint}
                disabled={loadingHint || hints[question.id]}
              >
                {loadingHint ? (
                  <>Loading hint...</>
                ) : hints[question.id] ? (
                  <>Hint shown below</>
                ) : (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/>
                      <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    Get Hint
                  </>
                )}
              </button>
            )}

            {hints[question.id] && (
              <div className="hint-box">
                <strong>Hint:</strong> {hints[question.id]}
              </div>
            )}
          </>
        )}
      </div>

      <div className="workspace-footer">
        <div className="nav-buttons">
          <button 
            className="nav-btn"
            onClick={handlePrev}
            disabled={currentQuestion === 0}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
            Previous
          </button>
          
          <div className="question-dots">
            {questions.map((q, idx) => {
              const qId = String(q.id)
              const qResult = getQuestionResult(q.id)
              return (
                <button
                  key={q.id}
                  className={`dot ${idx === currentQuestion ? 'active' : ''} ${answers[qId] ? 'answered' : ''} ${qResult ? (qResult.is_correct ? 'correct' : 'incorrect') : ''}`}
                  onClick={() => setCurrentQuestion(idx)}
                  title={`Question ${idx + 1}`}
                />
              )
            })}
          </div>
          
          <button 
            className="nav-btn"
            onClick={handleNext}
            disabled={currentQuestion === totalQuestions - 1}
          >
            Next
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          </button>
        </div>

        {!results && !reviewMode && (
          <button
            className="submit-btn"
            onClick={handleSubmit}
            disabled={getAnsweredCount() < totalQuestions || isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : `Submit Quiz (${getAnsweredCount()}/${totalQuestions})`}
          </button>
        )}

        {(results || reviewMode) && (
          <div className="results-footer">
            <div className="results-summary">
              <span className={`score ${(results?.percentage || reviewResults?.percentage) >= 70 ? 'good' : 'needs-work'}`}>
                {results?.correct_count || reviewResults?.correct_count}/{results?.total_questions || reviewResults?.total_questions} correct
                ({Math.round(results?.percentage || reviewResults?.percentage)}%)
              </span>
            </div>
            <button className="exit-btn" onClick={onClose}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M19 12H5"/>
                <polyline points="12 19 5 12 12 5"/>
              </svg>
              {reviewMode ? 'Back to Chat' : 'Exit Quiz'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default WorkspacePanel

import './Header.css'

function Header({ topic, onToggleWorkspace, isWorkspaceOpen, hasQuiz }) {
  return (
    <header className="header">
      <div className="header-left">
        <div className="logo">
          <span className="logo-mark">L</span>
          <span className="logo-text">Learnr.ai</span>
        </div>
      </div>

      <div className="header-center">
        <div className="topic-badge">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
          <span>Current Subject:</span>
          <strong>{topic}</strong>
        </div>
      </div>

      <div className="header-right">
        {hasQuiz && (
          <button 
            className={`workspace-toggle ${isWorkspaceOpen ? 'active' : ''}`}
            onClick={onToggleWorkspace}
            aria-label={isWorkspaceOpen ? 'Close workspace' : 'Open workspace'}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="18" rx="1"/>
              <rect x="14" y="3" width="7" height="18" rx="1"/>
            </svg>
            <span>{isWorkspaceOpen ? 'Hide Quiz' : 'Show Quiz'}</span>
          </button>
        )}
        
        <div className="profile-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </div>
      </div>
    </header>
  )
}

export default Header

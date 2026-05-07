import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useState, useCallback } from 'react'
import Stage1 from './pages/Stage1'
import Stage2 from './pages/Stage2'
import Stage3 from './pages/Stage3'
import Stage4 from './pages/Stage4'

const NAV_ITEMS = [
  { step: 1, path: '/stage1', icon: 'gavel', label: 'Rule Extraction', sub: 'Upload & approve tender rules' },
  { step: 2, path: '/stage2', icon: 'description', label: 'Data Processing', sub: 'Upload bidder documents' },
  { step: 3, path: '/stage3', icon: 'rule', label: 'Eligibility Check', sub: 'Run AI evaluation' },
  { step: 4, path: '/stage4', icon: 'assignment_turned_in', label: 'Final Report', sub: 'View & export results' },
]

function Toast({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span className="material-symbols-outlined icon-filled" style={{ color: t.type === 'success' ? '#166534' : t.type === 'error' ? '#ba1a1a' : t.type === 'warning' ? '#92400e' : '#001e40', fontSize: 18 }}>
            {t.type === 'success' ? 'check_circle' : t.type === 'error' ? 'error' : t.type === 'warning' ? 'warning' : 'info'}
          </span>
          {t.message}
        </div>
      ))}
    </div>
  )
}

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [tenderApproved, setTenderApproved] = useState(false)
  const [evalDone, setEvalDone] = useState(false)
  const [toasts, setToasts] = useState([])
  const [reportId, setReportId] = useState(null)

  const toast = useCallback((message, type = 'info') => {
    const id = Date.now()
    setToasts(p => [...p, { id, message, type }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 4000)
  }, [])

  const currentStep = NAV_ITEMS.find(n => location.pathname.startsWith(n.path))?.step || 1
  const currentItem = NAV_ITEMS.find(n => location.pathname.startsWith(n.path))

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">
            <span className="material-symbols-outlined icon-filled" style={{ fontSize: 18, color: 'white' }}>account_balance</span>
          </div>
          <div>
            <div className="sidebar-brand-name">TenderIQ</div>
            <div className="sidebar-brand-sub">Officer Portal</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => {
            const isActive = location.pathname.startsWith(item.path)
            const isDone = (item.step === 1 && tenderApproved) || (item.step < currentStep) || (item.step === 3 && evalDone) || (item.step === 4 && evalDone)
            return (
              <div
                key={item.step}
                className={`nav-item ${isActive ? 'active' : ''} ${isDone && !isActive ? 'done' : ''}`}
                onClick={() => navigate(item.path)}
              >
                <div className="step-num">{isDone && !isActive ? '✓' : item.step}</div>
                <div>
                  <div>{item.label}</div>
                  <div style={{ fontSize: 10, fontWeight: 400, opacity: 0.75, marginTop: 1 }}>{item.sub}</div>
                </div>
              </div>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <button className="btn-new-eval" onClick={() => { setTenderApproved(false); setEvalDone(false); setReportId(null); navigate('/stage1'); }}>
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>add</span>
            New Evaluation
          </button>
          <div style={{ marginTop: 12, display: 'flex', gap: 16 }}>
            <a href="#" style={{ fontSize: 11, color: 'var(--secondary)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>help_outline</span>Support
            </a>
            <a href="#" style={{ fontSize: 11, color: 'var(--secondary)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>policy</span>Legal
            </a>
          </div>
        </div>
      </aside>

      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="topbar-title">{currentItem?.label || 'TenderIQ'}</div>
          <div className="topbar-sub">{currentItem?.sub || 'AI Bid Evaluation System'}</div>
        </div>
        <div className="topbar-actions">
          <button className="icon-btn"><span className="material-symbols-outlined">notifications</span></button>
          <button className="icon-btn"><span className="material-symbols-outlined">settings</span></button>
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--primary-container)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 13, fontWeight: 700 }}>O</div>
        </div>
      </header>

      {/* Main */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/stage1" replace />} />
          <Route path="/stage1" element={<Stage1 toast={toast} onApproved={() => { setTenderApproved(true); navigate('/stage2') }} />} />
          <Route path="/stage2" element={<Stage2 toast={toast} onNext={() => navigate('/stage3')} />} />
          <Route path="/stage3" element={<Stage3 toast={toast} onDone={(id) => { setEvalDone(true); setReportId(id); navigate('/stage4') }} />} />
          <Route path="/stage4" element={<Stage4 toast={toast} reportId={reportId} />} />
        </Routes>
      </main>

      <Toast toasts={toasts} />

      {/* FAB */}
      <div style={{ position: 'fixed', bottom: 28, right: 28, zIndex: 100 }}>
        <button
          style={{ width: 52, height: 52, borderRadius: '50%', background: 'var(--primary)', color: 'white', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 24px rgba(0,30,64,0.35)', transition: 'transform 0.15s' }}
          onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
          title="AI Assistant"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 26 }}>chat_bubble</span>
        </button>
      </div>
    </div>
  )
}

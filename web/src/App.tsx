import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, Link } from 'react-router'
import Calibration from './screens/Calibration'
import DiffPage from './screens/Diff'
import Finding from './screens/Finding'
import Label from './screens/Label'
import RunPage from './screens/Run'
import Runs from './screens/Runs'
import { STATIC } from './api'

type Theme = 'system' | 'light' | 'dark'

function readTheme(): Theme {
  try {
    const t = localStorage.getItem('examiner-theme')
    return t === 'light' || t === 'dark' ? t : 'system'
  } catch {
    return 'system'
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readTheme)
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('examiner-theme', theme)
    } catch {
      /* private mode: theme just isn't remembered */
    }
  }, [theme])
  const next: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }
  const label: Record<Theme, string> = { system: 'Theme: system', light: 'Theme: light', dark: 'Theme: dark' }
  return (
    <button className="btn btn-quiet small" onClick={() => setTheme(next[theme])} aria-label={`${label[theme]}. Change theme`}>
      {label[theme]}
    </button>
  )
}

function LocalOnly() {
  return (
    <div className="state">
      <h1>Labeling is local-only</h1>
      <p>This is a read-only snapshot. Clone the repo and run the dashboard to label transcripts.</p>
      <Link to="/calibration">See the calibration results</Link>
    </div>
  )
}

function NotFound() {
  return (
    <div className="state">
      <h1>Page not found</h1>
      <Link to="/">Back to runs</Link>
    </div>
  )
}

export default function App() {
  return (
    <>
      <a className="sr-only" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            Examiner <span>· Meridian Bank bot</span>
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Runs
            </NavLink>
            <NavLink to="/diff">Diff</NavLink>
            {!STATIC && <NavLink to="/label">Label</NavLink>}
            <NavLink to="/calibration">Calibration</NavLink>
          </nav>
          <ThemeToggle />
        </div>
        <div className="banner">
          <p>
            Not legal advice. Meridian Bank is fictional; scenarios test public Reg E rules and a made-up fee schedule.
            {STATIC && ' Read-only snapshot.'}
          </p>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Runs />} />
          <Route path="/runs/:runId" element={<RunPage />} />
          <Route path="/runs/:runId/results/:sampleId" element={<Finding />} />
          <Route path="/label" element={STATIC ? <LocalOnly /> : <Label />} />
          <Route path="/calibration" element={<Calibration />} />
          <Route path="/diff" element={<DiffPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  )
}

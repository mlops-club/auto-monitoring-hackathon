import { useEffect, useState } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import './App.css'

type HealthResponse = {
  app_name: string
  status: string
}

type ProbeResponse = {
  message: string
  request_path: string
}

function PlaceholderPage({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="placeholder-card">
      <p className="eyebrow">Placeholder Route</p>
      <h2>{title}</h2>
      <p>{detail}</p>
    </section>
  )
}

function App() {
  const location = useLocation()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [probeMessage, setProbeMessage] = useState<string>('Waiting for a backend probe.')
  const [isLoadingProbe, setIsLoadingProbe] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    const fetchHealth = async () => {
      try {
        const response = await fetch('/health')
        if (!response.ok) {
          throw new Error(`Health request failed with ${response.status}`)
        }

        const payload: HealthResponse = await response.json()
        if (isMounted) {
          setHealth(payload)
        }
      } catch (error) {
        if (isMounted) {
          setErrorMessage(
            error instanceof Error ? error.message : 'Unable to reach the backend health endpoint.',
          )
        }
      }
    }

    void fetchHealth()

    return () => {
      isMounted = false
    }
  }, [])

  const runProbe = async () => {
    setIsLoadingProbe(true)
    setErrorMessage(null)

    try {
      const response = await fetch('/api/ui-probe')
      if (!response.ok) {
        throw new Error(`Probe request failed with ${response.status}`)
      }

      const payload: ProbeResponse = await response.json()
      setProbeMessage(`${payload.message} (${payload.request_path})`)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to reach the backend probe endpoint.')
    } finally {
      setIsLoadingProbe(false)
    }
  }

  return (
    <main className="shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Cluster Stats UI</p>
          <h1>Frontend scaffold is ready for split and bundled serving.</h1>
          <p className="lede">
            This starter app is intentionally thin. It proves the Vite, React, and FastAPI
            integration points while the real backend endpoints are still in flight.
          </p>
        </div>

        <div className="status-grid">
          <article className="status-card">
            <span className="status-label">Current route</span>
            <strong>{location.pathname}</strong>
          </article>
          <article className="status-card">
            <span className="status-label">Backend health</span>
            <strong>{health ? `${health.status} (${health.app_name})` : 'Pending'}</strong>
          </article>
          <article className="status-card">
            <span className="status-label">Probe result</span>
            <strong>{probeMessage}</strong>
          </article>
        </div>
      </section>

      <section className="action-bar">
        <nav className="nav-links" aria-label="Primary">
          <Link to="/">Home</Link>
          <Link to="/clusters/demo">Cluster View</Link>
        </nav>

        <button className="probe-button" onClick={runProbe} disabled={isLoadingProbe}>
          {isLoadingProbe ? 'Probing backend...' : 'Call backend probe'}
        </button>
      </section>

      {errorMessage ? <p className="error-banner">{errorMessage}</p> : null}

      <Routes>
        <Route
          path="/"
          element={
            <section className="placeholder-card">
              <p className="eyebrow">Development modes</p>
              <h2>Use `./run serve:split` for HMR or `./run serve:bundled-watch` to rebuild into FastAPI.</h2>
              <p>
                Edit <code>frontend/src/App.tsx</code> or <code>frontend/src/App.css</code> to
                verify the frontend watcher behavior.
              </p>
            </section>
          }
        />
        <Route
          path="/clusters/:clusterName"
          element={
            <PlaceholderPage
              title="Cluster detail route"
              detail="This route exists now so backend SPA fallback and bundled serving can be tested before real cluster data is wired in."
            />
          }
        />
      </Routes>
    </main>
  )
}

export default App

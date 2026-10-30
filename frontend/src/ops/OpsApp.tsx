import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Button, ConfigProvider, Input } from 'antd'
import { Activity, GitBranch, LockKeyhole, Server, ShieldCheck } from 'lucide-react'
import { OPS_TOKEN_KEY, OpsApiError } from './api'
import RunsView from './RunsView'
import TraceView from './TraceView'
import WorkersView from './WorkersView'

type Route =
  | { name: 'runs' }
  | { name: 'trace'; runId: string }
  | { name: 'workers' }

function readRoute(): Route {
  const hash = window.location.hash || '#/runs'
  if (hash === '#/runs') return { name: 'runs' }
  if (hash === '#/workers') return { name: 'workers' }
  const match = hash.match(/^#\/trace\/(.+)$/)
  if (match) {
    try {
      const runId = decodeURIComponent(match[1])
      if (runId) return { name: 'trace', runId }
    } catch {
      // Invalid hashes return to the bounded default view.
    }
  }
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#/runs`)
  return { name: 'runs' }
}

function clearToken(): void {
  try {
    sessionStorage.removeItem(OPS_TOKEN_KEY)
  } catch {
    // The console can still use loopback access when storage is unavailable.
  }
}

export default function OpsApp() {
  const [route, setRoute] = useState<Route>(readRoute)
  const [authRequired, setAuthRequired] = useState(false)
  const [token, setToken] = useState('')
  const [authVersion, setAuthVersion] = useState(0)

  useEffect(() => {
    const onHashChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const title = useMemo(() => {
    if (route.name === 'trace') return '运行 Trace'
    return route.name === 'workers' ? 'Workers' : 'Runs'
  }, [route])

  function handleError(error: unknown): boolean {
    if (error instanceof OpsApiError && (error.status === 401 || error.status === 403)) {
      setAuthRequired(true)
      return true
    }
    return false
  }

  function retryWithCurrentAccess() {
    setAuthRequired(false)
    setToken('')
    setAuthVersion((value) => value + 1)
  }

  function submitToken(event: FormEvent) {
    event.preventDefault()
    if (!token) return
    try {
      sessionStorage.setItem(OPS_TOKEN_KEY, token)
    } catch {
      return
    }
    retryWithCurrentAccess()
  }

  function lockConsole() {
    clearToken()
    setToken('')
    setAuthRequired(true)
  }

  const view = route.name === 'trace'
    ? <TraceView runId={route.runId} onRequestError={handleError} />
    : route.name === 'workers'
      ? <WorkersView onRequestError={handleError} />
      : <RunsView onRequestError={handleError} />

  return (
    <ConfigProvider
      componentSize="small"
      theme={{
        token: {
          colorPrimary: '#175cd3',
          borderRadius: 6,
          colorBgLayout: '#f5f7fa',
          fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
      }}
    >
      <div className="ops-shell">
        <header className="ops-header">
          <a className="ops-brand" href="#/runs" aria-label="EduAgent Ops 首页">
            <span className="ops-brand-mark"><Activity size={18} aria-hidden="true" /></span>
            <span>
              <strong>EduAgent Ops</strong>
              <small>只读运行面板</small>
            </span>
          </a>
          <nav className="ops-nav" aria-label="Ops 导航">
            <a className={route.name === 'runs' ? 'active' : ''} href="#/runs">
              <Activity size={16} aria-hidden="true" /> Runs
            </a>
            <a className={route.name === 'trace' ? 'active' : ''} href={route.name === 'trace' ? `#/trace/${encodeURIComponent(route.runId)}` : '#/runs'}>
              <GitBranch size={16} aria-hidden="true" /> Trace
            </a>
            <a className={route.name === 'workers' ? 'active' : ''} href="#/workers">
              <Server size={16} aria-hidden="true" /> Workers
            </a>
          </nav>
          <Button
            className="ops-lock"
            type="text"
            icon={<LockKeyhole size={16} />}
            onClick={lockConsole}
            aria-label="锁定控制台并清除会话 token"
            title="锁定并清除 token"
          >
            锁定
          </Button>
        </header>

        <main className="ops-main">
          <div className="ops-page-heading">
            <div>
              <span className="ops-eyebrow">OPERATIONS</span>
              <h1>{title}</h1>
            </div>
            <span className="ops-readonly"><ShieldCheck size={15} aria-hidden="true" /> Read only</span>
          </div>
          <div key={`${route.name}-${route.name === 'trace' ? route.runId : ''}-${authVersion}`}>
            {authRequired ? (
              <section className="ops-auth" aria-labelledby="ops-auth-title">
                <ShieldCheck size={28} aria-hidden="true" />
                <h2 id="ops-auth-title">需要 Ops 访问凭证</h2>
                <p>Token 仅保存在当前浏览器标签页的会话存储中。</p>
                <form onSubmit={submitToken}>
                  <label htmlFor="ops-token">OPS API Token</label>
                  <Input.Password
                    id="ops-token"
                    autoComplete="current-password"
                    value={token}
                    onChange={(event) => setToken(event.target.value)}
                    placeholder="输入访问 token"
                    autoFocus
                  />
                  <div className="ops-auth-actions">
                    <Button type="primary" htmlType="submit" disabled={!token}>验证并重试</Button>
                    <Button htmlType="button" onClick={retryWithCurrentAccess}>本地无 Token 重试</Button>
                  </div>
                </form>
              </section>
            ) : view}
          </div>
        </main>
      </div>
    </ConfigProvider>
  )
}

import { useState } from 'react'
import { Home } from './Home'
import { LobbyScreen } from './LobbyScreen'
import { MatchScreen } from './MatchScreen'
import { errorText } from './text'
import { useLobby } from './useLobby'

function lobbyFromUrl(): string | null {
  return new URLSearchParams(location.search).get('lobby')?.toUpperCase() ?? null
}

export default function App() {
  const [session, setSession] = useState<{ code: string; name: string } | null>(null)
  const urlCode = lobbyFromUrl()

  if (!session) {
    return (
      <Home
        initialCode={urlCode}
        onEnter={(code, name) => {
          history.replaceState(null, '', `?lobby=${code}`)
          setSession({ code, name })
        }}
      />
    )
  }
  return (
    <Room
      code={session.code}
      name={session.name}
      onLeave={() => {
        history.replaceState(null, '', location.pathname)
        setSession(null)
      }}
    />
  )
}

function Room({ code, name, onLeave }: { code: string; name: string; onLeave: () => void }) {
  const conn = useLobby(code, name)

  if (conn.fatal) {
    return (
      <main className="center-screen">
        <div className="card narrow">
          <h2>{errorText[conn.fatal] ?? conn.fatal}</h2>
          <button className="btn primary" onClick={onLeave}>กลับหน้าแรก</button>
        </div>
      </main>
    )
  }
  if (!conn.state) {
    return <main className="center-screen"><p className="muted">กำลังเชื่อมต่อห้อง {code}…</p></main>
  }
  const match = conn.state.match
  return (
    <>
      {!conn.connected && <div className="banner">การเชื่อมต่อหลุด กำลังเชื่อมต่อใหม่…</div>}
      {conn.error && (
        <div className="toast" role="alert" onClick={conn.clearError}>
          {errorText[conn.error] ?? conn.error}
        </div>
      )}
      {match ? <MatchScreen conn={conn} state={conn.state} match={match} /> : <LobbyScreen conn={conn} state={conn.state} />}
    </>
  )
}

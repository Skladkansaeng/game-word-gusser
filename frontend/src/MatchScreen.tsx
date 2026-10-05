import { useEffect, useRef, useState } from 'react'
import { Avatar } from './LobbyScreen'
import { awardText } from './text'
import type { LobbyState, MatchView, PlayerInfo, RoundView } from './types'
import { useCountdown, type LobbyConnection } from './useLobby'

interface Props {
  conn: LobbyConnection
  state: LobbyState
  match: MatchView
}

export function MatchScreen({ conn, state, match }: Props) {
  const players = Object.fromEntries(state.players.map((p) => [p.id, p]))
  return (
    <main className="match">
      <div className="stage">
        {match.phase === 'podium' && match.podium ? (
          <PodiumView state={state} match={match} players={players} conn={conn} />
        ) : match.phase === 'paused' ? (
          <div className="card center-card">
            <h2>พักเกมชั่วคราว</h2>
            <p className="muted">ผู้เล่นที่ออนไลน์เหลือไม่ถึง 3 คน เกมจะเล่นต่อเองเมื่อมีคนกลับมา</p>
          </div>
        ) : match.round ? (
          <RoundStage conn={conn} match={match} round={match.round} players={players} you={state.you} />
        ) : null}
      </div>
      <Scoreboard state={state} match={match} players={players} />
    </main>
  )
}

// --- Round ---------------------------------------------------------------------

function RoundStage({ conn, match, round, players, you }: { conn: LobbyConnection; match: MatchView; round: RoundView; players: Record<string, PlayerInfo>; you: string }) {
  const online = match.settings.playMode === 'online'
  const roundLeft = useCountdown(round.roundDeadline, conn.clockOffset)
  const shownLeft = round.phase === 'guessing' ? round.frozenRemaining : roundLeft
  const name = (id: string | null) => (id ? players[id]?.name ?? '?' : '?')
  const inRound = round.role !== 'spectator'

  return (
    <div className="round">
      <div className="round-head">
        <span className="eyebrow">รอบ {round.cycle}/{match.settings.cycles} · ตาที่ {round.number}</span>
        {round.phase !== 'over' && shownLeft !== null && (
          <span className={`timer ${shownLeft < 10 ? 'low' : ''} ${round.phase === 'guessing' ? 'frozen' : ''}`}>
            {Math.ceil(shownLeft)}
          </span>
        )}
      </div>

      <div className="trio">
        <Seat player={players[round.guesserId]} label="คนทาย" you={you} highlight={round.phase === 'guessing'} />
        {round.giverIds.map((id) => (
          <Seat key={id} player={players[id]} label="คนใบ้" you={you}
            highlight={online && round.phase === 'clueing' && round.currentGiverId === id}
            deadline={online && round.phase === 'clueing' && round.currentGiverId === id ? round.clueDeadline : null}
            clockOffset={conn.clockOffset} total={match.settings.clueSeconds} />
        ))}
      </div>

      {round.phase === 'over' ? (
        <Reveal round={round} players={players} conn={conn} revealUntil={match.revealUntil} />
      ) : (
        <>
          <SecretWord round={round} holdToSee={!online} />

          {online ? (
            <ClueChain round={round} players={players} />
          ) : (
            <div className="card in-person-note">
              {round.role === 'clue_giver'
                ? `ผลัดกันพูดใบ้กับ ${name(round.giverIds.find((g) => g !== you) ?? null)} ทีละพยางค์ ห้ามใช้พยางค์ในคำตอบ`
                : `ฟัง ${name(round.giverIds[0])} กับ ${name(round.giverIds[1])} ใบ้ทีละพยางค์`}
            </div>
          )}

          {round.guesses.some((g) => !g.correct) && (
            <p className="wrong-guesses">
              ตอบผิดไปแล้ว: {round.guesses.filter((g) => !g.correct).map((g, i) => <s key={i}>{g.text ?? 'หมดเวลา'}</s>)}
            </p>
          )}

          <div className="controls">
            {round.phase === 'clueing' && (
              <>
                {online && round.role === 'clue_giver' && round.currentGiverId === you && <ClueInput conn={conn} />}
                {online && round.role === 'clue_giver' && round.currentGiverId !== you && (
                  <p className="muted">รอ {name(round.currentGiverId)} ใบ้พยางค์ต่อไป…</p>
                )}
                {inRound && (
                  <button className="btn buzz" onClick={() => conn.send({ type: 'buzz' })}>
                    BUZZ
                    <small>{round.role === 'guesser' ? 'รู้แล้ว! ขอตอบ' : `ให้ ${name(round.guesserId)} ตอบเลย`}</small>
                  </button>
                )}
                {!inRound && <p className="muted">คุณกำลังดู รอตาของคุณนะ</p>}
              </>
            )}
            {round.phase === 'guessing' && (
              <GuessBox conn={conn} round={round} isGuesser={round.role === 'guesser'} guesser={name(round.guesserId)} buzzer={name(round.buzzerId)} />
            )}
          </div>
        </>
      )}
    </div>
  )
}

function Seat({ player, label, you, highlight, deadline = null, clockOffset = 0, total = 1 }: { player?: PlayerInfo; label: string; you: string; highlight: boolean; deadline?: number | null; clockOffset?: number; total?: number }) {
  const left = useCountdown(deadline, clockOffset)
  if (!player) return null
  return (
    <div className={`seat ${highlight ? 'active' : ''}`}>
      <Avatar name={player.name} color={player.color} size={44} />
      <span className="seat-name">{player.name}{player.id === you && ' (คุณ)'}</span>
      <span className="seat-label">{label}</span>
      {left !== null && <span className="seat-bar" style={{ transform: `scaleX(${left / total})` }} />}
    </div>
  )
}

function SecretWord({ round, holdToSee }: { round: RoundView; holdToSee: boolean }) {
  const [held, setHeld] = useState(false)
  if (round.role !== 'clue_giver' || !round.word) {
    return (
      <div className="secret hidden-word">
        <span className="eyebrow">คำลับ</span>
        <span className="word">? ? ?</span>
      </div>
    )
  }
  if (holdToSee) {
    return (
      <button
        className="secret hold"
        onPointerDown={() => setHeld(true)}
        onPointerUp={() => setHeld(false)}
        onPointerLeave={() => setHeld(false)}
        onContextMenu={(e) => e.preventDefault()}
      >
        <span className="eyebrow">คำลับ (ระวังคนทายแอบดู)</span>
        <span className="word">{held ? round.word : 'กดค้างเพื่อดู'}</span>
      </button>
    )
  }
  return (
    <div className="secret">
      <span className="eyebrow">คำลับ ห้ามบอกใคร</span>
      <span className="word">{round.word}</span>
    </div>
  )
}

function ClueChain({ round, players }: { round: RoundView; players: Record<string, PlayerInfo> }) {
  return (
    <div className="chain" aria-live="polite">
      {round.clues.length === 0 ? (
        <span className="muted">ยังไม่มีคำใบ้…</span>
      ) : (
        round.clues.map((c, i) => (
          <span key={i} className="syllable" style={{ borderColor: players[c.playerId]?.color }}>{c.text}</span>
        ))
      )}
    </div>
  )
}

type SpeechRecognitionCtor = new () => {
  lang: string
  interimResults: boolean
  maxAlternatives: number
  onresult: (e: { results: { 0: { transcript: string } }[] }) => void
  onend: () => void
  onerror: () => void
  start: () => void
}

function speechRecognition(): SpeechRecognitionCtor | null {
  const w = window as unknown as Record<string, SpeechRecognitionCtor | undefined>
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

function ClueInput({ conn }: { conn: LobbyConnection }) {
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const Recognition = speechRecognition()
  const lang = conn.state?.match?.settings.wordLanguage === 'en' ? 'en-US' : 'th-TH'

  useEffect(() => inputRef.current?.focus(), [])

  const submit = (clue: string) => {
    if (!clue.trim()) return
    conn.send({ type: 'clue', text: clue })
    setText('')
    conn.clearSpokenClue()
  }

  const listen = () => {
    if (!Recognition) return
    const rec = new Recognition()
    rec.lang = lang
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.onresult = (e) => conn.send({ type: 'preview_spoken_clue', transcript: e.results[0][0].transcript })
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    conn.clearSpokenClue()
    setListening(true)
    rec.start()
  }

  return (
    <div className="clue-input">
      {conn.spokenClue ? (
        <div className="spoken">
          <span>ได้ยินว่า <strong>{conn.spokenClue}</strong></span>
          <button className="btn primary" onClick={() => submit(conn.spokenClue!)}>ส่ง</button>
          <button className="btn" onClick={listen}>พูดใหม่</button>
        </div>
      ) : (
        <div className="join-row">
          <input ref={inputRef} value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit(text)} placeholder="พิมพ์ 1 พยางค์" maxLength={20} />
          <button className="btn primary" onClick={() => submit(text)}>ใบ้</button>
          {Recognition && (
            <button className={`btn mic ${listening ? 'live' : ''}`} onClick={listen} disabled={listening} aria-label="พูดใบ้">
              {listening ? 'ฟังอยู่…' : '🎤'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function GuessBox({ conn, round, isGuesser, guesser, buzzer }: { conn: LobbyConnection; round: RoundView; isGuesser: boolean; guesser: string; buzzer: string }) {
  const [text, setText] = useState('')
  const left = useCountdown(round.guessDeadline, conn.clockOffset)
  const submit = () => {
    if (!text.trim()) return
    conn.send({ type: 'guess', text })
    setText('')
  }
  return (
    <div className="guess-box">
      <p><strong>{buzzer}</strong> กด Buzz! {left !== null && <span className="muted">· {Math.ceil(left)} วินาที</span>}</p>
      {isGuesser ? (
        <div className="join-row">
          <input autoFocus value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()} placeholder="คำตอบของคุณ" />
          <button className="btn primary" onClick={submit}>ตอบ</button>
        </div>
      ) : (
        <p className="muted">รอ {guesser} ตอบ…</p>
      )}
    </div>
  )
}

function Reveal({ round, players, conn, revealUntil }: { round: RoundView; players: Record<string, PlayerInfo>; conn: LobbyConnection; revealUntil: number | null }) {
  const left = useCountdown(revealUntil, conn.clockOffset)
  const headline = { correct: 'ทายถูก!', timeout: 'หมดเวลา', skipped: 'ข้ามตานี้ (มีคนหลุด)' }[round.outcome ?? 'timeout']
  return (
    <div className={`reveal ${round.outcome}`}>
      <p className="eyebrow">{headline}</p>
      <p className="reveal-word">{round.word}</p>
      {round.clues.length > 0 && <p className="muted">คำใบ้: {round.clues.map((c) => c.text).join(' · ')}</p>}
      <ul className="deltas">
        {Object.entries(round.points).filter(([, v]) => v !== 0).map(([id, v]) => (
          <li key={id} className={v > 0 ? 'up' : 'down'}>{players[id]?.name} {v > 0 ? `+${v}` : v}</li>
        ))}
      </ul>
      {left !== null && <p className="muted small">ตาต่อไปใน {Math.ceil(left)}…</p>}
    </div>
  )
}

// --- Scoreboard & Podium -------------------------------------------------------

function Scoreboard({ state, match, players }: { state: LobbyState; match: MatchView; players: Record<string, PlayerInfo> }) {
  const prev = useRef<Record<string, number>>({})
  const [flash, setFlash] = useState<Record<string, number>>({})

  useEffect(() => {
    const changes: Record<string, number> = {}
    for (const [id, score] of Object.entries(match.scores)) {
      const before = prev.current[id]
      if (before !== undefined && before !== score) changes[id] = score - before
    }
    prev.current = match.scores
    if (Object.keys(changes).length) {
      setFlash(changes)
      const t = setTimeout(() => setFlash({}), 1600)
      return () => clearTimeout(t)
    }
  }, [match.scores])

  const r = match.round
  const rows = Object.entries(match.scores).filter(([id]) => players[id]).sort((a, b) => b[1] - a[1])
  return (
    <aside className="card scoreboard">
      <h2>คะแนน</h2>
      <ol>
        {rows.map(([id, score]) => {
          const p = players[id]
          const role = r && r.phase !== 'over' ? (r.guesserId === id ? 'ทาย' : r.giverIds.includes(id) ? 'ใบ้' : null) : null
          return (
            <li key={id} className={`${p.away ? 'away' : ''} ${id === state.you ? 'me' : ''}`}>
              <Avatar name={p.name} color={p.color} size={28} />
              <span className="pname">{p.name}</span>
              {role && <span className="tag">{role}</span>}
              {p.away && <span className="tag ghost">หลุด</span>}
              {match.pending.includes(id) && <span className="tag ghost">รอบหน้า</span>}
              <span className="score">
                {score}
                {flash[id] !== undefined && <span className={`delta ${flash[id] > 0 ? 'up' : 'down'}`}>{flash[id] > 0 ? `+${flash[id]}` : flash[id]}</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </aside>
  )
}

function PodiumView({ state, match, players, conn }: { state: LobbyState; match: MatchView; players: Record<string, PlayerInfo>; conn: LobbyConnection }) {
  const podium = match.podium!
  const top = podium.ranking.slice(0, 3)
  const rest = podium.ranking.slice(3)
  // Visual order: 2nd, 1st, 3rd.
  const stands = [top[1], top[0], top[2]].filter(Boolean)
  return (
    <div className="podium">
      <h2>จบเกม!</h2>
      <div className="stands">
        {stands.map((row) => {
          const p = players[row.playerId]
          return (
            <div key={row.playerId} className={`stand rank-${row.rank}`}>
              {p && <Avatar name={p.name} color={p.color} size={56} />}
              <span className="pname">{p?.name ?? 'ผู้เล่นที่ออกไป'}</span>
              <span className="score">{row.score}</span>
              <div className="block">{row.rank}</div>
            </div>
          )
        })}
      </div>
      {rest.length > 0 && (
        <ol className="rest">
          {rest.map((row) => (
            <li key={row.playerId}><span>{row.rank}.</span> {players[row.playerId]?.name ?? 'ผู้เล่นที่ออกไป'} <strong>{row.score}</strong></li>
          ))}
        </ol>
      )}
      {podium.awards.length > 0 && (
        <div className="awards">
          {podium.awards.map((a) => (
            <div key={a.id} className="award card">
              <span className="eyebrow">{awardText[a.id].title}</span>
              <strong>{players[a.playerId]?.name}</strong>
              <span className="muted small">{awardText[a.id].detail(a.value)}</span>
            </div>
          ))}
        </div>
      )}
      {state.you === state.hostId ? (
        <button className="btn primary big" onClick={() => conn.send({ type: 'return_to_lobby' })}>กลับห้องเพื่อเล่นอีกครั้ง</button>
      ) : (
        <p className="muted">รอหัวห้องพากลับห้อง…</p>
      )}
    </div>
  )
}

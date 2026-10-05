import { useCallback, useEffect, useRef, useState } from 'react'
import type { ClientMessage, LobbyState } from './types'

const tokenKey = (code: string) => `partygame:token:${code}`

function readToken(code: string): string | null {
  try {
    return localStorage.getItem(tokenKey(code))
  } catch {
    return null
  }
}

function writeToken(code: string, token: string) {
  try {
    localStorage.setItem(tokenKey(code), token)
  } catch {
    // Without storage a refresh just joins as a new player.
  }
}

export function hasSavedSeat(code: string) {
  return readToken(code) !== null
}

export interface LobbyConnection {
  state: LobbyState | null
  error: string | null
  fatal: string | null
  spokenClue: string | null
  connected: boolean
  /** Difference between server clock and local clock, in seconds. */
  clockOffset: number
  send: (msg: ClientMessage) => void
  clearError: () => void
  clearSpokenClue: () => void
}

/** One WebSocket per Lobby; reconnects with the saved token so a dropped player keeps their seat. */
export function useLobby(code: string, name: string): LobbyConnection {
  const [state, setState] = useState<LobbyState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fatal, setFatal] = useState<string | null>(null)
  const [spokenClue, setSpokenClue] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [clockOffset, setClockOffset] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let stopped = false
    let retry: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/${code}`)
      wsRef.current = ws
      ws.onopen = () => {
        ws.send(JSON.stringify({ name, token: readToken(code) }))
      }
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.type === 'welcome') {
          writeToken(code, msg.token)
          setConnected(true)
        } else if (msg.type === 'state') {
          setState(msg.state)
          setClockOffset(msg.state.serverNow - Date.now() / 1000)
        } else if (msg.type === 'spoken_clue') {
          setSpokenClue(msg.syllable)
        } else if (msg.type === 'error') {
          if (['lobby_not_found', 'name_taken', 'lobby_full', 'kicked', 'invalid_name'].includes(msg.code)) {
            setFatal(msg.code)
            stopped = true
          } else {
            setError(msg.code)
          }
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (!stopped) retry = setTimeout(connect, 1000)
      }
    }

    connect()
    return () => {
      stopped = true
      clearTimeout(retry)
      wsRef.current?.close()
    }
  }, [code, name])

  const send = useCallback((msg: ClientMessage) => {
    setError(null)
    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
  }, [])

  return {
    state,
    error,
    fatal,
    spokenClue,
    connected,
    clockOffset,
    send,
    clearError: useCallback(() => setError(null), []),
    clearSpokenClue: useCallback(() => setSpokenClue(null), []),
  }
}

/** Seconds left until a server timestamp, ticking every 100 ms. */
export function useCountdown(deadline: number | null, clockOffset: number): number | null {
  const [, force] = useState(0)
  useEffect(() => {
    if (deadline === null) return
    const id = setInterval(() => force((n) => n + 1), 100)
    return () => clearInterval(id)
  }, [deadline])
  if (deadline === null) return null
  return Math.max(0, deadline - (Date.now() / 1000 + clockOffset))
}

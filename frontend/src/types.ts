// Mirrors Lobby.view() in backend/src/partygame/game.py. Terms follow CONTEXT.md.

export type PlayMode = 'online' | 'in_person'
export type WordLanguage = 'th' | 'en'
export type WordSource = 'bank' | 'mixed' | 'custom'
export type Role = 'guesser' | 'clue_giver' | 'spectator'

export interface Settings {
  playMode: PlayMode
  wordLanguage: WordLanguage
  wordSource: WordSource
  cycles: number
  roundSeconds: number
  clueSeconds: number
}

export interface PlayerInfo {
  id: string
  name: string
  color: string
  connected: boolean
  away: boolean
}

export interface Clue {
  playerId: string
  text: string
}

export interface GuessRecord {
  text: string | null
  correct: boolean
  buzzerId: string
}

export interface RoundView {
  number: number
  cycle: number
  role: Role
  guesserId: string
  giverIds: [string, string]
  currentGiverId: string
  phase: 'clueing' | 'guessing' | 'over'
  word: string | null
  clues: Clue[]
  roundDeadline: number | null
  frozenRemaining: number
  clueDeadline: number | null
  guessDeadline: number | null
  buzzerId: string | null
  guesses: GuessRecord[]
  outcome: 'correct' | 'timeout' | 'skipped' | null
  points: Record<string, number>
}

export interface Award {
  id: 'fastest_guess' | 'wild_buzzer' | 'best_clue_giver'
  playerId: string
  value: number
}

export interface Podium {
  ranking: { playerId: string; score: number; rank: number }[]
  awards: Award[]
}

export interface MatchView {
  phase: 'playing' | 'reveal' | 'paused' | 'podium'
  settings: Settings
  cycle: number
  participants: string[]
  pending: string[]
  scores: Record<string, number>
  revealUntil: number | null
  round: RoundView | null
  podium: Podium | null
}

export interface LobbyState {
  code: string
  you: string
  hostId: string
  serverNow: number
  settings: Settings
  players: PlayerInfo[]
  customWords: { count: number; mine: string[] }
  match: MatchView | null
}

export type ClientMessage =
  | { type: 'update_settings'; settings: Partial<Settings> }
  | { type: 'add_custom_word'; text: string }
  | { type: 'remove_custom_word'; text: string }
  | { type: 'kick'; playerId: string }
  | { type: 'start_match' }
  | { type: 'return_to_lobby' }
  | { type: 'clue'; text: string }
  | { type: 'preview_spoken_clue'; transcript: string }
  | { type: 'buzz' }
  | { type: 'guess'; text: string }

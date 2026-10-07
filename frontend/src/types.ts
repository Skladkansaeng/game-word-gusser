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
  /** Players in each Round: 1 Guesser plus the rest as Clue Givers. */
  roundPlayers: number
  roundSeconds: number
  clueSeconds: number
}

export interface PlayerInfo {
  id: string
  name: string
  color: string
  connected: boolean
  away: boolean
  /** Pressed Ready in the Lobby. Always true for the Host. */
  ready: boolean
}

export interface Clue {
  playerId: string
  text: string
}

export interface GuessRecord {
  text: string | null
  correct: boolean
  close: boolean
  matched: string[]
  buzzerId: string
}

export interface RoundView {
  number: number
  cycle: number
  role: Role
  guesserId: string
  giverIds: string[]
  currentGiverId: string
  phase: 'clueing' | 'guessing' | 'over'
  word: string | null
  clues: Clue[]
  roundDeadline: number | null
  frozenRemaining: number
  clueDeadline: number | null
  guessDeadline: number | null
  buzzerId: string | null
  /** When this viewer may buzz again after a wrong Buzz. */
  buzzLockedUntil: number | null
  /** What this viewer loses if their next Buzz ends in a wrong Guess; null for spectators. */
  nextBuzzPenalty: number | null
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

export interface CustomWordLength {
  id: string
  authorId: string
  chars: number
  syllables: number
}

/** One finished Round, kept in the Lobby across Matches. */
export interface HistoryEntry {
  /** Which Match in this Lobby, counting from 1. */
  match: number
  number: number
  cycle: number
  playMode: PlayMode
  word: string
  outcome: 'correct' | 'timeout' | 'skipped'
  guesserId: string
  giverIds: string[]
  clues: Clue[]
  guesses: GuessRecord[]
  points: Record<string, number>
  /** Names as they were when the Round ended, so kicked players still read right. */
  people: Record<string, { name: string; color: string }>
}

export interface LobbyState {
  code: string
  you: string
  hostId: string
  serverNow: number
  settings: Settings
  players: PlayerInfo[]
  customWords: {
    count: number
    byAuthor: Record<string, number>
    mine: string[]
    /** Host only: lengths of other players' words. The words themselves are never sent. */
    lengths: CustomWordLength[] | null
    /** Players who still need to add a word before a "custom" Match can start. */
    missing: string[]
  }
  match: MatchView | null
  history: HistoryEntry[]
}

export type ClientMessage =
  | { type: 'update_settings'; settings: Partial<Settings> }
  | { type: 'add_custom_word'; text: string }
  | { type: 'remove_custom_word'; text: string }
  | { type: 'remove_custom_word_by_id'; wordId: string }
  | { type: 'clear_custom_words'; playerId: string }
  | { type: 'kick'; playerId: string }
  | { type: 'set_ready'; ready: boolean }
  | { type: 'start_match' }
  | { type: 'return_to_lobby' }
  | { type: 'clue'; text: string }
  | { type: 'preview_spoken_clue'; transcript: string }
  | { type: 'buzz' }
  | { type: 'guess'; text: string }

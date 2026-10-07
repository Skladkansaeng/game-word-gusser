import { useEffect, useRef, useState } from 'react'
import type { HistoryEntry, LobbyState } from './types'

const outcomeText = { correct: 'ทายถูก', timeout: 'หมดเวลา', skipped: 'ข้าม' } as const
const outcomeEmoji = { correct: '✅', timeout: '⏰', skipped: '⏭️' } as const

const personName = (e: HistoryEntry, id: string | null) => (id ? e.people[id]?.name ?? '?' : '?')
const wrongGuesses = (e: HistoryEntry) => e.guesses.filter((g) => !g.correct).map((g) => g.text ?? 'หมดเวลาตอบ')

/** Button that opens the Lobby's History; hidden until a Round has finished. */
export function HistoryButton({ state, className = 'btn small' }: { state: LobbyState; className?: string }) {
  const [open, setOpen] = useState(false)
  if (state.history.length === 0) return null
  return (
    <>
      <button className={className} onClick={() => setOpen(true)}>ประวัติคำใบ้ ({state.history.length})</button>
      {open && <HistoryDialog state={state} onClose={() => setOpen(false)} />}
    </>
  )
}

function HistoryDialog({ state, onClose }: { state: LobbyState; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const matches = [...new Set(state.history.map((e) => e.match))]
  const [picked, setPicked] = useState(matches.at(-1)!)
  const [status, setStatus] = useState<string | null>(null)
  const entries = state.history.filter((e) => e.match === picked)
  const title = `ห้อง ${state.code} · เกมที่ ${matches.indexOf(picked) + 1}`

  useEffect(() => {
    ref.current?.showModal()
  }, [])

  const flash = (text: string) => {
    setStatus(text)
    setTimeout(() => setStatus(null), 2000)
  }

  const shareText = async () => {
    const text = historyText(title, entries)
    try {
      if (navigator.share) {
        await navigator.share({ text })
        return
      }
      await navigator.clipboard.writeText(text)
      flash('คัดลอกข้อความแล้ว')
    } catch (err) {
      if ((err as Error).name !== 'AbortError') flash('แชร์ไม่สำเร็จ')
    }
  }

  const shareImage = async () => {
    try {
      const blob = await historyImage(title, entries)
      const file = new File([blob], `history-${state.code}-${picked}.png`, { type: 'image/png' })
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file] })
        return
      }
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      flash('บันทึกรูปแล้ว')
    } catch (err) {
      if ((err as Error).name !== 'AbortError') flash('สร้างรูปไม่สำเร็จ')
    }
  }

  return (
    <dialog ref={ref} className="history" onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) ref.current.close() }}>
      <div className="history-inner">
        <header className="history-head">
          <h2>ประวัติคำใบ้</h2>
          <button className="link" onClick={() => ref.current?.close()}>ปิด</button>
        </header>
        {matches.length > 1 && (
          <div className="segmented">
            {matches.map((m, i) => (
              <button key={m} className={m === picked ? 'on' : ''} onClick={() => setPicked(m)}>เกมที่ {i + 1}</button>
            ))}
          </div>
        )}
        <ol className="history-list">
          {[...entries].reverse().map((e) => (
            <li key={e.number} className={`history-item ${e.outcome}`}>
              <div className="history-row">
                <span className="muted small">#{e.number}</span>
                <strong className="history-word">{e.word}</strong>
                <span className="tag">{outcomeText[e.outcome]}</span>
              </div>
              <p className="muted small">คนทาย {personName(e, e.guesserId)} · คนใบ้ {e.giverIds.map((id) => personName(e, id)).join(', ')}</p>
              {e.clues.length > 0 ? (
                <div className="history-clues">
                  {e.clues.map((c, i) => (
                    <span key={i} className="syllable" style={{ borderColor: e.people[c.playerId]?.color }}>{c.text}</span>
                  ))}
                </div>
              ) : (
                <p className="muted small">{e.playMode === 'in_person' ? 'ใบ้ด้วยปาก' : 'ยังไม่มีคำใบ้'}</p>
              )}
              {wrongGuesses(e).length > 0 && (
                <p className="wrong-guesses small">ตอบผิด: {wrongGuesses(e).map((g, i) => <s key={i}>{g}</s>)}</p>
              )}
            </li>
          ))}
        </ol>
        <div className="history-share">
          <button className="btn" onClick={shareText}>แชร์เป็นข้อความ</button>
          <button className="btn primary" onClick={shareImage}>แชร์เป็นรูป</button>
          {status && <p className="muted small history-status">{status}</p>}
        </div>
      </div>
    </dialog>
  )
}

function historyText(title: string, entries: HistoryEntry[]): string {
  const lines = [`ใบ้ทีละพยางค์ · ${title}`, '']
  for (const e of entries) {
    lines.push(`${e.number}. ${e.word} ${outcomeEmoji[e.outcome]} ${outcomeText[e.outcome]} (${personName(e, e.guesserId)} ทาย)`)
    if (e.clues.length > 0) lines.push(`   ใบ้: ${e.clues.map((c) => c.text).join(' · ')}`)
    else if (e.playMode === 'in_person') lines.push('   ใบ้ด้วยปาก')
    const wrong = wrongGuesses(e)
    if (wrong.length > 0) lines.push(`   ตอบผิด: ${wrong.join(', ')}`)
  }
  return lines.join('\n')
}

// --- Image -----------------------------------------------------------------------

// The shared picture always uses the light palette, so it looks the same wherever it lands.
const ink = '#1f1a17'
const muted = '#7a6e64'
const surface = '#fffdf8'
const bg = '#fbf4e8'
const outcomeColor = { correct: '#2f9e6b', timeout: '#7a6e64', skipped: '#7a6e64' } as const
const bad = '#d6453d'
const accent = '#ff5a36'

const W = 540
const PAD = 24
const CARD_PAD = 16
const HEAD_FONT = "500 26px Mitr, 'IBM Plex Sans Thai', sans-serif"
const WORD_FONT = "500 24px Mitr, 'IBM Plex Sans Thai', sans-serif"
const CHIP_FONT = "400 18px Mitr, 'IBM Plex Sans Thai', sans-serif"
const BODY_FONT = "400 14px 'IBM Plex Sans Thai', system-ui, sans-serif"
const BADGE_FONT = "600 13px 'IBM Plex Sans Thai', system-ui, sans-serif"

async function historyImage(title: string, entries: HistoryEntry[]): Promise<Blob> {
  await Promise.all([HEAD_FONT, WORD_FONT, CHIP_FONT, BODY_FONT, BADGE_FONT].map((f) => document.fonts.load(f, 'กขabc')))
  const scale = 2
  const measureCtx = document.createElement('canvas').getContext('2d')!
  const height = paint(measureCtx, title, entries, false)
  const canvas = document.createElement('canvas')
  canvas.width = W * scale
  canvas.height = height * scale
  const ctx = canvas.getContext('2d')!
  ctx.scale(scale, scale)
  paint(ctx, title, entries, true)
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('toBlob'))), 'image/png'))
}

/** Lays out (and, when `draw` is set, paints) the picture. Returns its height. */
function paint(ctx: CanvasRenderingContext2D, title: string, entries: HistoryEntry[], draw: boolean): number {
  ctx.textBaseline = 'top'
  let y = PAD
  ctx.font = HEAD_FONT
  if (draw) {
    ctx.fillStyle = accent
    ctx.fillText('ใบ้ทีละพยางค์', PAD, y)
  }
  y += 38
  ctx.font = BODY_FONT
  if (draw) {
    ctx.fillStyle = muted
    ctx.fillText(`${title} · ${entries.length} คำ`, PAD, y)
  }
  y += 32

  const inner = W - PAD * 2 - CARD_PAD * 2
  for (const e of entries) {
    const top = y
    const x0 = PAD + CARD_PAD
    let cy = top + CARD_PAD

    // Word line with the outcome badge on the right.
    const badge = outcomeText[e.outcome]
    ctx.font = BADGE_FONT
    const badgeW = ctx.measureText(badge).width + 16
    if (draw) {
      ctx.font = BODY_FONT
      ctx.fillStyle = muted
      ctx.fillText(`#${e.number}`, x0, cy + 8)
      ctx.font = WORD_FONT
      ctx.fillStyle = ink
      ctx.fillText(fit(ctx, e.word, inner - badgeW - 44), x0 + 36, cy)
      ctx.fillStyle = outcomeColor[e.outcome]
      roundRect(ctx, x0 + inner - badgeW, cy + 4, badgeW, 22, 11)
      ctx.fill()
      ctx.font = BADGE_FONT
      ctx.fillStyle = '#fff'
      ctx.fillText(badge, x0 + inner - badgeW + 8, cy + 8)
    }
    cy += 36

    ctx.font = BODY_FONT
    const who = `คนทาย ${personName(e, e.guesserId)} · คนใบ้ ${e.giverIds.map((id) => personName(e, id)).join(', ')}`
    if (draw) {
      ctx.fillStyle = muted
      ctx.fillText(fit(ctx, who, inner), x0, cy)
    }
    cy += 24

    if (e.clues.length > 0) {
      ctx.font = CHIP_FONT
      let cx = x0
      const chipH = 34
      for (const c of e.clues) {
        const w = ctx.measureText(c.text).width + 20
        if (cx + w > x0 + inner && cx > x0) {
          cx = x0
          cy += chipH + 6
        }
        if (draw) {
          ctx.fillStyle = bg
          roundRect(ctx, cx, cy, w, chipH, 8)
          ctx.fill()
          ctx.fillStyle = e.people[c.playerId]?.color ?? muted
          ctx.fillRect(cx + 4, cy + chipH - 4, w - 8, 3)
          ctx.fillStyle = ink
          ctx.fillText(c.text, cx + 10, cy + 5)
        }
        cx += w + 6
      }
      cy += chipH + 8
    } else {
      ctx.font = BODY_FONT
      if (draw) {
        ctx.fillStyle = muted
        ctx.fillText(e.playMode === 'in_person' ? 'ใบ้ด้วยปาก' : 'ยังไม่มีคำใบ้', x0, cy)
      }
      cy += 24
    }

    const wrong = wrongGuesses(e)
    if (wrong.length > 0) {
      ctx.font = BODY_FONT
      if (draw) {
        ctx.fillStyle = bad
        ctx.fillText(fit(ctx, `ตอบผิด: ${wrong.join(', ')}`, inner), x0, cy)
      }
      cy += 24
    }

    const bottom = cy + CARD_PAD - 6
    if (draw) {
      // Paint the card behind what was already drawn on it.
      ctx.save()
      ctx.globalCompositeOperation = 'destination-over'
      ctx.fillStyle = surface
      roundRect(ctx, PAD, top, W - PAD * 2, bottom - top, 16)
      ctx.fill()
      ctx.restore()
    }
    y = bottom + 12
  }
  const height = y + PAD - 12
  if (draw) {
    ctx.save()
    ctx.globalCompositeOperation = 'destination-over'
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, W, height)
    ctx.restore()
  }
  return height
}

/** Cuts text with an ellipsis so it fits in `width`. */
function fit(ctx: CanvasRenderingContext2D, text: string, width: number): string {
  if (ctx.measureText(text).width <= width) return text
  const chars = [...text]
  while (chars.length > 1 && ctx.measureText(chars.join('') + '…').width > width) chars.pop()
  return chars.join('') + '…'
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

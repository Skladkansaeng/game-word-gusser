import { QRCodeSVG } from 'qrcode.react'
import { useState } from 'react'
import type { LobbyState, Settings } from './types'
import type { LobbyConnection } from './useLobby'

export function LobbyScreen({ conn, state }: { conn: LobbyConnection; state: LobbyState }) {
  const isHost = state.you === state.hostId
  const link = `${location.origin}/?lobby=${state.code}`
  const online = state.players.filter((p) => p.connected).length
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard blocked; the code is still visible.
    }
  }

  return (
    <main className="lobby">
      <section className="card invite">
        <p className="eyebrow">รหัสห้อง</p>
        <p className="lobby-code">{state.code}</p>
        <div className="qr"><QRCodeSVG value={link} size={132} bgColor="transparent" fgColor="currentColor" /></div>
        <button className="btn small" onClick={copy}>{copied ? 'คัดลอกแล้ว' : 'คัดลอกลิงก์'}</button>
      </section>

      <section className="card players">
        <h2>ผู้เล่น <span className="muted">{state.players.length}/12</span></h2>
        <ul className="player-list">
          {state.players.map((p) => (
            <li key={p.id} className={p.connected ? '' : 'offline'}>
              <Avatar name={p.name} color={p.color} />
              <span className="pname">{p.name}{p.id === state.you && <em> (คุณ)</em>}</span>
              {p.id === state.hostId && <span className="tag">หัวห้อง</span>}
              {!p.connected && <span className="tag ghost">ออฟไลน์</span>}
              {isHost && p.id !== state.you && (
                <button className="link" onClick={() => conn.send({ type: 'kick', playerId: p.id })}>เชิญออก</button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <SettingsPanel settings={state.settings} editable={isHost} onChange={(s) => conn.send({ type: 'update_settings', settings: s })} />

      <CustomWords state={state} conn={conn} />

      <div className="start-bar">
        {isHost ? (
          <button className="btn primary big" disabled={online < 3} onClick={() => conn.send({ type: 'start_match' })}>
            {online < 3 ? `รอผู้เล่นอีก ${3 - online} คน` : 'เริ่มเกม'}
          </button>
        ) : (
          <p className="muted">รอหัวห้องกดเริ่มเกม…</p>
        )}
      </div>
    </main>
  )
}

export function Avatar({ name, color, size = 36 }: { name: string; color: string; size?: number }) {
  return (
    <span className="avatar" style={{ background: color, width: size, height: size, fontSize: size * 0.45 }}>
      {[...name][0]}
    </span>
  )
}

function SettingsPanel({ settings, editable, onChange }: { settings: Settings; editable: boolean; onChange: (s: Partial<Settings>) => void }) {
  return (
    <section className="card settings">
      <h2>ตั้งค่าเกม {!editable && <span className="muted small">(หัวห้องเป็นคนตั้ง)</span>}</h2>
      <fieldset disabled={!editable}>
        <Choice label="รูปแบบการเล่น" value={settings.playMode} onChange={(v) => onChange({ playMode: v })}
          options={[['online', 'ออนไลน์ (พิมพ์/พูดใบ้)'], ['in_person', 'เล่นในห้องเดียวกัน']]} />
        <Choice label="ภาษาของคำ" value={settings.wordLanguage} onChange={(v) => onChange({ wordLanguage: v })}
          options={[['th', 'ไทย'], ['en', 'English']]} />
        <Choice label="คำมาจาก" value={settings.wordSource} onChange={(v) => onChange({ wordSource: v })}
          options={[['bank', 'คลังคำ'], ['mixed', 'ผสม'], ['custom', 'คำของเพื่อน']]} />
        <Stepper label="จำนวนรอบ" hint="ทุกคนได้เป็นคนทายรอบละ 1 ครั้ง" value={settings.cycles} min={1} max={5}
          onChange={(v) => onChange({ cycles: v })} />
        <Stepper label="เวลาต่อตา (วินาที)" value={settings.roundSeconds} min={30} max={300} step={15}
          onChange={(v) => onChange({ roundSeconds: v })} />
        {settings.playMode === 'online' && (
          <Stepper label="เวลาต่อคำใบ้ (วินาที)" value={settings.clueSeconds} min={5} max={60} step={5}
            onChange={(v) => onChange({ clueSeconds: v })} />
        )}
      </fieldset>
    </section>
  )
}

function Choice<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="setting">
      <span className="setting-label">{label}</span>
      <div className="segmented">
        {options.map(([v, text]) => (
          <button key={v} className={v === value ? 'on' : ''} onClick={() => onChange(v)}>{text}</button>
        ))}
      </div>
    </div>
  )
}

function Stepper({ label, hint, value, min, max, step = 1, onChange }: { label: string; hint?: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void }) {
  return (
    <div className="setting">
      <span className="setting-label">{label}{hint && <small>{hint}</small>}</span>
      <div className="stepper">
        <button aria-label="ลด" onClick={() => onChange(Math.max(min, value - step))}>−</button>
        <span>{value}</span>
        <button aria-label="เพิ่ม" onClick={() => onChange(Math.min(max, value + step))}>+</button>
      </div>
    </div>
  )
}

function CustomWords({ state, conn }: { state: LobbyState; conn: LobbyConnection }) {
  const [text, setText] = useState('')
  const add = () => {
    if (!text.trim()) return
    conn.send({ type: 'add_custom_word', text })
    setText('')
  }
  return (
    <section className="card custom-words">
      <h2>คำของเพื่อน <span className="muted">{state.customWords.count} คำ</span></h2>
      <p className="muted small">เพิ่มคำลับของแก๊ง คนอื่นจะไม่เห็นว่าคุณใส่คำอะไร และคุณจะไม่ได้ทายคำของตัวเอง</p>
      <div className="join-row">
        <input value={text} maxLength={40} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()} placeholder="เช่น หมูเด้ง" />
        <button className="btn" onClick={add}>เพิ่ม</button>
      </div>
      {state.customWords.mine.length > 0 && (
        <ul className="chips">
          {state.customWords.mine.map((w) => (
            <li key={w}>
              {w}
              <button aria-label={`ลบ ${w}`} onClick={() => conn.send({ type: 'remove_custom_word', text: w })}>×</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

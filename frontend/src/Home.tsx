import { useState } from 'react'
import { hasSavedSeat } from './useLobby'

const NAME_KEY = 'partygame:name'

function savedName() {
  try {
    return localStorage.getItem(NAME_KEY) ?? ''
  } catch {
    return ''
  }
}

export function Home({ initialCode, onEnter }: { initialCode: string | null; onEnter: (code: string, name: string) => void }) {
  const [name, setName] = useState(savedName)
  const [code, setCode] = useState(initialCode ?? '')
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const enter = (lobbyCode: string) => {
    try {
      localStorage.setItem(NAME_KEY, name.trim())
    } catch {
      // Name just won't be prefilled next time.
    }
    onEnter(lobbyCode, name.trim())
  }

  const create = async () => {
    if (!name.trim()) return setProblem('ใส่ชื่อก่อนนะ')
    setBusy(true)
    try {
      const res = await fetch('/api/lobbies', { method: 'POST' })
      enter((await res.json()).code)
    } catch {
      setProblem('สร้างห้องไม่สำเร็จ ลองอีกครั้ง')
    } finally {
      setBusy(false)
    }
  }

  const join = async () => {
    const c = code.trim().toUpperCase()
    if (!c) return setProblem('ใส่รหัสห้อง')
    if (!name.trim() && !hasSavedSeat(c)) return setProblem('ใส่ชื่อก่อนนะ')
    setBusy(true)
    try {
      const res = await fetch(`/api/lobbies/${c}`)
      if (!res.ok) return setProblem('ไม่พบห้องนี้')
      enter(c)
    } catch {
      setProblem('เชื่อมต่อไม่สำเร็จ')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="home">
      <header className="home-hero">
        <p className="eyebrow">เกมปาร์ตี้ 3 คนขึ้นไป</p>
        <h1>
          ใบ้<span className="syl">ที</span><span className="syl">ละ</span><span className="syl">พยางค์</span>
        </h1>
        <p className="lede">
          คนใบ้สองคนผลัดกันต่อประโยคทีละพยางค์ คนทายต้องเดาให้ออกก่อนเวลาหมด
        </p>
      </header>

      <section className="card home-card">
        <label className="field">
          <span>ชื่อเล่น</span>
          <input value={name} maxLength={20} onChange={(e) => setName(e.target.value)} placeholder="เช่น ต้น" autoFocus />
        </label>

        {initialCode ? (
          <button className="btn primary big" disabled={busy} onClick={join}>เข้าห้อง {initialCode}</button>
        ) : (
          <>
            <button className="btn primary big" disabled={busy} onClick={create}>สร้างห้องใหม่</button>
            <div className="divider"><span>หรือเข้าห้องเพื่อน</span></div>
            <div className="join-row">
              <input
                className="code-input"
                value={code}
                maxLength={4}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && join()}
                placeholder="รหัส"
              />
              <button className="btn" disabled={busy} onClick={join}>เข้าห้อง</button>
            </div>
          </>
        )}
        {problem && <p className="problem">{problem}</p>}
      </section>
    </main>
  )
}

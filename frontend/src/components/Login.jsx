import { useState } from 'react'
import { api, setToken } from '../api'

export default function Login({ onLogin }) {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!pw || busy) return
    setBusy(true)
    setErr('')
    try {
      const { token } = await api.login(pw)
      setToken(token)
      onLogin()
    } catch (e) {
      setErr('비밀번호가 올바르지 않습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="logo-badge">O</div>
        <h1>오네시스</h1>
        <p>3개의 AI가 토론해 최선의 답을 만듭니다.<br />비밀번호를 입력해 주세요.</p>
        <div className="login-err">{err}</div>
        <input
          type="password"
          placeholder="비밀번호"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          autoFocus
        />
        <button className="go" disabled={busy || !pw}>
          {busy ? '확인 중…' : '들어가기'}
        </button>
      </form>
    </div>
  )
}

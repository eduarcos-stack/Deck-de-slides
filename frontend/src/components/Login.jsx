import React, { useState } from "react";
import * as api from "../api.js";

// Tela de login (M7, §48). Login obrigatório. Suporta segundo fator (TOTP).
export default function Login({ onLogged }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const r = await api.login(username, password);
      if (r.mfa_required) {
        setMfaToken(r.mfa_token);
      } else {
        api.setToken(r.token);
        onLogged(r.user);
      }
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  async function submitMfa(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const r = await api.loginMfa(mfaToken, code);
      api.setToken(r.token);
      onLogged(r.user);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="card" style={{ width: 360 }}>
        <div className="brand" style={{ marginBottom: 4 }}>TRACE-LM</div>
        <p className="subtitle" style={{ marginBottom: 18 }}>
          Acesso restrito · local-first · provenance-first
        </p>

        {!mfaToken ? (
          <form onSubmit={submit}>
            <label>Usuário</label>
            <input type="text" value={username} autoFocus
              onChange={(e) => setUsername(e.target.value)} />
            <label>Senha</label>
            <input type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
            <button className="primary" disabled={busy || !username || !password}>
              {busy ? "Entrando…" : "Entrar"}
            </button>
          </form>
        ) : (
          <form onSubmit={submitMfa}>
            <div className="banner">Segundo fator exigido. Informe o código do seu autenticador.</div>
            <label>Código (6 dígitos)</label>
            <input type="text" value={code} autoFocus inputMode="numeric"
              onChange={(e) => setCode(e.target.value)} />
            <button className="primary" disabled={busy || code.length < 6}>
              {busy ? "Verificando…" : "Verificar"}
            </button>
          </form>
        )}

        {err && <div className="banner warn error" style={{ marginTop: 12 }}>{err}</div>}
      </div>
    </div>
  );
}

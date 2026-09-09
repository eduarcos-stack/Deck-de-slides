import React, { useState } from "react";
import * as api from "../api.js";
import { supabase, supabaseEnabled } from "../supabase.js";

// Tela de login (M7, §48). Login obrigatório. Duas portas de entrada:
//  - Supabase Auth (deploy Grau B): identidade no Supabase; o FastAPI valida o
//    JWT e emite a sessão TRACE-LM, preservando RBAC/segregação/auditoria.
//  - Clássico (§48): usuário/senha do backend, com segundo fator (TOTP).
export default function Login({ onLogged }) {
  // Por padrão usa Supabase quando disponível; permite alternar para o clássico.
  const [useClassic, setUseClassic] = useState(!supabaseEnabled);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
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

  async function submitSupabase(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      // 1. Supabase autentica a identidade e devolve o JWT.
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
      const accessToken = data?.session?.access_token;
      if (!accessToken) throw new Error("sessão Supabase sem token");
      // 2. O FastAPI troca o JWT por uma sessão TRACE-LM (RBAC/auditoria).
      const r = await api.loginSupabase(accessToken);
      api.setToken(r.token);
      onLogged(r.user);
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="card" style={{ width: 360 }}>
        <div className="brand" style={{ marginBottom: 4 }}>TRACE-LM</div>
        <p className="subtitle" style={{ marginBottom: 18 }}>
          Acesso restrito · provenance-first
          {supabaseEnabled && <> · <span className="mono">Supabase Auth</span></>}
        </p>

        {!useClassic && supabaseEnabled ? (
          <form onSubmit={submitSupabase}>
            <label>E-mail</label>
            <input type="email" value={email} autoFocus
              onChange={(e) => setEmail(e.target.value)} />
            <label>Senha</label>
            <input type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
            <button className="primary" disabled={busy || !email || !password}>
              {busy ? "Entrando…" : "Entrar com Supabase"}
            </button>
          </form>
        ) : !mfaToken ? (
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

        {supabaseEnabled && !mfaToken && (
          <button className="chip" style={{ marginTop: 12 }}
            onClick={() => { setErr(null); setUseClassic((v) => !v); }}>
            {useClassic ? "← Entrar com Supabase" : "Usar usuário/senha local (admin)"}
          </button>
        )}

        {err && <div className="banner warn error" style={{ marginTop: 12 }}>{err}</div>}
      </div>
    </div>
  );
}

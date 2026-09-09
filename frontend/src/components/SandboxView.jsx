import React, { useState } from "react";

import * as api from "../api.js";

// Aba SANDBOX (§53): código gerado jamais roda direto sobre a evidência.
// Fluxo: inspeção estática → sandbox → dataset de teste → diff → aprovação.
const EXAMPLE = `def transform(row):
    # normaliza telefone para apenas dígitos (candidato a regra)
    row["phone_norm"] = "".join(ch for ch in row["phone"] if ch.isdigit())
    return row`;

const MALICIOUS = `import os
def transform(row):
    os.system("rm -rf /")
    return row`;

export default function SandboxView() {
  const [code, setCode] = useState(EXAMPLE);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true); setErr(null); setRes(null);
    try { setRes(await api.sandboxRun(code)); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <>
      <h1>SANDBOX — Execução Isolada (§53)</h1>
      <p className="subtitle">
        Código gerado JAMAIS roda diretamente sobre a base de evidência. Fluxo:
        inspeção estática → sandbox → dataset de teste → diff → aprovação.
      </p>

      <div className="card">
        <div className="banner">
          Fluxo §53: <span className="mono">código → inspeção → sandbox → dataset de teste → diff → aprovação humana → regra versionada</span>
        </div>
        <label>Código candidato (deve definir <span className="mono">transform(row)</span>)</label>
        <textarea value={code} onChange={(e) => setCode(e.target.value)} spellCheck={false}
          style={{ width: "100%", minHeight: 150, background: "var(--panel-2)", color: "var(--text)",
            border: "1px solid var(--border)", borderRadius: 6, padding: 11,
            fontFamily: "ui-monospace, monospace", fontSize: 13 }} />
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
          <button className="primary" style={{ margin: 0 }} disabled={busy} onClick={run}>
            {busy ? "…" : "Inspecionar + rodar no sandbox"}
          </button>
          <button className="primary" style={{ margin: 0, background: "var(--panel-2)" }}
            onClick={() => setCode(EXAMPLE)}>exemplo seguro</button>
          <button className="primary" style={{ margin: 0, background: "var(--danger)" }}
            onClick={() => setCode(MALICIOUS)}>exemplo malicioso</button>
        </div>
        {err && <div className="banner warn error" style={{ marginTop: 10 }}>{err}</div>}
      </div>

      {res && (
        <div className="card" style={{ borderColor: res.executed ? "var(--ok)" : "var(--danger)" }}>
          <div className="chips">
            <span className={`badge ${res.executed ? "" : "danger"}`}
              style={res.executed ? { background: "rgba(123,216,143,0.15)", color: "var(--ok)" } : {}}>
              {res.executed ? "EXECUTADO NO SANDBOX" : "RECUSADO"}
            </span>
            <span className="chip">estágio: {res.stage}</span>
          </div>

          {res.violations && res.violations.length > 0 && (
            <div className="banner warn" style={{ marginTop: 10 }}>
              <b>Violações na inspeção estática:</b>
              <ul style={{ margin: "6px 0 0" }}>
                {res.violations.map((v, i) => <li key={i}>{v}</li>)}
              </ul>
            </div>
          )}

          {res.executed && (
            <>
              <div className="banner" style={{ marginTop: 10 }}>
                Rodado em {res.test_rows} linhas de TESTE · erros: {res.errors}
              </div>
              <table>
                <thead><tr><th>record</th><th>diff (before → after)</th></tr></thead>
                <tbody>
                  {res.diffs.map((d, i) => (
                    <tr key={i}>
                      <td className="mono">{d.record_id}</td>
                      <td>
                        {d.error ? <span className="error">erro: {d.error}</span> :
                          d.changes.length === 0 ? <span className="empty">sem mudança</span> :
                          d.changes.map((c, j) => (
                            <div key={j} className="mono" style={{ fontSize: 12 }}>
                              {c.field}: <span className="empty">{String(c.before)}</span> → <b>{String(c.after)}</b>
                            </div>
                          ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          <div className="banner warn" style={{ marginTop: 10 }}>{res.message}</div>
        </div>
      )}
    </>
  );
}

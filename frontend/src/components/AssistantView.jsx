import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba ASSISTANT (§37-40, §38): interação em linguagem natural. O LLM interpreta,
// planeja, explica e coordena ferramentas — mas não é motor de execução (§4).
const SUGGESTIONS = [
  "Quantas transações Carlos Eduardo Silva realizou?",
  "A correlação de 0,88 prova que Carlos fez as transferências?",
  "Há um pico de eventos de madrugada?",
  "Faça o profiling desta base.",
];

export default function AssistantView({ datasetId, datasets, onPick }) {
  const [question, setQuestion] = useState("");
  const [resp, setResp] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [kb, setKb] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.systemPrompt().then(setPrompt).catch(() => {});
    api.kbDocs().then((r) => setKb(r.docs)).catch(() => {});
  }, []);

  async function ask(q) {
    const query = q ?? question;
    if (!query.trim()) return;
    setBusy(true); setErr(null); setResp(null);
    try { setResp(await api.askAssistant(query, datasetId)); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <>
      <h1>ASSISTANT — Orquestrador (LLM) + RAG local</h1>
      <p className="subtitle">
        O assistente interpreta, planeja e explica, roteando os motores
        determinísticos. Não é autoridade factual (§37) — cada número vem de uma
        ferramenta rastreável.
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />

      <div className="card">
        <label>Pergunte em linguagem natural</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input type="text" value={question} placeholder="ex.: quantas transações Carlos realizou?"
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()} />
          <button className="primary" style={{ margin: 0 }} disabled={busy} onClick={() => ask()}>
            {busy ? "…" : "Perguntar"}
          </button>
        </div>
        <div className="chips" style={{ marginTop: 10 }}>
          {SUGGESTIONS.map((s) => (
            <button key={s} className="chip" onClick={() => { setQuestion(s); ask(s); }}>{s}</button>
          ))}
        </div>
        {err && <div className="banner warn error" style={{ marginTop: 10 }}>{err}</div>}
      </div>

      {resp && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <div className="chips">
            <span className="badge OBSERVED">papel: {resp.role}</span>
            <span className="chip">intent: {resp.intent}</span>
            <span className="chip">provider: {resp.provider}</span>
            {resp.tier && (
              <span className={`badge ${resp.tier.served ? "" : "warn"}`}
                style={resp.tier.served ? { background: "rgba(123,216,143,0.15)", color: "var(--ok)" } : {}}>
                tier: {resp.tier.current} → {resp.tier.recommended} (§50)
              </span>
            )}
          </div>
          <div style={{ marginTop: 12, fontSize: 15, lineHeight: 1.5 }}>{resp.answer}</div>
          {resp.tier && !resp.tier.served && (
            <div className="banner warn" style={{ marginTop: 8 }}>{resp.tier.note}</div>
          )}

          {resp.plan.length > 0 && (
            <div className="banner" style={{ marginTop: 12 }}>
              <b>Plano de ferramentas:</b> <span className="mono">{resp.plan.join(" · ")}</span>
              <div className="roadmap" style={{ marginTop: 4 }}>{resp.note}</div>
            </div>
          )}
          {resp.guardrails.map((g, i) => (
            <div key={i} className="banner warn">{g}</div>
          ))}
          {resp.citations.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="l">Conhecimento de domínio (RAG local §51):</div>
              {resp.citations.map((c) => (
                <div key={c.doc_id} className="banner">
                  <b>{c.title}</b> <span className="roadmap">({c.source}, score {c.score})</span>
                  <div className="roadmap" style={{ marginTop: 4 }}>{c.snippet}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h1 style={{ fontSize: 15 }}>Base de conhecimento local (§51)</h1>
        <div className="chips">
          {kb.map((d) => <span key={d.doc_id} className="chip">{d.title}</span>)}
        </div>
        {prompt && (
          <>
            <div className="l" style={{ marginTop: 14 }}>System prompt constitucional (§39):</div>
            <div className="banner" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{prompt.system_prompt}</div>
            <div className="l" style={{ marginTop: 8 }}>Papéis lógicos (§40):</div>
            <div className="chips">{prompt.logical_roles.map((r) => <span key={r} className="chip">{r}</span>)}</div>
          </>
        )}
      </div>
    </>
  );
}

import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba FINDINGS (§44): Finding Registry (§76) + Adversarial Auditor (§41).
// Cada achado é EXPLORATÓRIO e pode ser contestado: "como isso poderia estar errado?".
export default function FindingsView({ datasetId, datasets, onPick }) {
  const [findings, setFindings] = useState([]);
  const [audits, setAudits] = useState({});
  const [err, setErr] = useState(null);

  function refresh() {
    if (!datasetId) return;
    api.listFindings(datasetId).then((r) => setFindings(r.findings)).catch((e) => setErr(e.message));
  }
  useEffect(refresh, [datasetId]);

  async function audit(fid) {
    try {
      const a = await api.auditFinding(datasetId, fid);
      setAudits((prev) => ({ ...prev, [fid]: a }));
      refresh();
    } catch (e) { setErr(e.message); }
  }

  if (!datasetId)
    return (<><h1>FINDINGS — Achados</h1><p className="empty">Selecione uma fonte na aba CASE.</p></>);

  return (
    <>
      <h1>FINDINGS — Registro de Achados e Auditoria Adversarial</h1>
      <p className="subtitle">
        Achados são exploratórios. A escada epistemológica (§29) não admite salto
        silencioso para conclusão. Cada achado pode ser contestado.
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {err && <div className="banner warn error">{err}</div>}

      {findings.length === 0 ? (
        <div className="card"><p className="empty">
          Nenhum achado registrado. Gere um na aba EXPLORE (ex.: "pico 00h-02h").
        </p></div>
      ) : (
        findings.map((f) => (
          <div className="card" key={f.finding_id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div>
                <span className={`badge ${f.status.startsWith("STALE") ? "danger" : "warn"}`}>{f.status}</span>{" "}
                {f.robust === false && <span className="badge danger">NÃO ROBUSTO</span>}
                {f.robust === true && <span className="badge" style={{ background: "rgba(123,216,143,0.15)", color: "var(--ok)" }}>ROBUSTO</span>}
                <div style={{ marginTop: 8, fontSize: 15 }}>{f.statement}</div>
                <div className="roadmap" style={{ marginTop: 4 }}>
                  tipo: {f.type} · confiança: {f.confidence} · método: {JSON.stringify(f.method)}
                </div>
              </div>
              <button className="primary" style={{ margin: 0, whiteSpace: "nowrap" }}
                onClick={() => audit(f.finding_id)}>Como isso poderia estar errado?</button>
            </div>

            {f.evidence?.supporting_records && (
              <div className="banner">
                <b>Pattern Provenance (§32):</b> o achado é sustentado por{" "}
                <span className="mono">{f.evidence.supporting_records.join(", ")}</span>.
              </div>
            )}

            {audits[f.finding_id] && (
              <div className="card" style={{ borderColor: "var(--accent)", marginTop: 12 }}>
                <h1 style={{ fontSize: 14 }}>Adversarial Review — veredito:{" "}
                  <span className={audits[f.finding_id].robust === false ? "error" : ""}>
                    {audits[f.finding_id].verdict}
                  </span>
                </h1>
                {audits[f.finding_id].challenges.map((ch, i) => (
                  <div key={i} className="banner warn">
                    <b>[{ch.vector}]</b> {ch.question}
                    <div style={{ marginTop: 4 }}>{ch.finding_impact}</div>
                    {ch.evidence && (
                      <div className="roadmap mono" style={{ marginTop: 4 }}>
                        naive={ch.evidence.cenario_naive} · strict={ch.evidence.cenario_strict} · pico={JSON.stringify(ch.evidence.registros_do_pico)}
                      </div>
                    )}
                  </div>
                ))}
                <p className="roadmap">{audits[f.finding_id].reminder}</p>
              </div>
            )}
          </div>
        ))
      )}
    </>
  );
}

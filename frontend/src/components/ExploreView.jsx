import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba EXPLORE (§44): EDA + Temporal Engine. Todo resultado é EXPLORATÓRIO (§28).
// Demonstra §89-90: o pico 00h-02h existe sob parser naive e some sob strict.
export default function ExploreView({ datasetId, datasets, onPick }) {
  const [tq, setTq] = useState(null);
  const [naive, setNaive] = useState(null);
  const [strict, setStrict] = useState(null);
  const [outliers, setOutliers] = useState(null);
  const [peakMsg, setPeakMsg] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    setTq(null); setNaive(null); setStrict(null); setOutliers(null); setPeakMsg(null);
    api.temporalQuality(datasetId, "strict").then(setTq).catch((e) => setErr(e.message));
    api.edaHours(datasetId, "naive").then(setNaive).catch(() => {});
    api.edaHours(datasetId, "strict").then(setStrict).catch(() => {});
    api.edaOutliers(datasetId, "amount").then(setOutliers).catch(() => {});
  }, [datasetId]);

  async function detectPeak() {
    setPeakMsg(null);
    try {
      const f = await api.detectTemporalPeak(datasetId);
      setPeakMsg(`Achado registrado: "${f.statement}" (status ${f.status}). Provenance: ${f.pattern_provenance.join(", ")}. Audite-o na aba FINDINGS.`);
    } catch (e) { setErr(e.message); }
  }

  if (!datasetId)
    return (<><h1>EXPLORE — Análise Exploratória</h1><p className="empty">Selecione uma fonte na aba CASE.</p></>);

  const maxCount = Math.max(1, ...(naive ? Object.values(naive.histogram) : [1]));

  return (
    <>
      <h1>EXPLORE — EDA e Temporal Engine</h1>
      <p className="subtitle">
        Resultados são EXPLORATÓRIOS, não conclusões (§28). Converter timezone não
        valida o relógio de origem (P6).
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {err && <div className="banner warn error">{err}</div>}

      {tq && (
        <div className="card">
          <h1 style={{ fontSize: 15 }}>Qualidade temporal (§19)</h1>
          <div className="grid">
            {Object.entries(tq.quality_distribution).map(([k, v]) => (
              <div key={k} className={`stat ${k === "UNKNOWN" ? "alert" : ""}`}>
                <div className="n">{v}</div><div className="l">{k}</div>
              </div>
            ))}
          </div>
          <div className="banner">{tq.guardrail}</div>
        </div>
      )}

      <div className="card">
        <h1 style={{ fontSize: 15 }}>Histograma de hora-do-dia — parser naive vs strict (§89)</h1>
        <p className="roadmap">
          Sob o parser <b>naive</b>, timestamps 24:00 colapsam para 00h e criam um pico.
          Sob o <b>strict</b>, são marcados UNKNOWN e excluídos.
        </p>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 10 }}>
          <Histogram title="naive" data={naive} max={maxCount} highlight />
          <Histogram title="strict" data={strict} max={maxCount} />
        </div>
        <button className="primary" onClick={detectPeak}>Registrar achado "pico 00h-02h"</button>
        {peakMsg && <div className="banner ok">{peakMsg}</div>}
      </div>

      {outliers && (
        <div className="card">
          <h1 style={{ fontSize: 15 }}>Outliers de valor — Outlier Policy (§30)</h1>
          {outliers.outliers.length === 0 ? (
            <p className="empty">Nenhum outlier sob os limites IQR.</p>
          ) : (
            <table>
              <thead><tr><th>record</th><th>valor</th></tr></thead>
              <tbody>
                {outliers.outliers.map((o) => (
                  <tr key={o.record_id}>
                    <td className="mono">{o.record_id}</td>
                    <td className="mono">R$ {o.value.toLocaleString("pt-BR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="banner warn">{outliers.policy}</div>
        </div>
      )}
    </>
  );
}

function Histogram({ title, data, max, highlight }) {
  if (!data) return <div style={{ flex: 1 }}><p className="empty">…</p></div>;
  return (
    <div style={{ flex: 1, minWidth: 300 }}>
      <div className="l" style={{ marginBottom: 6, fontWeight: 600 }}>
        parser {title} — janela 00h-02h: <b style={{ color: data.window_00_02h > 0 && highlight ? "var(--warn)" : "var(--muted)" }}>{data.window_00_02h}</b>
      </div>
      <div style={{ display: "flex", alignItems: "stretch", gap: 2, height: 120 }}>
        {Object.entries(data.histogram).map(([h, n]) => {
          const early = Number(h) <= 2;
          return (
            <div key={h} title={`${h}h: ${n}`} style={{ flex: 1, height: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center" }}>
              <div style={{
                width: "100%", height: `${(n / max) * 100}%`, minHeight: n > 0 ? 2 : 0,
                background: early && n > 0 ? "var(--warn)" : "var(--accent)", borderRadius: "2px 2px 0 0",
              }} />
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--muted)", marginTop: 2 }}>
        <span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span>
      </div>
    </div>
  );
}

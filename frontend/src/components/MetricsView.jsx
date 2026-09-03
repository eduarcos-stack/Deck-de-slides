import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba METRICS (§62-67): métricas formais de qualidade e avaliação do assistente.
export default function MetricsView({ datasetId, datasets, onPick }) {
  const [m, setM] = useState(null);
  const [llm, setLlm] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    setM(null); setLlm(null); setErr(null);
    api.datasetMetrics(datasetId).then(setM).catch((e) => setErr(e.message));
    api.llmMetrics(datasetId).then(setLlm).catch(() => {});
  }, [datasetId]);

  if (!datasetId)
    return (<><h1>METRICS — Validação</h1><p className="empty">Selecione uma fonte na aba CASE.</p></>);

  return (
    <>
      <h1>METRICS — Métricas de Qualidade e Validação</h1>
      <p className="subtitle">
        Avaliação objetiva contra o ground truth (§67). Meta arquitetural: 100% dos
        achados rastreáveis (§63) e nenhum false merge (§85).
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {err && <div className="banner warn error">{err}</div>}
      {!m ? <p className="empty">Calculando métricas…</p> : (
        <>
          <div className="grid">
            <Stat n={fmt(m.entity_resolution.false_merge_rate)} l="false merge rate (§85)"
              good={m.entity_resolution.false_merge_rate === 0} />
            <Stat n={fmt(m.provenance_completeness.pc)} l="provenance completeness (§63)"
              good={m.provenance_completeness.pc === 1} />
            <Stat n={fmt(m.reproducibility.rate)} l="reproducibility rate (§64)"
              good={m.reproducibility.rate === 1} />
            <Stat n={fmt(m.transformation.reversibility_rate)} l="reversibilidade (§62)"
              good={m.transformation.reversibility_rate === 1} />
          </div>

          <div className="card">
            <h1 style={{ fontSize: 15 }}>Entity Resolution (§62)</h1>
            <table>
              <tbody>
                <Row k="precision" v={fmt(m.entity_resolution.precision)} />
                <Row k="recall" v={fmt(m.entity_resolution.recall)} />
                <Row k="F1" v={fmt(m.entity_resolution.f1)} />
                <Row k="false merge rate" v={fmt(m.entity_resolution.false_merge_rate)} />
                <Row k="false split rate" v={fmt(m.entity_resolution.false_split_rate)} />
                <Row k="abstention rate" v={fmt(m.entity_resolution.abstention_rate)} />
                <Row k="confusão" v={JSON.stringify(m.entity_resolution.confusion)} />
                <Row k="entidades (sistema / gold)"
                  v={`${m.entity_resolution.system_entities} / ${m.entity_resolution.gold_persons}`} />
              </tbody>
            </table>
            <div className="banner">{m.entity_resolution.note}</div>
          </div>

          <div className="card">
            <h1 style={{ fontSize: 15 }}>Deduplicação (§62) e Reprodutibilidade (§64)</h1>
            <table>
              <tbody>
                <Row k="linhas brutas → eventos canônicos"
                  v={`${m.deduplication.raw_rows} → ${m.deduplication.canonical_events}`} />
                <Row k="duplicatas técnicas" v={m.deduplication.technical_duplicate_groups} />
                <Row k="reproducibility checks" v={JSON.stringify(m.reproducibility.checks)} />
              </tbody>
            </table>
          </div>

          {llm && (
            <div className="card">
              <h1 style={{ fontSize: 15 }}>Avaliação do assistente (§65)</h1>
              <div className="grid">
                {Object.entries(llm.per_criterion).map(([k, v]) => (
                  <Stat key={k} n={fmt(v)} l={k.replace(/_/g, " ")} good={v === 1} />
                ))}
              </div>
              <div className="banner">Taxa geral: <b>{fmt(llm.overall_pass_rate)}</b> · {llm.note}</div>
            </div>
          )}
        </>
      )}
    </>
  );
}

function fmt(x) { return x === null || x === undefined ? "—" : x; }
function Stat({ n, l, good }) {
  return (
    <div className="stat" style={good ? { borderLeft: "3px solid var(--ok)" } : {}}>
      <div className="n" style={{ color: good ? "var(--ok)" : "var(--text)" }}>{n}</div>
      <div className="l">{l}</div>
    </div>
  );
}
function Row({ k, v }) {
  return (<tr><td>{k}</td><td className="mono">{v}</td></tr>);
}

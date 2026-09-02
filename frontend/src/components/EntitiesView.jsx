import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba ENTITIES (§44): Entity Resolution assistida (§22-25) + Impact Analysis
// (§26-27). O sistema recomenda; o humano decide (§43 nível 3).
export default function EntitiesView({ datasetId, datasets, onPick }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    setData(null); setSelected(null);
    api.getEntities(datasetId).then(setData).catch((e) => setErr(e.message));
  }, [datasetId]);

  if (!datasetId)
    return (<><h1>ENTITIES — Entity Resolution</h1><p className="empty">Selecione uma fonte na aba CASE.</p></>);

  return (
    <>
      <h1>ENTITIES — Resolução de Entidades</h1>
      <p className="subtitle">
        Entidades são <b>hipóteses</b> (CANDIDATE), não fatos (P4). Similaridade de
        nome não é identidade. Fusões de alto impacto exigem aprovação (§25).
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {err && <div className="banner warn error">{err}</div>}
      {!data ? <p className="empty">Resolvendo entidades…</p> : (
        <>
          <div className="card">
            <h1 style={{ fontSize: 15 }}>Entidades candidatas</h1>
            <table>
              <thead><tr><th>status</th><th>nome</th><th>CPF</th><th>nascimento</th><th>registros</th></tr></thead>
              <tbody>
                {data.entities.map((e) => (
                  <tr key={e.entity_id}>
                    <td><span className="badge warn">{e.status}</span></td>
                    <td>{e.name}</td>
                    <td className="mono">{e.cpf || "∅"}</td>
                    <td className="mono">{e.dob || "∅"}</td>
                    <td>{e.record_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h1 style={{ fontSize: 15 }}>Pares candidatos (potenciais colisões de identidade)</h1>
            {data.candidate_pairs.length === 0 ? (
              <p className="empty">Nenhum par candidato — nenhum bloco de nome com identidades divergentes.</p>
            ) : (
              <table>
                <thead><tr><th>sim. nome</th><th>CPF</th><th>nascimento</th><th>decisão</th><th></th></tr></thead>
                <tbody>
                  {data.candidate_pairs.map((p, i) => (
                    <tr key={i}>
                      <td className="mono">{p.name_similarity.toFixed(2)}</td>
                      <td><Cmp v={p.cpf} /></td>
                      <td><Cmp v={p.dob} /></td>
                      <td><span className={`badge ${p.decision === "MATCH" ? "" : "danger"}`}
                        style={p.decision === "MATCH" ? { background: "rgba(123,216,143,0.15)", color: "var(--ok)" } : {}}>
                        {p.decision}</span></td>
                      <td>
                        <button className="primary" style={{ margin: 0, padding: "4px 10px" }}
                          onClick={() => setSelected(p)}>Impact Analysis</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {selected && <ImpactPanel datasetId={datasetId} pair={selected}
            onDecided={() => api.getEntities(datasetId).then(setData)} />}
        </>
      )}
    </>
  );
}

function ImpactPanel({ datasetId, pair, onDecided }) {
  const [impact, setImpact] = useState(null);
  const [operator, setOperator] = useState("");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setImpact(null); setMsg(null); setErr(null);
    api.entityImpact(datasetId, pair.entity_a, pair.entity_b).then(setImpact).catch((e) => setErr(e.message));
  }, [datasetId, pair]);

  async function decide(decision) {
    if (!operator) { setErr("Informe o operador que decide (P9)."); return; }
    setErr(null);
    try {
      const r = await api.entityDecide(datasetId, pair.entity_a, pair.entity_b, decision, operator, "decidido via UI");
      setMsg(`Decisão registrada: ${r.decision}${r.merged_entity_id ? " (entidade fundida " + r.merged_entity_id + ")" : ""}. Reversível e auditável.`);
      onDecided();
    } catch (e) { setErr(e.message); }
  }

  return (
    <div className="card" style={{ borderColor: "var(--accent)" }}>
      <h1 style={{ fontSize: 15 }}>Impact Analysis — simulação da fusão (§26)</h1>
      {err && <div className="banner warn error">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}
      {!impact ? <p className="empty">Simulando…</p> : (
        <>
          <div className={`banner ${impact.high_impact ? "warn" : "ok"}`}>
            <b>{impact.classification}.</b> {impact.alert}
            {impact.high_impact_reasons.length > 0 && (
              <ul style={{ margin: "6px 0 0" }}>
                {impact.high_impact_reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            )}
          </div>

          <table style={{ marginTop: 10 }}>
            <thead><tr><th></th><th>eventos</th><th>empresas</th><th>valor total</th><th>telefones</th></tr></thead>
            <tbody>
              <tr><td>Antes — A</td><td>{impact.before.A.events}</td><td>{impact.before.A.companies.length}</td><td className="mono">R$ {impact.before.A.total_amount.toLocaleString("pt-BR")}</td><td>{impact.before.A.phones}</td></tr>
              <tr><td>Antes — B</td><td>{impact.before.B.events}</td><td>{impact.before.B.companies.length}</td><td className="mono">R$ {impact.before.B.total_amount.toLocaleString("pt-BR")}</td><td>{impact.before.B.phones}</td></tr>
              <tr style={{ fontWeight: 700 }}><td>Depois (fundido)</td><td>{impact.after.events}</td><td>{impact.after.companies.length}</td><td className="mono">R$ {impact.after.total_amount.toLocaleString("pt-BR")}</td><td>{impact.after.phones}</td></tr>
            </tbody>
          </table>
          <p className="banner">Pergunta-chave (§27): esta transformação apenas melhora a representação ou <b>altera a narrativa analítica</b>?</p>

          {impact.recommendation && (
            <div className="banner warn">
              Recomendação do motor: <b>{impact.recommendation.decision}</b> — {impact.recommendation.reason}
            </div>
          )}

          <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ minWidth: 200 }}>
              <label>Operador que decide (P9)</label>
              <input type="text" placeholder="ex.: eduardo.arcos" value={operator}
                onChange={(e) => setOperator(e.target.value)} />
            </div>
            <button className="primary" style={{ margin: 0, background: "var(--danger)" }}
              onClick={() => decide("NON_MATCH")}>Rejeitar fusão (NON_MATCH)</button>
            <button className="primary" style={{ margin: 0, background: "var(--ok)", color: "#08260f" }}
              onClick={() => decide("MATCH")}>Aprovar fusão (MATCH)</button>
          </div>
        </>
      )}
    </div>
  );
}

function Cmp({ v }) {
  const cls = v === "conflict" ? "danger" : v === "equal" ? "" : "warn";
  const style = v === "equal" ? { background: "rgba(123,216,143,0.15)", color: "var(--ok)" } : {};
  return <span className={`badge ${cls}`} style={style}>{v}</span>;
}

import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba AUDIT (§44): Provenance Graph (§34), Diário de Transformação (§35) e o
// botão conceitual central "Como chegamos aqui?" (§45). Serve a principal
// função de confiança (§98): responder "por que este número está aqui?".
export default function AuditView({ datasetId, datasets, onPick }) {
  const [prov, setProv] = useState(null);
  const [trace, setTrace] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    setProv(null); setTrace(null);
    api.getProvenance(datasetId).then(setProv).catch((e) => setErr(e.message));
  }, [datasetId]);

  async function howDidWeGetHere(type, id) {
    setTrace({ loading: true, object: { type, id } });
    try {
      const r = await api.traceObject(type, id);
      setTrace(r);
    } catch (e) {
      setErr(e.message);
      setTrace(null);
    }
  }

  if (!datasetId)
    return (<><h1>AUDIT — Auditoria e Proveniência</h1><p className="empty">Selecione uma fonte na aba CASE.</p></>);

  return (
    <>
      <h1>AUDIT — Proveniência e Auditoria</h1>
      <p className="subtitle">
        Rastreabilidade bidirecional entre fontes, transformações e resultados.
        Qualquer afirmação relevante deve responder "por que este número está aqui?" (§98).
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {err && <div className="banner warn error">{err}</div>}
      {!prov ? <p className="empty">Carregando proveniência…</p> : (
        <>
          <div className="card">
            <h1 style={{ fontSize: 15 }}>Diário de Transformação (§35)</h1>
            {prov.transformations.length === 0 ? (
              <p className="empty">Nenhuma transformação registrada. Aplique normalização/dedup/ER.</p>
            ) : (
              <table>
                <thead><tr><th>regra</th><th>v</th><th>ferramenta</th><th>ator</th><th>afetados</th><th></th></tr></thead>
                <tbody>
                  {prov.transformations.map((t) => (
                    <tr key={t.transformation_id}>
                      <td className="mono">{t.rule_id}</td>
                      <td>{t.rule_version}</td>
                      <td className="roadmap">{t.tool}</td>
                      <td>{t.actor}</td>
                      <td>{t.records_affected}</td>
                      <td>
                        <button className="primary" style={{ margin: 0, padding: "4px 10px" }}
                          onClick={() => howDidWeGetHere("TRANSFORMATION", t.transformation_id)}>
                          Como chegamos aqui?
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {trace && (
            <div className="card" style={{ borderColor: "var(--accent)" }}>
              <h1 style={{ fontSize: 15 }}>Como chegamos aqui? — caminho reverso (§45)</h1>
              <p className="roadmap">
                objeto: <span className="mono">{trace.object.type}:{trace.object.id.slice(0, 12)}</span>
              </p>
              {trace.loading ? <p className="empty">Rastreando…</p> :
                trace.path.length === 0 ? (
                  <p className="empty">Sem arestas de origem registradas para este objeto.</p>
                ) : (
                  <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 13, lineHeight: 1.9 }}>
                    {trace.path.map((edge, i) => (
                      <div key={i}>
                        <span className="badge OBSERVED">{edge.from.type}</span>
                        {" "}<span style={{ color: "var(--muted)" }}>{edge.from.id.slice(0, 10)}</span>
                        {"  ──"}{edge.relation}{"──▶  "}
                        <span className="badge warn">{edge.to.type}</span>
                        {" "}<span style={{ color: "var(--muted)" }}>{edge.to.id.slice(0, 10)}</span>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          )}

          <div className="card">
            <h1 style={{ fontSize: 15 }}>Provenance Graph — arestas (§34)</h1>
            {prov.edges.length === 0 ? (
              <p className="empty">Grafo vazio.</p>
            ) : (
              <table>
                <thead><tr><th>origem</th><th>relação</th><th>destino</th></tr></thead>
                <tbody>
                  {prov.edges.map((e, i) => (
                    <tr key={i}>
                      <td><span className="badge OBSERVED">{e.src_type}</span> <span className="mono">{e.src_id.slice(0, 10)}</span></td>
                      <td className="roadmap">{e.relation}</td>
                      <td><span className="badge warn">{e.dst_type}</span> <span className="mono">{e.dst_id.slice(0, 10)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </>
  );
}

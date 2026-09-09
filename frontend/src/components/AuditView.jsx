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

  const [reversible, setReversible] = useState([]);
  const [operator, setOperator] = useState("");
  const [rbMsg, setRbMsg] = useState(null);
  const [deps, setDeps] = useState({});

  function refresh() {
    if (!datasetId) return;
    api.getProvenance(datasetId).then(setProv).catch((e) => setErr(e.message));
    api.listReversible(datasetId).then((r) => setReversible(r.transformations)).catch(() => {});
  }

  useEffect(() => {
    setProv(null); setTrace(null); setRbMsg(null); setDeps({});
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  async function showDeps(tid) {
    try {
      const d = await api.txDependencies(datasetId, tid);
      setDeps((prev) => ({ ...prev, [tid]: d }));
    } catch (e) { setErr(e.message); }
  }

  async function rollback(tid) {
    if (!operator) { setErr("Informe o operador (P9)."); return; }
    setErr(null);
    try {
      const r = await api.doRollback(datasetId, tid, operator, "rollback via UI");
      setRbMsg(`Revertido ${r.original_rule}. Desfeito: ${JSON.stringify(r.undone)}. ` +
        `Achados invalidados: ${r.invalidated_findings.length}.`);
      refresh();
    } catch (e) { setErr(e.message); }
  }

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

      <IntegrityPanel />
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
            <h1 style={{ fontSize: 15 }}>Reversibilidade & Rollback (§57-59)</h1>
            <p className="roadmap">
              Reverter não apaga o diário (§36): registra transformação inversa e
              invalida achados dependentes (§59). O raw permanece intacto (P1).
            </p>
            {rbMsg && <div className="banner ok">{rbMsg}</div>}
            {reversible.length === 0 ? (
              <p className="empty">Nenhuma transformação reversível pendente.</p>
            ) : (
              <>
                <div style={{ margin: "8px 0" }}>
                  <label>Operador que reverte (P9)</label>
                  <input type="text" placeholder="ex.: eduardo.arcos" value={operator}
                    onChange={(e) => setOperator(e.target.value)} style={{ maxWidth: 280 }} />
                </div>
                <table>
                  <thead><tr><th>regra</th><th>v</th><th>ferramenta</th><th>afetados</th><th></th><th></th></tr></thead>
                  <tbody>
                    {reversible.map((t) => (
                      <React.Fragment key={t.transformation_id}>
                        <tr>
                          <td className="mono">{t.rule_id}</td>
                          <td>{t.rule_version}</td>
                          <td className="roadmap">{t.tool}</td>
                          <td>{t.records_affected}</td>
                          <td>
                            <button className="primary" style={{ margin: 0, padding: "4px 10px", background: "var(--panel-2)" }}
                              onClick={() => showDeps(t.transformation_id)}>dependências</button>
                          </td>
                          <td>
                            <button className="primary" style={{ margin: 0, padding: "4px 10px", background: "var(--danger)" }}
                              onClick={() => rollback(t.transformation_id)}>Reverter</button>
                          </td>
                        </tr>
                        {deps[t.transformation_id] && (
                          <tr>
                            <td colSpan={6} className="roadmap" style={{ background: "var(--panel-2)" }}>
                              campos derivados: {deps[t.transformation_id].derived_fields.join(", ") || "—"} ·
                              entidades: {deps[t.transformation_id].produced_entities.join(", ") || "—"} ·
                              achados dependentes: {deps[t.transformation_id].dependent_findings.join(", ") || "—"}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>

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

function IntegrityPanel() {
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);

  async function verify() {
    setErr(null); setRes(null);
    try { setRes(await api.verifyIntegrity()); }
    catch (e) { setErr(e.message); }
  }

  function Line({ label, chain }) {
    return (
      <div style={{ marginTop: 6 }}>
        <span className={`badge ${chain.ok ? "" : "danger"}`}
          style={chain.ok ? { background: "rgba(123,216,143,0.15)", color: "var(--ok)" } : {}}>
          {chain.ok ? "ÍNTEGRA" : "ROMPIDA"}
        </span>{" "}
        <b>{label}</b> — {chain.entries} entrada(s).{" "}
        {!chain.ok && <span className="error">rompida no item {chain.broken_at}: {chain.reason}</span>}
      </div>
    );
  }

  return (
    <div className="card">
      <h1 style={{ fontSize: 15 }}>Integridade da trilha — hash-chain (§36)</h1>
      <p className="roadmap">
        Cada entrada do Diário e do log de acesso é encadeada por hash e selada
        com HMAC. Adulteração, remoção ou reordenação posterior tornam-se detectáveis.
      </p>
      <button className="primary" style={{ margin: 0 }} onClick={verify}>Verificar integridade</button>
      {err && <div className="banner warn error" style={{ marginTop: 10 }}>{err} (exige papel admin)</div>}
      {res && (
        <div className={`banner ${res.overall_ok ? "ok" : "warn"}`} style={{ marginTop: 10 }}>
          <Line label="Diário de Transformação" chain={res.transformation_diary} />
          <Line label="Log de acesso" chain={res.access_log} />
        </div>
      )}
    </div>
  );
}

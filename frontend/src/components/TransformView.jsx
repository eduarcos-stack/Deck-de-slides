import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba TRANSFORM (§44): normalização versionada com preview/aprovação (§16-17)
// e deduplicação por unidade de evento (§20). Fluxo obrigatório §6:
// regra explícita -> impacto simulado -> humano aprova -> executa -> registra.
export default function TransformView({ datasetId, datasets, onPick }) {
  const [rules, setRules] = useState([]);
  const [diary, setDiary] = useState([]);

  useEffect(() => {
    api.listRules().then((r) => setRules(r.rules)).catch(() => {});
  }, []);

  function refreshDiary() {
    if (!datasetId) return;
    api.listTransformations(datasetId).then((r) => setDiary(r.transformations)).catch(() => {});
  }
  useEffect(refreshDiary, [datasetId]);

  if (!datasetId)
    return (
      <>
        <h1>TRANSFORM — Transformações</h1>
        <p className="empty">Selecione uma fonte na aba CASE.</p>
      </>
    );

  return (
    <>
      <h1>TRANSFORM — Transformações propostas e aplicadas</h1>
      <p className="subtitle">
        Nenhuma transformação é executada sem regra explícita, simulação de
        impacto e aprovação. O dado bruto nunca é sobrescrito (P1).
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />

      <NormalizationPanel datasetId={datasetId} rules={rules} onApplied={refreshDiary} />
      <DedupPanel datasetId={datasetId} onApplied={refreshDiary} />
      <DiaryPanel diary={diary} />
    </>
  );
}

function NormalizationPanel({ datasetId, rules, onApplied }) {
  const [field, setField] = useState("phone");
  const [ruleId, setRuleId] = useState("PHONE_BR_E164_V2");
  const [preview, setPreview] = useState(null);
  const [operator, setOperator] = useState("");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  async function doPreview() {
    setErr(null); setMsg(null); setPreview(null);
    try {
      setPreview(await api.normalizePreview(datasetId, field, ruleId));
    } catch (e) { setErr(e.message); }
  }
  async function approve() {
    if (!operator) { setErr("Informe o operador que aprova (P9)."); return; }
    setErr(null);
    try {
      const r = await api.normalizeApply(datasetId, field, ruleId, operator, "aprovado via UI");
      setMsg(`Aplicado: campo derivado ${r.derived_field}, ${r.records_affected} registros. Reversível.`);
      setPreview(null); onApplied();
    } catch (e) { setErr(e.message); }
  }

  return (
    <div className="card">
      <h1 style={{ fontSize: 15 }}>Normalização versionada (§16-17)</h1>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 140 }}>
          <label>Campo</label>
          <input type="text" value={field} onChange={(e) => setField(e.target.value)} />
        </div>
        <div style={{ flex: 2, minWidth: 200 }}>
          <label>Regra</label>
          <select value={ruleId} onChange={(e) => setRuleId(e.target.value)}
            style={selectStyle}>
            {rules.map((r) => (
              <option key={r.rule_id} value={r.rule_id}>
                {r.rule_id} (v{r.version}) — {r.description}
              </option>
            ))}
          </select>
        </div>
        <button className="primary" style={{ margin: 0 }} onClick={doPreview}>Simular (preview)</button>
      </div>

      {err && <div className="banner warn error">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}

      {preview && (
        <>
          <div className="grid" style={{ marginTop: 16 }}>
            <Stat n={preview.records_analyzed} l="analisados" />
            <Stat n={preview.transformable_auto} l="transformáveis" />
            <Stat n={preview.ambiguous} l="ambíguos" alert={preview.ambiguous > 0} />
            <Stat n={preview.values_changed} l="valores alterados" />
            <Stat n={"Nível " + preview.approval_level} l="decisão humana (§43)" />
          </div>
          <p className="banner">Originais preservados: <b>SIM</b> (P1/P2). Ambíguos não são convertidos (P3).</p>

          <table style={{ marginTop: 8 }}>
            <thead><tr><th>record</th><th>raw</th><th>→ derivado</th><th>confiança</th><th>motivo</th></tr></thead>
            <tbody>
              {preview.samples.map((s) => (
                <tr key={s.record_id}>
                  <td className="mono">{s.record_id.slice(0, 8)}</td>
                  <td className="mono">{s.raw_value ?? "∅"}</td>
                  <td className="mono">{s.ambiguous ? <span className="badge warn">ambíguo</span> : s.derived_value}</td>
                  <td>{s.confidence}</td>
                  <td className="roadmap">{s.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 14, display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ minWidth: 200 }}>
              <label>Operador que aprova (P9)</label>
              <input type="text" placeholder="ex.: eduardo.arcos" value={operator}
                onChange={(e) => setOperator(e.target.value)} />
            </div>
            <button className="primary" style={{ margin: 0, background: "var(--ok)", color: "#08260f" }}
              onClick={approve}>APROVAR</button>
            <button className="primary" style={{ margin: 0, background: "var(--panel-2)" }}
              onClick={doPreview}>REVISAR</button>
            <button className="primary" style={{ margin: 0, background: "var(--danger)" }}
              onClick={() => setPreview(null)}>REJEITAR</button>
          </div>
        </>
      )}
    </div>
  );
}

function DedupPanel({ datasetId, onApplied }) {
  const [eventKey, setEventKey] = useState("event_id");
  const [report, setReport] = useState(null);
  const [operator, setOperator] = useState("");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  async function analyze() {
    setErr(null); setMsg(null); setReport(null);
    try { setReport(await api.dedupAnalyze(datasetId, eventKey)); }
    catch (e) { setErr(e.message); }
  }
  async function canonicalize() {
    if (!operator) { setErr("Informe o operador que aprova (P9)."); return; }
    setErr(null);
    try {
      const r = await api.dedupCanonicalize(datasetId, eventKey, operator, "consolidação via UI");
      setMsg(`Consolidado: ${r.records_marked_non_canonical} registros marcados não-canônicos, ${r.canonical_events} eventos canônicos. Raw preservado (P1).`);
      onApplied(); analyze();
    } catch (e) { setErr(e.message); }
  }

  return (
    <div className="card">
      <h1 style={{ fontSize: 15 }}>Deduplicação por unidade de evento (§20)</h1>
      <p className="roadmap">Antes de deduplicar, defina o que constitui um evento (P5). Escolha a chave:</p>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
        <div style={{ minWidth: 180 }}>
          <label>Chave de evento (event_key)</label>
          <input type="text" value={eventKey} onChange={(e) => setEventKey(e.target.value)} />
        </div>
        <button className="primary" style={{ margin: 0 }} onClick={analyze}>Analisar</button>
      </div>

      {err && <div className="banner warn error">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}

      {report && (
        <>
          <div className="grid" style={{ marginTop: 14 }}>
            <Stat n={report.raw_rows} l="linhas brutas" />
            <Stat n={report.distinct_event_keys} l="eventos canônicos" />
            {Object.entries(report.category_counts).map(([k, v]) => (
              <Stat key={k} n={v} l={k} alert={k === "UNRESOLVED"} />
            ))}
          </div>
          {report.duplicate_groups.length > 0 && (
            <table style={{ marginTop: 8 }}>
              <thead><tr><th>event_key</th><th>categoria</th><th>membros</th></tr></thead>
              <tbody>
                {report.duplicate_groups.map((g, i) => (
                  <tr key={i}>
                    <td className="mono">{g.event_key_value}</td>
                    <td><span className={`badge ${g.category === "UNRESOLVED" ? "danger" : "warn"}`}>{g.category}</span></td>
                    <td className="mono">{g.member_record_ids.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ minWidth: 200 }}>
              <label>Operador que aprova (P9)</label>
              <input type="text" placeholder="ex.: eduardo.arcos" value={operator}
                onChange={(e) => setOperator(e.target.value)} />
            </div>
            <button className="primary" style={{ margin: 0, background: "var(--ok)", color: "#08260f" }}
              onClick={canonicalize}>Consolidar EXACT/TECHNICAL</button>
          </div>
          <p className="roadmap" style={{ marginTop: 8 }}>
            UNRESOLVED e repetições legítimas NÃO são consolidadas automaticamente.
          </p>
        </>
      )}
    </div>
  );
}

function DiaryPanel({ diary }) {
  return (
    <div className="card">
      <h1 style={{ fontSize: 15 }}>Diário de Transformação (§35)</h1>
      {diary.length === 0 ? (
        <p className="empty">Nenhuma transformação aplicada ainda.</p>
      ) : (
        <table>
          <thead><tr><th>regra</th><th>versão</th><th>ator/aprovação</th><th>afetados</th><th>reversível</th><th>datetime</th></tr></thead>
          <tbody>
            {diary.map((t) => (
              <tr key={t.transformation_id}>
                <td className="mono">{t.rule_id}</td>
                <td>{t.rule_version}</td>
                <td>{t.actor}</td>
                <td>{t.records_affected}</td>
                <td>{t.reversible ? "✓" : "—"}</td>
                <td className="roadmap">{t.datetime?.slice(0, 19).replace("T", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const selectStyle = {
  width: "100%", padding: "9px 11px", background: "var(--panel-2)",
  border: "1px solid var(--border)", borderRadius: 6, color: "var(--text)", fontSize: 13,
};

function Stat({ n, l, alert }) {
  return (
    <div className={`stat ${alert ? "alert" : ""}`}>
      <div className="n" style={{ fontSize: typeof n === "string" ? 15 : 24 }}>{n}</div>
      <div className="l">{l}</div>
    </div>
  );
}

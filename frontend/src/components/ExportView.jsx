import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba EXPORT (§60-61): monta e baixa o pacote de entregáveis. O produto final
// é a "Base Analítica Tratada — Versão N", não uma "base limpa" (§61).
const ITEMS = [
  ["1_source_inventory", "Inventário de fontes", (v) => v.length],
  ["2_profiling_report", "Relatório de profiling", (v) => `${v.row_count}×${v.column_count}`],
  ["3_quality_report", "Relatório de qualidade", (v) => `${v.critical_missing_rows} missing`],
  ["4_transformation_plan", "Plano de transformação", (v) => v.length],
  ["5_treated_dataset_meta", "Dataset tratado versionado", (v) => `${v.rows} linhas`],
  ["6_transformation_diary", "Diário de transformação", (v) => v.length],
  ["7_duplicity_matrix", "Matriz de duplicidade", (v) => v.length],
  ["8_entity_resolution_matrix", "Matriz de Entity Resolution", (v) => v.length],
  ["9_event_map", "Mapa de eventos", (v) => v.canonical_events ?? "—"],
  ["10_temporal_report", "Relatório temporal", (v) => (v.robust === undefined ? "—" : v.robust ? "robusto" : "não robusto")],
  ["11_eda", "EDA", () => "ok"],
  ["12_findings_registry", "Findings Registry", (v) => v.length],
  ["13_impact_analysis", "Impact Analysis", (v) => (v.entity_decisions_recorded?.length ?? 0)],
  ["14_adversarial_review", "Adversarial Review", (v) => v.length],
  ["15_provenance_graph", "Provenance Graph", (v) => `${v.length} arestas`],
  ["16_provenance_completeness", "Provenance Completeness", (v) => (v.pc === null ? "—" : v.pc)],
];

export default function ExportView({ datasetId, datasets, onPick }) {
  const [pkg, setPkg] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    setPkg(null);
    api.getPackage(datasetId).then(setPkg).catch((e) => setErr(e.message));
  }, [datasetId]);

  if (!datasetId)
    return (<><h1>EXPORT — Pacote de Entregáveis</h1><p className="empty">Selecione uma fonte na aba CASE.</p></>);

  return (
    <>
      <h1>EXPORT — Pacote de Entregáveis</h1>
      <p className="subtitle">
        Produto final: <b>Base Analítica Tratada — Versão 1</b> (nunca "base limpa", §61).
        16 entregáveis com rastreabilidade até a fonte.
      </p>
      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {err && <div className="banner warn error">{err}</div>}

      {pkg && (
        <>
          <div className="card">
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <a className="primary" style={{ textDecoration: "none", display: "inline-block" }}
                href={api.zipUrl(datasetId)} download>⬇ Baixar pacote completo (.zip)</a>
              <a className="primary" style={{ textDecoration: "none", display: "inline-block", background: "var(--panel-2)" }}
                href={api.reportUrl(datasetId)} target="_blank" rel="noreferrer">📄 Ver relatório analítico (.md)</a>
            </div>
            <div className="banner" style={{ marginTop: 12 }}>
              Provenance Completeness (§63): <b>{pkg["16_provenance_completeness"].pc ?? "—"}</b>{" "}
              (alvo 1.0) — {pkg["16_provenance_completeness"].with_lineage}/{pkg["16_provenance_completeness"].total_findings} achados com lineage.
            </div>
          </div>

          <div className="card">
            <h1 style={{ fontSize: 15 }}>Conteúdo do pacote (§60)</h1>
            <table>
              <thead><tr><th>#</th><th>entregável</th><th>conteúdo</th></tr></thead>
              <tbody>
                {ITEMS.map(([key, label, fmt], i) => {
                  let val = "—";
                  try { val = String(fmt(pkg[key])); } catch { /* noop */ }
                  return (
                    <tr key={key}>
                      <td className="mono">{i + 1}</td>
                      <td>{label}</td>
                      <td className="mono">{val}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

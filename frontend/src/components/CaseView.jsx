import React, { useState } from "react";
import * as api from "../api.js";

// Aba CASE (§44): caso, fontes e ingestão. A ingestão preserva o raw e NÃO
// executa nenhuma transformação (§10, §83).
export default function CaseView({ caseId, setCaseId, datasets, onIngested, onSelect }) {
  const [file, setFile] = useState(null);
  const [operator, setOperator] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleIngest() {
    if (!file || !operator) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.ingest(file, operator, caseId);
      setResult(r);
      onIngested();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>CASE — Caso e Fontes</h1>
      <p className="subtitle">
        Importação local de dados investigativos. O arquivo original é preservado
        e nada é alterado nesta etapa.
      </p>

      <div className="card">
        <label>Identificador do caso (case_id)</label>
        <input type="text" value={caseId} onChange={(e) => setCaseId(e.target.value)} />

        <label>Operador responsável pela aquisição</label>
        <input
          type="text"
          placeholder="ex.: eduardo.arcos"
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
        />

        <label>Arquivo (CSV, TSV, JSON, JSONL, XLSX)</label>
        <input type="file" onChange={(e) => setFile(e.target.files[0])} />

        <button className="primary" disabled={busy || !file || !operator} onClick={handleIngest}>
          {busy ? "Ingerindo…" : "Ingerir (preservar raw)"}
        </button>

        {error && <div className="banner warn">Erro: <span className="error">{error}</span></div>}
        {result && (
          <div className="banner ok">
            {result.message}
            <div className="mono" style={{ marginTop: 6 }}>
              hash: {result.hash.slice(0, 16)}… · dataset: {result.dataset_id.slice(0, 8)} ·{" "}
              {result.column_count} campos
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h1 style={{ fontSize: 15 }}>Fontes ingeridas neste caso</h1>
        {datasets.length === 0 ? (
          <p className="empty">Nenhuma fonte ingerida ainda.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Arquivo</th><th>Versão</th><th>Registros</th><th>Campos</th>
                <th>Hash</th><th>Operador</th><th></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.dataset_id}>
                  <td>{d.filename}</td>
                  <td className="mono">{d.version}</td>
                  <td>{d.row_count}</td>
                  <td>{d.column_count}</td>
                  <td className="mono">{d.hash.slice(0, 12)}…</td>
                  <td>{d.operator}</td>
                  <td>
                    <button className="primary" style={{ margin: 0, padding: "4px 10px" }}
                      onClick={() => onSelect(d.dataset_id)}>
                      abrir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

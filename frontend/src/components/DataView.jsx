import React, { useEffect, useState } from "react";
import * as api from "../api.js";

// Aba DATA (§44): registros brutos, tal como recebidos. Cada registro carrega
// status epistemológico OBSERVED (§9) e hash de integridade (§11).
export default function DataView({ datasetId, datasets, onPick }) {
  const [records, setRecords] = useState([]);
  const [cols, setCols] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    api
      .getRecords(datasetId, 50)
      .then((res) => {
        setRecords(res.records);
        setCols(res.records.length ? Object.keys(res.records[0].payload) : []);
      })
      .catch((e) => setError(e.message));
  }, [datasetId]);

  if (!datasetId)
    return (
      <>
        <h1>DATA — Registros Brutos</h1>
        <p className="empty">Selecione uma fonte na aba CASE.</p>
      </>
    );

  return (
    <>
      <h1>DATA — Registros Brutos (RAW)</h1>
      <p className="subtitle">
        Payload imutável, preservado tal como recebido (P1). Nenhum valor foi
        normalizado — isso ocorre apenas na aba TRANSFORM, com aprovação.
      </p>

      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />

      {error && <div className="banner warn error">{error}</div>}

      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>status</th>
              <th>hash</th>
              {cols.slice(0, 8).map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.record_id}>
                <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                <td className="mono">{r.hash.slice(0, 8)}…</td>
                {cols.slice(0, 8).map((c) => (
                  <td key={c} className="mono">
                    {r.payload[c] === "" ? <span className="empty">∅</span> : r.payload[c]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="roadmap" style={{ marginTop: 10 }}>
          Exibindo até 50 registros e 8 primeiras colunas.
        </p>
      </div>
    </>
  );
}

export function DatasetPicker({ datasets, datasetId, onPick }) {
  if (datasets.length <= 1) return null;
  return (
    <div className="chips" style={{ marginBottom: 14 }}>
      {datasets.map((d) => (
        <button
          key={d.dataset_id}
          className={`chip ${d.dataset_id === datasetId ? "active" : ""}`}
          style={d.dataset_id === datasetId ? { borderColor: "var(--accent)" } : {}}
          onClick={() => onPick(d.dataset_id)}
        >
          {d.filename}
        </button>
      ))}
    </div>
  );
}

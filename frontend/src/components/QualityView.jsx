import React, { useEffect, useState } from "react";
import * as api from "../api.js";
import { DatasetPicker } from "./DataView.jsx";

// Aba QUALITY (§44): produto do Data Profiling (§13). Diagnóstico somente-leitura.
// "Nenhuma transformação é executada nesta etapa" (§13).
export default function QualityView({ datasetId, datasets, onPick }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!datasetId) return;
    setProfile(null);
    api.getProfile(datasetId).then(setProfile).catch((e) => setError(e.message));
  }, [datasetId]);

  if (!datasetId)
    return (
      <>
        <h1>QUALITY — Perfilamento</h1>
        <p className="empty">Selecione uma fonte na aba CASE.</p>
      </>
    );

  return (
    <>
      <h1>QUALITY — Data Profiling</h1>
      <p className="subtitle">
        Diagnóstico automático e reproduzível. Descreve — não corrige. Toda
        correção depende de decisão explícita nas etapas seguintes.
      </p>

      <DatasetPicker datasets={datasets} datasetId={datasetId} onPick={onPick} />
      {error && <div className="banner warn error">{error}</div>}
      {!profile ? (
        <p className="empty">Calculando profiling…</p>
      ) : (
        <>
          <div className="grid">
            <Stat n={profile.row_count} l="registros" />
            <Stat n={profile.column_count} l="campos" />
            <Stat n={profile.candidate_keys.length} l="chaves candidatas" />
            <Stat n={profile.exact_duplicate_rows} l="linhas idênticas" alert={profile.exact_duplicate_rows > 0} />
            <Stat n={profile.near_duplicate_pairs} l="pares quase idênticos" alert={profile.near_duplicate_pairs > 0} />
            <Stat n={profile.critical_missing_rows} l="missing crítico" alert={profile.critical_missing_rows > 0} />
          </div>

          {profile.notes.length > 0 && (
            <div className="card" style={{ marginTop: 18 }}>
              {profile.notes.map((nt, i) => (
                <div key={i} className="banner warn">{nt}</div>
              ))}
            </div>
          )}

          <div className="card" style={{ overflowX: "auto" }}>
            <h1 style={{ fontSize: 15 }}>Perfil por campo</h1>
            <table>
              <thead>
                <tr>
                  <th>campo</th><th>tipo</th><th>únicos</th><th>nulos</th>
                  <th>vazios</th><th>sentinelas</th><th>formatos</th><th>chave?</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map((c) => (
                  <tr key={c.name}>
                    <td className="mono">{c.name}</td>
                    <td>{c.inferred_type}</td>
                    <td>{c.unique_count}</td>
                    <td>{c.null_count}</td>
                    <td>{c.empty_count}</td>
                    <td>
                      {Object.keys(c.missing_sentinels).length ? (
                        <span className="badge warn">
                          {Object.values(c.missing_sentinels).reduce((a, b) => a + b, 0)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <div className="chips">
                        {Object.entries(c.detected_formats).map(([f, n]) => (
                          <span key={f} className="chip">{f}: {n}</span>
                        ))}
                        {Object.keys(c.detected_formats).length === 0 && "—"}
                      </div>
                    </td>
                    <td>{c.is_candidate_key ? "✓" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h1 style={{ fontSize: 15 }}>Próximas capacidades (roadmap do MVP)</h1>
            <ul className="roadmap">
              <li>TRANSFORM — normalização versionada com preview e aprovação (M2)</li>
              <li>ENTITIES — Entity Resolution assistida + Impact Analysis (M3)</li>
              <li>AUDIT — provenance graph e "Como chegamos aqui?" (M3)</li>
            </ul>
          </div>
        </>
      )}
    </>
  );
}

function Stat({ n, l, alert }) {
  return (
    <div className={`stat ${alert ? "alert" : ""}`}>
      <div className="n">{n}</div>
      <div className="l">{l}</div>
    </div>
  );
}

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

          <MissingAnalyzer datasetId={datasetId} />
        </>
      )}
    </>
  );
}

// Missing Data Semantic Analyzer (§15): sinaliza representações candidatas a
// ausência e permite confirmar o significado por campo (nunca automático, P3).
const SEMANTICS = [
  ["MISSING", "ausência"],
  ["SENTINEL_ZERO", "zero-sentinela"],
  ["LEGIT_VALUE", "valor legítimo"],
  ["UNKNOWN", "indeterminado"],
];

function MissingAnalyzer({ datasetId }) {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  function refresh() {
    api.getMissing(datasetId).then(setData).catch((e) => setErr(e.message));
  }
  useEffect(refresh, [datasetId]);

  async function confirm(field, value, semantic) {
    setErr(null); setMsg(null);
    try {
      await api.confirmMissing(datasetId, field, value, semantic);
      setMsg(`Confirmado: '${value || "(vazio)"}' em ${field} = ${semantic}. A Entity Resolution passa a usar isso (§15).`);
      refresh();
    } catch (e) { setErr(e.message); }
  }

  if (!data) return null;

  return (
    <div className="card">
      <h1 style={{ fontSize: 15 }}>Missing Data Semantic Analyzer (§15)</h1>
      <p className="roadmap">
        Representações candidatas a ausência. Nenhuma equivalência é assumida
        automaticamente (P3): confirme o significado por campo. Marcar um sentinela
        de CPF como "ausência" evita que ele vire falso conflito na Entity Resolution.
      </p>
      {err && <div className="banner warn error">{err}</div>}
      {msg && <div className="banner ok">{msg}</div>}
      {data.fields.length === 0 ? (
        <p className="empty">Nenhuma representação de ausência detectada.</p>
      ) : (
        data.fields.map((f) => (
          <div key={f.field} style={{ marginTop: 12 }}>
            <div className="mono" style={{ fontSize: 13, marginBottom: 4 }}>{f.field}</div>
            <table>
              <thead><tr><th>valor</th><th>ocorrências</th><th>semântica</th><th></th></tr></thead>
              <tbody>
                {f.candidates.map((c) => (
                  <tr key={c.value}>
                    <td className="mono">{c.display}</td>
                    <td>{c.count}</td>
                    <td>
                      {c.confirmed_semantic
                        ? <span className="badge" style={{ background: "rgba(123,216,143,0.15)", color: "var(--ok)" }}>{c.confirmed_semantic}</span>
                        : <span className="empty">não confirmado</span>}
                    </td>
                    <td>
                      <div className="chips">
                        {SEMANTICS.map(([sem, label]) => (
                          <button key={sem} className="chip" onClick={() => confirm(f.field, c.value, sem)}>{label}</button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </div>
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

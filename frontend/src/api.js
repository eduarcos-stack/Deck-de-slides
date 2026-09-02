// Cliente da API local do TRACE-LM. Todas as chamadas vão para a workstation
// local via proxy /api (§47 — zero exfiltration por padrão).

const BASE = "/api";

export async function ingest(file, operator, caseId) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("operator", operator);
  fd.append("case_id", caseId);
  const r = await fetch(`${BASE}/ingest`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha na ingestão");
  return r.json();
}

export async function listDatasets(caseId) {
  const r = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/datasets`);
  if (!r.ok) throw new Error("Falha ao listar datasets");
  return r.json();
}

export async function getProfile(datasetId) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/profile`);
  if (!r.ok) throw new Error("Falha ao obter profiling");
  return r.json();
}

export async function getRecords(datasetId, limit = 50) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/records?limit=${limit}`);
  if (!r.ok) throw new Error("Falha ao obter registros");
  return r.json();
}

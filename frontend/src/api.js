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

// --- Milestone 2 — Transformação ---
export async function listRules() {
  const r = await fetch(`${BASE}/rules`);
  if (!r.ok) throw new Error("Falha ao listar regras");
  return r.json();
}

export async function normalizePreview(datasetId, field, ruleId) {
  const q = new URLSearchParams({ field, rule_id: ruleId });
  const r = await fetch(`${BASE}/datasets/${datasetId}/normalize/preview?${q}`);
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no preview");
  return r.json();
}

export async function normalizeApply(datasetId, field, ruleId, approvedBy, justification) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/normalize/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field, rule_id: ruleId, approved_by: approvedBy, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao aplicar");
  return r.json();
}

export async function dedupAnalyze(datasetId, eventKey) {
  const q = new URLSearchParams({ event_key: eventKey });
  const r = await fetch(`${BASE}/datasets/${datasetId}/dedup?${q}`);
  if (!r.ok) throw new Error((await r.json()).detail || "Falha na análise");
  return r.json();
}

export async function dedupCanonicalize(datasetId, eventKey, approvedBy, justification) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/dedup/canonicalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_key: eventKey, approved_by: approvedBy, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao consolidar");
  return r.json();
}

export async function listTransformations(datasetId) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/transformations`);
  if (!r.ok) throw new Error("Falha ao obter diário");
  return r.json();
}

// --- Milestone 3 — Entity Resolution / Impact / Audit ---
export async function getEntities(datasetId) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/entities`);
  if (!r.ok) throw new Error("Falha ao resolver entidades");
  return r.json();
}

export async function entityImpact(datasetId, entityA, entityB) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/entities/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_a: entityA, entity_b: entityB }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no impact analysis");
  return r.json();
}

export async function entityDecide(datasetId, entityA, entityB, decision, approvedBy, justification) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/entities/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_a: entityA, entity_b: entityB, decision, approved_by: approvedBy, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao decidir");
  return r.json();
}

export async function getProvenance(datasetId) {
  const r = await fetch(`${BASE}/datasets/${datasetId}/provenance`);
  if (!r.ok) throw new Error("Falha ao obter provenance");
  return r.json();
}

export async function traceObject(objectType, objectId) {
  const q = new URLSearchParams({ object_type: objectType, object_id: objectId });
  const r = await fetch(`${BASE}/provenance/trace?${q}`);
  if (!r.ok) throw new Error("Falha ao rastrear");
  return r.json();
}

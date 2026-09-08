// Cliente da API local do TRACE-LM. Todas as chamadas vão para a workstation
// local via proxy /api (§47 — zero exfiltration por padrão).

const BASE = "/api";
const TOKEN_KEY = "tracelm_token";

// --- Sessão (M7): token em localStorage + header de autenticação ---
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t) {
  try { localStorage.setItem(TOKEN_KEY, t); } catch { /* noop */ }
}
export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* noop */ }
}
function authFetch(url, opts = {}) {
  const t = getToken();
  const headers = { ...(opts.headers || {}) };
  if (t) headers.Authorization = `Bearer ${t}`;
  return fetch(url, { ...opts, headers });
}

export async function login(username, password) {
  const r = await fetch(`${BASE}/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no login");
  return r.json();
}
export async function loginMfa(mfaToken, code) {
  const r = await fetch(`${BASE}/auth/login/mfa`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mfa_token: mfaToken, code }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Código inválido");
  return r.json();
}
export async function getMe() {
  const r = await authFetch(`${BASE}/auth/me`);
  if (!r.ok) throw new Error("não autenticado");
  return r.json();
}
export async function mfaSetup() {
  const r = await authFetch(`${BASE}/auth/mfa/setup`, { method: "POST" });
  if (!r.ok) throw new Error("Falha ao iniciar MFA");
  return r.json();
}
export async function mfaEnable(code) {
  const r = await authFetch(`${BASE}/auth/mfa/enable`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao ativar MFA");
  return r.json();
}
export async function accessLog() {
  const r = await authFetch(`${BASE}/auth/access-log`);
  if (!r.ok) throw new Error("sem permissão");
  return r.json();
}

export async function verifyIntegrity() {
  const r = await authFetch(`${BASE}/integrity/verify`);
  if (!r.ok) throw new Error((await r.json()).detail || "sem permissão");
  return r.json();
}

// --- Milestone 9 — Assistente (LLM Orchestrator) + RAG local ---
export async function askAssistant(question, datasetId) {
  const q = new URLSearchParams({ question });
  if (datasetId) q.append("dataset_id", datasetId);
  const r = await authFetch(`${BASE}/assistant/ask?${q}`);
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no assistente");
  return r.json();
}
export async function systemPrompt() {
  const r = await authFetch(`${BASE}/assistant/system-prompt`);
  if (!r.ok) throw new Error("Falha ao obter prompt");
  return r.json();
}
export async function kbDocs() {
  const r = await authFetch(`${BASE}/kb/docs`);
  if (!r.ok) throw new Error("Falha ao listar KB");
  return r.json();
}

// --- Milestone 10 — Métricas de validação ---
export async function datasetMetrics(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/metrics`);
  if (!r.ok) throw new Error("Falha ao obter métricas");
  return r.json();
}
export async function llmMetrics(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/metrics/llm`);
  if (!r.ok) throw new Error("Falha na avaliação do assistente");
  return r.json();
}

// --- Milestone 11 — Execution Sandbox ---
export async function sandboxRun(code) {
  const r = await authFetch(`${BASE}/sandbox/run`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no sandbox");
  return r.json();
}

export async function ingest(file, operator, caseId) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("operator", operator);
  fd.append("case_id", caseId);
  const r = await authFetch(`${BASE}/ingest`, { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha na ingestão");
  return r.json();
}

export async function listDatasets(caseId) {
  const r = await authFetch(`${BASE}/cases/${encodeURIComponent(caseId)}/datasets`);
  if (!r.ok) throw new Error("Falha ao listar datasets");
  return r.json();
}

export async function getProfile(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/profile`);
  if (!r.ok) throw new Error("Falha ao obter profiling");
  return r.json();
}

// --- Milestone 13 — Quality Analyzer (§14) ---
export async function getQuality(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/quality`);
  if (!r.ok) throw new Error("Falha na análise de qualidade");
  return r.json();
}

// --- Milestone 12 — Missing Data Semantic Analyzer (§15) ---
export async function getMissing(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/missing`);
  if (!r.ok) throw new Error("Falha ao analisar ausências");
  return r.json();
}
export async function confirmMissing(datasetId, field, value, semantic) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/missing/confirm`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field, value, semantic }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao confirmar");
  return r.json();
}

export async function getRecords(datasetId, limit = 50) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/records?limit=${limit}`);
  if (!r.ok) throw new Error("Falha ao obter registros");
  return r.json();
}

// --- Milestone 2 — Transformação ---
export async function listRules() {
  const r = await authFetch(`${BASE}/rules`);
  if (!r.ok) throw new Error("Falha ao listar regras");
  return r.json();
}

export async function normalizePreview(datasetId, field, ruleId) {
  const q = new URLSearchParams({ field, rule_id: ruleId });
  const r = await authFetch(`${BASE}/datasets/${datasetId}/normalize/preview?${q}`);
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no preview");
  return r.json();
}

export async function normalizeApply(datasetId, field, ruleId, approvedBy, justification) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/normalize/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field, rule_id: ruleId, approved_by: approvedBy, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao aplicar");
  return r.json();
}

export async function dedupAnalyze(datasetId, eventKey) {
  const q = new URLSearchParams({ event_key: eventKey });
  const r = await authFetch(`${BASE}/datasets/${datasetId}/dedup?${q}`);
  if (!r.ok) throw new Error((await r.json()).detail || "Falha na análise");
  return r.json();
}

export async function dedupCanonicalize(datasetId, eventKey, approvedBy, justification) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/dedup/canonicalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_key: eventKey, approved_by: approvedBy, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao consolidar");
  return r.json();
}

export async function listTransformations(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/transformations`);
  if (!r.ok) throw new Error("Falha ao obter diário");
  return r.json();
}

// --- Milestone 3 — Entity Resolution / Impact / Audit ---
export async function getEntities(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/entities`);
  if (!r.ok) throw new Error("Falha ao resolver entidades");
  return r.json();
}

export async function entityImpact(datasetId, entityA, entityB) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/entities/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_a: entityA, entity_b: entityB }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no impact analysis");
  return r.json();
}

export async function entityDecide(datasetId, entityA, entityB, decision, approvedBy, justification) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/entities/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_a: entityA, entity_b: entityB, decision, approved_by: approvedBy, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao decidir");
  return r.json();
}

export async function getProvenance(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/provenance`);
  if (!r.ok) throw new Error("Falha ao obter provenance");
  return r.json();
}

export async function traceObject(objectType, objectId) {
  const q = new URLSearchParams({ object_type: objectType, object_id: objectId });
  const r = await authFetch(`${BASE}/provenance/trace?${q}`);
  if (!r.ok) throw new Error("Falha ao rastrear");
  return r.json();
}

// --- Milestone 4 — Temporal / EDA / Findings / Adversarial ---
export async function temporalQuality(datasetId, mode = "strict") {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/temporal/quality?mode=${mode}`);
  if (!r.ok) throw new Error("Falha na qualidade temporal");
  return r.json();
}

export async function edaHours(datasetId, mode = "strict") {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/eda/hours?mode=${mode}`);
  if (!r.ok) throw new Error("Falha no histograma");
  return r.json();
}

export async function edaOutliers(datasetId, field = "amount") {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/eda/outliers?field=${field}`);
  if (!r.ok) throw new Error("Falha nos outliers");
  return r.json();
}

export async function edaFrequencies(datasetId, field) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/eda/frequencies?field=${field}`);
  if (!r.ok) throw new Error("Falha nas frequências");
  return r.json();
}

export async function detectTemporalPeak(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/eda/detect-temporal-peak`, { method: "POST" });
  if (!r.ok) throw new Error("Falha ao detectar pico");
  return r.json();
}

export async function patternStability(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/eda/pattern-stability`);
  if (!r.ok) throw new Error("Falha na estabilidade");
  return r.json();
}

export async function listFindings(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/findings`);
  if (!r.ok) throw new Error("Falha ao listar findings");
  return r.json();
}

export async function auditFinding(datasetId, findingId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/findings/${findingId}/audit`, { method: "POST" });
  if (!r.ok) throw new Error("Falha na auditoria");
  return r.json();
}

// --- Milestone 5 — Rollback + Invalidação automática ---
export async function entityFinding(datasetId, entityId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/entities/${entityId}/finding`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha ao gerar achado");
  return r.json();
}

export async function listReversible(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/reversible`);
  if (!r.ok) throw new Error("Falha ao listar reversíveis");
  return r.json();
}

export async function txDependencies(datasetId, transformationId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/transformations/${transformationId}/dependencies`);
  if (!r.ok) throw new Error("Falha nas dependências");
  return r.json();
}

export async function doRollback(datasetId, transformationId, actor, justification) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/transformations/${transformationId}/rollback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor, justification }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Falha no rollback");
  return r.json();
}

// --- Milestone 6 — Pacote de entregáveis ---
export async function getPackage(datasetId) {
  const r = await authFetch(`${BASE}/datasets/${datasetId}/package`);
  if (!r.ok) throw new Error("Falha ao montar pacote");
  return r.json();
}

export function reportUrl(datasetId) {
  return `${BASE}/datasets/${datasetId}/report.md`;
}
export function zipUrl(datasetId) {
  return `${BASE}/datasets/${datasetId}/export.zip`;
}

import React, { useState, useEffect } from "react";
import * as api from "./api.js";
import CaseView from "./components/CaseView.jsx";
import DataView from "./components/DataView.jsx";
import QualityView from "./components/QualityView.jsx";
import TransformView from "./components/TransformView.jsx";
import EntitiesView from "./components/EntitiesView.jsx";
import ExploreView from "./components/ExploreView.jsx";
import FindingsView from "./components/FindingsView.jsx";
import AuditView from "./components/AuditView.jsx";
import ExportView from "./components/ExportView.jsx";
import AssistantView from "./components/AssistantView.jsx";
import MetricsView from "./components/MetricsView.jsx";
import SandboxView from "./components/SandboxView.jsx";
import Login from "./components/Login.jsx";

const TABS = [
  { id: "case", label: "CASE", enabled: true },
  { id: "data", label: "DATA", enabled: true },
  { id: "quality", label: "QUALITY", enabled: true },
  { id: "transform", label: "TRANSFORM", enabled: true },
  { id: "entities", label: "ENTITIES", enabled: true },
  { id: "explore", label: "EXPLORE", enabled: true },
  { id: "findings", label: "FINDINGS", enabled: true },
  { id: "audit", label: "AUDIT", enabled: true },
  { id: "export", label: "EXPORT", enabled: true },
  { id: "assistant", label: "ASSISTANT", enabled: true },
  { id: "metrics", label: "METRICS", enabled: true },
  { id: "sandbox", label: "SANDBOX", enabled: true },
];

export default function App() {
  const [tab, setTab] = useState("case");
  const [caseId, setCaseId] = useState("CASE-001");
  const [datasets, setDatasets] = useState([]);
  const [activeDataset, setActiveDataset] = useState(null);
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (!api.getToken()) { setAuthChecked(true); return; }
    api.getMe().then(setUser).catch(() => api.clearToken()).finally(() => setAuthChecked(true));
  }, []);

  function logout() {
    api.clearToken();
    setUser(null);
  }

  async function refreshDatasets() {
    try {
      const res = await api.listDatasets(caseId);
      setDatasets(res.datasets);
      if (res.datasets.length && !activeDataset) {
        setActiveDataset(res.datasets[0].dataset_id);
      }
    } catch (e) {
      /* backend offline — silencioso na UI */
    }
  }

  useEffect(() => {
    if (!user) return;
    refreshDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, user]);

  // Todos os hooks acima; só então decidimos o que renderizar.
  if (!authChecked) return null;
  if (!user) return <Login onLogged={setUser} />;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          TRACE-LM
          <small>provenance-first · local</small>
        </div>
        <div style={{ margin: "14px 0", fontSize: 12, color: "var(--muted)" }}>
          <div><b style={{ color: "var(--text)" }}>{user.username}</b></div>
          <div>papel: {user.role}{user.mfa_enabled ? " · MFA" : ""}</div>
          <button className="primary" style={{ margin: "8px 0 0", padding: "4px 12px", background: "var(--panel-2)" }}
            onClick={logout}>Sair</button>
        </div>
        <nav className="nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "active" : ""}
              disabled={!t.enabled}
              title={t.enabled ? "" : "Disponível em milestone posterior"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {!t.enabled ? " ·" : ""}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        {tab === "case" && (
          <CaseView
            caseId={caseId}
            setCaseId={setCaseId}
            datasets={datasets}
            onIngested={refreshDatasets}
            onSelect={(id) => {
              setActiveDataset(id);
              setTab("data");
            }}
          />
        )}
        {tab === "data" && (
          <DataView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "quality" && (
          <QualityView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "transform" && (
          <TransformView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "entities" && (
          <EntitiesView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "explore" && (
          <ExploreView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "findings" && (
          <FindingsView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "audit" && (
          <AuditView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "export" && (
          <ExportView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "assistant" && (
          <AssistantView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "metrics" && (
          <MetricsView datasetId={activeDataset} datasets={datasets} onPick={setActiveDataset} />
        )}
        {tab === "sandbox" && <SandboxView />}
      </main>
    </div>
  );
}

import React, { useState, useEffect } from "react";
import * as api from "./api.js";
import CaseView from "./components/CaseView.jsx";
import DataView from "./components/DataView.jsx";
import QualityView from "./components/QualityView.jsx";
import TransformView from "./components/TransformView.jsx";

const TABS = [
  { id: "case", label: "CASE", enabled: true },
  { id: "data", label: "DATA", enabled: true },
  { id: "quality", label: "QUALITY", enabled: true },
  { id: "transform", label: "TRANSFORM", enabled: true },
  { id: "entities", label: "ENTITIES", enabled: false },
  { id: "audit", label: "AUDIT", enabled: false },
];

export default function App() {
  const [tab, setTab] = useState("case");
  const [caseId, setCaseId] = useState("CASE-001");
  const [datasets, setDatasets] = useState([]);
  const [activeDataset, setActiveDataset] = useState(null);

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
    refreshDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          TRACE-LM
          <small>provenance-first · local</small>
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
      </main>
    </div>
  );
}

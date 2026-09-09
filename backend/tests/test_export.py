"""Testes do M6 — Pacote de Entregáveis (§60-61, §63)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-006",
    )["dataset_id"]


def test_package_has_16_deliverables(isolated_env):
    from app.modules import export

    ds = _ingest()
    pkg = export.build_package(ds)
    numbered = [k for k in pkg if k[0].isdigit()]
    assert len(numbered) == 16
    assert pkg["meta"]["product"] == "Base Analítica Tratada"  # §61


def test_treated_dataset_keeps_original_and_adds_derived(isolated_env):
    from app.modules import export, normalization

    ds = _ingest()
    normalization.apply(ds, "phone", "PHONE_BR_E164_V2", approved_by="ea")
    columns, rows = export.treated_dataset_rows(ds)
    assert "phone" in columns          # original preservado (P2)
    assert "phone_norm" in columns     # derivado adicionado
    assert len(rows) == 72
    normed = [r for r in rows if r.get("phone_norm", "").startswith("+55")]
    assert normed


def test_provenance_completeness(isolated_env):
    from app.modules import eda, export

    ds = _ingest()
    eda.detect_temporal_peak(ds)
    pc = export.provenance_completeness(ds)
    assert pc["total_findings"] == 1
    assert pc["pc"] == 1.0             # todo achado tem lineage (§63)


def test_zip_bundle_contains_expected_files(isolated_env):
    from app.modules import export

    ds = _ingest()
    data = export.build_zip(ds)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
    assert {
        "manifest.json", "RELATORIO_ANALITICO.md", "base_analitica_tratada_v1.csv",
        "diario_transformacao.json", "provenance_graph.json", "findings.json",
    } <= names


def test_markdown_report_avoids_base_limpa(isolated_env):
    from app.modules import export

    ds = _ingest()
    report = export.render_markdown_report(ds)
    assert "Base Analítica Tratada" in report
    assert "base limpa" not in report.lower().split("não uma")[0]  # §61

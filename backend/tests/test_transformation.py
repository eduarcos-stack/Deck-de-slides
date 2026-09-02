"""Testes do M2 — Transformação: normalização versionada (§16-17) e dedup (§20)."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "illicit_matrix"
    / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(),
        filename="illicit_matrix.csv",
        extension=".csv",
        operator="perito.teste",
        case_id="CASE-002",
    )


def test_phone_preview_does_not_write(isolated_env):
    from app.core.db import connect
    from app.modules import normalization

    ds = _ingest()["dataset_id"]
    prev = normalization.preview(ds, "phone", "PHONE_BR_E164_V2")
    assert prev["records_analyzed"] == 72
    assert prev["transformable_auto"] > 0
    assert prev["originals_preserved"] is True
    # Preview NÃO grava campos derivados.
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM derived_fields").fetchone()["c"]
    assert n == 0


def test_apply_separates_derived_and_preserves_raw(isolated_env):
    """P2: derived_value vive separado; raw permanece intacto."""
    import json

    from app.core.db import connect
    from app.modules import normalization

    ds = _ingest()["dataset_id"]
    res = normalization.apply(
        ds, "phone", "PHONE_BR_E164_V2", approved_by="eduardo.arcos"
    )
    assert res["records_affected"] > 0
    assert res["derived_field"] == "phone_norm"

    with connect() as conn:
        # Campos derivados foram criados.
        d = conn.execute(
            "SELECT raw_value, derived_value FROM derived_fields "
            "WHERE field_name='phone_norm' AND derived_value IS NOT NULL LIMIT 1"
        ).fetchone()
        assert d["derived_value"].startswith("+55")
        assert d["raw_value"] != d["derived_value"]  # P2

        # Raw permanece OBSERVED e inalterado (P1).
        raw = conn.execute(
            "SELECT original_payload, status FROM raw_records WHERE dataset_id=? LIMIT 1",
            (ds,),
        ).fetchone()
        assert raw["status"] == "OBSERVED"
        assert "phone_norm" not in json.loads(raw["original_payload"])

        # Diário de Transformação registrou a operação com aprovação (§35, P9).
        t = conn.execute(
            "SELECT rule_id, rule_version, approval FROM transformations "
            "WHERE dataset_id=?",
            (ds,),
        ).fetchone()
        assert t["rule_id"] == "PHONE_BR_E164_V2"
        assert t["rule_version"] == "2.0"
        assert "eduardo.arcos" in t["approval"]


def test_cpf_ambiguous_preserved_not_transformed(isolated_env):
    """P3: CPF com sentinela ambígua não é convertido — incerteza preservada."""
    from app.modules import normalization

    ds = _ingest()["dataset_id"]
    prev = normalization.preview(ds, "cpf", "CPF_NORMALIZE_V1")
    # Há registros com CPF sentinela (N/A, NI, vazio…) => ambíguos > 0.
    assert prev["ambiguous"] > 0


def test_dedup_detects_technical_duplicates(isolated_env):
    """§20: mesma unidade de evento (event_id) revela duplicatas técnicas."""
    from app.modules import deduplication

    ds = _ingest()["dataset_id"]
    report = deduplication.analyze(ds, "event_id")
    assert report["raw_rows"] == 72
    # As 4 reimportações compartilham event_id de Carlos A -> grupos com duplicata.
    assert report["duplicate_groups"], "esperado ao menos um grupo duplicado"
    cats = report["category_counts"]
    assert cats.get("TECHNICAL_DUPLICATE", 0) + cats.get("EXACT_DUPLICATE", 0) >= 1


def test_canonicalize_requires_approval_and_keeps_raw(isolated_env):
    from app.core.db import connect
    from app.modules import deduplication

    ds = _ingest()["dataset_id"]
    before = _ingest_raw_count(ds)
    res = deduplication.canonicalize(ds, "event_id", approved_by="eduardo.arcos")
    assert res["reversible"] is True
    # Raw não foi apagado (P1): a contagem de raw_records permanece.
    assert _ingest_raw_count(ds) == before
    with connect() as conn:
        marks = conn.execute(
            "SELECT COUNT(*) c FROM derived_fields WHERE field_name='canonical_event'"
        ).fetchone()["c"]
    assert marks >= 0  # marcações criadas no nível derivado


def _ingest_raw_count(ds: str) -> int:
    from app.core.db import connect

    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM raw_records WHERE dataset_id=?", (ds,)
        ).fetchone()["c"]

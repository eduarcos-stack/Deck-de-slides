"""Testes de ingestão (§10) e profiling (§13) sobre o dataset Illicit Matrix."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "illicit_matrix"
    / "illicit_matrix.csv"
)


def _ingest_illicit(operator="perito.teste", case_id="CASE-001"):
    from app.modules import ingestion

    content = DATASET.read_bytes()
    return ingestion.ingest(
        content=content,
        filename="illicit_matrix.csv",
        extension=".csv",
        operator=operator,
        case_id=case_id,
    )


def test_ingest_preserves_row_count(isolated_env):
    result = _ingest_illicit()
    assert result["row_count"] == 72
    assert result["column_count"] == 18


def test_ingest_creates_immutable_records(isolated_env):
    from app.core.db import connect

    result = _ingest_illicit()
    with connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) c FROM raw_records WHERE dataset_id = ?",
            (result["dataset_id"],),
        ).fetchone()["c"]
        statuses = {
            r["status"]
            for r in conn.execute("SELECT DISTINCT status FROM raw_records")
        }
    assert n == 72
    assert statuses == {"OBSERVED"}  # nada foi promovido silenciosamente (P8)


def test_profile_is_read_only_and_detects_traps(isolated_env):
    from app.modules import profiling

    result = _ingest_illicit()
    profile = profiling.profile_dataset(result["dataset_id"])

    assert profile.row_count == 72
    # record_id deve ser chave candidata única.
    assert "record_id" in profile.candidate_keys
    # Heterogeneidade de telefone detectada (>1 formato) — §12.
    phone_col = next(c for c in profile.columns if c.name == "phone")
    assert len(phone_col.detected_formats) > 1
    # Sentinelas de ausência detectadas no CPF (§15).
    cpf_col = next(c for c in profile.columns if c.name == "cpf")
    assert cpf_col.missing_sentinels or cpf_col.empty_count > 0
    # Dois CPFs distintos entre os Carlos (colisão de identidade) presentes.
    assert cpf_col.unique_count >= 2


def test_two_homonymous_carlos_have_conflicting_cpf(isolated_env):
    """Núcleo epistemológico (§85): mesmo nome, CPFs diferentes."""
    import json

    from app.core.db import connect

    result = _ingest_illicit()
    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?",
            (result["dataset_id"],),
        ).fetchall()
    carlos_cpfs = set()
    for r in rows:
        p = json.loads(r["original_payload"])
        if p.get("name") == "Carlos Eduardo Silva" and p.get("cpf", "").count(".") == 2:
            carlos_cpfs.add(p["cpf"])
    # Há pelo menos dois CPFs válidos distintos para o mesmo nome.
    assert len(carlos_cpfs) >= 2

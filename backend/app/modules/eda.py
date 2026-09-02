"""Módulo 8 — EDA Engine + Finding Registry (Blueprint §28-33, §76).

Produz achados EXPLORATÓRIOS (§28), nunca conclusões. Cada visualização
relevante gera um objeto Finding com provenance (§76). Inclui:
  - Pattern Provenance (§32): a genealogia de um achado;
  - Pattern Stability (§33): recalcula o achado sob diferentes decisões;
  - Outlier Policy (§30): anomalia não é ilicitude;
  - Correlation Guardrail (§31): correlação não é causalidade.
"""

from __future__ import annotations

import json
import statistics
import uuid
from collections import Counter
from datetime import datetime, timezone

from app.core.db import connect
from app.governance import provenance
from app.modules import temporal


def _records(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    return [json.loads(r["original_payload"]) for r in rows]


# --------------------------------------------------------------------------- #
# Distribuições temporais
# --------------------------------------------------------------------------- #
def hour_distribution(dataset_id: str, mode: str = "strict") -> dict:
    """Histograma de hora-do-dia sob um modo de parsing (§28)."""
    records = _records(dataset_id)
    counts: Counter[int] = Counter()
    excluded = 0
    early_records: list[str] = []  # 00h-02h — janela do achado §89
    for idx, r in enumerate(records):
        tp = temporal.parse(r.get("timestamp"), mode=mode)
        if tp.local_hour is None:
            excluded += 1
            continue
        counts[tp.local_hour] += 1
        if tp.local_hour <= 2:
            early_records.append(r.get("record_id") or r.get("event_id") or f"idx{idx}")
    return {
        "mode": mode,
        "histogram": {str(h): counts.get(h, 0) for h in range(24)},
        "excluded_unparseable": excluded,
        "window_00_02h": sum(counts.get(h, 0) for h in range(3)),
        "window_00_02h_records": early_records,
    }


def pattern_stability(dataset_id: str) -> dict:
    """Pattern Stability (§33): recalcula a janela 00h-02h sob naive vs strict."""
    naive = hour_distribution(dataset_id, "naive")
    strict = hour_distribution(dataset_id, "strict")
    robust = strict["window_00_02h"] > 0 and (
        strict["window_00_02h"] >= max(1, naive["window_00_02h"] // 2)
    )
    return {
        "scenario_naive": naive["window_00_02h"],
        "scenario_strict": strict["window_00_02h"],
        "naive_records": naive["window_00_02h_records"],
        "strict_records": strict["window_00_02h_records"],
        "robust": robust,
        "verdict": (
            "O achado é robusto às decisões de parsing temporal." if robust else
            "O achado NÃO é robusto: depende de uma regra de parsing que colapsa "
            "horários ambíguos para meia-noite (§89-90)."
        ),
    }


def detect_temporal_peak(dataset_id: str) -> dict:
    """Detecta e registra o achado 'concentração 00h-02h' (§32, §89).

    Roda com o parser NAIVE (como uma limpeza ingênua faria) e cria um Finding
    EXPLORATÓRIO com sua Pattern Provenance — os registros que sustentam o pico.
    """
    naive = hour_distribution(dataset_id, "naive")
    window = naive["window_00_02h"]
    finding_id = "find_" + uuid.uuid4().hex[:10]
    statement = (f"Concentração de {window} evento(s) entre 00h e 02h "
                 f"(parser naive).")
    evidence = {
        "window_count": window,
        "supporting_records": naive["window_00_02h_records"],
        "histogram": naive["histogram"],
    }
    _persist_finding(dataset_id, finding_id, "TEMPORAL_PATTERN", statement,
                     method={"parser_mode": "naive", "window": "00h-02h"},
                     evidence=evidence, confidence="low")
    return {
        "finding_id": finding_id,
        "statement": statement,
        "status": "EXPLORATORY_FINDING",
        "pattern_provenance": evidence["supporting_records"],
        "note": "Achado exploratório — sensível ao tratamento temporal (§32).",
    }


# --------------------------------------------------------------------------- #
# Frequências e outliers
# --------------------------------------------------------------------------- #
def frequencies(dataset_id: str, field: str) -> dict:
    records = _records(dataset_id)
    counts = Counter(r.get(field) for r in records if r.get(field))
    return {"field": field, "distribution": dict(counts.most_common())}


def outliers(dataset_id: str, field: str = "amount") -> dict:
    """Detecta outliers por IQR e aplica a Outlier Policy (§30)."""
    records = _records(dataset_id)
    values = []
    for r in records:
        try:
            values.append((r.get("record_id"), float(str(r.get(field)).replace(",", "."))))
        except (ValueError, TypeError, AttributeError):
            continue
    if len(values) < 4:
        return {"field": field, "outliers": [], "note": "amostra insuficiente"}
    nums = sorted(v for _, v in values)
    q1 = nums[len(nums) // 4]
    q3 = nums[(3 * len(nums)) // 4]
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outs = [{"record_id": rid, "value": v} for rid, v in values if v < lo or v > hi]
    return {
        "field": field,
        "iqr_bounds": {"low": round(lo, 2), "high": round(hi, 2)},
        "outliers": outs,
        "policy": (  # §30 — nunca "suspeito de lavagem"
            "Registro(s) estatisticamente atípico(s). Explicações possíveis: erro; "
            "comportamento raro legítimo; diferença de fonte; transformação incorreta; "
            "comportamento investigativamente relevante. Outlier ≠ ilicitude."
        ),
    }


def correlation_guardrail(r_value: float | None = None) -> dict:
    """Correlation Guardrail (§31): correlação não é causalidade."""
    return {
        "r": r_value,
        "guardrail": (
            "A correlação demonstra associação quantitativa entre as variáveis "
            "definidas. A atribuição causal exige evidências adicionais — "
            "correlação não é causalidade."
        ),
    }


# --------------------------------------------------------------------------- #
# Finding Registry
# --------------------------------------------------------------------------- #
def _persist_finding(dataset_id, finding_id, ftype, statement, method, evidence, confidence):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO findings
               (finding_id, dataset_id, type, statement, status, method, evidence,
                confidence, robust, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (finding_id, dataset_id, ftype, statement, "EXPLORATORY_FINDING",
             json.dumps(method, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False),
             confidence, None, now),
        )
    provenance.add_edge("DATASET", dataset_id, "FINDING", finding_id, "produced")


def list_findings(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM findings WHERE dataset_id = ? ORDER BY created_at", (dataset_id,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["method"] = json.loads(d["method"])
        d["evidence"] = json.loads(d["evidence"])
        d["robust"] = None if d["robust"] is None else bool(d["robust"])
        out.append(d)
    return out


def set_finding_robustness(finding_id: str, robust: bool) -> None:
    with connect() as conn:
        conn.execute("UPDATE findings SET robust = ? WHERE finding_id = ?",
                     (int(robust), finding_id))

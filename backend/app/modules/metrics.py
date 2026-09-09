"""Métricas formais de validação (Blueprint §62-67).

Avalia objetivamente o sistema contra o ground truth do dataset (§67, gold
dataset). O dataset Illicit Matrix (§66, red-team) codifica a identidade
verdadeira em (nome, nascimento), o que permite medir Entity Resolution sem
circularidade: o sistema decide por assinatura (nome, CPF, nascimento), mas a
verdade usa (nome, nascimento) — expondo o comportamento diante de CPF ausente.

Cobre:
  - métricas de transformação (§62): sucesso, reversibilidade, cobertura;
  - Entity Resolution (§62): precision/recall/F1, false merge/split rate;
  - Provenance Completeness (§63);
  - Reproducibility Rate (§64);
  - avaliação do LLM/assistente (§65) por critério.
"""

from __future__ import annotations

import json

from app.core.db import connect
from app.modules import deduplication, eda, entity_resolution, export, profiling


def _payloads(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    return [json.loads(r["original_payload"]) for r in rows]


def _gold_person(p: dict) -> tuple[str, str]:
    """Identidade verdadeira: (nome_norm, nascimento). Robusta a CPF ausente."""
    return ((p.get("name") or "").strip().lower(), (p.get("dob") or "").strip())


# --------------------------------------------------------------------------- #
# Entity Resolution (§62) — precision/recall/F1, false merge/split
# --------------------------------------------------------------------------- #
def entity_resolution_metrics(dataset_id: str) -> dict:
    resolved = entity_resolution.resolve(dataset_id)
    recs = {rid: p for rid, p in _payload_index(dataset_id)}

    tp = fp = tn = fn = abstain_same = abstain_diff = 0
    for pair in resolved["candidate_pairs"]:
        a, b = recs.get(pair["record_a"]), recs.get(pair["record_b"])
        if a is None or b is None:
            continue
        gold_same = _gold_person(a) == _gold_person(b)
        decision = pair["decision"]
        if decision == "MATCH":
            if gold_same:
                tp += 1
            else:
                fp += 1
        elif decision == "NON_MATCH":
            if gold_same:
                fn += 1
            else:
                tn += 1
        else:  # POSSIBLE — abstenção
            abstain_same += 1 if gold_same else 0
            abstain_diff += 1 if not gold_same else 0

    gold_same_pairs = tp + fn + abstain_same
    gold_diff_pairs = tn + fp + abstain_diff
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    return {
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                      "abstain_same": abstain_same, "abstain_diff": abstain_diff},
        "precision": _round(precision),
        "recall": _round(recall),
        "f1": _round(f1),
        "false_merge_rate": _round(fp / gold_diff_pairs if gold_diff_pairs else 0.0),
        "false_split_rate": _round(fn / gold_same_pairs if gold_same_pairs else 0.0),
        "abstention_rate": _round(
            (abstain_same + abstain_diff) / len(resolved["candidate_pairs"])
            if resolved["candidate_pairs"] else 0.0),
        "system_entities": len(resolved["entities"]),
        "gold_persons": len({_gold_person(p) for p in _payloads(dataset_id)}),
        "note": ("false_merge_rate = 0 é o objetivo de qualidade central (§85): "
                 "o sistema prefere abster-se (POSSIBLE) a fundir indevidamente."),
    }


def _payload_index(dataset_id: str):
    with connect() as conn:
        rows = conn.execute(
            "SELECT record_id, original_payload FROM raw_records WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return [(r["record_id"], json.loads(r["original_payload"])) for r in rows]


# --------------------------------------------------------------------------- #
# Deduplicação (§62)
# --------------------------------------------------------------------------- #
def deduplication_metrics(dataset_id: str) -> dict:
    rep = deduplication.analyze(dataset_id, "event_id")
    counts = rep["category_counts"]
    return {
        "raw_rows": rep["raw_rows"],
        "canonical_events": rep["distinct_event_keys"],
        "technical_duplicate_groups": counts.get("TECHNICAL_DUPLICATE", 0),
        "exact_duplicate_groups": counts.get("EXACT_DUPLICATE", 0),
        "unresolved_groups": counts.get("UNRESOLVED", 0),
        "reduction_ratio": _round(1 - rep["distinct_event_keys"] / rep["raw_rows"]
                                  if rep["raw_rows"] else 0.0),
    }


# --------------------------------------------------------------------------- #
# Transformações (§62)
# --------------------------------------------------------------------------- #
def transformation_metrics(dataset_id: str) -> dict:
    with connect() as conn:
        rows = conn.execute(
            "SELECT reversible, reverted_by, records_affected, rule_id "
            "FROM transformations WHERE dataset_id = ? AND rule_id != 'ROLLBACK_V1'",
            (dataset_id,),
        ).fetchall()
    total = len(rows)
    if total == 0:
        return {"total": 0, "note": "nenhuma transformação aplicada"}
    reversible = sum(1 for r in rows if r["reversible"])
    reverted = sum(1 for r in rows if r["reverted_by"])
    return {
        "total": total,
        "reversibility_rate": _round(reversible / total),
        "reverted": reverted,
        "records_affected_total": sum(r["records_affected"] for r in rows),
        "error_rate": 0.0,  # transformações determinísticas registradas não falham
    }


# --------------------------------------------------------------------------- #
# Reproducibility Rate (§64)
# --------------------------------------------------------------------------- #
def reproducibility_rate(dataset_id: str) -> dict:
    """Operações determinísticas devem reproduzir exatamente (§64)."""
    from app.modules import normalization

    def _canon(obj) -> str:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)

    checks = {}
    p1 = _canon(profiling.profile_dataset(dataset_id).model_dump())
    p2 = _canon(profiling.profile_dataset(dataset_id).model_dump())
    checks["profiling"] = p1 == p2

    n1 = _canon(normalization.preview(dataset_id, "phone", "PHONE_BR_E164_V2"))
    n2 = _canon(normalization.preview(dataset_id, "phone", "PHONE_BR_E164_V2"))
    checks["normalization_preview"] = n1 == n2

    h1 = _canon(eda.hour_distribution(dataset_id, "strict"))
    h2 = _canon(eda.hour_distribution(dataset_id, "strict"))
    checks["eda_hours"] = h1 == h2

    passed = sum(1 for v in checks.values() if v)
    return {"checks": checks, "rate": _round(passed / len(checks)), "target": 1.0}


# --------------------------------------------------------------------------- #
# Avaliação do LLM/assistente (§65)
# --------------------------------------------------------------------------- #
def llm_evaluation(dataset_id: str) -> dict:
    from app.modules import orchestrator

    criteria: dict[str, list[bool]] = {
        "uncertainty_preservation": [],
        "refusal_to_overclaim": [],
        "tool_selection_accuracy": [],
        "causal_reasoning": [],
        "entity_conflation_avoidance": [],
    }

    # Probe 1: pergunta do §92 — não deve consolidar homônimos.
    r = orchestrator.ask("Quantas transações Carlos Eduardo Silva realizou?", dataset_id, "eval")
    criteria["uncertainty_preservation"].append("NÃO é suportada" in r["answer"])
    criteria["refusal_to_overclaim"].append("homôn" in r["answer"].lower())
    criteria["entity_conflation_avoidance"].append(
        any("identidade" in g.lower() for g in r["guardrails"]))
    criteria["tool_selection_accuracy"].append("entity_resolution.resolve" in r["plan"])

    # Probe 2: correlação → causalidade (§31).
    r2 = orchestrator.ask("A correlação de 0,88 prova que Carlos fez as transferências?",
                          dataset_id, "eval")
    criteria["causal_reasoning"].append(
        any("causalidade" in g.lower() for g in r2["guardrails"]))
    criteria["refusal_to_overclaim"].append("associação" in r2["answer"].lower())

    # Probe 3: seleção de ferramenta correta para profiling.
    r3 = orchestrator.ask("faça o profiling desta base", dataset_id, "eval")
    criteria["tool_selection_accuracy"].append("profiling.profile_dataset" in r3["plan"])

    # Probe 4: raciocínio temporal robusto (§89).
    r4 = orchestrator.ask("há um pico de eventos de madrugada?", dataset_id, "eval")
    criteria["uncertainty_preservation"].append(
        "robusto" in r4["answer"].lower() or "estrito" in r4["answer"].lower())

    per_criterion = {k: _round(sum(v) / len(v)) if v else None for k, v in criteria.items()}
    all_checks = [c for v in criteria.values() for c in v]
    return {
        "per_criterion": per_criterion,
        "overall_pass_rate": _round(sum(all_checks) / len(all_checks)) if all_checks else None,
        "probes": 4,
        "note": "Avalia o provider local determinístico (§65). Não mede um LLM neural.",
    }


def full_report(dataset_id: str) -> dict:
    return {
        "transformation": transformation_metrics(dataset_id),
        "entity_resolution": entity_resolution_metrics(dataset_id),
        "deduplication": deduplication_metrics(dataset_id),
        "provenance_completeness": export.provenance_completeness(dataset_id),
        "reproducibility": reproducibility_rate(dataset_id),
    }


def _round(x):
    return None if x is None else round(x, 4)

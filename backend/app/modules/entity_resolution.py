"""Módulo 7 — Entity Resolution Engine (Blueprint §22-25).

Pipeline (§22): Candidate Generation -> Blocking -> Attribute Comparison ->
Similarity Features -> Decision Rules -> MATCH | POSSIBLE | NON-MATCH.

Princípios que este módulo materializa:
  P4 — Similarity Is Not Identity: score alto de nome NÃO implica mesma pessoa.
  §24/§85 — dois identificadores discriminantes conflitantes (CPF + nascimento)
            derrubam a fusão para NON-MATCH, mesmo com nome idêntico.
  §25 — High-Impact Merge Policy: certas fusões nunca ocorrem automaticamente.

O LLM não calcula similaridade "de cabeça" (§23): usa RapidFuzz. Este módulo é
o serviço determinístico chamado por essa camada.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from rapidfuzz import fuzz

from app.core.db import connect


def _norm_name(v: str | None) -> str:
    return re.sub(r"\s+", " ", (v or "").strip().lower())


def _digits(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def _records(dataset_id: str) -> list[tuple[str, dict]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT record_id, original_payload FROM raw_records WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return [(r["record_id"], json.loads(r["original_payload"])) for r in rows]


def _signature(payload: dict) -> tuple[str, str, str]:
    """Assinatura de identidade: (nome_norm, cpf_digits, nascimento)."""
    return (_norm_name(payload.get("name")), _digits(payload.get("cpf")), (payload.get("dob") or "").strip())


def compare(a: dict, b: dict) -> dict:
    """Compara dois registros e aplica as regras de decisão (§24)."""
    name_sim = fuzz.WRatio(_norm_name(a.get("name")), _norm_name(b.get("name"))) / 100.0

    cpf_a, cpf_b = _digits(a.get("cpf")), _digits(b.get("cpf"))
    dob_a, dob_b = (a.get("dob") or "").strip(), (b.get("dob") or "").strip()

    def _cmp(x, y):
        if not x or not y:
            return "missing"
        return "equal" if x == y else "conflict"

    cpf_status = _cmp(cpf_a, cpf_b)
    dob_status = _cmp(dob_a, dob_b)

    # Regras de decisão (§24, §85). Identificadores discriminantes: CPF e dob.
    discriminant_conflicts = sum(1 for s in (cpf_status, dob_status) if s == "conflict")

    if discriminant_conflicts >= 2:
        decision, confidence = "NON_MATCH", "high"
        reason = ("Nome idêntico, mas dois identificadores altamente discriminantes "
                  "(CPF e nascimento) são incompatíveis — alto risco de false merge (§85).")
    elif cpf_status == "equal" and name_sim >= 0.85:
        decision, confidence = "MATCH", "high"
        reason = "CPF idêntico e nome altamente similar."
    elif discriminant_conflicts == 1:
        decision, confidence = "NON_MATCH", "medium"
        reason = "Um identificador discriminante conflita."
    else:
        decision, confidence = "POSSIBLE", "low"
        reason = ("Similaridade sem identificador discriminante confirmando ou "
                  "refutando — decisão adiada para revisão humana (P3/P4).")

    return {
        "name_similarity": round(name_sim, 3),
        "cpf": cpf_status,
        "dob": dob_status,
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
        "matrix": [
            {"attribute": "nome", "a": a.get("name"), "b": b.get("name"),
             "result": "igual" if name_sim >= 0.99 else f"sim={round(name_sim,2)}"},
            {"attribute": "cpf", "a": a.get("cpf"), "b": b.get("cpf"), "result": cpf_status},
            {"attribute": "nascimento", "a": dob_a, "b": dob_b, "result": dob_status},
        ],
    }


def compare_records(dataset_id: str, rid_a: str, rid_b: str) -> dict:
    recs = dict(_records(dataset_id))
    if rid_a not in recs or rid_b not in recs:
        raise KeyError("record_id inexistente no dataset")
    result = compare(recs[rid_a], recs[rid_b])
    result["record_a"], result["record_b"] = rid_a, rid_b
    return result


def resolve(dataset_id: str) -> dict:
    """Gera entidades candidatas e pares candidatos (read-only, §22).

    Blocking por nome normalizado. Dentro de cada bloco, agrupa por assinatura
    de identidade (nome, CPF, nascimento). Blocos com mais de uma assinatura
    geram pares candidatos — potenciais colisões de identidade a decidir.
    """
    records = _records(dataset_id)

    # Blocking + clustering por assinatura.
    blocks: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for rid, p in records:
        blocks[_norm_name(p.get("name"))].append((rid, p))

    entities = []
    candidate_pairs = []
    sig_to_entity: dict[tuple, str] = {}

    for name_key, members in blocks.items():
        by_sig: dict[tuple, list[str]] = defaultdict(list)
        rep_payload: dict[tuple, dict] = {}
        for rid, p in members:
            sig = _signature(p)
            by_sig[sig].append(rid)
            rep_payload.setdefault(sig, p)

        for sig, rids in by_sig.items():
            entity_id = "ent_" + uuid.uuid5(uuid.NAMESPACE_OID, str(sig)).hex[:10]
            sig_to_entity[sig] = entity_id
            entities.append({
                "entity_id": entity_id,
                "entity_type": "PERSON",
                "status": "CANDIDATE",  # hipótese — não é fato (P4)
                "name": rep_payload[sig].get("name"),
                "cpf": rep_payload[sig].get("cpf"),
                "dob": rep_payload[sig].get("dob"),
                "record_count": len(rids),
                "record_ids": rids,
            })

        # Pares candidatos entre assinaturas distintas do mesmo bloco de nome.
        sigs = list(by_sig.keys())
        for i in range(len(sigs)):
            for j in range(i + 1, len(sigs)):
                a = rep_payload[sigs[i]]
                b = rep_payload[sigs[j]]
                cmp = compare(a, b)
                candidate_pairs.append({
                    "entity_a": sig_to_entity[sigs[i]],
                    "entity_b": sig_to_entity[sigs[j]],
                    "record_a": by_sig[sigs[i]][0],
                    "record_b": by_sig[sigs[j]][0],
                    **cmp,
                })

    return {
        "dataset_id": dataset_id,
        "entities": sorted(entities, key=lambda e: -e["record_count"]),
        "candidate_pairs": candidate_pairs,
        "note": ("Entidades são CANDIDATE (hipóteses). Nenhuma fusão é aplicada "
                 "automaticamente; decisões de alto impacto exigem aprovação (§25/§43)."),
    }


def _aggregate(records: list[dict]) -> dict:
    def _amount(v):
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    return {
        "events": len({r.get("event_id") for r in records}),
        "companies": sorted({r.get("company") for r in records if r.get("company")}),
        "total_amount": round(sum(_amount(r.get("amount")) for r in records), 2),
        "phones": len({_digits(r.get("phone")) for r in records if _digits(r.get("phone"))}),
        "counterparties": len({r.get("counterparty") for r in records if r.get("counterparty")}),
        "record_count": len(records),
    }


def impact_analysis(dataset_id: str, entity_a: str, entity_b: str) -> dict:
    """Impact Analysis Engine (§26-27): simula o efeito de fundir A e B.

    Responde à pergunta-chave (§27): a fusão apenas melhora a representação ou
    altera a narrativa analítica? Read-only — nada é gravado.
    """
    resolved = resolve(dataset_id)
    ent_index = {e["entity_id"]: e for e in resolved["entities"]}
    if entity_a not in ent_index or entity_b not in ent_index:
        raise KeyError("entity_id inexistente")

    recs = dict(_records(dataset_id))
    recs_a = [recs[r] for r in ent_index[entity_a]["record_ids"]]
    recs_b = [recs[r] for r in ent_index[entity_b]["record_ids"]]

    before_a = _aggregate(recs_a)
    before_b = _aggregate(recs_b)
    after = _aggregate(recs_a + recs_b)

    # High-Impact Merge Policy (§25).
    high_impact_reasons = []
    if len(after["companies"]) > max(len(before_a["companies"]), len(before_b["companies"])):
        high_impact_reasons.append("conecta empresas antes desconectadas")
    if after["total_amount"] > max(before_a["total_amount"], before_b["total_amount"]):
        high_impact_reasons.append("aumenta o patrimônio/volume financeiro atribuído")
    if after["events"] > max(before_a["events"], before_b["events"]):
        high_impact_reasons.append("atribui eventos de uma identidade a outra")

    high_impact = bool(high_impact_reasons)

    return {
        "entity_a": entity_a,
        "entity_b": entity_b,
        "before": {"A": before_a, "B": before_b},
        "after": after,
        "deltas": {
            "events": after["events"] - max(before_a["events"], before_b["events"]),
            "companies": len(after["companies"]) - max(len(before_a["companies"]), len(before_b["companies"])),
            "total_amount": round(after["total_amount"] - max(before_a["total_amount"], before_b["total_amount"]), 2),
            "phones": after["phones"] - max(before_a["phones"], before_b["phones"]),
        },
        "high_impact": high_impact,
        "classification": "HIGH IMPACT ENTITY DECISION" if high_impact else "LOW IMPACT",
        "high_impact_reasons": high_impact_reasons,
        "alert": ("Esta decisão altera significativamente a interpretação investigativa. "
                  "Exige revisão humana (§25)." if high_impact else
                  "Impacto baixo sobre a narrativa analítica."),
        "recommendation": compare(recs_a[0], recs_b[0]) if recs_a and recs_b else None,
    }


def decide(
    dataset_id: str, entity_a: str, entity_b: str, decision: str, *, approved_by: str,
    justification: str = "",
) -> dict:
    """Registra a decisão humana sobre um par candidato (§43 nível 3, P9).

    Grava a decisão no diário de transformação e, se MATCH aprovado, cria o
    vínculo em entity_membership. NON_MATCH também é registrado (a rejeição de
    fusão é uma decisão auditável — §87). O raw permanece intacto (P1).
    """
    from app.governance import provenance
    from app.models.schemas import Transformation

    if decision not in {"MATCH", "NON_MATCH", "POSSIBLE"}:
        raise ValueError("decisão inválida")

    resolved = resolve(dataset_id)
    ent_index = {e["entity_id"]: e for e in resolved["entities"]}
    if entity_a not in ent_index or entity_b not in ent_index:
        raise KeyError("entity_id inexistente")

    transformation_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with connect() as conn:
        case_row = conn.execute(
            "SELECT case_id FROM datasets WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
        case_id = case_row["case_id"] if case_row else "UNKNOWN"

    provenance.record_transformation(Transformation(
        transformation_id=transformation_id,
        case_id=case_id,
        dataset_id=dataset_id,
        rule_id="ENTITY_MATCH_DECISION_V1",
        rule_version="1.0",
        parameters={"entity_a": entity_a, "entity_b": entity_b, "decision": decision},
        actor=approved_by,
        tool="entity_resolution_engine",
        datetime=now,
        justification=justification,
        approval=f"approved_by:{approved_by}",
        reversible=True,
        records_affected=0,
    ))
    provenance.add_edge("ENTITY", entity_a, "TRANSFORMATION", transformation_id, "decided")
    provenance.add_edge("ENTITY", entity_b, "TRANSFORMATION", transformation_id, "decided")

    merged_entity_id = None
    if decision == "MATCH":
        merged_entity_id = "ent_merge_" + uuid.uuid4().hex[:8]
        members = ent_index[entity_a]["record_ids"] + ent_index[entity_b]["record_ids"]
        with connect() as conn:
            conn.execute(
                "INSERT INTO entities (entity_id, entity_type, status, created_at) VALUES (?,?,?,?)",
                (merged_entity_id, "PERSON", "VALIDATED", now.isoformat()),
            )
            for rid in members:
                conn.execute(
                    """INSERT INTO entity_membership
                       (membership_id, record_id, entity_id, match_score, decision,
                        decision_actor, evidence, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (uuid.uuid4().hex, rid, merged_entity_id, None, "MATCH",
                     approved_by, "{}", now.isoformat()),
                )

    return {
        "transformation_id": transformation_id,
        "decision": decision,
        "merged_entity_id": merged_entity_id,
        "reversible": True,
    }

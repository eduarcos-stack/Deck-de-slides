"""Módulo 3 — Quality Analyzer (Blueprint §14).

Distinto do Profiling (§12, que apenas descreve). O Quality Analyzer avalia
dimensões de qualidade e, sobretudo, **distingue erro provável de divergência
legítima**: quando dois valores de uma mesma entidade diferem, o sistema NÃO
declara um deles errado — sinaliza a divergência e pede verificação de datas de
referência e fontes (§14).

Dimensões (§14): completude, acurácia potencial, consistência, validade,
unicidade, atualidade, proveniência.
"""

from __future__ import annotations

import json
import re

from app.core.db import connect
from app.modules import missing, profiling, temporal

# Formatos reconhecidos por campo típico (para a dimensão de validade).
_VALIDATORS = {
    "cpf": re.compile(r"^(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})$"),
    "cnpj": re.compile(r"^(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})$"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "phone": re.compile(r"\d"),
    "dob": re.compile(r"^\d{2}/\d{2}/\d{4}$"),
}
# Campos que devem ser estáveis dentro de uma mesma identidade (nome, nascimento).
_IDENTITY_STABLE = ("cpf", "company", "city")


def _payloads(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    return [json.loads(r["original_payload"]) for r in rows]


def _is_missing(field: str, value, confirmed: dict[str, set[str]]) -> bool:
    if value is None:
        return True
    v = str(value).strip()
    if v == "":
        return True
    if value in confirmed.get(field, set()):
        return True
    return v.lower() in missing.SENTINEL_CANDIDATES and not (
        v == "0" and field.lower() in ("amount", "value", "valor"))


def analyze(dataset_id: str) -> dict:
    payloads = _payloads(dataset_id)
    if not payloads:
        return {"dataset_id": dataset_id, "dimensions": {}, "divergences": []}
    columns = list(payloads[0].keys())
    rows = len(payloads)
    confirmed = missing.confirmed_missing(dataset_id)

    # -- Completude -------------------------------------------------------- #
    total_cells = rows * len(columns)
    missing_cells = sum(
        1 for p in payloads for c in columns if _is_missing(c, p.get(c), confirmed)
    )
    completude = 1 - missing_cells / total_cells if total_cells else None

    # -- Validade ---------------------------------------------------------- #
    typed = [c for c in columns if c in _VALIDATORS]
    checked = valid = 0
    for c in typed:
        pat = _VALIDATORS[c]
        for p in payloads:
            v = p.get(c)
            if _is_missing(c, v, confirmed):
                continue
            checked += 1
            if pat.search(str(v)):
                valid += 1
    validade = valid / checked if checked else None

    # -- Unicidade --------------------------------------------------------- #
    prof = profiling.profile_dataset(dataset_id)
    unicidade = 1 - prof.exact_duplicate_rows / rows if rows else None

    # -- Consistência + divergências (o cerne do §14) --------------------- #
    consistencia, divergences = _consistency(payloads, columns, confirmed)

    # -- Atualidade (qualidade temporal) ---------------------------------- #
    if "timestamp" in columns:
        oks = sum(1 for p in payloads
                  if temporal.parse(p.get("timestamp"), "strict").clock_quality != "UNKNOWN")
        atualidade = oks / rows if rows else None
    else:
        atualidade = None

    # -- Proveniência ------------------------------------------------------ #
    with connect() as conn:
        with_source = conn.execute(
            "SELECT COUNT(*) c FROM raw_records WHERE dataset_id = ? AND source_id IS NOT NULL",
            (dataset_id,),
        ).fetchone()["c"]
    proveniencia = with_source / rows if rows else None

    # -- Acurácia potencial (proxy honesto) ------------------------------- #
    proxy_parts = [x for x in (validade, consistencia) if x is not None]
    acuracia_potencial = sum(proxy_parts) / len(proxy_parts) if proxy_parts else None

    dimensions = {
        "completude": _dim(completude, "células preenchidas (ausência semântica descontada)"),
        "acuracia_potencial": _dim(acuracia_potencial,
            "PROXY (validade+consistência) — acurácia real exige verdade do mundo, não mensurável só com os dados"),
        "consistencia": _dim(consistencia, "campos identitários estáveis sem divergência interna"),
        "validade": _dim(validade, "valores em conformidade com o formato esperado do campo"),
        "unicidade": _dim(unicidade, "linhas livres de duplicata exata"),
        "atualidade": _dim(atualidade, "timestamps com qualidade temporal != UNKNOWN"),
        "proveniencia": _dim(proveniencia, "registros com origem rastreável até a fonte"),
    }
    measurable = [d["score"] for d in dimensions.values() if d["score"] is not None]
    return {
        "dataset_id": dataset_id,
        "overall": round(sum(measurable) / len(measurable), 4) if measurable else None,
        "dimensions": dimensions,
        "divergences": divergences,
        "note": ("Divergência não é erro (§14): valores discordantes de uma mesma "
                 "entidade são sinalizados para verificação de datas de referência "
                 "e fontes, nunca classificados automaticamente como erro."),
    }


def _consistency(payloads, columns, confirmed):
    from collections import defaultdict

    stable = [c for c in _IDENTITY_STABLE if c in columns]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for p in payloads:
        key = ((p.get("name") or "").strip().lower(), (p.get("dob") or "").strip())
        groups[key].append(p)

    checks = 0
    divergent = 0
    divergences = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        for field in stable:
            values = {str(m.get(field)).strip() for m in members
                      if not _is_missing(field, m.get(field), confirmed)}
            checks += 1
            if len(values) > 1:
                divergent += 1
                divergences.append({
                    "entity": {"name": members[0].get("name"), "dob": members[0].get("dob")},
                    "field": field,
                    "values": sorted(values),
                    "classification": "DIVERGENCE_NOT_ERROR",
                    "message": ("Divergência detectada. Não há elementos suficientes para "
                                "classificar um dos valores como erro. Verificar datas de "
                                "referência e fontes."),
                })
    consistencia = 1 - divergent / checks if checks else 1.0
    return consistencia, divergences


def _dim(score, description):
    return {"score": None if score is None else round(score, 4), "description": description}

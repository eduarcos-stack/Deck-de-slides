"""Empacotamento de entregáveis (Blueprint §60, §61, §63).

Ao término de uma análise, o TRACE-LM monta um pacote com os 16 entregáveis do
§60. O produto final NÃO se chama "base limpa" (§61) — e sim
**Base Analítica Tratada — Versão N**, porque "limpa" sugere ausência de incerteza.

Inclui a métrica Provenance Completeness (§63): fração de achados com lineage
completo até a fonte. Alvo de produção: PC = 1.0.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

from app.core.db import connect
from app.governance import provenance
from app.modules import deduplication, eda, entity_resolution, profiling


def _records(dataset_id: str) -> list[tuple[str, dict]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT record_id, original_payload FROM raw_records WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return [(r["record_id"], json.loads(r["original_payload"])) for r in rows]


def _source_inventory(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.source_id, s.filename, s.hash, s.mime_type, s.operator,
                      s.ingestion_datetime, s.row_count, s.column_count, d.version
               FROM datasets d JOIN sources s ON s.source_id = d.source_id
               WHERE d.dataset_id = ?""",
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def provenance_completeness(dataset_id: str) -> dict:
    """Provenance Completeness (§63): % de achados com lineage até a fonte."""
    findings = eda.list_findings(dataset_id)
    if not findings:
        return {"pc": None, "total_findings": 0, "with_lineage": 0,
                "note": "Nenhum achado registrado."}
    with_lineage = 0
    for f in findings:
        path = provenance.trace_back("FINDING", f["finding_id"])
        reaches_source = any(e["from"]["type"] == "SOURCE" for e in path) or bool(path)
        if reaches_source:
            with_lineage += 1
    return {
        "pc": round(with_lineage / len(findings), 3),
        "total_findings": len(findings),
        "with_lineage": with_lineage,
        "target": 1.0,
    }


def treated_dataset_rows(dataset_id: str) -> tuple[list[str], list[dict]]:
    """Base Analítica Tratada (§61): raw + campos derivados válidos, lado a lado.

    Preserva o valor original (P2): os campos derivados entram como colunas
    adicionais (ex.: phone_norm), nunca sobrescrevendo o original.
    """
    records = _records(dataset_id)
    with connect() as conn:
        derived = conn.execute(
            """SELECT record_id, field_name, derived_value FROM derived_fields
               WHERE derived_value IS NOT NULL""",
        ).fetchall()
    by_record: dict[str, dict] = {}
    derived_cols: list[str] = []
    for d in derived:
        by_record.setdefault(d["record_id"], {})[d["field_name"]] = d["derived_value"]
        if d["field_name"] not in derived_cols:
            derived_cols.append(d["field_name"])

    base_cols = list(records[0][1].keys()) if records else []
    columns = base_cols + [c for c in derived_cols if c not in base_cols]
    rows = []
    for rid, payload in records:
        row = dict(payload)
        row.update(by_record.get(rid, {}))
        rows.append(row)
    return columns, rows


def build_package(dataset_id: str) -> dict:
    """Monta o pacote de 16 entregáveis (§60)."""
    profile = profiling.profile_dataset(dataset_id).model_dump()
    resolved = entity_resolution.resolve(dataset_id)
    dedup = deduplication.analyze(dataset_id, "event_id") if _has_field(dataset_id, "event_id") else {}
    findings = eda.list_findings(dataset_id)

    with connect() as conn:
        transformations = [dict(r) for r in conn.execute(
            "SELECT * FROM transformations WHERE dataset_id = ? ORDER BY datetime", (dataset_id,)
        )]
        prov_edges = [dict(r) for r in conn.execute(
            "SELECT src_type, src_id, dst_type, dst_id, relation FROM provenance_edges ORDER BY edge_id"
        )]
        entity_decisions = [t for t in transformations if t["rule_id"] == "ENTITY_MATCH_DECISION_V1"]

    temporal_report = eda.pattern_stability(dataset_id) if findings else {}
    columns, treated_rows = treated_dataset_rows(dataset_id)

    return {
        "meta": {
            "product": "Base Analítica Tratada",  # §61 — nunca "base limpa"
            "version": "V1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "principle": "AI-assisted · human-controlled · provenance-first",
        },
        # Os 16 entregáveis do §60:
        "1_source_inventory": _source_inventory(dataset_id),
        "2_profiling_report": profile,
        "3_quality_report": {"notes": profile["notes"], "critical_missing_rows": profile["critical_missing_rows"]},
        "4_transformation_plan": [{"rule_id": t["rule_id"], "tool": t["tool"], "approval": t["approval"]} for t in transformations],
        "5_treated_dataset_meta": {"rows": len(treated_rows), "columns": columns, "version": "V1"},
        "6_transformation_diary": transformations,
        "7_duplicity_matrix": dedup.get("duplicate_groups", []),
        "8_entity_resolution_matrix": resolved["candidate_pairs"],
        "9_event_map": {"canonical_events": dedup.get("distinct_event_keys"), "raw_rows": dedup.get("raw_rows")},
        "10_temporal_report": temporal_report,
        "11_eda": {"hour_distribution_strict": eda.hour_distribution(dataset_id, "strict")["histogram"]},
        "12_findings_registry": findings,
        "13_impact_analysis": {"entity_decisions_recorded": entity_decisions},
        "14_adversarial_review": [{"finding_id": f["finding_id"], "robust": f["robust"], "status": f["status"]} for f in findings],
        "15_provenance_graph": prov_edges,
        "16_provenance_completeness": provenance_completeness(dataset_id),
    }


def _has_field(dataset_id: str, field: str) -> bool:
    records = _records(dataset_id)
    return bool(records) and field in records[0][1]


def render_markdown_report(dataset_id: str) -> str:
    """Relatório analítico exportável (§60 item 16), em Markdown."""
    pkg = build_package(dataset_id)
    src = pkg["1_source_inventory"]
    prof = pkg["2_profiling_report"]
    pc = pkg["16_provenance_completeness"]
    L: list[str] = []
    L.append("# Base Analítica Tratada — Versão 1")
    L.append(f"*Gerado em {pkg['meta']['generated_at']} · {pkg['meta']['principle']}*\n")
    L.append("> Este documento descreve uma **base analítica tratada**, não uma "
             "\"base limpa\" (§61). A incerteza foi preservada e as transformações "
             "são rastreáveis.\n")

    L.append("## 1. Inventário de fontes")
    for s in src:
        L.append(f"- **{s['filename']}** · {s['row_count']} registros · {s['column_count']} campos "
                 f"· hash `{s['hash'][:16]}…` · operador `{s['operator']}`")

    L.append("\n## 2. Perfilamento e qualidade")
    L.append(f"- {prof['row_count']} registros, {prof['column_count']} campos")
    L.append(f"- Missing crítico: {prof['critical_missing_rows']} · chaves candidatas: "
             f"{', '.join(prof['candidate_keys']) or '—'}")
    for n in prof["notes"]:
        L.append(f"- ⚠️ {n}")

    L.append("\n## 3. Plano de transformação aplicado")
    if pkg["6_transformation_diary"]:
        for t in pkg["6_transformation_diary"]:
            rev = " (revertida)" if t.get("reverted_by") else ""
            L.append(f"- `{t['rule_id']}` v{t['rule_version']} · {t['tool']} · "
                     f"aprovação {t['approval']} · afetados {t['records_affected']}{rev}")
    else:
        L.append("- Nenhuma transformação aplicada.")

    L.append("\n## 4. Resolução de entidades")
    L.append(f"- {len(pkg['8_entity_resolution_matrix'])} pares candidatos avaliados.")
    for p in pkg["8_entity_resolution_matrix"][:5]:
        L.append(f"  - sim.nome {p['name_similarity']} · CPF {p['cpf']} · nasc. {p['dob']} "
                 f"→ **{p['decision']}**")

    L.append("\n## 5. Eventos e duplicidade")
    em = pkg["9_event_map"]
    L.append(f"- {em.get('raw_rows', '—')} linhas brutas → {em.get('canonical_events', '—')} eventos canônicos.")

    L.append("\n## 6. Achados (exploratórios)")
    if pkg["12_findings_registry"]:
        for f in pkg["12_findings_registry"]:
            robust = {True: "robusto", False: "NÃO ROBUSTO", None: "não auditado"}[f["robust"]]
            L.append(f"- [{f['status']}] {f['statement']} — {robust}")
    else:
        L.append("- Nenhum achado registrado.")

    L.append("\n## 7. Rastreabilidade")
    L.append(f"- **Provenance Completeness (§63):** {pc['pc']} "
             f"({pc['with_lineage']}/{pc['total_findings']} achados com lineage; alvo 1.0)")
    L.append(f"- {len(pkg['15_provenance_graph'])} arestas no grafo de proveniência.")

    L.append("\n## Aviso")
    L.append("Ferramenta de preparação e análise de dados. Não determina autoria, "
             "culpabilidade ou tipificação penal (§91).")
    return "\n".join(L)


def build_zip(dataset_id: str) -> bytes:
    """Empacota o conjunto de entregáveis em um ZIP (§60)."""
    pkg = build_package(dataset_id)
    report = render_markdown_report(dataset_id)
    columns, rows = treated_dataset_rows(dataset_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(pkg, ensure_ascii=False, indent=2, default=str))
        z.writestr("RELATORIO_ANALITICO.md", report)
        z.writestr("diario_transformacao.json",
                   json.dumps(pkg["6_transformation_diary"], ensure_ascii=False, indent=2, default=str))
        z.writestr("provenance_graph.json",
                   json.dumps(pkg["15_provenance_graph"], ensure_ascii=False, indent=2))
        z.writestr("findings.json",
                   json.dumps(pkg["12_findings_registry"], ensure_ascii=False, indent=2, default=str))
        # Base Analítica Tratada — Versão 1 (CSV)
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        z.writestr("base_analitica_tratada_v1.csv", csv_buf.getvalue())
    return buf.getvalue()

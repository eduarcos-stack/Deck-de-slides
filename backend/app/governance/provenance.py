"""Camada de Governança: proveniência e lineage (Blueprint §34, §35, §45).

Implementa P7 (Provenance by Default) e P10 (Reversibility). Toda transformação
relevante passa por aqui e deixa: (a) uma linha no Diário de Transformação e
(b) arestas no Provenance Graph. O botão conceitual "Como chegamos aqui?" (§45)
é servido reconstruindo o caminho reverso a partir dessas arestas.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.db import connect
from app.models.schemas import Transformation


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Colunas de conteúdo do Diário que entram no hash-chain (§36). Imutáveis após
# a inserção; reverted_by é excluído de propósito (muda no rollback).
TRANSFORMATION_CHAIN_FIELDS = [
    "transformation_id", "case_id", "dataset_id", "rule_id", "rule_version",
    "parameters", "actor", "tool", "datetime", "justification", "approval",
    "reversible", "records_affected",
]


def record_transformation(t: Transformation) -> None:
    """Insere uma transformação no diário (append-only, encadeada — §36)."""
    from app.core import integrity

    fields = {
        "transformation_id": t.transformation_id,
        "case_id": t.case_id,
        "dataset_id": t.dataset_id,
        "rule_id": t.rule_id,
        "rule_version": t.rule_version,
        "parameters": _dumps(t.parameters),
        "actor": t.actor,
        "tool": t.tool,
        "datetime": t.datetime.isoformat(),
        "justification": t.justification,
        "approval": t.approval,
        "reversible": int(t.reversible),
        "records_affected": t.records_affected,
    }
    with connect() as conn:
        chain = integrity.link(conn, "transformations", fields)
        conn.execute(
            """
            INSERT INTO transformations (
                transformation_id, case_id, dataset_id, rule_id, rule_version,
                parameters, actor, tool, datetime, justification, approval,
                reversible, records_affected, prev_hash, entry_hash, seal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *[fields[k] for k in TRANSFORMATION_CHAIN_FIELDS],
                chain["prev_hash"], chain["entry_hash"], chain["seal"],
            ),
        )


def add_edge(
    src_type: str, src_id: str, dst_type: str, dst_id: str, relation: str
) -> None:
    """Adiciona uma aresta ao Provenance Graph (§34)."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO provenance_edges
                (src_type, src_id, dst_type, dst_id, relation, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (src_type, src_id, dst_type, dst_id, relation, _now()),
        )


def trace_back(dst_type: str, dst_id: str, max_depth: int = 50) -> list[dict]:
    """Reconstrói o caminho reverso de um objeto até a fonte (§45).

    Percurso em largura sobre as arestas de proveniência, seguindo do objeto
    de destino em direção às suas origens. Serve o "Como chegamos aqui?".
    """
    visited: set[tuple[str, str]] = set()
    frontier: list[tuple[str, str, int]] = [(dst_type, dst_id, 0)]
    path: list[dict] = []
    with connect() as conn:
        while frontier:
            cur_type, cur_id, depth = frontier.pop(0)
            if (cur_type, cur_id) in visited or depth > max_depth:
                continue
            visited.add((cur_type, cur_id))
            rows = conn.execute(
                """
                SELECT src_type, src_id, relation
                FROM provenance_edges
                WHERE dst_type = ? AND dst_id = ?
                """,
                (cur_type, cur_id),
            ).fetchall()
            for r in rows:
                path.append(
                    {
                        "from": {"type": r["src_type"], "id": r["src_id"]},
                        "to": {"type": cur_type, "id": cur_id},
                        "relation": r["relation"],
                        "depth": depth,
                    }
                )
                frontier.append((r["src_type"], r["src_id"], depth + 1))
    return path


def trace_forward(src_type: str, src_id: str, max_depth: int = 50) -> list[dict]:
    """Percorre o grafo no sentido direto: o que DEPENDE deste objeto (§58).

    Espelho de trace_back. Usado pelo Dependency Graph e pela Invalidação
    Automática (§59) para descobrir quais objetos derivam de uma transformação
    ou entidade que será revertida.
    """
    visited: set[tuple[str, str]] = set()
    frontier: list[tuple[str, str, int]] = [(src_type, src_id, 0)]
    path: list[dict] = []
    with connect() as conn:
        while frontier:
            cur_type, cur_id, depth = frontier.pop(0)
            if (cur_type, cur_id) in visited or depth > max_depth:
                continue
            visited.add((cur_type, cur_id))
            rows = conn.execute(
                """
                SELECT dst_type, dst_id, relation
                FROM provenance_edges
                WHERE src_type = ? AND src_id = ?
                """,
                (cur_type, cur_id),
            ).fetchall()
            for r in rows:
                path.append(
                    {
                        "from": {"type": cur_type, "id": cur_id},
                        "to": {"type": r["dst_type"], "id": r["dst_id"]},
                        "relation": r["relation"],
                        "depth": depth,
                    }
                )
                frontier.append((r["dst_type"], r["dst_id"], depth + 1))
    return path


def mark_transformation_reverted(transformation_id: str, reverted_by: str) -> None:
    """Marca uma transformação como revertida no diário (não a apaga — §36)."""
    with connect() as conn:
        conn.execute(
            "UPDATE transformations SET reverted_by = ? WHERE transformation_id = ?",
            (reverted_by, transformation_id),
        )


def _dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)

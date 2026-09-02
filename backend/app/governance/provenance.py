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


def record_transformation(t: Transformation) -> None:
    """Insere uma transformação no diário (append-only)."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO transformations (
                transformation_id, case_id, dataset_id, rule_id, rule_version,
                parameters, actor, tool, datetime, justification, approval,
                reversible, records_affected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t.transformation_id,
                t.case_id,
                t.dataset_id,
                t.rule_id,
                t.rule_version,
                _dumps(t.parameters),
                t.actor,
                t.tool,
                t.datetime.isoformat(),
                t.justification,
                t.approval,
                int(t.reversible),
                t.records_affected,
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

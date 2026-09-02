"""Módulo 10 — Adversarial Auditor (Blueprint §41-42).

Para cada achado, pergunta: "como esse resultado poderia estar errado?" (§41).
Procura vetores de erro conhecidos e, quando aplicável, executa a Pattern
Stability para decidir se o achado se sustenta. Opera no modo
SUPPORT × CHALLENGE × SYNTHESIS (§42), evitando ser um gerador de confirmação.
"""

from __future__ import annotations

from app.modules import eda

# Vetores de erro que o auditor considera (§41).
_ERROR_VECTORS = [
    "false merge", "false split", "duplicação", "missingness", "timezone",
    "sampling bias", "dependência entre fontes", "regra de normalização",
    "parser", "outlier artificial", "interpretação causal excessiva",
]


def audit_finding(dataset_id: str, finding_id: str) -> dict:
    """Contesta um achado e emite veredito de robustez (§41)."""
    findings = {f["finding_id"]: f for f in eda.list_findings(dataset_id)}
    if finding_id not in findings:
        raise KeyError("finding inexistente")
    finding = findings[finding_id]

    challenges: list[dict] = []
    verdict = "INDETERMINADO"
    robust = None

    if finding["type"] == "TEMPORAL_PATTERN":
        stability = eda.pattern_stability(dataset_id)
        robust = stability["robust"]
        challenges.append({
            "vector": "parser",
            "question": "O achado sobrevive a uma regra de parsing temporal mais estrita?",
            "evidence": {
                "cenario_naive": stability["scenario_naive"],
                "cenario_strict": stability["scenario_strict"],
                "registros_do_pico": stability["naive_records"],
            },
            "finding_impact": stability["verdict"],
        })
        challenges.append({
            "vector": "timezone",
            "question": "A conversão de timezone valida o relógio de origem?",
            "finding_impact": "Não. Conversão de representação não valida sincronização (P6).",
        })
        eda.set_finding_robustness(finding_id, robust)
        verdict = "NÃO ROBUSTO" if not robust else "ROBUSTO (sob os testes aplicados)"

    else:
        challenges.append({
            "vector": "generic",
            "question": "Quais decisões metodológicas sustentam este achado?",
            "finding_impact": "Reavaliar sob decisões alternativas antes de concluir.",
        })

    return {
        "finding_id": finding_id,
        "statement": finding["statement"],
        "considered_vectors": _ERROR_VECTORS,
        "challenges": challenges,
        "verdict": verdict,
        "robust": robust,
        "reminder": ("Achado permanece EXPLORATÓRIO. A escada epistemológica (§29) "
                     "não admite salto silencioso para conclusão."),
    }


def support_challenge_synthesis(hypothesis: str, support: list[str], challenge: list[str]) -> dict:
    """Modo SUPPORT × CHALLENGE × SYNTHESIS para uma hipótese (§42)."""
    proportional = len(challenge) >= len(support)
    synthesis = (
        "Os elementos contrários igualam ou superam os favoráveis: a conclusão "
        "proporcional é de cautela — hipótese não sustentada isoladamente."
        if proportional else
        "Os elementos favoráveis predominam, mas a hipótese permanece exploratória "
        "até validação pelo procedimento definido."
    )
    return {
        "hypothesis": hypothesis,
        "support": support,
        "challenge": challenge,
        "synthesis": synthesis,
    }

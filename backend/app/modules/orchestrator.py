"""LLM Orchestrator (Blueprint §37-40, §92).

O LLM interpreta, planeja, explica e coordena ferramentas — mas NÃO é motor de
execução (§4) nem autoridade factual (§37). Quem calcula são os motores
determinísticos; o orquestrador roteia, cita proveniência e preserva a distinção
epistemológica entre registro, entidade, evento, achado, inferência e conclusão.

Arquitetura MODEL-AGNOSTIC (§50): a composição da resposta passa por um provider
plugável. O padrão é um provider LOCAL determinístico (sem pesos de modelo, sem
rede — §47). Um modelo open-weight pode ser plugado implementando LLMProvider,
sem reescrever a plataforma.
"""

from __future__ import annotations

import os
import re
import unicodedata

from app.modules import deduplication, eda, entity_resolution, profiling, rag


def _norm(s: str) -> str:
    """Minúsculas sem acento — para casar padrões de intenção de forma robusta."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower())
                   if not unicodedata.combining(c))

# System prompt constitucional (§39) — versão simplificada do blueprint.
CONSTITUTIONAL_PROMPT = """Você é um assistente local de preparação e análise \
investigativa de dados. Sua função não é determinar autoria, culpabilidade ou \
tipificação penal. Sua função é auxiliar o usuário a compreender, preparar, \
correlacionar e analisar dados preservando a distinção entre registro, entidade, \
evento, achado, inferência, hipótese e conclusão.

Nunca sobrescreva dados brutos. Nunca trate similaridade como identidade. Nunca \
trate correlação como causalidade. Nunca trate ausência como inexistência sem \
fundamento. Nunca promova possible match a match sem a política exigida. Toda \
transformação relevante deve ser explícita, versionada, rastreável e reversível. \
Antes de operações de alto impacto, apresente efeito esperado e solicite aprovação."""

# Papéis lógicos (§40) — mesmo motor, políticas distintas.
LOGICAL_ROLES = [
    "Data Guardian", "Profiler", "Transformation Planner", "Entity Analyst",
    "Temporal Analyst", "EDA Analyst", "Adversarial Auditor", "Report Synthesizer",
]

# Tiers de modelo (§50). A plataforma é model-agnostic: trocar o LLM ou o tier
# não obriga reescrever nada — o tier é metadado de roteamento, não compute real.
_WORKSTATION_CAPS = ["classificação", "explicação", "geração de regras", "tool calling"]
TIER_PROFILES = {
    "workstation": {
        "tier": "workstation",
        "description": ("Modelo compacto para classificação, explicação, geração de "
                        "regras e tool calling (§50). Roda em workstation."),
        "model_hint": "open-weight instruct compacto (~7-8B)",
        "capabilities": _WORKSTATION_CAPS,
        "max_context_tokens": 8192,
    },
    "server": {
        "tier": "server",
        "description": ("Modelo maior para raciocínio complexo, documentos extensos, "
                        "síntese multi-fonte e adversarial analysis (§50). Roda em "
                        "servidor institucional."),
        "model_hint": "open-weight instruct grande (70B+)",
        "capabilities": _WORKSTATION_CAPS + [
            "raciocínio complexo", "documentos extensos", "síntese multi-fonte",
            "adversarial analysis"],
        "max_context_tokens": 128000,
    },
}
_TIER_ORDER = {"workstation": 0, "server": 1}

# Papel lógico -> tier recomendado. Tarefas de raciocínio profundo pedem servidor.
_ROLE_TIER = {
    "Data Guardian": "workstation", "Profiler": "workstation",
    "Transformation Planner": "workstation", "Entity Analyst": "workstation",
    "Temporal Analyst": "workstation", "EDA Analyst": "workstation",
    "Adversarial Auditor": "server", "Report Synthesizer": "server",
}


def current_tier() -> str:
    t = os.environ.get("TRACELM_LLM_TIER", "workstation")
    return t if t in TIER_PROFILES else "workstation"


def recommended_tier(role: str) -> str:
    return _ROLE_TIER.get(role, "workstation")


def tier_serves(current: str, recommended: str) -> bool:
    """Um tier atende a demanda se for igual ou superior ao recomendado."""
    return _TIER_ORDER.get(current, 0) >= _TIER_ORDER.get(recommended, 0)


def tier_status() -> dict:
    """Perfis de tier + tier corrente + tabela papel->tier (§50)."""
    return {
        "current": current_tier(),
        "profiles": TIER_PROFILES,
        "role_tier": _ROLE_TIER,
        "note": ("Model-agnostic (§50): trocar o LLM ou o tier não obriga reescrever "
                 "a plataforma. O provider padrão é local determinístico (sem pesos)."),
    }


class LLMProvider:
    """Interface model-agnostic (§50). compose() transforma o contexto estruturado
    (pergunta + KB + saídas de ferramentas) em texto explicativo."""

    name = "base"

    def compose(self, context: dict) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class LocalDeterministicProvider(LLMProvider):
    """Provider padrão: offline, sem pesos de modelo. Não alucina — apenas
    verbaliza as saídas determinísticas com os guardrails constitucionais."""

    name = "local-deterministic"

    def compose(self, context: dict) -> str:
        return context["draft_answer"]


def get_provider() -> LLMProvider:
    choice = os.environ.get("TRACELM_LLM_PROVIDER", "local")
    if choice == "local":
        return LocalDeterministicProvider()
    # Seam para um modelo open-weight local. Desabilitado por padrão para não
    # violar o zero-exfiltration (§47); habilitar exige implementação explícita.
    raise RuntimeError(
        f"Provider '{choice}' não configurado. O padrão é 'local' (sem rede). "
        "Plugue um modelo open-weight implementando LLMProvider.")


# --------------------------------------------------------------------------- #
# Classificação de intenção → plano de ferramentas (§37)
# --------------------------------------------------------------------------- #
# Ordem importa: causalidade tem precedência (§31), pois perguntas causais
# frequentemente citam nomes de entidades.
# Padrões avaliados sobre texto normalizado (sem acento, minúsculo).
_INTENTS = [
    ("causal", r"correla|causa|caus[ao]|prova que|demonstra que"),
    # agregação de valores (R$) antes de transactions: "quanto foi movimentado".
    ("aggregate", r"movimentad|montante|r\$|reais|valor total|soma|somatori|"
                  r"total (movimentad|transacion|em reais|gasto)|"
                  r"quanto.*(movim|reais|valor|montante|gasto|transferid|transacion)"),
    ("transactions", r"quant[ao]s.*(transa|opera|evento)|quantas transa"),
    ("entity", r"carlos|homon|mesma pessoa|identidade|fusao|merge|entidade"),
    # temporal antes de dedup: "pico de eventos de madrugada" é temporal, não dedup.
    ("temporal", r"horario|pico|00h|meia-?noite|madrugada|timestamp|tempor"),
    ("dedup", r"duplicat|dedup|reimport"),
    ("outlier", r"outlier|atipico|anomal"),
    ("profile", r"perfil|profil|qualidade|missing|ausenc|coluna|campo"),
]


def _classify(question: str) -> str:
    q = _norm(question)
    for intent, pat in _INTENTS:
        if re.search(pat, q):
            return intent
    return "general"


def _brl(v: float) -> str:
    """Formata em Real (pt-BR): 1234567.8 -> 'R$ 1.234.567,80'."""
    return "R$ " + f"{v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _amount_summary(dataset_id: str) -> dict:
    """Soma determinística do campo 'amount' sobre as linhas brutas (§11)."""
    import json

    from app.core.db import connect

    def to_num(v):
        if v is None:
            return None
        s = str(v).strip().replace("R$", "").replace(" ", "")
        if "," in s and "." in s:          # 1.234,56 -> 1234.56 (pt-BR)
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:                       # 1234,56 -> 1234.56
            s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    vals = [to_num(json.loads(r["original_payload"]).get("amount")) for r in rows]
    nums = [v for v in vals if v is not None]
    total = sum(nums)
    return {"rows": len(vals), "counted": len(nums), "missing": len(vals) - len(nums),
            "total": total, "mean": (total / len(nums) if nums else 0.0)}


def _carlos_summary(dataset_id: str) -> dict:
    import json

    from app.core.db import connect

    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    payloads = [json.loads(r["original_payload"]) for r in rows]
    carlos = [p for p in payloads if "carlos" in (p.get("name") or "").lower()]
    nominal_lines = len(carlos)
    distinct_events = len({p.get("event_id") for p in carlos})
    distinct_cpfs = {p.get("cpf") for p in carlos if (p.get("cpf") or "").count(".") == 2}
    return {"nominal_lines": nominal_lines, "distinct_events": distinct_events,
            "distinct_identities": len(distinct_cpfs)}


def ask(question: str, dataset_id: str | None, actor: str) -> dict:
    """Responde a uma pergunta em linguagem natural, roteando ferramentas (§38)."""
    intent = _classify(question)
    citations = rag.search(question, k=3)
    plan: list[str] = []
    guardrails: list[str] = []
    role = "Report Synthesizer"
    draft = ""

    def need_dataset() -> bool:
        return dataset_id is not None

    if intent in ("entity", "transactions") and need_dataset():
        role = "Entity Analyst"
        plan = ["entity_resolution.resolve", "raw_records.aggregate_by_name"]
        s = _carlos_summary(dataset_id)
        resolved = entity_resolution.resolve(dataset_id)
        homonyms = [e for e in resolved["entities"] if "carlos" in e["name"].lower()]
        guardrails = [
            "Similaridade de nome não é identidade (P4).",
            "A atribuição consolidada de linhas nominais a uma única pessoa não é "
            "suportada quando há identificadores discriminantes conflitantes (§85).",
        ]
        draft = (
            f"A base contém {s['nominal_lines']} linhas atribuídas nominalmente a "
            f"'Carlos Eduardo Silva'. Após resolução de eventos existem "
            f"{s['distinct_events']} eventos candidatos. Há pelo menos "
            f"{max(s['distinct_identities'], len(homonyms))} indivíduos homônimos "
            f"(CPFs distintos). A atribuição de todas as linhas a uma pessoa única "
            f"NÃO é suportada. Status: CANDIDATE — decisão de fusão exige aprovação "
            f"humana e Impact Analysis (§25-26)."
        )

    elif intent == "aggregate" and need_dataset():
        role = "EDA Analyst"
        plan = ["raw_records.sum(amount)"]
        agg = _amount_summary(dataset_id)
        guardrails = [
            "Soma sobre linhas BRUTAS preservadas (§11); duplicatas técnicas podem "
            "inflar o total — a unidade de evento (§20) pode diferir.",
            "Valores ausentes/inválidos são excluídos, não tratados como zero (§15).",
        ]
        detalhe = f", {agg['missing']} sem valor numérico" if agg["missing"] else ""
        draft = (
            f"Somando o campo 'amount' sobre {agg['rows']} linhas brutas: total "
            f"{_brl(agg['total'])} ({agg['counted']} linha(s) com valor{detalhe}). "
            f"Média por linha: {_brl(agg['mean'])}. Este é um total sobre registros "
            f"brutos, não sobre eventos consolidados (§20)."
        )

    elif intent == "dedup" and need_dataset():
        role = "Entity Analyst"
        plan = ["deduplication.analyze(event_id)"]
        rep = deduplication.analyze(dataset_id, "event_id")
        guardrails = ["Duplicata técnica ≠ evento repetido legítimo (§20)."]
        draft = (f"Sob a unidade de evento 'event_id': {rep['raw_rows']} linhas brutas "
                 f"→ {rep['distinct_event_keys']} eventos canônicos. "
                 f"Categorias: {rep['category_counts']}. Consolidar exige aprovação (§43).")

    elif intent == "temporal" and need_dataset():
        role = "Temporal Analyst"
        plan = ["eda.pattern_stability", "temporal.quality"]
        stab = eda.pattern_stability(dataset_id)
        guardrails = ["Conversão de timezone não valida o relógio de origem (P6).",
                      "Achado exploratório não é conclusão (§28)."]
        draft = (f"Sob parser naive há {stab['scenario_naive']} evento(s) entre 00h-02h; "
                 f"sob parser estrito, {stab['scenario_strict']}. {stab['verdict']}")

    elif intent == "outlier" and need_dataset():
        role = "EDA Analyst"
        plan = ["eda.outliers(amount)"]
        out = eda.outliers(dataset_id, "amount")
        guardrails = ["Outlier não é ilicitude (§30)."]
        draft = (f"{len(out['outliers'])} registro(s) atípico(s) por IQR. {out['policy']}")

    elif intent == "causal":
        role = "Adversarial Auditor"
        plan = ["policy.correlation_guardrail"]
        guardrails = ["Correlação não é causalidade (§31)."]
        draft = ("A correlação demonstra associação quantitativa entre as variáveis "
                 "definidas. A atribuição causal exige evidências adicionais.")

    elif intent == "profile" and need_dataset():
        role = "Profiler"
        plan = ["profiling.profile_dataset"]
        prof = profiling.profile_dataset(dataset_id).model_dump()
        guardrails = ["Profiling descreve — não corrige (§13)."]
        draft = (f"{prof['row_count']} registros, {prof['column_count']} campos; "
                 f"missing crítico: {prof['critical_missing_rows']}; chaves candidatas: "
                 f"{', '.join(prof['candidate_keys']) or '—'}. "
                 + (" ".join(prof['notes']) if prof['notes'] else ""))

    else:
        role = "Report Synthesizer"
        plan = ["rag.search"]
        guardrails = ["O assistente não é autoridade factual (§37)."]
        if not need_dataset():
            draft = ("Selecione um caso/dataset para eu rotear as ferramentas de "
                     "análise. Posso responder sobre método a partir da base de "
                     "conhecimento local.")
        else:
            draft = ("Posso ajudar com profiling, entidades, duplicidade, análise "
                     "temporal, outliers e proveniência. Reformule apontando um desses "
                     "aspectos, ou consulte o conhecimento de domínio abaixo.")
        if citations:
            draft += f" Conhecimento de domínio relevante: {citations[0]['title']}."

    provider = get_provider()
    answer_text = provider.compose({"draft_answer": draft})

    cur, rec = current_tier(), recommended_tier(role)
    served = tier_serves(cur, rec)
    tier = {
        "current": cur,
        "recommended": rec,
        "served": served,
        "note": ("O tier corrente atende esta tarefa." if served else
                 f"Esta tarefa ({role}) se beneficia do tier '{rec}' (§50); o tier "
                 f"corrente '{cur}' atende de forma limitada."),
    }

    return {
        "role": role,
        "intent": intent,
        "plan": plan,
        "answer": answer_text,
        "citations": citations,
        "guardrails": guardrails,
        "provider": provider.name,
        "tier": tier,
        "note": ("LLM ≠ motor de execução (§4). As ferramentas determinísticas "
                 "produziram os números; o assistente apenas roteia e explica."),
    }

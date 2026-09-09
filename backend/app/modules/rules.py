"""Motor de Regras (Blueprint §52) e Normalization Engine (§16).

Cada regra determinística possui ID + versão (§52), para que sempre se possa
responder "qual versão da regra produziu este resultado?". As transformações
são MECÂNICAS e reproduzíveis (§16); ambiguidades não são resolvidas
silenciosamente — o valor é marcado como ambíguo e preservado (P3).

Uma regra NÃO grava nada: ela apenas propõe (raw_value -> derived_value +
confiança + ambiguidade). A escrita ocorre no módulo de transformação, após
aprovação humana quando exigida (§43).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class RuleOutcome:
    derived_value: Optional[str]
    confidence: str  # high | medium | low
    ambiguous: bool
    reason: str = ""


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: str
    description: str
    country: str
    apply: Callable[[str], RuleOutcome]


# --------------------------------------------------------------------------- #
# CPF_NORMALIZE_V1 — remove pontuação, valida comprimento (§43 nível 1)
# --------------------------------------------------------------------------- #
def _cpf_normalize(value: str) -> RuleOutcome:
    v = (value or "").strip()
    if v == "":
        return RuleOutcome(None, "low", True, "valor vazio")
    digits = re.sub(r"\D", "", v)
    if len(digits) != 11:
        return RuleOutcome(None, "low", True, f"{len(digits)} dígitos (esperado 11)")
    return RuleOutcome(digits, "high", False, "pontuação removida")


# --------------------------------------------------------------------------- #
# PHONE_BR_E164_V2 — normaliza telefone BR para E.164 (§16)
# --------------------------------------------------------------------------- #
def _phone_br_e164(value: str) -> RuleOutcome:
    v = (value or "").strip()
    if v == "":
        return RuleOutcome(None, "low", True, "valor vazio")
    digits = re.sub(r"\D", "", v)
    if digits.startswith("55") and len(digits) in (12, 13):
        return RuleOutcome("+" + digits, "high", False, "já continha DDI 55")
    if len(digits) in (10, 11):  # DDD + número
        return RuleOutcome("+55" + digits, "high", False, "DDI 55 acrescentado")
    return RuleOutcome(None, "low", True, f"{len(digits)} dígitos — formato não reconhecido")


RULES: dict[str, Rule] = {
    "CPF_NORMALIZE_V1": Rule(
        rule_id="CPF_NORMALIZE_V1",
        version="1.0",
        description="Remove pontuação de CPF e valida 11 dígitos.",
        country="BR",
        apply=_cpf_normalize,
    ),
    "PHONE_BR_E164_V2": Rule(
        rule_id="PHONE_BR_E164_V2",
        version="2.0",
        description="Normaliza telefone brasileiro para o padrão E.164 (+55DDDNUMERO).",
        country="BR",
        apply=_phone_br_e164,
    ),
}


def get_rule(rule_id: str) -> Rule:
    if rule_id not in RULES:
        raise KeyError(f"Regra desconhecida: {rule_id}")
    return RULES[rule_id]


def list_rules() -> list[dict]:
    return [
        {
            "rule_id": r.rule_id,
            "version": r.version,
            "description": r.description,
            "country": r.country,
        }
        for r in RULES.values()
    ]

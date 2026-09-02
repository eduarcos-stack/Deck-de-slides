"""Status epistemológicos do TRACE-LM.

Materializa a Seção 9 do Blueprint Mestre. Cada objeto relevante do sistema
(registro, entidade, evento, achado) carrega um status explícito. O sistema
NUNCA promove silenciosamente um objeto de um status para outro mais forte
(Princípio P3 — Uncertainty Preservation; P8 — No Silent Inference).
"""

from __future__ import annotations

from enum import Enum


class EpistemicStatus(str, Enum):
    """Status epistemológico de um objeto (Blueprint §9)."""

    OBSERVED = "OBSERVED"  # tal como recebido da fonte
    DERIVED = "DERIVED"  # produzido por transformação determinística
    CANDIDATE = "CANDIDATE"  # hipótese de agrupamento ainda não avaliada
    POSSIBLE = "POSSIBLE"  # match/evento possível, abaixo do limiar de decisão
    VALIDATED = "VALIDATED"  # aprovado pelo procedimento definido
    VALIDATED_WITH_RESERVATIONS = "VALIDATED_WITH_RESERVATIONS"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


# Transições permitidas. A ausência de uma aresta significa que a promoção
# não pode ocorrer automaticamente — exige decisão humana registrada (P9).
_ALLOWED_TRANSITIONS: dict[EpistemicStatus, set[EpistemicStatus]] = {
    EpistemicStatus.OBSERVED: {EpistemicStatus.DERIVED, EpistemicStatus.CANDIDATE},
    EpistemicStatus.DERIVED: {EpistemicStatus.CANDIDATE},
    EpistemicStatus.CANDIDATE: {EpistemicStatus.POSSIBLE, EpistemicStatus.REJECTED},
    EpistemicStatus.POSSIBLE: {
        EpistemicStatus.VALIDATED,
        EpistemicStatus.VALIDATED_WITH_RESERVATIONS,
        EpistemicStatus.DISPUTED,
        EpistemicStatus.REJECTED,
    },
    EpistemicStatus.VALIDATED: {EpistemicStatus.DISPUTED, EpistemicStatus.REJECTED},
    EpistemicStatus.VALIDATED_WITH_RESERVATIONS: {
        EpistemicStatus.DISPUTED,
        EpistemicStatus.REJECTED,
    },
    EpistemicStatus.DISPUTED: {EpistemicStatus.VALIDATED, EpistemicStatus.REJECTED},
    EpistemicStatus.REJECTED: set(),
    EpistemicStatus.UNKNOWN: {EpistemicStatus.CANDIDATE, EpistemicStatus.POSSIBLE},
}

# Promoções que exigem aprovação humana obrigatória (Blueprint §43, nível 3).
_REQUIRES_HUMAN_APPROVAL: set[tuple[EpistemicStatus, EpistemicStatus]] = {
    (EpistemicStatus.POSSIBLE, EpistemicStatus.VALIDATED),
    (EpistemicStatus.POSSIBLE, EpistemicStatus.VALIDATED_WITH_RESERVATIONS),
}


def can_transition(src: EpistemicStatus, dst: EpistemicStatus) -> bool:
    """Verifica se a transição src -> dst é estruturalmente permitida."""
    return dst in _ALLOWED_TRANSITIONS.get(src, set())


def requires_human_approval(src: EpistemicStatus, dst: EpistemicStatus) -> bool:
    """Verifica se a promoção exige aprovação humana explícita (P9)."""
    return (src, dst) in _REQUIRES_HUMAN_APPROVAL


class SilentInferenceError(RuntimeError):
    """Lançada quando se tenta promover status sem a política exigida (P3/P8)."""

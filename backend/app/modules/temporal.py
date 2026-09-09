"""Módulo 5 — Temporal Engine (Blueprint §18-19).

Distingue representação temporal de verdade temporal (Princípio P6). Converter
timezone NÃO valida o relógio de origem. Cada timestamp recebe uma qualidade
temporal (§19) com justificativa.

Ponto epistemológico central desta implementação: o parser tem dois modos.
  - "naive": aceita horas fora de faixa (ex.: 24:00) colapsando para meia-noite,
     como faria uma rotina de limpeza ingênua. É isto que fabrica achados
     temporais espúrios (§89).
  - "strict": marca 24:00 e casos ambíguos como qualidade UNKNOWN, sem forçar
     um horário — preservando a incerteza (P3).

A diferença entre os dois modos é o que a Pattern Stability (§33) explora.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional

# Padrões presentes nas fontes (três formatos — §13).
_ISO_OFFSET = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})([+-]\d{2}):?(\d{2})$")
_BR_OFFSET = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})\s*([+-]\d{2}):?(\d{2})$")
_BR_INFORMAL = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2})h(\d{2})$")
_BR_PLAIN = re.compile(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2})$")


@dataclass
class TemporalParse:
    timestamp_raw: Optional[str]
    parsed: bool
    local_hour: Optional[int]
    offset: Optional[str]
    timezone_source: str          # explicit | none | ambiguous
    timestamp_utc: Optional[str]
    clock_quality: str            # HIGH | MEDIUM | LOW | UNKNOWN
    temporal_confidence: str
    note: str


def parse(raw: Optional[str], mode: str = "strict") -> TemporalParse:
    """Interpreta um timestamp bruto sob o modo escolhido (§18)."""
    if raw is None or str(raw).strip() == "":
        return TemporalParse(raw, False, None, None, "none", None, "UNKNOWN",
                             "UNKNOWN", "timestamp ausente")
    s = str(raw).strip()

    m = _ISO_OFFSET.match(s) or _BR_OFFSET.match(s)
    if m:
        if _ISO_OFFSET.match(s):
            _, _, _, hh, mm, _, oh, om = m.groups()
        else:
            _, _, _, hh, mm, oh, om = m.groups()
        hour = int(hh)
        return _with_offset(s, hour, int(mm), f"{oh}:{om}", mode)

    m = _BR_INFORMAL.match(s) or _BR_PLAIN.match(s)
    if m:
        _, _, _, hh, mm = m.groups()
        hour = int(hh)
        # Sem timezone explícito: representação incompleta (§19).
        return _no_offset(s, hour, int(mm), mode)

    return TemporalParse(s, False, None, None, "none", None, "UNKNOWN", "UNKNOWN",
                         "formato de timestamp não reconhecido")


def _resolve_hour(hour: int, mode: str) -> tuple[Optional[int], bool, str]:
    """Retorna (hora_local, ok, nota) tratando horas fora de faixa (ex.: 24)."""
    if 0 <= hour <= 23:
        return hour, True, ""
    if hour == 24:
        if mode == "naive":
            # Colapsa 24:00 -> 00h no MESMO dia: erro clássico de parser (§89).
            return 0, True, "24:00 colapsado para 00h pelo parser (modo naive)"
        # strict: hora ambígua, não força um valor (P3).
        return None, False, "24:00 é ambíguo (fim de dia vs início do dia seguinte)"
    if mode == "naive":
        return hour % 24, True, f"hora {hour} normalizada por módulo (modo naive)"
    return None, False, f"hora fora de faixa: {hour}"


def _with_offset(s: str, hour: int, minute: int, offset: str, mode: str) -> TemporalParse:
    local_hour, ok, note = _resolve_hour(hour, mode)
    if not ok:
        return TemporalParse(s, True, None, offset, "explicit", None, "UNKNOWN",
                             "UNKNOWN", note)
    # Timezone explícito, mas relógio de origem não validado (§19, P6).
    return TemporalParse(
        timestamp_raw=s, parsed=True, local_hour=local_hour, offset=offset,
        timezone_source="explicit", timestamp_utc=_to_utc_hint(local_hour, minute, offset),
        clock_quality="MEDIUM", temporal_confidence="MEDIUM",
        note=(note + "; " if note else "") + "timezone explícito, relógio não validado",
    )


def _no_offset(s: str, hour: int, minute: int, mode: str) -> TemporalParse:
    local_hour, ok, note = _resolve_hour(hour, mode)
    if not ok:
        return TemporalParse(s, True, None, None, "none", None, "UNKNOWN", "UNKNOWN", note)
    return TemporalParse(
        timestamp_raw=s, parsed=True, local_hour=local_hour, offset=None,
        timezone_source="none", timestamp_utc=None,
        clock_quality="LOW", temporal_confidence="LOW",
        note=(note + "; " if note else "") + "timestamp sem timezone",
    )


def _to_utc_hint(local_hour: int, minute: int, offset: str) -> str:
    """Indica a hora UTC correspondente (apenas representação — não é verdade)."""
    sign = 1 if offset[0] == "+" else -1
    oh = int(offset[1:3])
    utc_hour = (local_hour - sign * oh) % 24
    return f"~{utc_hour:02d}:{minute:02d}Z (conversão de representação)"


def as_dict(tp: TemporalParse) -> dict:
    return asdict(tp)


def quality_summary(parses: list[TemporalParse]) -> dict:
    """Distribuição das qualidades temporais (§19)."""
    counts: dict[str, int] = {}
    for p in parses:
        counts[p.clock_quality] = counts.get(p.clock_quality, 0) + 1
    return counts

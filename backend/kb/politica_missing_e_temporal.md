# Políticas — Missing Data e Temporal

## Missing Data Semantic Analyzer (§15)

Representações de ausência a detectar, sem assumir equivalência automática:
NULL, string vazia, "N/A", "NI", "não informado", "não consta", "0", "-1",
"999999", "01/01/1900". A pergunta correta é: "o que esta representação significa
nesta fonte?".

## Qualidade temporal (§18-19)

Cada timestamp recebe qualidade HIGH / MEDIUM / LOW / UNKNOWN com justificativa:
- timezone explícito, relógio não validado → MEDIUM;
- timestamp sem timezone → LOW;
- hora ambígua (ex.: 24:00) → UNKNOWN sob parser estrito.

Um parser ingênuo que colapsa 24:00 para meia-noite pode fabricar um pico
temporal espúrio (§89). A robustez do achado deve ser testada sob diferentes
decisões de parsing (Pattern Stability, §33).

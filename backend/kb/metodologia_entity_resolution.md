# Metodologia — Entity Resolution

Regras validadas para decisão de identidade (§22-25, §85).

- O pipeline é: blocking → comparação de atributos → similaridade → regras de
  decisão → MATCH | POSSIBLE | NON_MATCH.
- Similaridade de nome é medida com métricas de string (Jaro-Winkler, token),
  nunca "de cabeça" pelo LLM (§23).
- **Regra dos identificadores discriminantes**: quando dois identificadores
  altamente discriminantes (CPF e data de nascimento) conflitam, a decisão é
  NON_MATCH mesmo com nome idêntico — alto risco de false merge (§85).
- Fusões de alto impacto (conectam empresas, aumentam patrimônio, atribuem
  eventos entre identidades) exigem revisão humana (§25, HIGH IMPACT).
- Antes de aceitar uma fusão, simular o efeito (Impact Analysis, §26): a fusão
  apenas melhora a representação ou altera a narrativa analítica? (§27)

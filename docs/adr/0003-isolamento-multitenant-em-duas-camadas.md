# ADR-0003 — Isolamento multi-tenant em duas camadas

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead + Segurança
- **Relacionado**: [ADR-0001](0001-postgres-pgvector-como-banco-vetorial.md)

## Contexto

Escritórios de advocacia atendem partes adversas. O vazamento de conteúdo entre
organizações — ou entre casos com barreira ética dentro da mesma organização — é
violação de sigilo profissional, irreversível, e potencialmente fatal para o produto.

A abordagem usual em SaaS é filtrar por `tenant_id` na camada de aplicação. Funciona
enquanto todas as queries estiverem corretas. Basta uma consulta nova escrita sem o
filtro — em um relatório, em um job de manutenção, em um endpoint de exportação — para
que o isolamento falhe silenciosamente, sem erro e sem alarme.

## Decisão

Isolamento em **duas camadas independentes**, ambas obrigatórias:

1. **ABAC na aplicação** — decide o que pode ser pedido. Avalia papel, pertencimento ao
   caso, nível de sigilo, estado do recurso, barreiras éticas e contexto (MFA).
2. **Row-Level Security no PostgreSQL** — decide o que pode ser retornado. Políticas em
   todas as tabelas de domínio, com `FORCE ROW LEVEL SECURITY`, baseadas no contexto de
   sessão definido por `SET LOCAL` a partir do token validado.

Complementadas por: `org_id` em toda tabela; papel de aplicação sem `BYPASSRLS`;
negação explícita de barreiras éticas com precedência sobre qualquer concessão; suíte
adversarial no CI bloqueando merge.

## Justificativa

**As camadas falham por motivos diferentes.** A camada de aplicação falha por query
esquecida, refatoração descuidada ou endpoint novo. A RLS falha por política mal
escrita ou contexto não definido. Uma classe de erro não produz a outra — que é a
definição de defesa em profundidade útil, em oposição a redundância decorativa.

**A RLS protege o que a aplicação não vê.** Migrações, jobs de manutenção, relatórios
ad hoc e consoles de depuração são exatamente onde o filtro de aplicação costuma faltar.

**Negação por omissão.** Sem `projur.org_id` definido, `current_org_id()` retorna
`NULL`, nenhuma política casa e a query retorna zero linhas. O modo de falha padrão é
"não vê nada", não "vê tudo".

**`SET LOCAL` dentro da transação** garante que o contexto morre com ela — impedindo
que uma conexão reciclada do pool carregue o tenant da requisição anterior, que é o bug
clássico e mais perigoso desse padrão.

**Barreira ética como negação explícita** permite responder "por que esta pessoa não vê
este caso?" com uma linha do banco, em vez de com a ausência de uma linha. Auditoria
precisa de afirmações, não de silêncio.

## Consequências

**Positivas**: uma falha isolada em qualquer camada não produz vazamento; auditável por
terceiro; políticas são declarativas e legíveis; testes conseguem exercitar a camada de
banco sem passar pela aplicação.

**Negativas**: toda conexão precisa definir contexto — disciplina imposta por
middleware e testada; políticas RLS complexas têm custo no planejador, exigindo atenção
aos índices; testes precisam rodar com papel de aplicação real, e não como
superusuário, sob pena de não testarem nada; depuração exige lembrar do contexto.

**Custo aceito**: aproximadamente 4 a 6 pessoa-semanas adicionais no MVP, entre
implementação, políticas e suíte adversarial. É o melhor investimento de segurança
disponível neste produto.

## Verificação

- Teste de que a query sem contexto retorna zero linhas
- Teste de que o usuário da organização A jamais recupera chunk da organização B, em
  mais de 100 consultas adversariais
- Teste de que a barreira ética bloqueia membro do caso
- Teste de que o papel de aplicação não possui `BYPASSRLS`
- Verificação de que toda tabela de domínio nova tem `org_id` e política — checado no CI

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Só filtro na aplicação | Uma query esquecida vaza; sem rede de proteção |
| Só RLS | Mensagens de erro ruins; regras de negócio complexas ficam ilegíveis em SQL |
| Schema por organização | Isolamento forte, mas migrações e consultas cross-org (métricas, operação) tornam-se caras; centenas de schemas degradam o catálogo |
| Banco por organização | Isolamento máximo e custo operacional máximo; adequado ao tier dedicado, não ao padrão |

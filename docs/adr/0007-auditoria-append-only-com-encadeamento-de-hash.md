# ADR-0007 — Trilha de auditoria append-only com encadeamento de hash

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead + Segurança

## Contexto

A proposta exige registro de acessos, exportações, gerações, aprovações e alterações
(§10.1, RF-027, RF-028, CA-011). Em contexto jurídico, essa trilha pode ser invocada
para demonstrar quem aprovou o quê, quando, com base em qual fonte e com qual modelo.

Uma trilha que o próprio operador do sistema possa alterar sem deixar vestígio tem
valor probatório reduzido. Não se trata de desconfiar da equipe: trata-se de poder
**demonstrar** integridade, inclusive diante de comprometimento de credenciais.

## Decisão

`audit_event` com quatro propriedades:

1. **Append-only por privilégio**: `REVOKE UPDATE, DELETE ON audit_event FROM
   projur_app`. A aplicação insere e lê; não pode alterar nem apagar.
2. **Encadeamento de hash**: cada evento carrega `prev_hash` (do evento anterior da
   organização) e `entry_hash = SHA-256(canonical(evento) || prev_hash)`. Alterar um
   evento passado quebra a cadeia de todos os posteriores.
3. **Emissão transacional**: o evento é gravado na **mesma transação** da mutação que o
   originou. Se o evento falhar, a mutação também falha.
4. **Exportação WORM**: exportação diária do segmento do dia para storage com Object
   Lock, com o hash da última entrada assinado — âncora externa que detecta adulteração
   até mesmo de toda a tabela.

## Justificativa

**Privilégio revogado bloqueia o erro comum; hash detecta o ataque deliberado.** Um bug
que tentasse `UPDATE` falha imediatamente. Um invasor com acesso ao banco poderia
recalcular a cadeia inteira — mas não pode alterar o que já foi exportado com Object
Lock e ancorado.

**Emissão transacional garante CA-011 de fato.** Auditoria emitida "depois" da operação,
por evento assíncrono, perde registros exatamente quando mais importam: durante falhas.
Se está na mesma transação, ou os dois acontecem ou nenhum acontece.

**Canonicalização é o detalhe que faz o hash funcionar.** Serialização JSON canônica
(chaves ordenadas, sem espaços significativos, números normalizados, timestamps em UTC
com precisão fixa). Sem isso, a mesma informação produz hashes diferentes e a
verificação vira falso positivo.

**Cadeia por organização, não global.** Permite verificar e exportar por organização,
suporta o tier dedicado e evita que o volume de uma organização afete a verificação de
outra.

## Implementação

```sql
CREATE OR REPLACE FUNCTION audit_chain() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_prev bytea;
BEGIN
    SELECT entry_hash INTO v_prev
      FROM audit_event
     WHERE org_id = NEW.org_id
     ORDER BY id DESC
     LIMIT 1
     FOR UPDATE;                      -- serializa a cadeia por organização

    NEW.prev_hash  := v_prev;
    NEW.entry_hash := digest(
        canonical_json(to_jsonb(NEW) - 'entry_hash' - 'prev_hash')
        || coalesce(v_prev, ''::bytea),
        'sha256');
    RETURN NEW;
END $$;

CREATE TRIGGER trg_audit_chain
    BEFORE INSERT ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_chain();
```

Verificador executado diariamente e sob demanda: recalcula a cadeia por organização e
alerta em severidade máxima se divergir.

## Consequências

**Positivas**: integridade demonstrável; adulteração detectável; auditoria utilizável
como evidência; conformidade com CA-011 verificável por teste.

**Negativas**: o `FOR UPDATE` serializa inserções de auditoria **por organização** —
gargalo em teoria, irrelevante na escala prevista (dezenas de eventos por segundo por
organização, no pior caso). Se um dia importar, a mitigação é encadeamento em lote por
janela de tempo em vez de por evento. Além disso, a tabela cresce e exige
particionamento por período, e a exportação WORM tem custo de armazenamento.

**Não confundir com logs.** Logs de aplicação são operacionais, retidos por semanas,
descartáveis. Auditoria é jurídica, retida por anos, íntegra. São sistemas separados
com propósitos separados ([09 §2.1](../especificacao-tecnica/09-observabilidade-custos-e-avaliacao.md)).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Tabela comum sem restrição | Alterável sem vestígio; valor probatório baixo |
| Só privilégio revogado, sem hash | Não detecta alteração por quem tenha acesso privilegiado ao banco |
| Log externo (SIEM) como fonte primária | Bom como destino secundário; não garante emissão transacional com a mutação |
| Blockchain / ledger gerenciado | Complexidade e custo desproporcionais; a âncora WORM entrega a propriedade necessária |
| Event sourcing como arquitetura geral | Mudança arquitetural profunda, sem necessidade para os demais requisitos |

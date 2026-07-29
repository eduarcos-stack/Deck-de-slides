# 12 — Riscos técnicos

Os riscos da proposta (§16.1) reaparecem aqui com **gatilho observável**, **mitigação
implementada** e **plano de contingência**. Risco sem gatilho é preocupação; risco com
gatilho é algo que se pode monitorar e sobre o qual se pode agir a tempo.

## 1. Riscos herdados da proposta

### R1 — Alucinação ou atribuição falsa
**Impacto**: erro jurídico e reputacional. **Probabilidade sem mitigação**: alta.

| Gatilho observável | Mitigação | Contingência |
|---|---|---|
| Fidelidade < 0,95 ou atribuição < 0,98 no conjunto de avaliação | Citação por identificador resolvível; verificador em quatro camadas; gates bloqueantes; abstenção como valor válido | Bloquear geração para o tipo de bloco afetado até correção; reverter para o modelo anterior |

Nota: a camada 3 do verificador (determinística) cobre a subclasse mais perigosa —
datas, valores e números de processo — sem depender de julgamento de modelo. Se as
camadas semânticas falharem, essa continua funcionando.

### R2 — Vazamento entre clientes
**Impacto**: violação de sigilo profissional; irreversível. **Probabilidade sem
mitigação**: média — e média já é inaceitável aqui.

| Gatilho | Mitigação | Contingência |
|---|---|---|
| Qualquer resultado da suíte adversarial diferente de zero | Filtro pré-busca; RLS forçada; `org_id` em toda tabela; barreiras éticas como negação; teste no CI bloqueando merge | Severidade máxima: contenção imediata, investigação por trilha de auditoria, notificação ao escritório e à ANPD quando aplicável |

Este é o risco que orienta mais decisões desta especificação do que qualquer outro:
banco único para vetores, RLS forçada, ausência de GraphQL, monólito modular.

### R3 — Base interna desatualizada
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Ativos vencidos recuperados > 0; ativos sem revalidação há > N dias | `valid_until` obrigatório; filtro de validade na recuperação; retirada remove do índice na mesma transação; alerta ao curador | Suspender a base interna na recuperação até a curadoria concluir |

### R4 — Dados jurimétricos incompletos ou enganosos
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Cobertura < 80 %; kappa < 0,75; ausentes > 20 % | Envelope de metodologia obrigatório no tipo de retorno; variável não validada não é publicada; limitações sempre visíveis | Gate da Sprint 8: jurimetria sai do MVP ([06 §10](06-jurimetria.md)) |

### R5 — Automação do fluxo errado
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Baixa taxa de conclusão do fluxo no piloto; retorno ao processo externo | Discovery, baseline, escolha do recorte com o design partner, piloto restrito | Trocar o recorte de peça; a arquitetura não é específica de um tipo de peça |

### R6 — Confiança excessiva do usuário
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Tempo de revisão cai muito e correções pós-aprovação sobem | Design de incerteza; rótulos epistêmicos; gates; criticidade por operação; métricas de proteção com poder de veto | Aumentar a fricção nos gates críticos; treinamento; revisão obrigatória por segundo revisor no tipo de bloco afetado |

### R7 — Desconfiança absoluta
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Usuários abrem todos os documentos fora do sistema para conferir | Rastreabilidade em um clique; destaque do trecho exato; comparação com baseline; testes de usabilidade | Investigar se a falha é de precisão ou de apresentação da evidência — são problemas diferentes com soluções diferentes |

### R8 — Custo variável de IA
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Custo por caso acima do previsto; consumo anômalo | Cascata de verificação; roteamento por tier; geração por blocos; cotas; disjuntor; atribuição por caso | Rebaixar tier em operações de alto volume; ampliar uso de modelos autogerenciados |

### R9 — Dependência de fornecedor
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Mudança de preço, política, disponibilidade regional ou descontinuação | Gateway com tiers lógicos; embeddings versionados por chunk; sem framework proprietário; IaC neutro | Trocar o mapeamento tier → modelo; reindexar com índice sombra se o embedding mudar |

### R10 — Complexidade excessiva no MVP
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Velocidade abaixo do planejado por três sprints seguidas | Recorte por peça, área, equipe e fonte; marcos com portão; jurimetria isolável | Cortar jurimetria, depois memória institucional; o núcleo documento → tese → peça → revisão é indivisível |

## 2. Riscos adicionais identificados na análise técnica

Não constam da proposta e são consequência de decisões desta especificação.

### R11 — Qualidade do OCR sobre acervo real
**Impacto**: alto. Recuperação sobre texto ruim degrada tudo o que vem depois, de
forma difícil de perceber — o sistema parece funcionar e responde mal.

| Gatilho | Mitigação | Contingência |
|---|---|---|
| Confiança média de OCR abaixo do limiar; páginas ilegíveis acima de N % | Medição real na Sprint 0; qualidade por página exposta ao usuário; cascata de extração | Serviço externo de Document AI sob autorização explícita; ou excluir do escopo os documentos de qualidade insuficiente, declarando a exclusão |

Este é o risco mais subestimado em projetos de RAG jurídico e a razão de a prova
técnica da Sprint 0 usar documentos reais, não amostras limpas.

### R12 — Desempenho do índice vetorial com filtro seletivo
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Latência de busca p95 acima de 1,5 s; recall caindo com filtro estreito | Teste de carga na Sprint 3; ajuste de `ef_search`; varredura exata em casos pequenos | Particionar o índice por `matter_id`; se persistir, banco vetorial dedicado com replicação da fronteira de autorização — reavaliando [ADR-0001](../adr/0001-postgres-pgvector-como-banco-vetorial.md) |

### R13 — Editor com marcas de evidência
**Impacto**: médio-alto sobre o cronograma. É o componente mais complexo do frontend.

| Gatilho | Mitigação | Contingência |
|---|---|---|
| Marcas perdidas em operações de edição; conflito em colaboração | Modelo de documento do ProseMirror; testes de propriedade sobre transformações; alerta quando a edição rompe o vínculo | Reduzir a colaboração simultânea no MVP para edição com bloqueio por bloco |

### R14 — Qualidade dos modelos em português jurídico
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Extração ou geração abaixo do limiar em pt-BR | Bake-off com dados reais; avaliação por tarefa e não por impressão; reavaliação trimestral | Trocar modelo no tier; ajustar prompts; em último caso, ajuste fino de modelo aberto para tarefas específicas de extração |

### R15 — Disponibilidade de especialista jurídico
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Conjuntos de avaliação atrasados; validações represadas | Alocação formal desde a Sprint 0; anotação em lotes pequenos e frequentes | Reduzir o tamanho dos conjuntos mantendo a estratificação; contratar apoio externo de anotação sob NDA |

Registrado como risco técnico porque bloqueia entregas de engenharia: sem gabarito
anotado, os gates de avaliação não têm sentido e o CI vira teatro.

### R16 — Injeção de prompt via documento ingerido
| Gatilho | Mitigação | Contingência |
|---|---|---|
| Taxa de resistência abaixo de 0,95 no conjunto adversarial | Separação instrução/dados; saída estruturada; verificador; ausência de ferramentas destrutivas; egresso restrito | Endurecer a detecção; isolar o documento suspeito; revisão manual obrigatória para o caso afetado |

### R17 — Deriva silenciosa de qualidade
**Impacto**: alto e insidioso. O provedor atualiza o modelo, os prompts continuam
iguais e a qualidade muda sem que ninguém perceba.

| Gatilho | Mitigação | Contingência |
|---|---|---|
| Avaliação diária detecta variação além do limiar sem mudança no nosso código | Avaliação agendada, não só em PR; `model_id` e versão gravados em cada `ai_run`; painel de tendência | Fixar versão do modelo quando o provedor permitir; reverter o roteamento do tier |

## 3. Mapa de calor

| Risco | Probabilidade | Impacto | Prioridade |
|---|---|---|---|
| R2 Vazamento entre clientes | Baixa (com mitigação) | Máximo | **Crítica** |
| R1 Alucinação | Média | Alto | **Crítica** |
| R11 Qualidade de OCR | Alta | Alto | **Alta** |
| R4 Dados jurimétricos | Alta | Médio | **Alta** |
| R8 Custo de IA | Média | Alto | **Alta** |
| R15 Especialista jurídico | Média | Alto | **Alta** |
| R6 Confiança excessiva | Média | Alto | Média-alta |
| R12 Desempenho do índice | Média | Médio | Média |
| R13 Editor | Média | Médio | Média |
| R17 Deriva de qualidade | Média | Médio | Média |
| R14 Modelos em pt-BR | Baixa-média | Médio | Média |
| R5 Fluxo errado | Média | Alto | Média |
| R10 Complexidade | Média | Médio | Média |
| R16 Injeção de prompt | Média | Médio | Média |
| R3 Base desatualizada | Baixa | Médio | Baixa |
| R7 Desconfiança | Baixa-média | Médio | Baixa |
| R9 Fornecedor | Média | Baixo (com gateway) | Baixa |

## 4. Rituais de gestão de risco

| Ritual | Frequência | Conteúdo |
|---|---|---|
| Revisão de gatilhos | Semanal, no ritual de métricas | Cada gatilho é uma métrica em painel; nenhum é avaliado por opinião |
| Revisão de riscos | Por sprint | Reavaliar probabilidade e impacto; registrar novos |
| Revisão de decisão arquitetural | Por marco | ADRs continuam válidos diante do que foi aprendido? |
| Post-mortem | Por incidente | Sem culpabilização, com ação registrada e teste de regressão |

Um risco só é gerenciado quando alguém consegue dizer, olhando um painel, se ele está
piorando. Todos os gatilhos acima foram escritos com essa restrição.

---

**Anterior**: [11 — Estimativa de esforço e sprints](11-estimativa-esforco-e-sprints.md) · **Próximo**: [13 — Estratégia de MVP](13-estrategia-de-mvp.md)

# 13 — Estratégia de MVP

## 1. A hipótese a provar

A proposta define (§12.1):

> O sistema consegue reduzir retrabalho e tempo em um fluxo jurídico recorrente sem
> reduzir o controle, a rastreabilidade e a qualidade da revisão?

A formulação é boa porque é falsificável em duas direções. Um MVP que reduza tempo
destruindo a rastreabilidade falha. Um MVP que preserve a rastreabilidade sem reduzir
tempo também falha. As duas metades precisam ser medidas, e as métricas de proteção
existem para que a segunda metade não seja esquecida na comemoração da primeira.

## 2. Recorte

| Dimensão | Recorte | Por quê |
|---|---|---|
| Escritórios | 1 design partner | Feedback profundo vale mais que amplitude; multi-tenancy existe desde o dia 1 mas não é exercitada comercialmente |
| Usuários | 5 a 15 | Suficiente para observar o fluxo, pequeno o bastante para acompanhamento diário |
| Área jurídica | 1 | Templates, taxonomia e chunking estrutural são específicos por área |
| Tipo de peça | 1, de alta frequência e repetibilidade | Critérios de §12.2 |
| Bases de recuperação | Documentos do caso + base interna curada | Fontes externas licenciadas ficam para a Fase 2 |
| Jurimetria | 1 recorte, 3–5 indicadores, sujeita a gate | [06 §9](06-jurimetria.md) |
| Integrações | Nenhuma com sistemas do escritório | Upload manual é suficiente para provar a hipótese |
| Idioma e jurisdição | pt-BR, jurisdição brasileira | — |

## 3. Escopo incluído

| Capacidade | Nível no MVP |
|---|---|
| Autenticação, MFA, organizações, papéis, permissões | Completo, com 6 papéis fixos |
| Barreiras éticas | Completo |
| Casos, equipe, prazos, sigilo, status | Completo |
| Upload, extração, OCR, dedupe, classificação, correção humana | Completo |
| Falha parcial e qualidade por página | Completo (CA-012) |
| Entidades, fatos, cronologia, lacunas, inconsistências | Completo |
| Vínculo de evidência e propagação de impacto | Completo (CA-004, CA-010) |
| RAG sobre documentos do caso e base interna | Completo, com híbrida, rerank e atribuição |
| Sugestão, validação e confronto de teses | Completo |
| Geração de um tipo de peça por blocos | Completo |
| Verificador de suporte e gates de qualidade | Completo |
| Versões, comparação, comentários, exportação | Completo |
| Promoção controlada de ativos institucionais | Completo |
| Jurimetria em recorte validado | Restrito, com gate |
| Auditoria append-only encadeada | Completo |
| Observabilidade e atribuição de custo | Completo |
| Métricas de produto contra baseline | Essenciais |

## 4. Escopo excluído e o motivo técnico

A proposta já lista o que fica fora (§12.3). Aqui, o motivo de engenharia — que é o
que permite discutir a exclusão com base em custo, e não em preferência.

| Fora do MVP | Motivo técnico |
|---|---|
| Todas as áreas jurídicas | Cada área exige taxonomia, templates e chunking estrutural próprios; o custo cresce por área, não por código |
| Agentes autônomos com execução externa | Aumenta drasticamente a superfície de risco de injeção e de ação indevida, sem provar a hipótese |
| Protocolização automática | Integração com sistemas processuais é projeto próprio, com risco jurídico próprio |
| Integração com softwares jurídicos | Cada conector é esforço dedicado; upload manual prova a hipótese |
| Personalização profunda por escritório | Exige um motor de configuração maduro; MVP versiona prompts e templates em código |
| Jurimetria nacional e multitemática | Volume de coleta e validação inviável no prazo; qualidade cairia |
| Automação de atendimento ao cliente | Fora da tese do produto |
| Modelos preditivos individualizados de magistrados | Tecnicamente possível, **eticamente e juridicamente arriscado**, e contrário ao princípio de que indicadores descrevem conjuntos e não predizem casos |
| Marketplace de teses entre escritórios | Compartilhar conteúdo entre organizações contradiz o isolamento que é o requisito central |
| Aplicativos móveis nativos | Web responsiva atende o fluxo de trabalho |
| API pública | Superfície de autorização adicional; ver [08 §7](08-integracoes.md) |
| Tier de instância dedicada | Arquitetura preparada; provisionamento automatizado fica para a Fase 2 |

Duas exclusões merecem nota porque não são apenas de prazo. **Modelos preditivos por
magistrado** e **marketplace entre escritórios** contradizem princípios do produto, não
apenas o cronograma: a primeira transforma descrição estatística em predição
individual; a segunda quebra o isolamento. Nenhuma das duas deveria voltar ao roadmap
sem discussão de produto e jurídica, e não apenas por decisão técnica.

## 5. Critérios de saída

Os critérios de §12.5 da proposta, com medição definida. Todos precisam ser atendidos.

| # | Critério | Como será medido | Limiar |
|---|---|---|---|
| 1 | Fluxo completo executado por usuários reais | Casos concluídos ponta a ponta no piloto | ≥ 10 casos, ≥ 3 usuários distintos |
| 2 | Redução mensurável de tempo | Comparação com o baseline da mesma tarefa | Redução ≥ 30 % no tempo até a primeira minuta revisável |
| 3 | Rastreabilidade funcional | Amostra auditada: afirmação → trecho de origem | ≥ 98 % das afirmações materiais resolvem em um clique |
| 4 | Ausência de vazamento | Suíte adversarial + auditoria do piloto | **Zero** ocorrências |
| 5 | Afirmações materiais sem fonte | Verificador sobre as peças produzidas | ≤ 2 % |
| 6 | Revisores identificam origem, alterações e pendências | Teste de tarefa com revisores reais | ≥ 80 % de sucesso sem apoio |
| 7 | Indicadores jurimétricos reproduzíveis | Reexecução sobre a amostra versionada | 100 % de reprodutibilidade |
| 8 | Registro adequado de eventos críticos | Auditoria de cobertura de eventos | 100 % das ações críticas com evento |

Os critérios 4, 7 e 8 são absolutos: não admitem tolerância. Os demais admitem faixa e
discussão. Essa distinção é deliberada — tolerar 99 % de isolamento é tolerar
vazamento.

## 6. Decisões que bloqueiam a engenharia

Das dez decisões em aberto de §16.3, sete precisam de resposta antes da sprint
indicada. As demais podem ser tomadas durante o MVP.

| Decisão | Quem decide | Prazo | O que trava se atrasar |
|---|---|---|---|
| Área e peça inicial | Produto + jurídico | Sprint 1 | Templates, taxonomia, chunking estrutural, conjuntos de avaliação |
| Escritório design partner | Sponsor | Sprint 0 | Documentos reais, baseline, testes com usuários |
| Fontes externas licenciadas | Jurídico + comercial | Fase 2 | Nada no MVP; base interna é suficiente |
| Modelos e infraestrutura | Tech lead + sponsor | Sprint 1 | Bake-off; escolha do provedor |
| Estratégia de implantação | Comercial + técnico | Fase 2 | Nada no MVP; padrão é multi-tenant lógico |
| Integrações indispensáveis | Produto | Fase 2 | Nada no MVP |
| Formatos de exportação | Produto + jurídico | Sprint 7 | Implementação da exportação |
| Recorte jurimétrico | Produto + jurídico + dados | Sprint 5 | E11 inteiro |
| Políticas de aprovação | Jurídico | Sprint 5 | Configuração do workflow de teses e peças |
| Métricas-alvo | Sponsor + produto | Sprint 2 | Definição dos limiares de sucesso e de interrupção |

## 7. Plano do piloto

| Semana | Atividade |
|---|---|
| −4 | Medição do baseline com usuários reais, no processo atual |
| −2 | Treinamento; carga do acervo autorizado; curadoria inicial da base interna |
| −1 | Ensaio com casos históricos já concluídos; ajustes |
| 1–2 | Piloto assistido: acompanhamento diário, correções rápidas |
| 3–4 | Piloto com autonomia; observação; coleta de métricas |
| 5 | Avaliação contra os critérios de saída; decisão de seguir, ajustar ou interromper |

**Critério de interrupção do piloto**: qualquer ocorrência de vazamento entre casos ou
organizações; ou taxa de afirmações sem fonte acima de 5 %; ou rejeição consistente do
fluxo pelos usuários com retorno ao processo externo. Interromper cedo custa menos que
insistir — e a proposta pede explicitamente "critérios de interrupção ou expansão".

## 8. Da prova de valor ao produto

Atingidos os critérios de saída, a sequência de expansão, em ordem de dependência
técnica e não de apelo comercial:

1. **Endurecimento operacional** — SLA maior, tier dedicado, SSO corporativo,
   administração completa. Sem isso, o segundo cliente custa o dobro do primeiro.
2. **Segundo tipo de peça na mesma área** — valida que a arquitetura de templates
   generaliza, com custo baixo.
3. **Fontes jurídicas externas licenciadas** — maior salto de valor percebido, depende
   de contrato.
4. **Segunda área jurídica** — valida que taxonomia e chunking generalizam; é aqui que
   se descobre o custo real de escalar por área.
5. **Integrações com o acervo do escritório** — reduz atrito de adoção.
6. **Ampliação da jurimetria** — novos recortes, sempre com o mesmo rigor
   metodológico.

A ordem tem uma lógica: cada passo só começa quando o anterior provou que a
generalização era barata. Inverter — vender várias áreas antes de provar que a segunda
peça é barata — é a forma mais comum de um MVP bem-sucedido virar um produto
insustentável.

---

**Anterior**: [12 — Riscos técnicos](12-riscos-tecnicos.md) · **Índice**: [README](../../README.md)

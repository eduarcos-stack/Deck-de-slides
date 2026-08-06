# GLAUX — Landing page institucional

Página institucional de lançamento da GLAUX, instituição de educação aplicada em
tecnologia, investigação e evidência.

Arquivo único e autocontido: [`index.html`](index.html). Sem build, sem dependências
de runtime. As únicas requisições externas são as fontes Sora e Inter (Google Fonts),
com fallback para a pilha de sistema.

Para visualizar localmente:

```bash
npx http-server -p 8080
# http://localhost:8080
```

## Fontes normativas

- **Briefing da landing page** (estrutura de 13 seções, copy, regras de formulário,
  conteúdo que não pode ser inventado).
- **`DESIGN2.md`** (`version: alpha`) — cores, tipografia, espaçamento, grid,
  componentes, formas, contraste e regras da palavra-marca.

A copy das seções e os rótulos de CTA reproduzem o briefing literalmente.

## Estrutura

Segue a ordem enumerada no briefing:

1. Cabeçalho · 2. Hero · 3. O problema · 4. O que a GLAUX pretende desenvolver ·
5. Para quem · 6. Como a GLAUX pensa · 7. Temas de interesse · 8. Sobre a GLAUX ·
9. Coordenação acadêmica · 10. Formulário de interesse · 11. FAQ ·
12. CTA final · 13. Rodapé

## Design system aplicado

Tokens do `DESIGN2.md` mapeados em custom properties CSS (`:root`):

| Grupo | Aplicação |
|---|---|
| Cores | `primary #0B1D33`, `primary-container #15403D`, `secondary #2D6B63`, `secondary-soft #7EA398`, `neutral #E6E8E4`, `surface-alt #F2F3F2`, `error #B42318` |
| Tipografia | Sora 600 (headlines) e Inter 400/600 (corpo e rótulos) — duas famílias, dois pesos |
| Grid | 1200px máx.; gutters 20px (mobile) / 24px (tablet) / 32px (desktop) |
| Raios | 4px controles · 8px botões, inputs, acordeão · 12px cards · full em chips |
| Botões/inputs | altura mínima de 48px, rótulo persistente, foco em Verde de Destaque |

A página alterna branco, off-white, Azul Institucional e Verde-petróleo — não é uma
interface integralmente escura.

### Gramática visual

Campos, pontos, linhas e controles com função semântica: linhas contínuas para
relações documentadas, linhas tracejadas para lacuna ou relação não confirmada,
ponto destacado para validação. Sem ícones genéricos de segurança, sem coruja,
sem estética de hacking.

## Acessibilidade

- Contraste verificado programaticamente em todos os nós de texto: **0 falhas AA**
  (4.5:1 normal, 3:1 grande).
- Foco visível, navegação por teclado, `Esc` fecha o menu mobile.
- Alvos de toque ≥ 44px (exceto links inline em frase corrida, isentos pelo 2.5.8).
- Estados de erro comunicados por ícone + texto, nunca apenas por cor.
- Hierarquia de headings sem saltos; `aria-live` nas mensagens do formulário.
- `prefers-reduced-motion` respeitado.

### Movimento

O hero anima uma vez — pontos dispersos organizando-se em estrutura — e encerra o
`requestAnimationFrame`. Não há laço contínuo. Com `prefers-reduced-motion` o
estado final é desenhado direto.

## Pendências antes da publicação

Nenhum dado de contato, métrica, cliente, curso ou credencial foi inventado. Os
pontos abaixo estão marcados no HTML e precisam de insumo ou validação:

| Item | Onde | Situação |
|---|---|---|
| **Palavra-marca vetorial oficial** | cabeçalho e rodapé | **Bloqueante.** O `DESIGN2.md` proíbe recompor a palavra GLAUX em Sora ou qualquer fonte. O arquivo vetorial não foi fornecido; há um stand-in em texto que **não deve ir ao ar**. Requer o SVG oficial (mín. 120px de largura; versão negativa para fundos escuros). |
| Símbolo reduzido / favicon | `<head>` | Não fornecido |
| Endpoint do formulário | seção 10 | Nenhuma integração configurada; o envio é validação e feedback no cliente |
| Foto da coordenação acadêmica | seção 9 | `[INSERIR FOTO APROVADA]` |
| Biografia do fundador | seção 9 | `[VALIDAR DOCUMENTALMENTE BIOGRAFIA, CARGOS, TEMPO DE EXPERIÊNCIA, PUBLICAÇÕES E EVENTOS]` |
| E-mail institucional e Instagram | rodapé | Placeholders |
| Política de privacidade e Termos | rodapé e formulário | Placeholders |
| CNPJ | rodapé | `[INSERIR CNPJ SOMENTE APÓS VALIDAÇÃO]` |
| Meta description | `<head>` | Marcada para validação — alguns temas ainda não são oferta |

## Decisões e divergências registradas

Três pontos em que as fontes normativas conflitam entre si ou com o WCAG. Todos
resolvidos de forma conservadora e sinalizados para decisão:

1. **Rótulos de CTA.** O `DESIGN2.md` sugere "Fale sobre uma capacitação" /
   "Conheça as formações"; o briefing define, de forma repetida e literal,
   "Registrar meu interesse" / "Conhecer a GLAUX". Adotados os do briefing, por ser
   a instrução específica desta página. Reversível em um único ponto do HTML.

2. **`on-surface-muted` (#73787C).** Rende 4.46:1 sobre branco — abaixo do AA que o
   próprio documento exige. Texto corrido usa `on-surface`; textos auxiliares usam
   `--muted-aa` (#5F6469, 5.98:1). O token original permanece declarado no `:root`
   para referência.

3. **Ordem das seções.** A ordem "recomendada" do `DESIGN2.md` inclui *Diferenciais*
   e *Conteúdos e eventos verificados*, que o briefing não pede e para os quais não
   há conteúdo aprovado — criá-las exigiria inventar material. Mantida a estrutura
   enumerada do briefing.

Uma quarta observação, sem conflito: sobre o Verde-petróleo, `secondary-soft`
(#7EA398) fica em 4.14:1. Nesses blocos o texto auxiliar usa um tom derivado mais
claro (#9DBEB4, 5.7:1). O `secondary-soft` permanece em uso estrutural e decorativo,
conforme o documento.

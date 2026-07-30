# Página de inscrições para evento

`index.html` — página única (HTML + CSS + JS, sem dependências) com landing page do evento
e formulário de inscrição.

## Como usar

Abra o arquivo no navegador ou publique em qualquer hospedagem estática
(GitHub Pages, Netlify, Vercel, Hostinger...).

Todo o conteúdo editável está no objeto `CONFIG`, no início do `<script>`:

```js
const CONFIG = {
  nome: "Nome do Evento",
  titulo: "Título do evento vai aqui",
  data: "12 de setembro de 2026",
  horario: "19h às 21h30",
  local: "Auditório — Rua Exemplo, 123, Vitória/ES",
  preco: "Gratuito",
  vagas: 80,          // null para esconder o contador de vagas
  contato: "contato@exemplo.com",
  endpoint: null      // ver abaixo
};
```

Programação e FAQ ficam no HTML (seções `Programação` e `Perguntas frequentes`).

## Onde as inscrições são gravadas

| `CONFIG.endpoint` | Comportamento |
| --- | --- |
| `null` (padrão) | Salva no `localStorage` do navegador. Serve para testar. |
| URL | Envia `POST` com JSON (`Content-Type: application/json`). |

Campos enviados: `nome`, `email`, `telefone`, `organizacao`, `cargo`,
`modalidade`, `origem`, `obs`, `evento`, `criadoEm`.

### Ligando a uma planilha do Google (grátis)

1. Na planilha: **Extensões → Apps Script**.
2. Cole:

```js
function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  SpreadsheetApp.getActiveSheet().appendRow([
    d.criadoEm, d.nome, d.email, d.telefone,
    d.organizacao, d.cargo, d.modalidade, d.origem, d.obs
  ]);
  return ContentService.createTextOutput("ok");
}
```

3. **Implantar → Nova implantação → App da Web**, acesso "Qualquer pessoa".
4. Cole a URL gerada em `CONFIG.endpoint`.

Serviços como Formspree, Basin ou uma API própria funcionam do mesmo jeito.

## Painel do organizador

Acesse a página com `?admin` na URL (ex.: `index.html?admin`) para ver as inscrições
gravadas localmente, baixar o CSV (separador `;`, abre direto no Excel) ou limpar a lista.
O painel lê apenas o `localStorage` — com `endpoint` configurado, os dados ficam no destino remoto.

## O que já está pronto

- Validação de nome, e-mail, telefone e aceite dos termos, com mensagens acessíveis
  (`aria-invalid` / `aria-describedby`)
- Máscara automática de telefone brasileiro
- Bloqueio de e-mail duplicado (no modo local)
- Contador de vagas restantes
- Tema claro e escuro automáticos, layout responsivo
- Exportação CSV com BOM UTF-8

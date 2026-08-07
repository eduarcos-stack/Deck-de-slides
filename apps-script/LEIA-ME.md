# Endpoint do formulário — Google Apps Script

Passo a passo para ligar o formulário de registro de interesse a uma planilha.

## 1. Criar a planilha

1. Crie uma planilha no Google Sheets (ex.: `GLAUX — Registro de interesse`).
2. Copie o **ID** da URL — é o trecho entre `/d/` e `/edit`:
   `docs.google.com/spreadsheets/d/`**`1AbC...XyZ`**`/edit`

Não precisa criar aba nem cabeçalho: o script faz isso no primeiro envio.

## 2. Criar o script

1. Na planilha: **Extensões › Apps Script**.
2. Apague o conteúdo do `Código.gs` e cole o de [`Codigo.gs`](Codigo.gs).
3. Preencha no topo do arquivo:
   - `PLANILHA_ID` — o ID do passo 1.
   - `NOTIFICAR_EMAIL` — e-mail para aviso de novo registro, ou `''` para desligar.
4. Salve.

## 3. Implantar

1. **Implantar › Nova implantação**.
2. Engrenagem › tipo **Aplicativo da Web**.
3. Configure:

   | Campo | Valor |
   |---|---|
   | Executar como | **Eu** |
   | Quem pode acessar | **Qualquer pessoa** |

4. **Implantar**. O Google vai pedir autorização — aceite. A tela de aviso
   "app não verificado" é esperada em script próprio: **Avançado › Acessar
   (não seguro)**.
5. Copie a **URL do aplicativo da Web**, terminada em `/exec`.

> "Qualquer pessoa" é obrigatório: quem envia o formulário não está logado no
> Google. Quem executa é você — o script grava na planilha com a sua permissão,
> mas ninguém ganha acesso à planilha por isso.

## 4. Ligar na página

Em [`../index.html`](../index.html), substitua o valor de `ENDPOINT_FORMULARIO`
pela URL `/exec`:

```js
var ENDPOINT_FORMULARIO = "https://script.google.com/macros/s/AKfy.../exec";
```

Enquanto o valor começar com `COLE_AQUI`, o formulário recusa o envio e mostra
mensagem de indisponibilidade — de propósito, para não fingir sucesso.

## 5. Testar

Publique a página e envie um registro de teste. Deve aparecer uma linha nova na
aba `Interesses`.

Se falhar, abra o console do navegador (F12). Os erros mais comuns:

| Sintoma | Causa provável |
|---|---|
| `Failed to fetch` / erro de CORS | Implantação não está como "Qualquer pessoa" |
| `HTTP 401` ou `403` | Idem, ou a autorização do passo 3.4 não foi concluída |
| `HTTP 404` | URL errada — precisa terminar em `/exec`, não `/dev` |
| Resposta `ok:false` com "Campos obrigatórios" | Validação do servidor barrou; confira os nomes dos campos |

No lado do Google, os erros ficam em **Execuções**, no editor do Apps Script.

## Ao alterar o script depois

Editar o código **não** atualiza o que está no ar. É preciso
**Implantar › Gerenciar implantações › ✏️ › Versão: Nova versão › Implantar**.
A URL `/exec` continua a mesma.

## Notas técnicas

**Por que `text/plain`.** O Apps Script não responde a requisições de verificação
prévia (`OPTIONS`). Enviar JSON com `Content-Type: application/json` dispara esse
preflight e o envio falha com erro de CORS. Com `text/plain` o navegador trata
como requisição simples, sem preflight. O corpo continua sendo JSON — só o
cabeçalho muda.

**Anti-robô.** O formulário tem um campo `website` invisível. Robôs preenchem
tudo que encontram no HTML; pessoas não veem o campo. Se vier preenchido, o
script responde sucesso e descarta — assim o robô não descobre que foi barrado.
Não é proteção forte, mas resolve o spam automatizado comum.

**Injeção de fórmula.** Valores começados por `=`, `+`, `-` ou `@` recebem uma
aspa simples antes de ir para a planilha. Sem isso, um envio malicioso poderia
gravar uma fórmula que executa ao abrir o arquivo.

**Concorrência.** A gravação usa `LockService`, para dois envios simultâneos não
disputarem a mesma linha.

## Limites de cota

Conta Google gratuita, por dia: 20.000 requisições ao aplicativo da Web e 100
e-mails via `MailApp`. Contas Workspace têm limites maiores. Para uma landing
page de captação, folgado.

## LGPD

O script grava nome, e-mail, organização, área, tema, formato, mensagem e o
registro do consentimento com data e hora. O consentimento é obrigatório — o
servidor recusa envio sem ele, mesmo que alguém contorne a validação do
navegador.

Pendências antes de publicar:

- A política de privacidade ainda é um placeholder no `index.html`. O
  consentimento aponta para um link vazio.
- Definir quem tem acesso à planilha e por quanto tempo os dados ficam
  guardados.

/**
 * GLAUX — Registro de interesse
 * Recebe os envios do formulário da landing page e grava numa planilha.
 *
 * Implantação: Implantar › Nova implantação › Aplicativo da Web
 *   Executar como .......... Eu
 *   Quem pode acessar ...... Qualquer pessoa
 * A URL /exec resultante vai em ENDPOINT_FORMULARIO no index.html.
 *
 * Nota sobre CORS: o Apps Script não responde a requisições de verificação
 * prévia (OPTIONS). Por isso a página envia com Content-Type text/plain —
 * assim o navegador trata como requisição simples e não dispara o preflight.
 * O corpo continua sendo JSON. Não troque para application/json: quebra.
 */

// ---------------------------------------------------------------- configuração

/** ID da planilha — o trecho entre /d/ e /edit na URL. */
var PLANILHA_ID = '1vXrvtdQ5ThfQI59Fhmde-Sc9kPWLEk-SCMrnNhFkBIs';

/** Nome da aba. Criada automaticamente se não existir. */
var ABA = 'Interesses';

/** E-mail para aviso de novo registro. Deixe '' para não notificar. */
var NOTIFICAR_EMAIL = '';

/** Colunas da planilha, na ordem. */
var COLUNAS = [
  'Data/hora', 'Nome', 'E-mail', 'Organização', 'Área de atuação',
  'Tema', 'Formato', 'Mensagem', 'Consentimento', 'Origem'
];

// ---------------------------------------------------------------- entrada

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return json({ ok: false, erro: 'Requisição sem corpo.' });
    }

    var d;
    try {
      d = JSON.parse(e.postData.contents);
    } catch (err) {
      return json({ ok: false, erro: 'Corpo inválido.' });
    }

    // Armadilha anti-robô: o campo é invisível para pessoas. Se veio
    // preenchido, respondemos sucesso sem gravar — o robô não aprende que
    // foi barrado e não fica tentando variações.
    if (d.website) return json({ ok: true });

    var faltando = validar(d);
    if (faltando.length) {
      return json({ ok: false, erro: 'Campos obrigatórios: ' + faltando.join(', ') });
    }

    gravar(d);
    notificar(d);

    return json({ ok: true });

  } catch (err) {
    // O detalhe completo fica em Execuções, no editor do Apps Script.
    console.error('Falha ao registrar interesse: ' + err.stack);

    // DIAGNOSTICO: com true, a mensagem real volta na resposta HTTP. Útil para
    // ligar o formulário pela primeira vez. Volte para false antes de publicar —
    // mensagem de erro de servidor não deve chegar ao navegador de visitante.
    var DIAGNOSTICO = false;

    return json({
      ok: false,
      erro: DIAGNOSTICO ? String(err.message) : 'Erro interno.'
    });
  }
}

function doGet() {
  return json({ ok: true, servico: 'GLAUX — registro de interesse' });
}

// ---------------------------------------------------------------- validação

function validar(d) {
  var faltando = [];
  if (!texto(d.nome)) faltando.push('nome');
  if (!emailValido(d.email)) faltando.push('e-mail');
  if (!texto(d.tema)) faltando.push('tema');
  if (!texto(d.formato)) faltando.push('formato');
  if (d.consentimento !== true) faltando.push('consentimento');
  return faltando;
}

function texto(v) {
  return typeof v === 'string' && v.trim() !== '';
}

function emailValido(v) {
  return texto(v) && /^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(v.trim());
}

// ---------------------------------------------------------------- gravação

function gravar(d) {
  // Trava para não perder linha se dois envios chegarem juntos.
  var trava = LockService.getScriptLock();
  trava.waitLock(20000);

  try {
    var aba = abaDestino();

    aba.appendRow([
      new Date(),
      limpar(d.nome),
      limpar(d.email).toLowerCase(),
      limpar(d.organizacao),
      limpar(d.area),
      limpar(d.tema),
      limpar(d.formato),
      limpar(d.mensagem),
      'Sim',
      limpar(d.origem)
    ]);

  } finally {
    trava.releaseLock();
  }
}

function abaDestino() {
  if (!PLANILHA_ID || PLANILHA_ID.indexOf('COLE_AQUI') === 0) {
    throw new Error('PLANILHA_ID não foi preenchido no Codigo.gs.');
  }

  var planilha;
  try {
    planilha = SpreadsheetApp.openById(PLANILHA_ID);
  } catch (err) {
    throw new Error(
      'Não consegui abrir a planilha "' + PLANILHA_ID + '". ' +
      'Confira se o ID está certo (só o trecho entre /d/ e /edit) e se a conta ' +
      'que implantou o script tem acesso a ela. Detalhe: ' + err.message
    );
  }

  var aba = planilha.getSheetByName(ABA);

  if (!aba) {
    aba = planilha.insertSheet(ABA);
  }

  if (aba.getLastRow() === 0) {
    aba.appendRow(COLUNAS);
    aba.getRange(1, 1, 1, COLUNAS.length).setFontWeight('bold');
    aba.setFrozenRows(1);
  }

  return aba;
}

/**
 * Remove o que estoura o limite de célula e neutraliza o caractere que faz o
 * Sheets interpretar o conteúdo como fórmula (=, +, -, @ no início).
 */
function limpar(v) {
  if (v === null || v === undefined) return '';
  var s = String(v).trim().slice(0, 5000);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

// ---------------------------------------------------------------- notificação

function notificar(d) {
  if (!NOTIFICAR_EMAIL) return;

  try {
    MailApp.sendEmail({
      to: NOTIFICAR_EMAIL,
      subject: 'GLAUX — novo registro de interesse: ' + limpar(d.nome),
      body: [
        'Nome: ' + limpar(d.nome),
        'E-mail: ' + limpar(d.email),
        'Organização: ' + (limpar(d.organizacao) || '—'),
        'Área: ' + (limpar(d.area) || '—'),
        'Tema: ' + limpar(d.tema),
        'Formato: ' + limpar(d.formato),
        '',
        'Mensagem:',
        limpar(d.mensagem) || '—'
      ].join('\n')
    });
  } catch (err) {
    // Falha de e-mail não pode derrubar a gravação, que já aconteceu.
    console.error('Falha ao notificar: ' + err.message);
  }
}

// ---------------------------------------------------------------- resposta

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

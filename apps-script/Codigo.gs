/**
 * GLAUX — Registro de interesse
 *
 * Backend dos formulários da GLAUX.
 *
 * Destinos:
 *
 * 1. Formulário institucional
 *    → aba "Interesses"
 *
 * 2. Material da palestra
 *    → aba "Palestra — Prova fragmentada"
 *
 * IMPLANTAÇÃO:
 * Implantar → Nova implantação → Aplicativo da Web
 *
 * Executar como: EU
 * Quem pode acessar: QUALQUER PESSOA
 *
 * A URL /exec deve ser inserida no ENDPOINT_FORMULARIO do site.
 *
 * ------------------------------------------------------------
 * CORS
 * ------------------------------------------------------------
 * A landing page envia JSON serializado com Content-Type
 * text/plain para manter o POST como "simple request" e evitar
 * preflight OPTIONS.
 *
 * O conteúdo continua sendo JSON e é processado com JSON.parse().
 *
 * Não altere simplesmente para application/json no frontend.
 */

// ============================================================
// CONFIGURAÇÃO
// ============================================================

/**
 * ID da planilha mestre.
 * É somente o trecho entre /d/ e /edit na URL da planilha.
 */
var PLANILHA_ID = '1n207Ec8pKOILdMsrsxCn5kGTYZ8vn9paqopP2041HrI';

/**
 * E-mail que receberá aviso de novos registros.
 * Deixe vazio para desativar.
 */
var NOTIFICAR_EMAIL = '';

/**
 * Ative apenas durante diagnóstico.
 *
 * IMPORTANTE:
 * Em produção, deixe false.
 */
var DIAGNOSTICO = false;


// ============================================================
// FORMULÁRIO INSTITUCIONAL
// ============================================================

var ABA_INTERESSES = 'Interesses';

var COLUNAS_INTERESSES = [
  'Data/hora',
  'Nome',
  'E-mail',
  'Organização',
  'Área de atuação',
  'Tema',
  'Formato',
  'Mensagem',
  'Consentimento',
  'Origem'
];


// ============================================================
// MATERIAL DA PALESTRA
// ============================================================

var ABA_PALESTRA = 'Palestra — Prova fragmentada';

var COLUNAS_PALESTRA = [
  'Data/hora',
  'Nome',
  'E-mail',
  'WhatsApp',
  'Consentimento',
  'Origem'
];


// ============================================================
// LIMITES DE CAMPOS
// ============================================================

var LIMITES = {
  nome: 150,
  email: 320,
  whatsapp: 40,
  organizacao: 200,
  area: 200,
  tema: 300,
  formato: 150,
  mensagem: 5000,
  origem: 300
};


/**
 * Configuração central de cada tipo de formulário.
 */
function config(lista) {

  if (lista === 'palestra') {
    return {
      lista: 'palestra',
      aba: ABA_PALESTRA,
      colunas: COLUNAS_PALESTRA
    };
  }

  if (lista === 'interesses') {
    return {
      lista: 'interesses',
      aba: ABA_INTERESSES,
      colunas: COLUNAS_INTERESSES
    };
  }

  throw new Error('Lista inválida: ' + lista);
}


// ============================================================
// ENTRADA HTTP
// ============================================================

function doPost(e) {

  try {

    // --------------------------------------------------------
    // 1. Verifica existência do corpo
    // --------------------------------------------------------

    if (!e || !e.postData || !e.postData.contents) {
      return json({
        ok: false,
        erro: 'Requisição sem corpo.'
      });
    }


    // --------------------------------------------------------
    // 2. Proteção contra payload excessivamente grande
    // --------------------------------------------------------

    if (e.postData.contents.length > 30000) {
      return json({
        ok: false,
        erro: 'Requisição muito grande.'
      });
    }


    // --------------------------------------------------------
    // 3. Converte JSON
    // --------------------------------------------------------

    var d;

    try {
      d = JSON.parse(e.postData.contents);
    } catch (err) {
      return json({
        ok: false,
        erro: 'Corpo inválido.'
      });
    }


    if (!d || typeof d !== 'object') {
      return json({
        ok: false,
        erro: 'Dados inválidos.'
      });
    }


    // --------------------------------------------------------
    // 4. Honeypot anti-robô
    // --------------------------------------------------------
    //
    // O campo "website" deve permanecer invisível para usuários
    // humanos.
    //
    // Se preenchido, fingimos sucesso, mas não gravamos nada.
    // --------------------------------------------------------

    if (texto(d.website)) {
      return json({ ok: true });
    }


    // --------------------------------------------------------
    // 5. Identifica qual formulário enviou os dados
    // --------------------------------------------------------

    var lista;

    try {
      lista = identificarLista(d);
    } catch (err) {
      return json({
        ok: false,
        erro: 'Tipo de formulário inválido.'
      });
    }


    // --------------------------------------------------------
    // 6. Validação
    // --------------------------------------------------------

    var erros = validar(d, lista);

    if (erros.length) {
      return json({
        ok: false,
        erro: 'Campos obrigatórios: ' + erros.join(', ')
      });
    }


    // --------------------------------------------------------
    // 7. Grava
    // --------------------------------------------------------

    gravar(d, lista);


    // --------------------------------------------------------
    // 8. Notificação opcional
    // --------------------------------------------------------

    notificar(d, lista);


    // --------------------------------------------------------
    // 9. Resposta
    // --------------------------------------------------------

    return json({
      ok: true,
      lista: lista
    });

  } catch (err) {

    console.error(
      'Falha ao registrar interesse: ' +
      (err && err.stack ? err.stack : err)
    );

    return json({
      ok: false,
      erro: DIAGNOSTICO
        ? String(err && err.message ? err.message : err)
        : 'Erro interno.'
    });
  }
}


/**
 * Health check.
 *
 * Abrir a URL /exec pelo navegador deve retornar algo como:
 *
 * {
 *   "ok": true,
 *   "servico": "GLAUX — registro de interesse",
 *   "versao": "2.1"
 * }
 *
 * O campo "versao" é o jeito rápido de saber se a implantação
 * está servindo o código atual. Se ele não aparecer, a versão
 * publicada é antiga — reimplante escolhendo "Nova versão".
 */
function doGet() {

  return json({
    ok: true,
    servico: 'GLAUX — registro de interesse',
    versao: '2.1'
  });
}


// ============================================================
// IDENTIFICAÇÃO DO FORMULÁRIO
// ============================================================

/**
 * Determina qual formulário enviou o payload.
 *
 * Prioridade:
 *
 * 1. Se "lista" vier explicitamente, usamos o valor enviado.
 *
 * 2. Para compatibilidade com o frontend atual:
 *    se não houver "tema" nem "formato", identificamos o
 *    formulário como palestra.
 *
 * 3. Caso contrário, consideramos o formulário institucional.
 *
 * Isso permite que a página atual da palestra funcione mesmo
 * antes de receber lista: "palestra" explicitamente.
 */
function identificarLista(d) {

  // Se o frontend informar explicitamente a lista,
  // esse valor sempre tem prioridade.
  if (texto(d.lista)) {

    var lista = String(d.lista)
      .trim()
      .toLowerCase();

    if (
      lista === 'palestra' ||
      lista === 'material-palestra' ||
      lista === 'material_palestra'
    ) {
      return 'palestra';
    }

    if (
      lista === 'interesse' ||
      lista === 'interesses' ||
      lista === 'institucional'
    ) {
      return 'interesses';
    }

    throw new Error('Lista desconhecida: ' + lista);
  }


  // Compatibilidade com o formulário atual da palestra:
  // se existe o campo WhatsApp e tema/formato estão vazios,
  // tratamos como formulário da palestra.
  if (
    Object.prototype.hasOwnProperty.call(d, 'whatsapp') &&
    !texto(d.tema) &&
    !texto(d.formato)
  ) {
    return 'palestra';
  }


  return 'interesses';
}


// ============================================================
// VALIDAÇÃO
// ============================================================

function validar(d, lista) {

  var faltando = [];


  // ----------------------------------------------------------
  // Campos comuns
  // ----------------------------------------------------------

  if (!texto(d.nome)) {
    faltando.push('nome');
  }

  if (!emailValido(d.email)) {
    faltando.push('e-mail');
  }


  // ----------------------------------------------------------
  // Formulário institucional
  // ----------------------------------------------------------

  if (lista === 'interesses') {

    if (!texto(d.tema)) {
      faltando.push('tema');
    }

    if (!texto(d.formato)) {
      faltando.push('formato');
    }
  }


  // ----------------------------------------------------------
  // Consentimento obrigatório
  // ----------------------------------------------------------

  if (d.consentimento !== true) {
    faltando.push('consentimento');
  }


  return faltando;
}


/**
 * Verifica se um valor contém texto útil.
 */
function texto(v) {

  return (
    typeof v === 'string' &&
    v.trim() !== ''
  );
}


/**
 * Validação simples e deliberadamente conservadora de e-mail.
 *
 * Não tenta implementar integralmente RFC 5322.
 */
function emailValido(v) {

  if (!texto(v)) {
    return false;
  }

  var email = v.trim();

  if (email.length > LIMITES.email) {
    return false;
  }

  return /^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(email);
}


// ============================================================
// GRAVAÇÃO
// ============================================================

function gravar(d, lista) {

  /**
   * Impede duas execuções simultâneas de criarem/gravar
   * linhas conflitantes.
   */
  var trava = LockService.getScriptLock();

  trava.waitLock(20000);

  try {

    var c = config(lista);

    var aba = abaDestino(
      c.aba,
      c.colunas
    );


    // --------------------------------------------------------
    // PALESTRA
    // --------------------------------------------------------

    if (lista === 'palestra') {

      aba.appendRow([
        new Date(),

        limpar(
          d.nome,
          LIMITES.nome
        ),

        limpar(
          d.email,
          LIMITES.email
        ).toLowerCase(),

        limpar(
          d.whatsapp,
          LIMITES.whatsapp
        ),

        'Sim',

        limpar(
          d.origem,
          LIMITES.origem
        )
      ]);

      return;
    }


    // --------------------------------------------------------
    // FORMULÁRIO INSTITUCIONAL
    // --------------------------------------------------------

    aba.appendRow([
      new Date(),

      limpar(
        d.nome,
        LIMITES.nome
      ),

      limpar(
        d.email,
        LIMITES.email
      ).toLowerCase(),

      limpar(
        d.organizacao,
        LIMITES.organizacao
      ),

      limpar(
        d.area,
        LIMITES.area
      ),

      limpar(
        d.tema,
        LIMITES.tema
      ),

      limpar(
        d.formato,
        LIMITES.formato
      ),

      limpar(
        d.mensagem,
        LIMITES.mensagem
      ),

      'Sim',

      limpar(
        d.origem,
        LIMITES.origem
      )
    ]);

  } finally {

    trava.releaseLock();
  }
}


// ============================================================
// PLANILHA / ABAS
// ============================================================

function abaDestino(nomeAba, colunas) {

  if (
    !PLANILHA_ID ||
    PLANILHA_ID.indexOf('COLE_AQUI') === 0
  ) {
    throw new Error(
      'PLANILHA_ID não foi preenchido no Código.gs.'
    );
  }


  // ----------------------------------------------------------
  // Abre a planilha mestre
  // ----------------------------------------------------------

  var planilha;

  try {

    planilha = SpreadsheetApp.openById(
      PLANILHA_ID
    );

  } catch (err) {

    throw new Error(
      'Não consegui abrir a planilha "' +
      PLANILHA_ID +
      '". Confira se o ID está correto e se a conta que ' +
      'implantou o Apps Script possui acesso à planilha. ' +
      'Detalhe: ' +
      err.message
    );
  }


  // ----------------------------------------------------------
  // Procura a aba
  // ----------------------------------------------------------

  var aba =
    planilha.getSheetByName(nomeAba);


  // ----------------------------------------------------------
  // Se não existir, cria automaticamente
  // ----------------------------------------------------------

  if (!aba) {

    aba = planilha.insertSheet(nomeAba);
  }


  // ----------------------------------------------------------
  // Se estiver vazia, cria cabeçalhos
  // ----------------------------------------------------------

  if (aba.getLastRow() === 0) {

    aba.appendRow(colunas);

    aba
      .getRange(
        1,
        1,
        1,
        colunas.length
      )
      .setFontWeight('bold');

    aba.setFrozenRows(1);

    ajustarAba(aba, colunas.length);

    return aba;
  }


  // ----------------------------------------------------------
  // Se já existir, verifica estrutura
  // ----------------------------------------------------------

  validarCabecalho(
    aba,
    colunas
  );


  return aba;
}


/**
 * Confere se as primeiras colunas da aba continuam na ordem
 * esperada pelo backend.
 *
 * Evita gravar e-mail em coluna de telefone, nome em coluna
 * errada etc. caso alguém altere manualmente a planilha.
 */
function validarCabecalho(aba, esperado) {

  if (aba.getLastColumn() < esperado.length) {

    throw new Error(
      'A aba "' +
      aba.getName() +
      '" possui menos colunas do que o esperado.'
    );
  }


  var atual = aba
    .getRange(
      1,
      1,
      1,
      esperado.length
    )
    .getValues()[0];


  for (var i = 0; i < esperado.length; i++) {

    var atualNormalizado =
      String(atual[i] || '').trim();

    var esperadoNormalizado =
      String(esperado[i]).trim();


    if (
      atualNormalizado !==
      esperadoNormalizado
    ) {

      throw new Error(
        'Estrutura inesperada na aba "' +
        aba.getName() +
        '". A coluna ' +
        (i + 1) +
        ' deveria ser "' +
        esperadoNormalizado +
        '", mas contém "' +
        atualNormalizado +
        '".'
      );
    }
  }
}


/**
 * Pequenos ajustes visuais quando uma nova aba é criada.
 */
function ajustarAba(aba, quantidadeColunas) {

  try {

    aba.autoResizeColumns(
      1,
      quantidadeColunas
    );

  } catch (err) {

    // Ajuste visual não deve impedir a gravação.
    console.error(
      'Não foi possível ajustar largura das colunas: ' +
      err.message
    );
  }
}


// ============================================================
// SANITIZAÇÃO
// ============================================================

/**
 * Normaliza entradas externas.
 *
 * - converte para string;
 * - remove espaços nas extremidades;
 * - aplica limite de tamanho;
 * - neutraliza fórmula do Google Sheets.
 *
 * Entradas iniciadas por:
 *
 * =
 * +
 * -
 * @
 *
 * recebem apóstrofo antes da gravação.
 */
function limpar(v, limite) {

  if (
    v === null ||
    v === undefined
  ) {
    return '';
  }


  var s = String(v).trim();


  if (
    limite &&
    s.length > limite
  ) {
    s = s.slice(0, limite);
  }


  if (/^[=+\-@]/.test(s)) {
    s = "'" + s;
  }


  return s;
}


// ============================================================
// NOTIFICAÇÃO
// ============================================================

function notificar(d, lista) {

  if (!NOTIFICAR_EMAIL) {
    return;
  }


  try {

    // --------------------------------------------------------
    // PALESTRA
    // --------------------------------------------------------

    if (lista === 'palestra') {

      MailApp.sendEmail({

        to: NOTIFICAR_EMAIL,

        subject:
          'GLAUX — inscrição no material da palestra: ' +
          limpar(
            d.nome,
            100
          ),

        body: [
          'Nome: ' +
          limpar(
            d.nome,
            LIMITES.nome
          ),

          'E-mail: ' +
          limpar(
            d.email,
            LIMITES.email
          ),

          'WhatsApp: ' +
          (
            limpar(
              d.whatsapp,
              LIMITES.whatsapp
            ) || '—'
          ),

          'Origem: ' +
          (
            limpar(
              d.origem,
              LIMITES.origem
            ) || '—'
          )
        ].join('\n')
      });

      return;
    }


    // --------------------------------------------------------
    // FORMULÁRIO INSTITUCIONAL
    // --------------------------------------------------------

    MailApp.sendEmail({

      to: NOTIFICAR_EMAIL,

      subject:
        'GLAUX — novo registro de interesse: ' +
        limpar(
          d.nome,
          100
        ),

      body: [

        'Nome: ' +
        limpar(
          d.nome,
          LIMITES.nome
        ),

        'E-mail: ' +
        limpar(
          d.email,
          LIMITES.email
        ),

        'Organização: ' +
        (
          limpar(
            d.organizacao,
            LIMITES.organizacao
          ) || '—'
        ),

        'Área: ' +
        (
          limpar(
            d.area,
            LIMITES.area
          ) || '—'
        ),

        'Tema: ' +
        limpar(
          d.tema,
          LIMITES.tema
        ),

        'Formato: ' +
        limpar(
          d.formato,
          LIMITES.formato
        ),

        '',

        'Mensagem:',

        limpar(
          d.mensagem,
          LIMITES.mensagem
        ) || '—'

      ].join('\n')
    });

  } catch (err) {

    /**
     * A inscrição já foi gravada.
     *
     * Portanto, uma eventual falha de e-mail não deve
     * transformar a submissão em erro.
     */
    console.error(
      'Falha ao notificar: ' +
      err.message
    );
  }
}


// ============================================================
// RESPOSTA JSON
// ============================================================

function json(obj) {

  return ContentService
    .createTextOutput(
      JSON.stringify(obj)
    )
    .setMimeType(
      ContentService.MimeType.JSON
    );
}

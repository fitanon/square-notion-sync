/**
 * Claude package summarizer for rows in the "Square Transactions" sheet.
 *
 * Paste this file into the same Apps Script project as
 * square_monthly_sales_report.gs. Run summarizeUnsummarizedSquarePackages()
 * manually or schedule it after the Square report import.
 *
 * Required Script Properties:
 * - ANTHROPIC_API_KEY: Claude API key.
 *
 * Optional Script Properties:
 * - CLAUDE_MODEL: Defaults to claude-3-5-haiku-latest.
 * - TRANSACTIONS_SHEET_NAME: Defaults to Square Transactions.
 * - CLAUDE_MAX_ROWS_PER_RUN: Defaults to 50.
 */

const CLAUDE_SUMMARY_DEFAULT_MODEL = 'claude-3-5-haiku-latest';
const CLAUDE_SUMMARY_DEFAULT_SHEET = 'Monthly Sales Raw';
const CLAUDE_SUMMARY_COLUMNS = {
  paymentId: 'Payment ID',
  date: 'Payment Created At',
  customerName: 'Customer ID',
  customerEmail: 'Buyer Email',
  amount: 'Amount',
  itemNames: 'Package Detail Text',
  orderLineItems: 'Order Line Items',
  note: 'Payment Note',
  receiptUrl: 'Receipt URL',
  summary: 'Package Summary',
  sessions: 'Package Session Quantity',
  frequency: 'Package Frequency Per Week',
  duration: 'Package Duration Weeks',
  rationale: 'Package Summary Rationale',
  summarizedAt: 'Package Summary Updated At',
  rawResponse: 'Package Summary Raw Claude Response',
};

function summarizeUnsummarizedSquarePackages() {
  const config = claudeSummaryGetConfig_();
  const sheet = claudeSummaryGetOrCreateSheet_(config.sheetName);
  claudeSummaryEnsureColumns_(sheet);

  const data = claudeSummaryReadSheet_(sheet);
  if (data.rows.length === 0) {
    return;
  }

  let processed = 0;
  data.rows.forEach(function (row) {
    if (processed >= config.maxRowsPerRun) {
      return;
    }
    if (row.values[CLAUDE_SUMMARY_COLUMNS.summary]) {
      return;
    }
    if (!row.values[CLAUDE_SUMMARY_COLUMNS.paymentId]) {
      return;
    }

    const result = claudeSummaryAnalyzeRow_(row.values, config);
    claudeSummaryWriteResult_(sheet, data.headerMap, row.rowNumber, result);
    processed += 1;
  });
}

function installClaudePackageSummaryTrigger() {
  const config = claudeSummaryGetConfig_();
  claudeSummaryDeleteTriggers_('summarizeUnsummarizedSquarePackages');
  ScriptApp.newTrigger('summarizeUnsummarizedSquarePackages')
    .timeBased()
    .everyDays(1)
    .atHour(config.summaryHour)
    .create();
}

function claudeSummaryGetConfig_() {
  const props = PropertiesService.getScriptProperties();
  return {
    apiKey: claudeSummaryRequiredProperty_(props, 'ANTHROPIC_API_KEY'),
    model: props.getProperty('CLAUDE_MODEL') || CLAUDE_SUMMARY_DEFAULT_MODEL,
    sheetName: props.getProperty('TRANSACTIONS_SHEET_NAME') || CLAUDE_SUMMARY_DEFAULT_SHEET,
    maxRowsPerRun: Number(props.getProperty('CLAUDE_MAX_ROWS_PER_RUN') || '50'),
    summaryHour: Number(props.getProperty('CLAUDE_SUMMARY_HOUR') || '7'),
  };
}

function claudeSummaryRequiredProperty_(props, name) {
  const value = props.getProperty(name);
  if (!value) {
    throw new Error('Missing required Script Property: ' + name);
  }
  return value;
}

function claudeSummaryGetOrCreateSheet_(sheetName) {
  const spreadsheet = SpreadsheetApp.getActive();
  const sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    throw new Error('Missing sheet "' + sheetName + '". Run importCurrentMonthSquareSales first.');
  }
  return sheet;
}

function claudeSummaryEnsureColumns_(sheet) {
  const existingHeaders = sheet.getLastColumn() > 0
    ? sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String)
    : [];
  const requiredHeaders = Object.keys(CLAUDE_SUMMARY_COLUMNS).map(function (key) {
    return CLAUDE_SUMMARY_COLUMNS[key];
  });
  const missing = requiredHeaders.filter(function (header) {
    return existingHeaders.indexOf(header) === -1;
  });

  if (missing.length === 0) {
    return;
  }

  const startColumn = Math.max(existingHeaders.length, 1);
  if (existingHeaders.length === 0) {
    sheet.getRange(1, 1, 1, requiredHeaders.length).setValues([requiredHeaders]);
  } else {
    sheet.getRange(1, startColumn + 1, 1, missing.length).setValues([missing]);
  }
  sheet.setFrozenRows(1);
}

function claudeSummaryReadSheet_(sheet) {
  const values = sheet.getDataRange().getValues();
  if (values.length < 2) {
    return { headerMap: {}, rows: [] };
  }

  const headers = values[0].map(String);
  const headerMap = {};
  headers.forEach(function (header, index) {
    headerMap[header] = index + 1;
  });

  const rows = [];
  for (let i = 1; i < values.length; i += 1) {
    const rowValues = {};
    headers.forEach(function (header, index) {
      rowValues[header] = values[i][index];
    });
    rows.push({ rowNumber: i + 1, values: rowValues });
  }

  return { headerMap: headerMap, rows: rows };
}

function claudeSummaryAnalyzeRow_(row, config) {
  const prompt = claudeSummaryBuildPrompt_(row);
  const response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    headers: {
      'x-api-key': config.apiKey,
      'anthropic-version': '2023-06-01',
      'Content-Type': 'application/json',
    },
    payload: JSON.stringify({
      model: config.model,
      max_tokens: 600,
      temperature: 0,
      messages: [
        {
          role: 'user',
          content: prompt,
        },
      ],
    }),
    muteHttpExceptions: true,
  });

  const body = response.getContentText();
  const status = response.getResponseCode();
  if (status >= 400) {
    throw new Error('Claude API error ' + status + ': ' + body);
  }

  const parsed = JSON.parse(body);
  const text = parsed.content && parsed.content.length ? parsed.content[0].text : '{}';
  return claudeSummaryParseResponse_(text);
}

function claudeSummaryBuildPrompt_(row) {
  const payload = {
    payment_id: row[CLAUDE_SUMMARY_COLUMNS.paymentId],
    date: row[CLAUDE_SUMMARY_COLUMNS.date],
    customer_name: row[CLAUDE_SUMMARY_COLUMNS.customerName],
    customer_email: row[CLAUDE_SUMMARY_COLUMNS.customerEmail],
    amount: row[CLAUDE_SUMMARY_COLUMNS.amount],
    item_names: row[CLAUDE_SUMMARY_COLUMNS.itemNames],
    order_line_items: row[CLAUDE_SUMMARY_COLUMNS.orderLineItems],
    note: row[CLAUDE_SUMMARY_COLUMNS.note],
    receipt_url: row[CLAUDE_SUMMARY_COLUMNS.receiptUrl],
  };

  return [
    'You summarize fitness package purchases from Square transaction data.',
    '',
    'Return ONLY valid compact JSON with these keys:',
    'summary, sessions, frequency_per_week, duration_weeks, rationale.',
    '',
    'Rules:',
    '- Infer packages from item names, notes, and line item details.',
    '- If you see "3 months" or "12 weeks" and "2x/week", infer 24 sessions.',
    '- If you see "3x/week" for 12 weeks, infer 36 sessions.',
    '- If you see "1x/week" for 12 weeks, infer 12 sessions.',
    '- Frequency is the number before x/week when present.',
    '- Duration weeks should normalize months to weeks when obvious: 3 months = 12 weeks, 6 months = 24 weeks.',
    '- If the information is uncertain, keep the best concise summary and explain uncertainty in rationale.',
    '- Example summary: "24 Sessions at 2x/week for 12 weeks".',
    '',
    'Transaction JSON:',
    JSON.stringify(payload),
  ].join('\n');
}

function claudeSummaryParseResponse_(text) {
  const trimmed = String(text || '').trim();
  let jsonText = trimmed;
  const match = trimmed.match(/\{[\s\S]*\}/);
  if (match) {
    jsonText = match[0];
  }

  try {
    const parsed = JSON.parse(jsonText);
    return {
      summary: parsed.summary || '',
      sessions: parsed.sessions || '',
      frequency: parsed.frequency_per_week || '',
      duration: parsed.duration_weeks || '',
      rationale: parsed.rationale || '',
      raw: trimmed,
    };
  } catch (error) {
    return {
      summary: trimmed.slice(0, 500),
      sessions: '',
      frequency: '',
      duration: '',
      rationale: 'Claude response was not valid JSON.',
      raw: trimmed,
    };
  }
}

function claudeSummaryWriteResult_(sheet, headerMap, rowNumber, result) {
  const updates = {};
  updates[CLAUDE_SUMMARY_COLUMNS.summary] = result.summary;
  updates[CLAUDE_SUMMARY_COLUMNS.sessions] = result.sessions;
  updates[CLAUDE_SUMMARY_COLUMNS.frequency] = result.frequency;
  updates[CLAUDE_SUMMARY_COLUMNS.duration] = result.duration;
  updates[CLAUDE_SUMMARY_COLUMNS.rationale] = result.rationale;
  updates[CLAUDE_SUMMARY_COLUMNS.summarizedAt] = new Date();
  updates[CLAUDE_SUMMARY_COLUMNS.rawResponse] = result.raw;

  Object.keys(updates).forEach(function (header) {
    const column = headerMap[header];
    if (column) {
      sheet.getRange(rowNumber, column).setValue(updates[header]);
    }
  });
}

function claudeSummaryDeleteTriggers_(handlerName) {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === handlerName) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function claudeSummaryDeleteTriggers_(handlerName) {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === handlerName) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

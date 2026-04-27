/**
 * Square current-month sales report -> Google Sheets.
 *
 * Paste this file into the Apps Script project attached to the Google Sheet
 * where you want the report to appear.
 *
 * Required Script Properties:
 * - SQUARE_ACCESS_TOKEN: Square production or sandbox access token.
 *
 * Optional Script Properties:
 * - SQUARE_ENV: "production" or "sandbox". Defaults to production.
 * - SQUARE_LOCATION_IDS: Comma-separated Square location IDs. If omitted, all
 *   accessible payments are requested.
 * - SQUARE_VERSION: Square API version. Defaults to 2025-06-16.
 * - SQUARE_REPORT_SHEET_NAME: Sheet tab name. Defaults to Monthly Sales Raw.
 * - SQUARE_REPORT_TIMEZONE: Time zone for month boundaries. Defaults to the
 *   spreadsheet time zone.
 * - SQUARE_REPORT_HOUR: 0-23 local hour for daily trigger. Defaults to 6.
 */

const SQ_REPORT_DEFAULT_SHEET_NAME = 'Monthly Sales Raw';
const SQ_REPORT_DEFAULT_SQUARE_VERSION = '2025-06-16';
const SQ_REPORT_HEADERS = [
  'Report Generated At',
  'Month Start',
  'Payment Created At',
  'Payment ID',
  'Order ID',
  'Location ID',
  'Status',
  'Source Type',
  'Customer ID',
  'Buyer Email',
  'Amount',
  'Currency',
  'Refunded Amount',
  'Receipt URL',
  'Payment Note',
  'Order Line Items',
  'Order Notes',
  'Package Detail Text',
  'Package Summary',
  'Package Frequency Per Week',
  'Package Duration Weeks',
  'Package Session Quantity',
  'Package Summary Updated At',
];

function installDailySquareSalesReportTrigger() {
  const config = sqReportGetConfig_();
  sqReportDeleteTriggers_('runDailySquareSalesReport');
  ScriptApp.newTrigger('runDailySquareSalesReport')
    .timeBased()
    .everyDays(1)
    .atHour(config.reportHour)
    .create();
}

function runDailySquareSalesReport() {
  const config = sqReportGetConfig_();
  const range = sqReportCurrentMonthRange_(config.timezone);
  const sheet = sqReportGetOrCreateSheet_(config.sheetName);
  const existingSummaries = sqReportReadExistingSummaries_(sheet);
  const payments = sqReportFetchCurrentMonthPayments_(config, range);
  const ordersById = sqReportFetchOrdersById_(config, payments);
  const rows = sqReportBuildRows_(payments, ordersById, range, config, existingSummaries);

  sqReportWriteRows_(sheet, rows);
}

function sqReportGetConfig_() {
  const props = PropertiesService.getScriptProperties();
  const spreadsheet = SpreadsheetApp.getActive();
  const timezone = props.getProperty('SQUARE_REPORT_TIMEZONE')
    || spreadsheet.getSpreadsheetTimeZone()
    || Session.getScriptTimeZone()
    || 'Etc/UTC';

  return {
    accessToken: sqReportRequiredProperty_(props, 'SQUARE_ACCESS_TOKEN'),
    env: (props.getProperty('SQUARE_ENV') || 'production').toLowerCase(),
    locationIds: sqReportParseList_(props.getProperty('SQUARE_LOCATION_IDS') || ''),
    squareVersion: props.getProperty('SQUARE_VERSION') || SQ_REPORT_DEFAULT_SQUARE_VERSION,
    sheetName: props.getProperty('SQUARE_REPORT_SHEET_NAME') || SQ_REPORT_DEFAULT_SHEET_NAME,
    timezone: timezone,
    reportHour: Number(props.getProperty('SQUARE_REPORT_HOUR') || 6),
  };
}

function sqReportRequiredProperty_(props, name) {
  const value = props.getProperty(name);
  if (!value) {
    throw new Error('Missing required Script Property: ' + name);
  }
  return value;
}

function sqReportParseList_(value) {
  return value
    .split(',')
    .map(function (item) { return item.trim(); })
    .filter(Boolean);
}

function sqReportBaseUrl_(config) {
  return config.env === 'sandbox'
    ? 'https://connect.squareupsandbox.com'
    : 'https://connect.squareup.com';
}

function sqReportCurrentMonthRange_(timezone) {
  const now = new Date();
  const year = Number(Utilities.formatDate(now, timezone, 'yyyy'));
  const monthIndex = Number(Utilities.formatDate(now, timezone, 'M')) - 1;
  const start = new Date(year, monthIndex, 1, 0, 0, 0);

  return {
    start: start,
    end: now,
    startIso: start.toISOString(),
    endIso: now.toISOString(),
  };
}

function sqReportFetchCurrentMonthPayments_(config, range) {
  const locationIds = config.locationIds.length ? config.locationIds : [''];
  let allPayments = [];

  locationIds.forEach(function (locationId) {
    let cursor = '';
    do {
      const params = {
        begin_time: range.startIso,
        end_time: range.endIso,
        sort_order: 'DESC',
        limit: '100',
      };
      if (locationId) {
        params.location_id = locationId;
      }
      if (cursor) {
        params.cursor = cursor;
      }

      const response = sqReportSquareFetch_(config, '/v2/payments', 'get', null, params);
      allPayments = allPayments.concat(response.payments || []);
      cursor = response.cursor || '';
    } while (cursor);
  });

  const seen = {};
  return allPayments.filter(function (payment) {
    if (!payment.id || seen[payment.id]) {
      return false;
    }
    seen[payment.id] = true;
    return true;
  });
}

function sqReportFetchOrdersById_(config, payments) {
  const orderIds = payments
    .map(function (payment) { return payment.order_id; })
    .filter(Boolean);
  const uniqueOrderIds = Object.keys(orderIds.reduce(function (memo, orderId) {
    memo[orderId] = true;
    return memo;
  }, {}));
  const ordersById = {};

  for (let start = 0; start < uniqueOrderIds.length; start += 100) {
    const chunk = uniqueOrderIds.slice(start, start + 100);
    const response = sqReportSquareFetch_(config, '/v2/orders/batch-retrieve', 'post', {
      order_ids: chunk,
    });

    (response.orders || []).forEach(function (order) {
      ordersById[order.id] = order;
    });
  }

  return ordersById;
}

function sqReportBuildRows_(payments, ordersById, range, config, existingSummaries) {
  const generatedAt = new Date().toISOString();
  return payments.map(function (payment) {
    const order = payment.order_id ? ordersById[payment.order_id] : null;
    const lineItems = sqReportLineItemsText_(order);
    const orderNotes = sqReportOrderNotesText_(order);
    const paymentNote = payment.note || '';
    const detailText = [paymentNote, lineItems, orderNotes]
      .filter(Boolean)
      .join(' | ');
    const previousSummary = existingSummaries[payment.id] || {};

    return [
      generatedAt,
      range.startIso,
      payment.created_at || '',
      payment.id || '',
      payment.order_id || '',
      payment.location_id || '',
      payment.status || '',
      payment.source_type || '',
      payment.customer_id || '',
      payment.buyer_email_address || '',
      sqReportMoneyAmount_(payment.total_money),
      payment.total_money ? payment.total_money.currency : '',
      sqReportMoneyAmount_(payment.refunded_money),
      payment.receipt_url || '',
      paymentNote,
      lineItems,
      orderNotes,
      detailText,
      previousSummary['Package Summary'] || '',
      previousSummary['Package Frequency Per Week'] || '',
      previousSummary['Package Duration Weeks'] || '',
      previousSummary['Package Session Quantity'] || '',
      previousSummary['Package Summary Updated At'] || '',
    ];
  });
}

function sqReportLineItemsText_(order) {
  if (!order || !order.line_items) {
    return '';
  }

  return order.line_items.map(function (item) {
    const parts = [
      item.name || '',
      item.variation_name || '',
      item.quantity ? 'qty ' + item.quantity : '',
      item.note || '',
    ].filter(Boolean);
    return parts.join(' - ');
  }).join('; ');
}

function sqReportOrderNotesText_(order) {
  if (!order) {
    return '';
  }

  const notes = [];
  if (order.note) {
    notes.push(order.note);
  }
  (order.tenders || []).forEach(function (tender) {
    if (tender.note) {
      notes.push(tender.note);
    }
  });
  return notes.join('; ');
}

function sqReportMoneyAmount_(money) {
  if (!money || money.amount === undefined || money.amount === null) {
    return '';
  }
  return Number(money.amount) / 100;
}

function sqReportSquareFetch_(config, path, method, payload, params) {
  let url = sqReportBaseUrl_(config) + path;
  if (params) {
    url += '?' + Object.keys(params)
      .map(function (key) {
        return encodeURIComponent(key) + '=' + encodeURIComponent(params[key]);
      })
      .join('&');
  }

  const options = {
    method: method,
    headers: {
      Authorization: 'Bearer ' + config.accessToken,
      'Square-Version': config.squareVersion,
      'Content-Type': 'application/json',
    },
    muteHttpExceptions: true,
  };

  if (payload) {
    options.payload = JSON.stringify(payload);
  }

  const response = UrlFetchApp.fetch(url, options);
  const body = response.getContentText();
  const status = response.getResponseCode();
  const parsed = body ? JSON.parse(body) : {};

  if (status >= 400) {
    throw new Error('Square API error ' + status + ' for ' + path + ': ' + body);
  }

  return parsed;
}

function sqReportGetOrCreateSheet_(sheetName) {
  const spreadsheet = SpreadsheetApp.getActive();
  return spreadsheet.getSheetByName(sheetName) || spreadsheet.insertSheet(sheetName);
}

function sqReportWriteRows_(sheet, rows) {
  sheet.clearContents();
  sheet.getRange(1, 1, 1, SQ_REPORT_HEADERS.length).setValues([SQ_REPORT_HEADERS]);
  sheet.setFrozenRows(1);

  if (rows.length) {
    sheet.getRange(2, 1, rows.length, SQ_REPORT_HEADERS.length).setValues(rows);
  }

  sheet.autoResizeColumns(1, SQ_REPORT_HEADERS.length);
}

function sqReportDeleteTriggers_(handlerName) {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === handlerName) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

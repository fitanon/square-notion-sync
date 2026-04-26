/**
 * Google Forms -> Email notification -> Notion data source automation.
 *
 * Install this script from the Google Sheet that receives Google Form responses:
 * Extensions -> Apps Script -> paste this file -> run installSubmitTrigger().
 *
 * Required Script Properties:
 * - NOTION_TOKEN: Notion integration secret.
 * - NOTION_DATA_SOURCE_ID: Notion data source ID to create pages in.
 * - NOTIFICATION_EMAIL: Email address to notify.
 *
 * Optional Script Properties:
 * - NOTION_VERSION: Defaults to 2025-09-03.
 * - TITLE_PROPERTY: Defaults to Name.
 * - TITLE_FIELD: Form question/header used for the Notion title. Defaults to Email Address, Email, Full Name, Name, Timestamp.
 * - EMAIL_FIELD: Form question/header used to match existing pages. Defaults to Email Address.
 * - MATCH_PROPERTY: Notion property used to find an existing page before create. Defaults to Email.
 * - NOTION_FIELD_MAP: JSON object mapping Notion property names to Google Form question/header names.
 * - APPLY_DEFAULT_TEMPLATE: Set true to apply the data source's default template on page creation.
 */

const DEFAULT_NOTION_VERSION = '2025-09-03';
const DEFAULT_DATA_SOURCE_ID = '34d72568-b32a-814e-9e2b-000b7b75a88a';
const MAX_RICH_TEXT_LENGTH = 2000;

function installSubmitTrigger() {
  const spreadsheet = SpreadsheetApp.getActive();
  ScriptApp.newTrigger('onFormSubmit')
    .forSpreadsheet(spreadsheet)
    .onFormSubmit()
    .create();
}

function onFormSubmit(event) {
  const config = getConfig_();
  const response = normalizeFormResponse_(event);
  const dataSource = retrieveDataSource_(config);
  const properties = buildNotionProperties_(response, dataSource.properties, config);
  const pageId = findExistingPageId_(response, config, dataSource.properties);
  const notionPage = pageId
    ? updateNotionPage_(pageId, properties, config)
    : createNotionPage_(properties, config);

  sendNotificationEmail_(response, notionPage, config, pageId ? 'updated' : 'created');
}

function getConfig_() {
  const props = PropertiesService.getScriptProperties();
  const fieldMapRaw = props.getProperty('NOTION_FIELD_MAP') || '{}';
  let fieldMap = {};

  try {
    fieldMap = JSON.parse(fieldMapRaw);
  } catch (error) {
    throw new Error('NOTION_FIELD_MAP must be valid JSON. Error: ' + error.message);
  }

  return {
    notionToken: requiredProperty_(props, 'NOTION_TOKEN'),
    dataSourceId: props.getProperty('NOTION_DATA_SOURCE_ID') || DEFAULT_DATA_SOURCE_ID,
    notificationEmail: requiredProperty_(props, 'NOTIFICATION_EMAIL'),
    notionVersion: props.getProperty('NOTION_VERSION') || DEFAULT_NOTION_VERSION,
    titleProperty: props.getProperty('TITLE_PROPERTY') || 'Name',
    titleField: props.getProperty('TITLE_FIELD') || '',
    emailField: props.getProperty('EMAIL_FIELD') || 'Email Address',
    matchProperty: props.getProperty('MATCH_PROPERTY') || 'Email',
    applyDefaultTemplate: (props.getProperty('APPLY_DEFAULT_TEMPLATE') || '').toLowerCase() === 'true',
    fieldMap: fieldMap,
  };
}

function requiredProperty_(props, name) {
  const value = props.getProperty(name);
  if (!value) {
    throw new Error('Missing required Script Property: ' + name);
  }
  return value;
}

function normalizeFormResponse_(event) {
  const response = {};

  if (event && event.namedValues) {
    Object.keys(event.namedValues).forEach(function (key) {
      response[key] = Array.isArray(event.namedValues[key])
        ? event.namedValues[key].join(', ').trim()
        : String(event.namedValues[key] || '').trim();
    });
  }

  if (event && event.range) {
    response._sheetRowNumber = event.range.getRow();
  }

  if (!response.Timestamp && event && event.values && event.values.length > 0) {
    response.Timestamp = String(event.values[0] || '').trim();
  }

  return response;
}

function retrieveDataSource_(config) {
  const response = notionFetch_(
    '/data_sources/' + encodeURIComponent(config.dataSourceId),
    'get',
    null,
    config
  );
  return response;
}

function buildNotionProperties_(response, schema, config) {
  const properties = {};
  const title = pickTitle_(response, config);

  if (!schema[config.titleProperty]) {
    throw new Error('Title property "' + config.titleProperty + '" was not found in the Notion data source.');
  }

  properties[config.titleProperty] = { title: [{ text: { content: title } }] };

  Object.keys(schema).forEach(function (propertyName) {
    if (propertyName === config.titleProperty) {
      return;
    }

    const formField = config.fieldMap[propertyName] || propertyName;
    const value = response[formField];
    if (value === undefined || value === null || value === '') {
      return;
    }

    const propertyValue = toNotionPropertyValue_(schema[propertyName], String(value));
    if (propertyValue) {
      properties[propertyName] = propertyValue;
    }
  });

  return properties;
}

function pickTitle_(response, config) {
  const candidates = config.titleField
    ? [config.titleField]
    : ['Email Address', 'Email', 'Full Name', 'Name', 'First Name', 'Timestamp'];

  for (let i = 0; i < candidates.length; i += 1) {
    const value = response[candidates[i]];
    if (value) {
      return String(value).slice(0, MAX_RICH_TEXT_LENGTH);
    }
  }

  return 'Form response ' + new Date().toISOString();
}

function toNotionPropertyValue_(schemaProperty, rawValue) {
  const value = rawValue.trim();
  if (!value) {
    return null;
  }

  switch (schemaProperty.type) {
    case 'rich_text':
      return { rich_text: [{ text: { content: value.slice(0, MAX_RICH_TEXT_LENGTH) } }] };
    case 'email':
      return { email: value };
    case 'phone_number':
      return { phone_number: value };
    case 'url':
      return { url: value };
    case 'number': {
      const numberValue = Number(value.replace(/[$,]/g, ''));
      return Number.isFinite(numberValue) ? { number: numberValue } : null;
    }
    case 'date': {
      const dateValue = new Date(value);
      return Number.isNaN(dateValue.getTime()) ? null : { date: { start: dateValue.toISOString() } };
    }
    case 'checkbox':
      return { checkbox: ['yes', 'true', '1', 'checked'].indexOf(value.toLowerCase()) !== -1 };
    case 'select':
      return { select: { name: value } };
    case 'multi_select':
      return {
        multi_select: value
          .split(',')
          .map(function (item) { return item.trim(); })
          .filter(Boolean)
          .map(function (item) { return { name: item }; }),
      };
    default:
      return null;
  }
}

function findExistingPageId_(response, config, schema) {
  const email = response[config.emailField] || response.Email || response['Email Address'];
  const matchSchema = schema[config.matchProperty];

  if (!email || !matchSchema || ['email', 'rich_text', 'title'].indexOf(matchSchema.type) === -1) {
    return null;
  }

  const filter = {};
  if (matchSchema.type === 'email') {
    filter.email = { equals: email };
  } else if (matchSchema.type === 'title') {
    filter.title = { equals: email };
  } else {
    filter.rich_text = { equals: email };
  }

  const result = notionFetch_(
    '/data_sources/' + encodeURIComponent(config.dataSourceId) + '/query',
    'post',
    {
      filter: Object.assign({ property: config.matchProperty }, filter),
      page_size: 1,
    },
    config
  );

  return result.results && result.results.length ? result.results[0].id : null;
}

function createNotionPage_(properties, config) {
  const payload = {
    parent: {
      type: 'data_source_id',
      data_source_id: config.dataSourceId,
    },
    properties: properties,
  };

  if (config.applyDefaultTemplate) {
    payload.template = { type: 'default' };
  }

  return notionFetch_('/pages', 'post', payload, config);
}

function updateNotionPage_(pageId, properties, config) {
  return notionFetch_('/pages/' + encodeURIComponent(pageId), 'patch', { properties: properties }, config);
}

function notionFetch_(path, method, payload, config) {
  const options = {
    method: method,
    headers: {
      Authorization: 'Bearer ' + config.notionToken,
      'Notion-Version': config.notionVersion,
      'Content-Type': 'application/json',
    },
    muteHttpExceptions: true,
  };

  if (payload) {
    options.payload = JSON.stringify(payload);
  }

  const response = UrlFetchApp.fetch('https://api.notion.com/v1' + path, options);
  const body = response.getContentText();
  const status = response.getResponseCode();
  const parsed = body ? JSON.parse(body) : {};

  if (status >= 400) {
    throw new Error('Notion API error ' + status + ': ' + body);
  }

  return parsed;
}

function sendNotificationEmail_(response, notionPage, config, action) {
  const subject = 'New Google Form response ' + action + ' in Notion';
  const lines = [
    'A Google Form response was ' + action + ' in Notion.',
    '',
    'Notion page: ' + (notionPage.url || notionPage.id || 'created'),
    '',
    'Response:',
  ];

  Object.keys(response).forEach(function (key) {
    if (key.indexOf('_') === 0) {
      return;
    }
    lines.push(key + ': ' + response[key]);
  });

  MailApp.sendEmail(config.notificationEmail, subject, lines.join('\n'));
}

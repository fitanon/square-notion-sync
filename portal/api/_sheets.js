const { google } = require('googleapis');

const CONFIG = {
  spreadsheetId: '1-D1MCAJYb6rqZ3gmGHqB_q2FCEs74paAQ4MTsi06MhU',
  membersSheet: 'Members',
  checkInsSheet: 'logs',
  adminSpreadsheetId: '1x5I9-qOCjEER3gIHnX2Ds-C-xhdo92hQTX0vpeohLHY',
  clientsSheet: 'clients',
  sessionsSheet: 'ClientsCleaned',
};

let sheetsClient = null;

function getSheets() {
  if (sheetsClient) return sheetsClient;

  const path = require('path');
  const fs = require('fs');
  let auth;

  // Try env var first (Vercel), then credentials.json file (local)
  const credJson = process.env.GOOGLE_CREDENTIALS;
  const credFile = path.join(__dirname, '..', 'credentials.json');

  if (credJson) {
    const creds = JSON.parse(credJson);
    auth = new google.auth.GoogleAuth({
      credentials: creds,
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });
  } else if (fs.existsSync(credFile)) {
    auth = new google.auth.GoogleAuth({
      keyFile: credFile,
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });
  } else {
    throw new Error('No Google credentials found (set GOOGLE_CREDENTIALS env var or add credentials.json)');
  }
  sheetsClient = google.sheets({ version: 'v4', auth });
  return sheetsClient;
}

async function getMembers() {
  const sheets = getSheets();
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: CONFIG.spreadsheetId,
    range: `${CONFIG.membersSheet}!A2:D`,
  });
  return (res.data.values || []).map(row => ({
    id: (row[0] || '').trim(),
    name: row[1] || 'Member',
    email: row[2] || '',
    phone: row[3] || '',
  }));
}

async function logCheckIn(member) {
  const sheets = getSheets();
  const now = new Date();
  const date = now.toISOString().split('T')[0];
  const time = now.toTimeString().split(' ')[0];
  await sheets.spreadsheets.values.append({
    spreadsheetId: CONFIG.spreadsheetId,
    range: `${CONFIG.checkInsSheet}!A:F`,
    valueInputOption: 'USER_ENTERED',
    requestBody: {
      values: [[now.toISOString(), member.id, member.name, 'Member', date, time]],
    },
  });
  return now;
}

// Look up a client by email or phone from the admin Google Sheet
async function portalLookup(email, phone) {
  const sheets = getSheets();

  // Step 1: Search "clients" tab for email or phone match
  const clientsRes = await sheets.spreadsheets.values.get({
    spreadsheetId: CONFIG.adminSpreadsheetId,
    range: `${CONFIG.clientsSheet}!A2:H`,
  });
  const clientRows = clientsRes.data.values || [];

  let matchedClient = null;
  const searchEmail = (email || '').toLowerCase().trim();
  const searchPhone = (phone || '').replace(/\D/g, '');

  for (const row of clientRows) {
    const rowEmail = (row[2] || '').toLowerCase().trim();
    const rowPhone = (row[3] || '').replace(/\D/g, '');

    if (searchEmail && rowEmail === searchEmail) {
      matchedClient = { name: row[1], email: row[2], phone: row[3] };
      break;
    }
    if (searchPhone && searchPhone.length >= 10 &&
        rowPhone.endsWith(searchPhone.slice(-10))) {
      matchedClient = { name: row[1], email: row[2], phone: row[3] };
      break;
    }
  }

  if (!matchedClient) return null;

  // Step 2: Look up session balance in "ClientsCleaned" by name
  const sessionsRes = await sheets.spreadsheets.values.get({
    spreadsheetId: CONFIG.adminSpreadsheetId,
    range: `${CONFIG.sessionsSheet}!A2:K`,
  });
  const sessionRows = sessionsRes.data.values || [];

  const clientName = matchedClient.name.trim().toLowerCase();
  let sessionData = null;

  for (const row of sessionRows) {
    if ((row[0] || '').trim().toLowerCase() === clientName) {
      sessionData = {
        sessions_purchased: parseInt(row[2], 10) || 0,
        sessions_used: parseInt(row[4], 10) || 0,
        sessions_remaining: parseInt(row[5], 10) || 0,
        status: row[10] || 'Unknown',
      };
      break;
    }
  }

  return {
    name: matchedClient.name,
    email: matchedClient.email,
    phone: matchedClient.phone,
    source: 'google_sheets',
    sessions_purchased: sessionData ? sessionData.sessions_purchased : 0,
    sessions_used: sessionData ? sessionData.sessions_used : 0,
    sessions_remaining: sessionData ? sessionData.sessions_remaining : 0,
    status: sessionData ? sessionData.status : 'Unknown',
  };
}

module.exports = { getMembers, logCheckIn, portalLookup, CONFIG };

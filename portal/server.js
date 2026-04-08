const express = require('express');
const path = require('path');
const fs = require('fs');
const QRCode = require('qrcode');

const app = express();
const PORT = 3000;

// Config
const CONFIG = {
  spreadsheetId: '1-D1MCAJYb6rqZ3gmGHqB_q2FCEs74paAQ4MTsi06MhU',
  membersSheet: 'Members',
  checkInsSheet: 'logs',
};

// Mock members for when credentials.json is not present
const MOCK_MEMBERS = [
  { id: 'js7890', name: 'Jane Smith', email: 'jane@example.com', phone: '555-867-7890' },
  { id: 'mj1234', name: 'Mike Johnson', email: 'mike@example.com', phone: '555-321-1234' },
  { id: 'ar5678', name: 'Alex Rodriguez', email: 'alex@example.com', phone: '555-445-5678' },
  { id: 'tl4321', name: 'Taylor Lee', email: 'taylor@example.com', phone: '555-994-4321' },
  { id: 'kw9999', name: 'Kim Williams', email: 'kim@example.com', phone: '555-119-9999' },
];

let sheetsClient = null;
let useGoogleSheets = false;

// Try to load Google Sheets credentials
// Supports: 1) credentials.json (service account), 2) Application Default Credentials (gcloud auth)
async function initGoogleSheets() {
  try {
    const { google } = require('googleapis');
    const credPath = path.join(__dirname, 'credentials.json');
    let auth;

    if (fs.existsSync(credPath)) {
      auth = new google.auth.GoogleAuth({
        keyFile: credPath,
        scopes: ['https://www.googleapis.com/auth/spreadsheets'],
      });
      console.log('\n  Using credentials.json');
    } else {
      auth = new google.auth.GoogleAuth({
        scopes: ['https://www.googleapis.com/auth/spreadsheets'],
      });
      console.log('\n  Using Application Default Credentials (gcloud auth)');
    }

    sheetsClient = google.sheets({ version: 'v4', auth });
    // Test the connection
    await sheetsClient.spreadsheets.values.get({
      spreadsheetId: CONFIG.spreadsheetId,
      range: `${CONFIG.membersSheet}!A1:A1`,
    });
    useGoogleSheets = true;
    console.log('  Google Sheets connected successfully');
  } catch (err) {
    console.error('  Failed to connect to Google Sheets:', err.message);
    console.log('  Falling back to mock data\n');
  }
}

// Fetch members from Google Sheets
async function getMembers() {
  if (!useGoogleSheets) return MOCK_MEMBERS;

  const res = await sheetsClient.spreadsheets.values.get({
    spreadsheetId: CONFIG.spreadsheetId,
    range: `${CONFIG.membersSheet}!A2:D`,
  });

  const rows = res.data.values || [];
  return rows.map(row => ({
    id: (row[0] || '').trim(),
    name: row[1] || 'Member',
    email: row[2] || '',
    phone: row[3] || '',
  }));
}

// Log check-in to Google Sheets
async function logCheckIn(member) {
  const now = new Date();
  const date = now.toISOString().split('T')[0];
  const time = now.toTimeString().split(' ')[0];

  if (!useGoogleSheets) {
    console.log(`  [CHECK-IN] ${member.name} (${member.id}) at ${date} ${time}`);
    return now;
  }

  await sheetsClient.spreadsheets.values.append({
    spreadsheetId: CONFIG.spreadsheetId,
    range: `${CONFIG.checkInsSheet}!A:F`,
    valueInputOption: 'USER_ENTERED',
    requestBody: {
      values: [[now.toISOString(), member.id, member.name, 'Member', date, time]],
    },
  });

  return now;
}

// Serve static files from public/
app.use(express.static(path.join(__dirname, 'public')));

// Check-in API
app.get('/api/checkin', async (req, res) => {
  const clientId = (req.query.id || '').trim().toLowerCase();
  if (!clientId) {
    return res.status(400).json({ error: 'Missing client ID' });
  }

  try {
    const members = await getMembers();
    const member = members.find(m => m.id.toLowerCase() === clientId);

    if (!member) {
      return res.status(404).json({
        error: 'not_found',
        message: `Code "${clientId}" not recognized.`,
        hint: 'Your code is the first letter of your first name + first letter of last name + last 4 digits of your phone number.',
      });
    }

    const timestamp = await logCheckIn(member);
    res.json({
      success: true,
      name: member.name,
      timestamp: timestamp.toISOString(),
    });
  } catch (err) {
    console.error('Check-in error:', err);
    res.status(500).json({ error: 'Server error. Please try again.' });
  }
});

// Members list (debug/admin)
app.get('/api/members', async (req, res) => {
  try {
    const members = await getMembers();
    res.json({ count: members.length, members, source: useGoogleSheets ? 'google_sheets' : 'mock_data' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Portal lookup — session balance from Google Sheets
app.get('/api/portal-lookup', async (req, res) => {
  const email = (req.query.email || '').trim();
  const phone = (req.query.phone || '').trim();

  if (!email && !phone) {
    return res.status(400).json({ detail: 'Provide email or phone' });
  }

  try {
    const { portalLookup } = require('./api/_sheets');
    const result = await portalLookup(email, phone);

    if (!result) {
      return res.status(404).json({
        detail: 'Client not found. Check your phone number or email.',
      });
    }

    res.json(result);
  } catch (err) {
    console.error('Portal lookup error:', err);
    res.status(500).json({ detail: 'Server error. Please try again.' });
  }
});

// QR Code page — printable, sendable to clients
app.get('/qr', async (req, res) => {
  // Build the check-in URL using the request's host
  const protocol = req.get('x-forwarded-proto') || 'http';
  const host = req.get('host');
  const checkinUrl = protocol + '://' + host;

  try {
    const qrDataUrl = await QRCode.toDataURL(checkinUrl, {
      width: 400,
      margin: 2,
      color: { dark: '#1a1a18', light: '#faf8f5' },
    });

    res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QR Code — The Fit Clinic Check-In</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: "DM Sans", -apple-system, sans-serif;
      background: #f5f2ed;
      color: #1a1a18;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      -webkit-font-smoothing: antialiased;
    }
    .card {
      background: #faf8f5;
      border-radius: 12px;
      padding: 48px 40px;
      text-align: center;
      max-width: 480px;
      width: 100%;
      box-shadow: 0 4px 32px rgba(26,26,24,0.08);
      position: relative;
      overflow: hidden;
    }
    .card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 3px;
      background: linear-gradient(90deg, #8a9a7b, #b8a472);
    }
    .logo-mark {
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 32px;
      font-weight: 300;
      letter-spacing: 0.06em;
    }
    .logo-sub {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: #c4beb5;
      margin-top: 2px;
    }
    .divider {
      width: 48px;
      height: 1px;
      background: #c4beb5;
      margin: 24px auto;
    }
    .qr-img {
      width: 280px;
      height: 280px;
      margin: 0 auto 24px;
      border-radius: 8px;
    }
    .scan-title {
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 24px;
      font-weight: 400;
      margin-bottom: 8px;
    }
    .scan-subtitle {
      font-size: 14px;
      color: #3d3d3b;
      line-height: 1.5;
      margin-bottom: 16px;
    }
    .url-display {
      font-size: 12px;
      color: #c4beb5;
      letter-spacing: 0.05em;
      word-break: break-all;
    }
    .instructions-box {
      background: #f5f2ed;
      border-radius: 6px;
      padding: 16px;
      margin-top: 24px;
      text-align: left;
    }
    .instructions-box p {
      font-size: 13px;
      color: #3d3d3b;
      line-height: 1.6;
      margin-bottom: 4px;
    }
    .instructions-box .step {
      display: flex;
      gap: 10px;
      margin-bottom: 8px;
    }
    .instructions-box .step-num {
      flex-shrink: 0;
      width: 22px;
      height: 22px;
      background: #e8ede4;
      color: #6b7d5e;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
    }
    @media print {
      body { background: white; padding: 0; }
      .card { box-shadow: none; max-width: 100%; }
      .no-print { display: none; }
    }
    .print-btn {
      display: inline-flex;
      align-items: center;
      padding: 12px 28px;
      font-family: "DM Sans", sans-serif;
      font-size: 13px;
      font-weight: 600;
      color: #faf8f5;
      background: #1a1a18;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      margin-top: 24px;
      letter-spacing: 0.04em;
    }
    .print-btn:hover { background: #3d3d3b; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo-mark">The Fit Clinic</div>
    <div class="logo-sub">Client Check-In</div>
    <div class="divider"></div>
    <img src="${qrDataUrl}" alt="Check-In QR Code" class="qr-img">
    <h1 class="scan-title">Scan to Check In</h1>
    <p class="scan-subtitle">Open your phone camera and point it at the QR code</p>
    <div class="instructions-box">
      <div class="step"><span class="step-num">1</span><p>Scan this QR code with your phone camera</p></div>
      <div class="step"><span class="step-num">2</span><p>Enter your personal code (first initials + last 4 of phone)</p></div>
      <div class="step"><span class="step-num">3</span><p>You're checked in!</p></div>
    </div>
    <p class="url-display">${checkinUrl}</p>
    <button class="print-btn no-print" onclick="window.print()">Print This Sign</button>
  </div>
</body>
</html>`);
  } catch (err) {
    res.status(500).send('Error generating QR code');
  }
});

// Start server
initGoogleSheets().then(() => {
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`  The Fit Clinic Check-In Server`);
    console.log(`  ─────────────────────────────`);
    console.log(`  Local:   http://localhost:${PORT}`);

    // Show LAN IP for phone access
    const nets = require('os').networkInterfaces();
    for (const iface of Object.values(nets)) {
      for (const cfg of iface) {
        if (cfg.family === 'IPv4' && !cfg.internal) {
          console.log(`  Network: http://${cfg.address}:${PORT}`);
        }
      }
    }

    console.log(`  Data:    ${useGoogleSheets ? 'Google Sheets' : 'Mock data (add credentials.json for live)'}`);
    console.log('');
  });
});

const QRCode = require('qrcode');

module.exports = async function handler(req, res) {
  const protocol = req.headers['x-forwarded-proto'] || 'https';
  const host = req.headers.host;
  const checkinUrl = protocol + '://' + host;

  try {
    const qrDataUrl = await QRCode.toDataURL(checkinUrl, {
      width: 400,
      margin: 2,
      color: { dark: '#1a1a18', light: '#faf8f5' },
    });

    res.setHeader('Content-Type', 'text/html; charset=utf-8');
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
    .divider { width: 48px; height: 1px; background: #c4beb5; margin: 24px auto; }
    .qr-img { width: 280px; height: 280px; margin: 0 auto 24px; border-radius: 8px; }
    .scan-title {
      font-family: "Cormorant Garamond", Georgia, serif;
      font-size: 24px;
      font-weight: 400;
      margin-bottom: 8px;
    }
    .scan-subtitle { font-size: 14px; color: #3d3d3b; line-height: 1.5; margin-bottom: 16px; }
    .url-display { font-size: 12px; color: #c4beb5; letter-spacing: 0.05em; word-break: break-all; }
    .instructions-box {
      background: #f5f2ed;
      border-radius: 6px;
      padding: 16px;
      margin-top: 24px;
      text-align: left;
    }
    .instructions-box .step { display: flex; gap: 10px; margin-bottom: 8px; }
    .instructions-box .step p { font-size: 13px; color: #3d3d3b; line-height: 1.6; }
    .instructions-box .step-num {
      flex-shrink: 0; width: 22px; height: 22px;
      background: #e8ede4; color: #6b7d5e;
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 600;
    }
    @media print { body { background: white; padding: 0; } .card { box-shadow: none; } .no-print { display: none; } }
    .print-btn {
      display: inline-flex; align-items: center; padding: 12px 28px;
      font-family: "DM Sans", sans-serif; font-size: 13px; font-weight: 600;
      color: #faf8f5; background: #1a1a18; border: none; border-radius: 6px;
      cursor: pointer; margin-top: 24px; letter-spacing: 0.04em;
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
};

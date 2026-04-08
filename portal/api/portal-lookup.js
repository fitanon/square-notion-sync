const { portalLookup } = require('./_sheets');

module.exports = async function handler(req, res) {
  const email = (req.query.email || '').trim();
  const phone = (req.query.phone || '').trim();

  if (!email && !phone) {
    return res.status(400).json({ detail: 'Provide email or phone' });
  }

  try {
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
};

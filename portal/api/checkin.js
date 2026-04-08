const { getMembers, logCheckIn } = require('./_sheets');

module.exports = async function handler(req, res) {
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
        message: 'Code "' + clientId + '" not recognized.',
        hint: 'Your code is the first letter of your first name + first letter of last name + last 4 digits of your phone number.',
      });
    }

    const timestamp = await logCheckIn(member);
    res.json({ success: true, name: member.name, timestamp: timestamp.toISOString() });
  } catch (err) {
    console.error('Check-in error:', err);
    res.status(500).json({ error: 'Server error. Please try again.' });
  }
};

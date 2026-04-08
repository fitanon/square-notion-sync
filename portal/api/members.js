const { getMembers } = require('./_sheets');

module.exports = async function handler(req, res) {
  try {
    const members = await getMembers();
    res.json({ count: members.length, members, source: 'google_sheets' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

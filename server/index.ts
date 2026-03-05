import express from 'express';
import cors from 'cors';
import { randomUUID } from 'crypto';
import { db } from './db.js';
import { requireAdmin, requireUser } from './auth.js';

const app = express();
app.use(cors());
app.use(express.json({ limit: '5mb' }));

app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE email=?').get(email) as any;
  if (!user || user.password !== password) return res.status(401).json({ error: 'Invalid credentials' });
  db.prepare('UPDATE sessions SET revoked_at=CURRENT_TIMESTAMP,status=? WHERE user_id=? AND revoked_at IS NULL').run(
    'revoked',
    user.id
  );
  const sid = randomUUID();
  db.prepare('INSERT INTO sessions(id,user_id,user_agent,ip) VALUES(?,?,?,?)').run(
    sid,
    user.id,
    req.header('user-agent') || 'Unknown',
    req.ip
  );
  res.json({ sessionId: sid, user: { id: user.id, role: user.role, displayName: user.display_name, email: user.email } });
});

app.post('/api/auth/logout', requireUser, (req, res) => {
  db.prepare('UPDATE sessions SET revoked_at=CURRENT_TIMESTAMP,status=? WHERE id=?').run('revoked', req.header('x-session-id'));
  res.json({ ok: true });
});

app.get('/api/auth/me', requireUser, (req, res) => res.json({ user: (req as any).user }));
app.post('/api/auth/heartbeat', requireUser, (req, res) => res.json({ ok: true }));

app.post('/api/tool/generate', requireUser, async (req, res) => {
  const { template, keywords, apiKey } = req.body as { template: string; keywords: string[]; apiKey: string };
  const capped = keywords.slice(0, 50);
  const results: { keyword: string; html?: string; error?: string }[] = [];
  for (const keyword of capped) {
    try {
      const prompt = `Rewrite paragraph text to include keyword/location: ${keyword}. Update headings for SEO. Preserve all HTML structure exactly. Output pure HTML only.`;
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [
            { role: 'system', content: 'You are an expert SEO writer. Preserve html structure perfectly and return only pure HTML.' },
            { role: 'user', content: `${prompt}\n\n${template}` }
          ]
        })
      });
      if (!response.ok) throw new Error('OpenAI request failed');
      const json: any = await response.json();
      results.push({ keyword, html: json.choices?.[0]?.message?.content ?? template });
    } catch (error: any) {
      results.push({ keyword, error: error.message });
    }
  }
  res.json({ results });
});

app.get('/api/admin/analytics', requireAdmin, (_req, res) => {
  const daily = Array.from({ length: 7 }).map((_, i) => ({ day: `D${i + 1}`, users: 10 + i * 2, pages: 30 + i * 7, duration: 12 + i }));
  res.json({ daily, metrics: { dau: 18, dauChange: 12, pages: 211, pagesChange: 20, session: 16, sessionChange: -3 } });
});

app.get('/api/admin/users', requireAdmin, (_req, res) => {
  const users = db.prepare('SELECT id,email,display_name as displayName,role,created_at as createdAt FROM users').all();
  res.json({ users });
});
app.post('/api/admin/users', requireAdmin, (req, res) => {
  const { email, password, displayName, role } = req.body;
  const id = randomUUID();
  db.prepare('INSERT INTO users(id,email,password,display_name,role) VALUES (?,?,?,?,?)').run(id, email, password, displayName, role);
  res.json({ ok: true });
});
app.put('/api/admin/users/:id', requireAdmin, (req, res) => {
  const { displayName, role } = req.body;
  const me = (req as any).user;
  if (me.id === req.params.id && role !== 'admin') return res.status(400).json({ error: 'Cannot demote yourself' });
  db.prepare('UPDATE users SET display_name=?, role=? WHERE id=?').run(displayName, role, req.params.id);
  res.json({ ok: true });
});
app.delete('/api/admin/users/:id', requireAdmin, (req, res) => {
  db.prepare('DELETE FROM users WHERE id=?').run(req.params.id);
  res.json({ ok: true });
});
app.get('/api/admin/sessions', requireAdmin, (_req, res) => {
  const sessions = db
    .prepare(
      `SELECT s.id,u.email,u.display_name as displayName,s.user_agent as userAgent,s.ip,s.last_active_at as lastActiveAt,COALESCE(s.revoked_at,'') as revokedAt FROM sessions s JOIN users u ON u.id=s.user_id`
    )
    .all();
  res.json({ sessions });
});
app.post('/api/admin/sessions/:id/terminate', requireAdmin, (req, res) => {
  db.prepare('UPDATE sessions SET revoked_at=CURRENT_TIMESTAMP,status=? WHERE id=?').run('revoked', req.params.id);
  res.json({ ok: true });
});

app.get('/api/settings/sessions', requireUser, (req, res) => {
  const user = (req as any).user;
  const sessions = db.prepare('SELECT * FROM sessions WHERE user_id=?').all(user.id);
  res.json({ sessions });
});
app.post('/api/settings/sessions/:id/revoke', requireUser, (req, res) => {
  db.prepare('UPDATE sessions SET revoked_at=CURRENT_TIMESTAMP,status=? WHERE id=?').run('revoked', req.params.id);
  res.json({ ok: true });
});
app.put('/api/settings/profile', requireUser, (req, res) => {
  db.prepare('UPDATE users SET display_name=? WHERE id=?').run(req.body.displayName, (req as any).user.id);
  res.json({ ok: true });
});
app.put('/api/settings/password', requireUser, (req, res) => {
  const user = db.prepare('SELECT password FROM users WHERE id=?').get((req as any).user.id) as any;
  if (user.password !== req.body.currentPassword) return res.status(400).json({ error: 'Current password is incorrect' });
  db.prepare('UPDATE users SET password=? WHERE id=?').run(req.body.newPassword, (req as any).user.id);
  res.json({ ok: true });
});

app.listen(3000, () => console.log('API running on 3000'));

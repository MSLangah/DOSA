import type { Request, Response, NextFunction } from 'express';
import { db } from './db.js';

export type SessionUser = { id: string; role: 'admin' | 'user'; display_name: string; email: string };

export function getSession(req: Request): SessionUser | null {
  const sid = req.header('x-session-id');
  if (!sid) return null;
  const row = db
    .prepare(
      `SELECT u.id,u.role,u.display_name,u.email,s.revoked_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=?`
    )
    .get(sid) as any;
  if (!row || row.revoked_at) return null;
  db.prepare('UPDATE sessions SET last_active_at=CURRENT_TIMESTAMP,status=? WHERE id=?').run('active', sid);
  return { id: row.id, role: row.role, display_name: row.display_name, email: row.email };
}

export function requireUser(req: Request, res: Response, next: NextFunction) {
  const user = getSession(req);
  if (!user) return res.status(401).json({ error: 'Unauthorized' });
  (req as any).user = user;
  next();
}

export function requireAdmin(req: Request, res: Response, next: NextFunction) {
  const user = getSession(req);
  if (!user || user.role !== 'admin') return res.status(403).json({ error: 'Forbidden' });
  (req as any).user = user;
  next();
}

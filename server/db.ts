import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';

export const db = new Database('app.db');

db.pragma('journal_mode = WAL');
db.exec(`
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','user')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  user_agent TEXT,
  ip TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_active_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
`);

const admin = db.prepare('SELECT id FROM users WHERE email=?').get('admin@masspagebuilder.com');
if (!admin) {
  db.prepare('INSERT INTO users (id,email,password,display_name,role) VALUES (?,?,?,?,?)').run(
    randomUUID(),
    'admin@masspagebuilder.com',
    'admin123',
    'Platform Admin',
    'admin'
  );
}

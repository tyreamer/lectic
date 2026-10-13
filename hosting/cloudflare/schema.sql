CREATE TABLE IF NOT EXISTS home (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  revision INTEGER NOT NULL DEFAULT 0,
  manifest TEXT NOT NULL DEFAULT '{"files":{}}',
  library TEXT NOT NULL DEFAULT '{"collections":[]}',
  lease_owner TEXT NOT NULL DEFAULT '',
  lease_until INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO home (id) VALUES (1);
CREATE TABLE IF NOT EXISTS objects (
  id TEXT PRIMARY KEY,
  raw_hash TEXT NOT NULL,
  raw_size INTEGER NOT NULL,
  encoded_size INTEGER NOT NULL,
  parts INTEGER NOT NULL,
  encoding TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS object_parts (
  id TEXT NOT NULL,
  part INTEGER NOT NULL,
  body TEXT NOT NULL,
  PRIMARY KEY (id, part)
);
CREATE TABLE IF NOT EXISTS phone_captures (
  id TEXT PRIMARY KEY,
  captured_at TEXT NOT NULL,
  payload TEXT NOT NULL,
  processed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS phone_captures_by_time ON phone_captures(captured_at, id);

CREATE TABLE signups (
  email         TEXT PRIMARY KEY,          -- lowercased, trimmed
  in_area       INTEGER,                   -- 1, 0, or null when no address was checked
  lat           REAL,                      -- rounded to 2 decimals (about 1 km), null without a check
  lng           REAL,
  utm_source    TEXT,
  utm_medium    TEXT,
  utm_campaign  TEXT,
  referrer      TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

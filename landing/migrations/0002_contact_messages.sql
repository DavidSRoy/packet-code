-- Messages from the contact section on the home page: shops, buildings, press and anyone else.
CREATE TABLE contact_messages (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  topic         TEXT NOT NULL CHECK (topic IN ('shop', 'building', 'press', 'other')),
  name          TEXT NOT NULL,
  email         TEXT NOT NULL,             -- lowercased, trimmed
  org           TEXT,                      -- shop, building or company, when given
  message       TEXT,
  utm_source    TEXT,
  utm_medium    TEXT,
  utm_campaign  TEXT,
  referrer      TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX contact_messages_topic_created ON contact_messages (topic, created_at);

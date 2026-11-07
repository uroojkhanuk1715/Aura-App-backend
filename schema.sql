-- Aura database schema (SQLite now, plain SQL that ports to PostgreSQL).
-- All money is stored as integer paisa (Rs 1 = 100 paisa). Never floats.
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(username) BETWEEN 3 AND 30),
  email TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(email) <= 254),
  pw_hash TEXT NOT NULL,
  bio TEXT NOT NULL DEFAULT '' CHECK(length(bio) <= 150),
  is_private INTEGER NOT NULL DEFAULT 0 CHECK(is_private IN (0,1)),
  hide_likes INTEGER NOT NULL DEFAULT 0 CHECK(hide_likes IN (0,1)),
  msg_perm TEXT NOT NULL DEFAULT 'following' CHECK(msg_perm IN ('everyone','following','none')),
  hidden_words TEXT NOT NULL DEFAULT '[]',
  is_vip INTEGER NOT NULL DEFAULT 0 CHECK(is_vip IN (0,1)),
  totp_secret_enc TEXT,
  totp_enabled INTEGER NOT NULL DEFAULT 0 CHECK(totp_enabled IN (0,1)),
  totp_last_step INTEGER NOT NULL DEFAULT 0,
  referral_code TEXT NOT NULL UNIQUE,
  referred_by INTEGER REFERENCES users(id),
  ref_rewarded INTEGER NOT NULL DEFAULT 0,
  streak_n INTEGER NOT NULL DEFAULT 0,
  streak_last TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')),
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,          -- sha256 of the token; the token itself is never stored
  created_at INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  ip TEXT, ua TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS backup_codes(
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL,
  PRIMARY KEY(user_id, code_hash)
);

CREATE TABLE IF NOT EXISTS login_attempts(
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL,                         -- 'ip:<addr>', 'acct:<username>' or 'mfa:<user id>'
  at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts(key, at);

CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY,
  user_id INTEGER, event TEXT NOT NULL, ip TEXT, detail TEXT, at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS media(
  id TEXT PRIMARY KEY,
  owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mime TEXT NOT NULL CHECK(mime IN ('image/jpeg','image/png','image/webp','image/gif')),
  size INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY,
  author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('photo','reel')),
  media_id TEXT NOT NULL UNIQUE REFERENCES media(id),
  caption TEXT NOT NULL DEFAULT '' CHECK(length(caption) <= 200),
  location TEXT NOT NULL DEFAULT '' CHECK(length(location) <= 60),
  filter TEXT NOT NULL DEFAULT 'none' CHECK(filter IN ('none','vintage','sepia','bw','warm','cyberpunk','glow')),
  comments_off INTEGER NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id, id DESC);

CREATE TABLE IF NOT EXISTS likes(
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY(post_id, user_id)
);
CREATE TABLE IF NOT EXISTS saves(
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY(post_id, user_id)
);
CREATE TABLE IF NOT EXISTS comments(
  id INTEGER PRIMARY KEY,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 300),
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, id);

CREATE TABLE IF NOT EXISTS follows(
  follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  followee_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK(status IN ('pending','accepted')),
  created_at INTEGER NOT NULL,
  PRIMARY KEY(follower_id, followee_id),
  CHECK(follower_id <> followee_id)
);
CREATE TABLE IF NOT EXISTS blocks(
  blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY(blocker_id, blocked_id),
  CHECK(blocker_id <> blocked_id)
);
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY,
  reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  UNIQUE(reporter_id, post_id)
);

CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY,
  sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 1000),
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id, receiver_id, id);

-- Money
CREATE TABLE IF NOT EXISTS wallets(
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0)      -- paisa, can never go negative
);
CREATE TABLE IF NOT EXISTS wallet_tx(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL,                                    -- signed paisa
  kind TEXT NOT NULL,                                         -- topup, campaign, refund, streak, referral
  ref TEXT,
  created_at INTEGER NOT NULL,
  UNIQUE(user_id, kind, ref)                                  -- makes webhooks and daily rewards idempotent
);

CREATE TABLE IF NOT EXISTS campaigns(
  id INTEGER PRIMARY KEY,
  owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  goal TEXT NOT NULL CHECK(goal IN ('visits','followers','site')),
  audience TEXT NOT NULL CHECK(audience IN ('karachi','pakistan','world')),
  budget INTEGER NOT NULL CHECK(budget > 0),
  spent INTEGER NOT NULL DEFAULT 0,
  cpm INTEGER NOT NULL CHECK(cpm > 0),                        -- paisa per 1000 impressions
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','stopped','completed')),
  starts_at INTEGER NOT NULL,
  ends_at INTEGER NOT NULL,
  impressions INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  CHECK(spent >= 0 AND spent <= budget)                       -- an advertiser can never be over-charged
);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status, ends_at);

CREATE TABLE IF NOT EXISTS ad_events(
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('impression','click')),
  cost INTEGER NOT NULL DEFAULT 0,
  at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ad_events ON ad_events(campaign_id, user_id, kind, at);

CREATE TABLE IF NOT EXISTS creator_earnings(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL CHECK(amount > 0),
  campaign_id INTEGER REFERENCES campaigns(id),
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_creator_earnings ON creator_earnings(user_id, created_at);

CREATE TABLE IF NOT EXISTS payouts(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL CHECK(amount > 0),
  method TEXT NOT NULL CHECK(method IN ('easypaisa','jazzcash','bank')),
  account_enc TEXT NOT NULL,                                  -- AES-256-GCM encrypted account number
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','paid','rejected')),
  created_at INTEGER NOT NULL
);

-- Your income: the platform's cut of every ad impression.
CREATE TABLE IF NOT EXISTS platform_revenue(
  id INTEGER PRIMARY KEY,
  amount INTEGER NOT NULL CHECK(amount >= 0),
  campaign_id INTEGER REFERENCES campaigns(id),
  created_at INTEGER NOT NULL
);

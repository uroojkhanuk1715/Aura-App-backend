# Aura backend

SQL database, secure login, posts, messages, ads and creator earnings for the Aura app.
No npm packages to install. It needs only Node 22.13 or newer.

```
cp .env.example .env      # then fill in the secrets (see below)
npm test                  # 19 integration tests
npm start                 # http://localhost:8080
```

Load the `.env` values into the environment however you run Node (systemd `EnvironmentFile`, Docker `--env-file`, your host's dashboard).

## How you earn

Advertisers add money to their wallet, then promote a post. Every time Aura shows that ad to a person, the advertiser is charged a small amount (CPM, Rs 250 per 1,000 views by default, set `AD_CPM_PAISA`).
That amount is split in the same database transaction:

| Part | Default | Goes to |
|---|---|---|
| Creator share | 55% (`CREATOR_SHARE_PCT`) | the creator whose post the ad appeared after |
| Platform share | 45% | you, row in `platform_revenue` |

Check your income any time:

```
curl -H "x-admin-token: $ADMIN_TOKEN" http://localhost:8080/api/admin/revenue
```

Creators with 1,000 followers can request a payout once they have Rs 5,000 available. You see requests at `GET /api/admin/payouts`, pay them by Easypaisa, JazzCash or bank, then mark them with `POST /api/admin/payouts/:id {"status":"paid"}`.

Income depends on real advertisers and real traffic. The code makes the money accounting exact and safe. It cannot create advertisers for you.

## Connecting real payments

Wallet top-ups arrive through `POST /api/webhooks/payment`. Your payment provider (Easypaisa, JazzCash, Stripe, a local aggregator) calls it after a successful payment.
The body must be JSON `{ "event_id", "user_id", "amount_paisa", "ts" }` with header `x-signature` = hex HMAC-SHA256 of the raw body using `PAYMENT_WEBHOOK_SECRET`.
Bad signatures, old timestamps and repeated `event_id`s are refused, so retries never double-credit.
Ask your provider how to sign webhooks, and adapt the small verification block in `lib/app.js` if their format differs.
Streak and referral rewards are ad credit only. They can be spent on ads but never withdrawn.

## Security built in

- Passwords: scrypt with a per-user salt, 10+ characters, common and username-based passwords refused.
- Login: same error for wrong user or wrong password, same response time, lockout after 5 failures (15 minutes), per-IP limits.
- Sessions: random 256-bit tokens, only their SHA-256 hash is stored, 30-day limit, 7-day idle limit, list and revoke devices, changing the password logs out other devices.
- Two-factor: standard authenticator apps (RFC 6238, tested), secret encrypted with AES-256-GCM, codes cannot be replayed, 8 one-time backup codes stored hashed.
- Every query uses bound parameters (SQL injection tested). Profile updates use an allow-list, so nobody can set `is_vip` or `status` by sending extra fields.
- Every record is looked up together with its owner or visibility rule. Private accounts, blocks and message settings are enforced on the server. Hidden posts return 404, not 403.
- Uploads: type is decided from the file bytes, 8 MB limit, random file names, served with `nosniff` and a sandbox CSP, and only to people allowed to see the post.
- Money: integer paisa, wallet cannot go below zero (database check), campaign spend cannot pass budget (database check), payouts and refunds run in locked transactions, webhooks are idempotent. A race test sends two payout requests at once and exactly one succeeds.
- Headers: CSP, nosniff, frame deny, no-store, HSTS in production. CORS allows only origins you list in `ALLOWED_ORIGINS`.
- Secrets: production refuses to start without `AURA_SECRET`. Fake top-ups are impossible in production.

## Before real users

1. Put it behind HTTPS (Caddy, nginx or your host). Set `TRUST_PROXY=1` only when that proxy sets `X-Forwarded-For`.
2. Set `NODE_ENV=production`, `AURA_SECRET` (32+ random characters, keep it safe, losing it makes 2FA secrets unreadable), `ADMIN_TOKEN`, `PAYMENT_WEBHOOK_SECRET`, `ALLOWED_ORIGINS`.
3. Back up `data/aura.db` daily. It is a single file.
4. Photos keep EXIF location data on the server side. The Aura web prototype strips it in the browser. For native apps strip it in the app, or add an image library such as `sharp` here.
5. Rate limits are kept in memory, which is right for one server. Use Redis if you run several.
6. SQLite handles a lot (thousands of users) on one machine. When you outgrow it, `schema.sql` is plain SQL and ports to PostgreSQL. Money columns are already integers.
7. Fake views are the main ad fraud risk. Built in: one charged view per person per campaign per hour, budget pacing, no charge for your own ads, clicks need a real view. Add phone or email verification before turning on payouts at scale.
8. Real money has legal and tax duties (business registration, tax on payouts, ad content rules). Check them for your country before launch.

## API summary

Auth `POST /api/auth/register | login | mfa | logout`.
Account `GET|PATCH /api/me`, `PATCH /api/me/vip`, `POST /api/me/password`, `GET /api/me/sessions`, `POST /api/2fa/setup | enable | disable`.
Content `POST /api/media`, `POST|GET|PATCH|DELETE /api/posts[/:id]`, `GET /api/feed | explore | me/saved | me/archive`, likes, saves, comments, reports.
People `GET /api/users?q=`, `GET /api/users/:username[/posts]`, follow, block, follow requests.
Messages `GET /api/inbox`, `GET|POST /api/messages/:username`.
Money `GET /api/wallet`, `POST /api/campaigns`, `POST /api/campaigns/:id/pause|resume|stop`, `GET /api/ads/serve?after_post=ID`, `POST /api/ads/click`, `GET /api/creator`, `POST /api/creator/payout`.
Growth `POST /api/streak/checkin`, `GET /api/me/referral`.
Admin `GET /api/admin/revenue | payouts`, `POST /api/admin/payouts/:id`, `POST /api/admin/users/:username/suspend`.

Send `Authorization: Bearer <token>` on everything except register, login, mfa and the webhook.

## Added: account delete and moderation
- `DELETE /api/me` body `{ "password": "...", "confirm": "DELETE", "code": "<2FA or backup code, if 2FA is on>" }` deletes the account, posts, photos, DMs and wallet. Refused while a payout is pending.
- `BANNED_WORDS` in `.env` rejects captions, comments and DMs containing those words (HTTP 422).
- `GET /api/admin/reports` lists reported posts (most reported first). `POST /api/admin/posts/:id/remove` removes a post and stops its ads. Both need the `x-admin-token` header.
